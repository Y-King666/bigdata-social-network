"""Structured Streaming：消费 spool 里的逐分钟事件，生成分钟级热层与规则告警。

回放器把事件按分钟投递；每个微批只做一次 toPandas，然后在本地按分钟聚合。
这样 1 秒触发一次也能稳定跟上，不会因为多个 Spark 聚合 job 的启动开销堆出延迟。
热层保留最近 300 个模拟分钟，供大屏做 60 分钟滚动窗口和排行榜。
"""

import json
import os
import shutil
import sys
import threading
import time

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import types as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "stream"))

import config
import spark_env

SCHEMA = T.StructType([
    T.StructField("ts", T.TimestampType()),
    T.StructField("repost_num", T.LongType()),
    T.StructField("pos", T.FloatType()),
    T.StructField("neg", T.FloatType()),
    T.StructField("topics", T.ArrayType(T.StringType())),
    T.StructField("region", T.StringType()),
])

TOP_TOPICS_PER_MINUTE = 20   # 每分钟只留高频话题，60 分钟求和后仍足以排出 Top 10
NEG_ALERT = 0.30
REGION_FACTOR = 3.0
TOPIC_FACTOR = 3.0
REGION_MIN = 80              # 60 分钟窗口内至少这么多条才判地区突增
TOPIC_MIN = 60
BASELINE_MIN = 20            # 前 180 分钟折算成 60 分钟后至少这么多条
ALERT_COOLDOWN = 120         # 同一对象两次告警的最小模拟分钟间隔
ALERT_HISTORY = config.HISTORY_MINUTES

MINUTES_SCHEMA = pa.schema([
    ("minute", pa.timestamp("us")),
    ("posts", pa.int64()),
    ("positive", pa.int64()),
    ("negative", pa.int64()),
    ("neutral", pa.int64()),
    ("reposts", pa.int64()),
    ("top_topic", pa.string()),
    ("top_region", pa.string()),
])
TOPIC_SCHEMA = pa.schema([
    ("minute", pa.timestamp("us")),
    ("topic", pa.string()),
    ("cnt", pa.int64()),
])
REGION_SCHEMA = pa.schema([
    ("minute", pa.timestamp("us")),
    ("region", pa.string()),
    ("cnt", pa.int64()),
])
ALERT_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("t", pa.timestamp("us")),
    ("type", pa.string()),
    ("key", pa.string()),
    ("value", pa.float64()),
    ("baseline", pa.float64()),
    ("level", pa.string()),
])

RUN_ID = 0
START_TIME = pd.Timestamp(config.DEFAULT_START)
total_posts = 0
total_alerts = 0
minutes_hist = pd.DataFrame()
topic_hist = pd.DataFrame()
region_hist = pd.DataFrame()
alerts = []
alert_seen = {}


def _replace_retry(tmp, path, attempts=30, delay=0.1):
    # 大屏进程持续读热层文件，Windows 上读取方持句柄时 os.replace 会短暂失败
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def atomic_write(frame, name, schema):
    path = os.path.join(config.HOT, name)
    tmp = path + ".tmp"
    table = pa.Table.from_pandas(frame, preserve_index=False).select(schema.names).cast(schema)
    pq.write_table(table, tmp, compression="snappy")
    _replace_retry(tmp, path)


def _empty_minutes():
    return pd.DataFrame({
        "minute": pd.Series(dtype="datetime64[us]"),
        "posts": pd.Series(dtype="int64"),
        "positive": pd.Series(dtype="int64"),
        "negative": pd.Series(dtype="int64"),
        "neutral": pd.Series(dtype="int64"),
        "reposts": pd.Series(dtype="int64"),
        "top_topic": pd.Series(dtype="string"),
        "top_region": pd.Series(dtype="string"),
    })


def _empty_topics():
    return pd.DataFrame({
        "minute": pd.Series(dtype="datetime64[us]"),
        "topic": pd.Series(dtype="string"),
        "cnt": pd.Series(dtype="int64"),
    })


def _empty_regions():
    return pd.DataFrame({
        "minute": pd.Series(dtype="datetime64[us]"),
        "region": pd.Series(dtype="string"),
        "cnt": pd.Series(dtype="int64"),
    })


def _empty_alerts():
    return pd.DataFrame({
        "id": pd.Series(dtype="string"),
        "t": pd.Series(dtype="datetime64[us]"),
        "type": pd.Series(dtype="string"),
        "key": pd.Series(dtype="string"),
        "value": pd.Series(dtype="float64"),
        "baseline": pd.Series(dtype="float64"),
        "level": pd.Series(dtype="string"),
    })


def _merge_minutes(new):
    global minutes_hist
    frames = [f for f in (minutes_hist, new) if not f.empty]
    if not frames:
        minutes_hist = _empty_minutes()
        return
    merged = pd.concat(frames, ignore_index=True)
    minutes_hist = (
        merged.groupby("minute", as_index=False)[["posts", "positive", "negative", "neutral", "reposts"]]
        .sum()
    )


def _merge_topics(new):
    global topic_hist
    frames = [f for f in (topic_hist, new) if not f.empty]
    if not frames:
        topic_hist = _empty_topics()
        return
    merged = pd.concat(frames, ignore_index=True)
    topic_hist = merged.groupby(["minute", "topic"], as_index=False)["cnt"].sum()


def _merge_regions(new):
    global region_hist
    frames = [f for f in (region_hist, new) if not f.empty]
    if not frames:
        region_hist = _empty_regions()
        return
    merged = pd.concat(frames, ignore_index=True)
    region_hist = merged.groupby(["minute", "region"], as_index=False)["cnt"].sum()


def _top_map(hist, key):
    if hist.empty:
        return {}
    idx = hist.groupby("minute")["cnt"].idxmax()
    return hist.loc[idx].set_index("minute")[key].to_dict()


def _alert(sim_time, kind, key, value, baseline, level):
    return {
        "id": "%d-%s-%s" % (int(sim_time.timestamp()), kind, key),
        "t": sim_time,
        "type": kind,
        "key": str(key),
        "value": float(value),
        "baseline": float(baseline),
        "level": level,
    }


def _spike_alerts(sim_time, hist, key, min_count, factor):
    window = pd.Timedelta(minutes=config.RANK_MINUTES)
    base_start = sim_time - window * 4
    base_end = sim_time - window
    recent = hist[hist["minute"] > sim_time - window].groupby(key)["cnt"].sum()
    base = hist[(hist["minute"] > base_start) & (hist["minute"] <= base_end)].groupby(key)["cnt"].sum() / 3.0
    out = []
    for name, cnt in recent.items():
        baseline = float(base.get(name, 0.0))
        if cnt >= min_count and baseline >= BASELINE_MIN and cnt > baseline * factor:
            out.append((name, int(cnt), baseline))
    return out


def evaluate_alerts(sim_time):
    out = []
    window = pd.Timedelta(minutes=config.RANK_MINUTES)
    recent = minutes_hist[minutes_hist["minute"] > sim_time - window]
    posts = int(recent["posts"].sum())
    negative = int(recent["negative"].sum())

    # 开头数据太少时占比没有统计意义
    if posts >= 60:
        share = negative / posts
        if share > NEG_ALERT:
            out.append(("负面占比", "全网", round(share, 3), NEG_ALERT, "高"))

    # 突增规则要先攒够 3 小时基线，否则开局会把正常波动全判成异常
    if (sim_time - START_TIME) / pd.Timedelta(minutes=1) >= 180:
        for region, cnt, baseline in _spike_alerts(sim_time, region_hist, "region", REGION_MIN, REGION_FACTOR):
            out.append(("地区突增", region, cnt, round(baseline, 1), "中"))
        for topic, cnt, baseline in _spike_alerts(sim_time, topic_hist, "topic", TOPIC_MIN, TOPIC_FACTOR):
            out.append(("话题突增", topic, cnt, round(baseline, 1), "中"))

    rows = []
    for kind, key, value, baseline, level in out:
        sig = (kind, key)
        last = alert_seen.get(sig)
        if last is not None and (sim_time - last) / pd.Timedelta(minutes=1) < ALERT_COOLDOWN:
            continue
        alert_seen[sig] = sim_time
        rows.append(_alert(sim_time, kind, key, value, baseline, level))
    return rows


def foreach_batch(batch_df, batch_id):
    global total_posts, total_alerts, alerts, minutes_hist, topic_hist, region_hist
    t0 = time.time()
    frame = batch_df.toPandas()
    if frame.empty:
        return
    if "ts" not in frame.columns:
        return

    frame["ts"] = pd.to_datetime(frame["ts"])
    frame["minute"] = frame["ts"].dt.floor("min").astype("datetime64[us]")
    frame["repost_num"] = frame["repost_num"].fillna(0).astype("int64")
    frame["positive_flag"] = (frame["pos"] > frame["neg"]).astype("int64")
    frame["negative_flag"] = (frame["pos"] < frame["neg"]).astype("int64")
    frame["region"] = frame["region"].fillna("未知").astype(str)

    per_min = frame.groupby("minute", as_index=False).agg(
        posts=("minute", "size"),
        positive=("positive_flag", "sum"),
        negative=("negative_flag", "sum"),
        reposts=("repost_num", "sum"),
    )
    per_min["neutral"] = per_min["posts"] - per_min["positive"] - per_min["negative"]

    exploded = frame[["minute", "topics"]].explode("topics").dropna(subset=["topics"])
    topic_min = (
        exploded.groupby(["minute", "topics"], as_index=False).size()
        .rename(columns={"topics": "topic", "size": "cnt"})
    )
    if not topic_min.empty:
        topic_min = (
            topic_min.sort_values(["minute", "cnt"], ascending=[True, False])
            .groupby("minute", as_index=False).head(TOP_TOPICS_PER_MINUTE)
        )
        topic_min["cnt"] = topic_min["cnt"].astype("int64")

    region_min = (
        frame.groupby(["minute", "region"], as_index=False).size()
        .rename(columns={"region": "region", "size": "cnt"})
    )
    region_min["cnt"] = region_min["cnt"].astype("int64")

    sim_time = per_min["minute"].max()
    total_posts += int(per_min["posts"].sum())

    _merge_minutes(per_min)
    _merge_topics(topic_min)
    _merge_regions(region_min)

    cutoff = sim_time - pd.Timedelta(minutes=config.HISTORY_MINUTES)
    minutes_hist = minutes_hist[minutes_hist["minute"] >= cutoff].reset_index(drop=True)
    topic_hist = topic_hist[topic_hist["minute"] >= cutoff].reset_index(drop=True)
    region_hist = region_hist[region_hist["minute"] >= cutoff].reset_index(drop=True)

    new_alerts = evaluate_alerts(sim_time)
    if new_alerts:
        alerts.extend(new_alerts)
        total_alerts += len(new_alerts)
    alert_cutoff = sim_time - pd.Timedelta(minutes=ALERT_HISTORY)
    alerts = [a for a in alerts if a["t"] >= alert_cutoff]

    topic_top = _top_map(topic_hist, "topic")
    region_top = _top_map(region_hist, "region")
    minutes_out = minutes_hist.copy()
    minutes_out["top_topic"] = minutes_out["minute"].map(topic_top).fillna("").astype(str)
    minutes_out["top_region"] = minutes_out["minute"].map(region_top).fillna("").astype(str)
    minutes_out = minutes_out.sort_values("minute").reset_index(drop=True)

    atomic_write(minutes_out, "live_minutes.parquet", MINUTES_SCHEMA)
    atomic_write(topic_hist.sort_values(["minute", "topic"]).reset_index(drop=True),
                 "live_topic_minutes.parquet", TOPIC_SCHEMA)
    atomic_write(region_hist.sort_values(["minute", "region"]).reset_index(drop=True),
                 "live_region_minutes.parquet", REGION_SCHEMA)
    if alerts:
        alert_frame = pd.DataFrame(alerts)
        alert_frame["t"] = pd.to_datetime(alert_frame["t"]).astype("datetime64[us]")
        alert_frame = alert_frame[ALERT_SCHEMA.names]
    else:
        alert_frame = _empty_alerts()
    atomic_write(alert_frame, "live_alerts.parquet", ALERT_SCHEMA)

    recent60 = minutes_hist[minutes_hist["minute"] > sim_time - pd.Timedelta(minutes=60)]
    posts60 = int(recent60["posts"].sum())
    rate = int(per_min.sort_values("minute")["posts"].iloc[-1])
    positive = int(recent60["positive"].sum())
    negative = int(recent60["negative"].sum())

    meta = {
        "run_id": RUN_ID,
        "batch": int(batch_id),
        "sim_time": str(sim_time),
        "batch_posts": int(len(frame)),
        "total_posts": int(total_posts),
        "rate": rate,
        "positive_share": round(positive / posts60, 4) if posts60 else 0.0,
        "negative_share": round(negative / posts60, 4) if posts60 else 0.0,
        "neutral": posts60 - positive - negative,
        "reposts": int(recent60["reposts"].sum()),
        "backlog": len([p for p in os.listdir(config.SPOOL) if p.startswith("evt_") and p.endswith(".parquet")]),
        "alerts": int(total_alerts),
        "batch_alerts": int(len(new_alerts)),
        "batch_seconds": round(time.time() - t0, 2),
        "updated_at": time.time(),
    }
    config.write_json(os.path.join(config.HOT, "live_meta.json"), meta)

    print("[batch %d] %s posts=%d rate=%d/min alerts=%d took=%.2fs backlog=%d" % (
        batch_id, str(sim_time)[:19], len(frame), rate, len(new_alerts),
        time.time() - t0, meta["backlog"]), flush=True)


def _clear_state():
    """删掉热层快照、旧 spool 分片与 checkpoint，让新一轮从空状态开始。"""
    for name in os.listdir(config.HOT):
        path = os.path.join(config.HOT, name)
        if os.path.isfile(path):
            for _ in range(40):
                try:
                    os.remove(path)
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    time.sleep(0.1)

    for name in os.listdir(config.SPOOL):
        if not (name.startswith("evt_") and name.endswith(".parquet")):
            continue
        path = os.path.join(config.SPOOL, name)
        for _ in range(40):
            try:
                os.remove(path)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                time.sleep(0.1)

    tmp_dir = os.path.join(config.SPOOL, "tmp")
    if os.path.isdir(tmp_dir):
        for name in os.listdir(tmp_dir):
            try:
                os.remove(os.path.join(tmp_dir, name))
            except OSError:
                pass

    checkpoint = os.path.join(config.STREAM_DIR, "checkpoint")
    for _ in range(3):
        shutil.rmtree(checkpoint, ignore_errors=True)
        if not os.path.exists(checkpoint):
            break
        time.sleep(0.5)


def _reset_runtime():
    """清掉上一场留在内存里的分钟级历史和告警基线。"""
    global total_posts, total_alerts, minutes_hist, topic_hist, region_hist, alerts
    total_posts = 0
    total_alerts = 0
    minutes_hist = _empty_minutes()
    topic_hist = _empty_topics()
    region_hist = _empty_regions()
    alerts = []
    alert_seen.clear()

    if not os.path.exists(os.path.join(config.HOT, "live_minutes.parquet")):
        atomic_write(_empty_minutes(), "live_minutes.parquet", MINUTES_SCHEMA)
    if not os.path.exists(os.path.join(config.HOT, "live_topic_minutes.parquet")):
        atomic_write(_empty_topics(), "live_topic_minutes.parquet", TOPIC_SCHEMA)
    if not os.path.exists(os.path.join(config.HOT, "live_region_minutes.parquet")):
        atomic_write(_empty_regions(), "live_region_minutes.parquet", REGION_SCHEMA)
    if not os.path.exists(os.path.join(config.HOT, "live_alerts.parquet")):
        atomic_write(_empty_alerts(), "live_alerts.parquet", ALERT_SCHEMA)


def _write_ack(run_id):
    config.write_json(config.ACK, {"run_id": run_id})


def _build_query(spark):
    stream = (
        spark.readStream.schema(SCHEMA)
        .option("maxFilesPerTrigger", 8)
        .parquet(config.SPOOL)
    )
    return (
        stream.writeStream.foreachBatch(foreach_batch)
        .option("checkpointLocation", os.path.join(config.STREAM_DIR, "checkpoint"))
        .trigger(processingTime="1 second")
        .start()
    )


def main():
    global RUN_ID, START_TIME
    os.makedirs(config.HOT, exist_ok=True)
    os.makedirs(config.SPOOL, exist_ok=True)
    _clear_state()

    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("20-stream-job", driver_memory="2g")
    spark.sparkContext.setLogLevel("WARN")
    # 回放器写入的是“北京时间墙钟”的 naive timestamp；固定会话时区为 UTC，
    # 避免 Spark 读 Parquet 时再按本机 Asia/Shanghai 加 8 小时。
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    spark.conf.set("spark.sql.shuffle.partitions", "4")

    ctl = config.read_control()
    RUN_ID = int(ctl["run_id"])
    START_TIME = pd.Timestamp(ctl["start_time"])
    _reset_runtime()
    _write_ack(RUN_ID)

    while True:
        query = _build_query(spark)
        print("STREAM_JOB_STARTED run_id=%d" % RUN_ID, flush=True)

        def report(q=query):
            last = -1
            while q.isActive:
                time.sleep(4)
                p = q.lastProgress
                if p and p.get("batchId") != last:
                    last = p.get("batchId")
                    print("[progress %s] %s" % (last, p.get("durationMs")), flush=True)

        threading.Thread(target=report, daemon=True).start()

        reset_to = None
        while query.isActive:
            time.sleep(0.5)
            current = int(config.read_control()["run_id"])
            if current != RUN_ID:
                reset_to = current
                query.stop()
                break

        try:
            query.awaitTermination(10)
        except Exception as exc:
            print("[reset] query stopped: %r" % exc, flush=True)

        if reset_to is None:
            break

        RUN_ID = reset_to
        START_TIME = pd.Timestamp(config.read_control()["start_time"])
        print("[reset] run_id=%d, clearing hot layer and checkpoint" % RUN_ID, flush=True)
        _clear_state()
        _reset_runtime()
        _write_ack(RUN_ID)


if __name__ == "__main__":
    main()
