"""回放器：把按天分区的历史事件按逐分钟虚拟时钟推送到 spool。

原始事件本身就落在整分钟（:00），这里只做 UTC +8 小时到北京时间的换算，
不再拆分秒槽。倍速 speed 表示 1 秒真实时间推进多少模拟分钟。
"""

import glob
import os
import time
from collections import deque
from datetime import timedelta

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import config

TARGET = pa.schema([
    ("ts", pa.timestamp("us")),
    ("repost_num", pa.int64()),
    ("pos", pa.float32()),
    ("neg", pa.float32()),
    ("topics", pa.list_(pa.string())),
    ("region", pa.string()),
])

CLEANUP_MINUTES = 10
ACK_TIMEOUT = 60


def list_days():
    return sorted(
        os.path.basename(p)[4:] for p in glob.glob(os.path.join(config.EVENTS, "day=*"))
    )


def day_index(days, start_time):
    date = start_time.strftime("%Y-%m-%d")
    if date in days:
        return days.index(date)
    for i, day in enumerate(days):
        if day >= date:
            return i
    return len(days)


def spool_size():
    return len(glob.glob(os.path.join(config.SPOOL, "evt_*.parquet")))


def parse_time(value):
    try:
        return pd.Timestamp(str(value).replace(" ", "T"))
    except (TypeError, ValueError):
        return pd.Timestamp(config.DEFAULT_START)


def load_day(day, start_time):
    """读一天事件，转北京时间，并把时间戳对齐到分钟。"""
    path = os.path.join(config.EVENTS, "day=" + day)
    t0 = time.time()
    frame = pq.read_table(path).to_pandas()
    frame["ts"] = pd.to_datetime(frame["ts"]).astype("datetime64[us]") + pd.Timedelta(hours=8)
    frame["ts"] = frame["ts"].dt.floor("min")
    frame = frame.sort_values("ts", kind="mergesort").reset_index(drop=True)

    if start_time is not None:
        frame = frame[frame["ts"] >= start_time].reset_index(drop=True)

    times = frame["ts"].to_numpy(dtype="datetime64[us]")
    print("[replay] loaded %s %s rows (%.1fs)" % (day, f"{len(frame):,}", time.time() - t0), flush=True)
    return frame, times


def write_piece(piece, seq):
    piece = piece.copy()
    piece["repost_num"] = piece["repost_num"].fillna(0).astype("int64")
    piece["pos"] = piece["pos"].fillna(0).astype("float32")
    piece["neg"] = piece["neg"].fillna(0).astype("float32")
    piece["region"] = piece["region"].fillna("未知").astype(str)
    if piece["topics"].isna().any():
        piece["topics"] = piece["topics"].apply(lambda x: x if isinstance(x, list) else [])

    table = pa.Table.from_pandas(piece, preserve_index=False).select(TARGET.names).cast(TARGET)
    tmp = os.path.join(config.SPOOL, "tmp", "evt_%06d.parquet" % seq)
    final = os.path.join(config.SPOOL, "evt_%06d.parquet" % seq)
    pq.write_table(table, tmp, compression="snappy")
    for i in range(30):
        try:
            os.replace(tmp, final)
            return
        except PermissionError:
            if i == 29:
                raise
            time.sleep(0.1)


def read_meta():
    meta = config.read_json(os.path.join(config.HOT, "live_meta.json"), {})
    return meta if meta else None


def write_state(**kw):
    payload = {
        "run_id": kw.get("run_id", 0),
        "day": kw.get("day", ""),
        "seq": kw.get("seq", 0),
        "sent": kw.get("sent", 0),
        "speed": kw.get("speed", config.DEFAULT_SPEED),
        "paused": kw.get("paused", False),
        "finished": kw.get("finished", False),
        "backlog": kw.get("backlog", 0),
        "sim_time": kw.get("sim_time", config.DEFAULT_START),
        "start_time": kw.get("start_time", config.DEFAULT_START),
        "phase": kw.get("phase", "running"),
    }
    config.write_json(config.STATE, payload)


def wait_ack(run_id):
    print("[replay] waiting for stream ack run_id=%d" % run_id, flush=True)
    deadline = time.time() + ACK_TIMEOUT
    while time.time() < deadline:
        ack = config.read_json(config.ACK, {"run_id": -1})
        if int(ack.get("run_id", -1)) >= run_id:
            print("[replay] ack received", flush=True)
            return
        if int(config.read_control().get("run_id", -1)) != run_id:
            return
        time.sleep(0.2)
    print("[replay] ack timeout, continue anyway", flush=True)


def cleanup(pending, meta_time):
    if meta_time is None:
        return
    threshold = meta_time - pd.Timedelta(minutes=CLEANUP_MINUTES)
    while pending and pending[0][1] < threshold:
        seq, _ = pending[0]
        path = os.path.join(config.SPOOL, "evt_%06d.parquet" % seq)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except PermissionError:
            break
        pending.popleft()


def main():
    days = list_days()
    if not days:
        raise SystemExit("no events under %s" % config.EVENTS)

    os.makedirs(config.SPOOL, exist_ok=True)
    os.makedirs(os.path.join(config.SPOOL, "tmp"), exist_ok=True)

    ctl = config.read_control()
    run_id = int(ctl["run_id"])
    start_time = parse_time(ctl["start_time"])
    di = day_index(days, start_time)
    frame = None
    times = None
    cursor = 0
    seq = 0
    sent = 0
    sim_clock = start_time
    finished = False
    last_real = time.time()
    last_report = 0.0
    pending = deque()

    write_state(run_id=run_id, start_time=start_time.isoformat(), sim_time=sim_clock.isoformat(),
                speed=ctl["speed"], phase="waiting")
    wait_ack(run_id)

    while True:
        ctl = config.read_control()
        if int(ctl["run_id"]) != run_id:
            run_id = int(ctl["run_id"])
            start_time = parse_time(ctl["start_time"])
            di = day_index(days, start_time)
            frame, times = None, None
            cursor = 0
            seq = 0
            sent = 0
            sim_clock = start_time
            finished = False
            pending.clear()
            last_real = time.time()
            write_state(run_id=run_id, start_time=start_time.isoformat(), sim_time=sim_clock.isoformat(),
                        speed=ctl["speed"], phase="waiting", day=days[min(di, len(days) - 1)])
            print("[replay] reset run_id=%d start=%s" % (run_id, start_time), flush=True)
            wait_ack(run_id)
            continue

        speed = max(0.1, min(10.0, float(ctl.get("speed", config.DEFAULT_SPEED))))
        if ctl.get("paused"):
            write_state(run_id=run_id, day=days[min(di, len(days) - 1)], seq=seq, sent=sent,
                        speed=speed, paused=True, finished=finished, backlog=spool_size(),
                        sim_time=sim_clock.isoformat(), start_time=start_time.isoformat(), phase="paused")
            time.sleep(0.2)
            last_real = time.time()
            continue

        if finished:
            write_state(run_id=run_id, day=days[-1], seq=seq, sent=sent, speed=speed,
                        finished=True, backlog=spool_size(), sim_time=sim_clock.isoformat(),
                        start_time=start_time.isoformat(), phase="finished")
            time.sleep(0.5)
            last_real = time.time()
            continue

        meta = read_meta()
        meta_time = None
        if meta and int(meta.get("run_id", -1)) == run_id:
            try:
                meta_time = pd.Timestamp(meta["sim_time"])
            except (KeyError, TypeError, ValueError):
                meta_time = None
        if meta_time is not None:
            lag = (sim_clock - meta_time) / pd.Timedelta(minutes=1)
            if lag > config.MAX_LAG_MINUTES:
                write_state(run_id=run_id, day=days[min(di, len(days) - 1)], seq=seq, sent=sent,
                            speed=speed, backlog=spool_size(), sim_time=sim_clock.isoformat(),
                            start_time=start_time.isoformat(), phase="catchup")
                if time.time() - last_report > 2:
                    print("[replay] CATCHUP lag=%.1fmin" % lag, flush=True)
                    last_report = time.time()
                time.sleep(0.1)
                last_real = time.time()
                continue
            cleanup(pending, meta_time)

        now = time.time()
        dt = min(max(0.0, now - last_real), 1.0)
        last_real = now
        sim_clock += timedelta(minutes=speed * dt)

        if di >= len(days):
            finished = True
            continue

        if frame is None:
            frame, times = load_day(days[di], start_time if di == day_index(days, start_time) else None)
            cursor = 0

        target = np.datetime64(sim_clock.to_pydatetime(), "us")
        end = int(np.searchsorted(times, target, side="right"))
        if end > cursor:
            piece = frame.iloc[cursor:end]
            write_piece(piece, seq)
            pending.append((seq, piece["ts"].iat[-1]))
            seq += 1
            sent += len(piece)
            cursor = end

        if cursor >= len(frame):
            di += 1
            frame, times = None, None
            cursor = 0

        if time.time() - last_report > 2:
            last_report = time.time()
            lag_text = "?" if meta_time is None else "%.1fmin" % ((sim_clock - meta_time) / pd.Timedelta(minutes=1))
            print("[replay] %s speed=%gx sent=%s backlog=%d lag=%s" % (
                sim_clock.strftime("%Y-%m-%d %H:%M:%S"), speed, f"{sent:,}", spool_size(), lag_text), flush=True)

        write_state(run_id=run_id, day=days[min(di, len(days) - 1)], seq=seq, sent=sent,
                    speed=speed, backlog=spool_size(), sim_time=sim_clock.isoformat(),
                    start_time=start_time.isoformat(), phase="running")

        rest = config.TICK_SECONDS - (time.time() - now)
        if rest > 0:
            time.sleep(rest)


if __name__ == "__main__":
    main()
