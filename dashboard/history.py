"""历史分析数据层：只读预计算 Parquet/CSV，返回页面级 JSON。"""

import glob
import math
import os
from functools import lru_cache

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    from . import paths
except ImportError:
    import paths

PALETTE = {
    "primary": "#C0392B",
    "secondary": "#1F3A5F",
    "accent": "#E8A33D",
    "muted": "#6B7280",
    "positive": "#2E8B57",
    "negative": "#C0392B",
    "neutral": "#9AA5B1",
}
SERIES = ["#C0392B", "#1F3A5F", "#E8A33D", "#2E8B57", "#7D5BA6", "#0E8B8B"]
FULL_SCALE_DAY = "2020-01-20"


def _text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _int(value):
    try:
        if value is None or pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float(value, digits=4):
    try:
        if value is None or pd.isna(value):
            return 0.0
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def _nullable_int(value):
    try:
        if value is None or pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _nullable_float(value, digits=6):
    try:
        if value is None or pd.isna(value):
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _day(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _time(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _human(n):
    if n >= 1e8:
        return "%.2f 亿" % (n / 1e8)
    if n >= 1e4:
        return "%.1f 万" % (n / 1e4)
    return "{:,}".format(int(n))


def _kpi(label, value, hint):
    return {"label": label, "value": value, "hint": hint}


def _parquet_rows(path):
    files = glob.glob(os.path.join(path, "*.parquet"))
    return sum(pq.ParquetFile(f).metadata.num_rows for f in files)


def _dir_size_mb(path):
    files = glob.glob(os.path.join(path, "*.parquet"))
    return round(sum(os.path.getsize(f) for f in files) / 1e6, 1)


@lru_cache(maxsize=1)
def inventory():
    return [
        {"name": name, "rows": _parquet_rows(path), "size_mb": _dir_size_mb(path)}
        for name, path in paths.INVENTORY
    ]


@lru_cache(maxsize=1)
def daily_frame():
    df = pd.read_parquet(paths.SENTIMENT_DAILY)
    df["day"] = pd.to_datetime(df["day"])
    return df.sort_values("day")


@lru_cache(maxsize=1)
def grid_frame():
    return pd.read_parquet(paths.GEO_GRID)


@lru_cache(maxsize=1)
def province_frame():
    return pd.read_parquet(paths.GEO_PROVINCE)


@lru_cache(maxsize=1)
def share_frame():
    df = pd.read_csv(paths.GEO_SHARE, encoding="utf-8")
    df["day"] = pd.to_datetime(df["day"])
    return df.sort_values(["day", "province"])


@lru_cache(maxsize=1)
def topic_stats_frame():
    return pd.read_parquet(paths.TOPIC_STATS).sort_values(
        "occurrences", ascending=False
    ).reset_index(drop=True)


@lru_cache(maxsize=1)
def topic_options():
    return topic_stats_frame().head(60)["topic"].tolist()


@lru_cache(maxsize=64)
def topic_daily_frame(topic):
    return pd.read_parquet(
        paths.TOPIC_DAILY, filters=[("topic", "==", topic)]
    ).sort_values("day")


@lru_cache(maxsize=1)
def hotsearch_frame():
    return pd.read_csv(paths.HOTSEARCH_COMPARE, encoding="utf-8")


@lru_cache(maxsize=1)
def cascade_frame():
    return pd.read_parquet(paths.CASCADE_STATS)


@lru_cache(maxsize=1)
def cascade_growth_frame():
    return pd.read_parquet(paths.CASCADE_GROWTH)


@lru_cache(maxsize=1)
def polarity_frame():
    return pd.read_csv(paths.SENTIMENT_POLARITY, encoding="utf-8")


@lru_cache(maxsize=1)
def bucket_frame():
    return pd.read_csv(paths.SENTIMENT_BUCKETS, encoding="utf-8")


@lru_cache(maxsize=1)
def graph_users():
    return pd.read_parquet(
        paths.GRAPH_USERS,
        columns=[
            "user_id", "in_degree", "out_degree", "pagerank", "leiden",
            "gender", "province", "city", "fans_num", "vip_level",
        ],
    )


@lru_cache(maxsize=1)
def user_edges():
    return pd.read_parquet(
        paths.USER_EDGES,
        columns=["source_user", "target_user", "weight", "first_time"],
    )


@lru_cache(maxsize=64)
def profile_frame(user_id):
    return pq.read_table(
        paths.USER_INDEX, filters=[("user_id", "==", user_id)]
    ).to_pandas()


@lru_cache(maxsize=128)
def graph_user(user_id):
    users = graph_users()
    return users[users["user_id"] == user_id]


@lru_cache(maxsize=64)
def edges_of(user_id):
    edges = user_edges()
    return edges[(edges["source_user"] == user_id) | (edges["target_user"] == user_id)]


def overview():
    inv = inventory()
    rows = {item["name"]: item["rows"] for item in inv}
    daily = daily_frame()
    span_start = _day(daily["day"].min())
    span_end = _day(daily["day"].max())
    full = daily[daily["day"] >= FULL_SCALE_DAY]

    return {
        "kpis": [
            _kpi("微博推文", _human(rows["推文原文"]), "%s 至 %s" % (span_start, span_end)),
            _kpi("用户画像", _human(rows["用户画像"]), "性别 / 地区 / 生日 / 粉丝数"),
            _kpi("带坐标推文", _human(rows["带坐标推文"]), "含 GPS 标签，可做空间分析"),
            _kpi("用户级转发边", _human(rows["用户级转发边"]), "转发关系图的有向边"),
        ],
        "daily": [
            {
                "day": _day(row.day),
                "posts": _int(row.posts),
                "positive_share": _float(row.positive_share, 4),
            }
            for row in full.itertuples(index=False)
        ],
        "inventory": inv,
        "layers": [
            {"name": "数据接入层", "description": "公开数据集 Weibo-COV 与热搜榜单 CSV\n统一解析为 Parquet 列式存储"},
            {"name": "计算层", "description": "Spark 分布式聚合（4.1 亿次话题提及归并）\nPython 多进程词典情感打分\nLouvain / Leiden 社区发现、PageRank"},
            {"name": "存储层", "description": "Parquet 分片存储 + 面向查询的服务层索引\n按 user_id 范围重排，支持毫秒级单用户检索"},
            {"name": "应用层", "description": "本系统：9 个交互页面\n覆盖空间、话题、传播、关系与模拟"},
        ],
        "span": {"start": span_start, "end": span_end, "days": _int(len(daily))},
    }


def geo():
    grid = grid_frame()
    prov = province_frame()
    share = share_frame()
    inland = grid[
        (grid["glon"] >= 73) & (grid["glon"] <= 136)
        & (grid["glat"] >= 3) & (grid["glat"] <= 54)
    ]
    inland_share = float(inland["posts"].sum()) / float(grid["posts"].sum())
    top = grid.loc[grid["posts"].idxmax()]

    return {
        "kpis": [
            _kpi("覆盖网格", "{:,}".format(len(grid)), "0.25° × 0.25° 经纬网格"),
            _kpi("最热网格发帖量", _human(top["posts"]),
                 "%.2f°E / %.2f°N" % (top["glon"], top["glat"])),
            _kpi("用户省份取值", "{:,}".format(len(prov)), "用户资料省份字段去重后的取值数"),
            _kpi("境内推文占比", "%.2f%%" % (inland_share * 100), "经纬度落在国境范围内"),
        ],
        "grid": [
            {
                "glon": _float(row.glon, 2),
                "glat": _float(row.glat, 2),
                "posts": _int(row.posts),
                "users": _int(row.users),
                "reposts": _int(row.reposts),
                "v": _float(math.log10(max(_int(row.posts), 1)), 4),
            }
            for row in grid.itertuples(index=False)
        ],
        "province": [
            {
                "province": _text(row.province),
                "posts": _int(row.posts),
                "users": _int(row.users),
                "avg_reposts": _float(row.avg_reposts, 2),
            }
            for row in prov.sort_values("posts", ascending=False).itertuples(index=False)
        ],
        "share": {
            "provinces": sorted(share["province"].dropna().unique().tolist()),
            "rows": [
                {
                    "day": _day(row.day),
                    "province": _text(row.province),
                    "share": _float(row.share, 6),
                }
                for row in share.itertuples(index=False)
            ],
        },
        "lockdown": {"start": "2020-01-23", "end": "2020-04-08"},
        "notes": [
            "仅展示发帖量 ≥ 500 的网格；点面积为对数发帖量，颜色越深表示越密集。",
            "占比除以当日全量带坐标推文量，剥离采集规模的整体增长。",
        ],
    }


def topics():
    stats = topic_stats_frame()
    hs = hotsearch_frame()
    top20 = stats.head(20)
    options = topic_options()
    default_topic = options[1] if len(options) > 1 else (options[0] if options else "")
    corr = {}
    for key, column in (("peak_heat", "peak_heat"),
                        ("appearances", "appearances"),
                        ("best_rank", "best_rank")):
        pair = hs[["occurrences", column]].astype(float)
        value = float(np.corrcoef(pair["occurrences"], pair[column])[0, 1])
        corr[key] = _float(value, 4)

    def table_rows(frame):
        return [
            {
                "topic": _text(row.topic),
                "occurrences": _int(row.occurrences),
                "peak_heat": _int(row.peak_heat),
                "best_rank": _int(row.best_rank),
            }
            for row in frame.itertuples(index=False)
        ]

    return {
        "kpis": [
            _kpi("话题标签", "{:,}".format(len(stats)), "去重后的话题数"),
            _kpi("话题提及", _human(int(stats["occurrences"].sum())), "全部推文中的标签出现次数"),
            _kpi("最热话题", _text(stats.iloc[0]["topic"]),
                 "{:,} 次提及".format(_int(stats.iloc[0]["occurrences"]))),
            _kpi("登上热搜的话题", "{:,}".format(len(hs)), "站内话题与热搜榜的交集"),
        ],
        "top20": [
            {
                "topic": _text(row.topic),
                "occurrences": _int(row.occurrences),
                "posts": _int(row.posts),
                "users": _int(row.users),
            }
            for row in top20.itertuples(index=False)
        ],
        "options": options,
        "default_topic": default_topic,
        "scatter": [
            {
                "topic": _text(row.topic),
                "occurrences": _int(row.occurrences),
                "peak_heat": _int(row.peak_heat),
                "appearances": _int(row.appearances),
                "best_rank": _int(row.best_rank),
            }
            for row in hs.itertuples(index=False)
        ],
        "correlations": corr,
        "tables": {
            "top_posts": table_rows(hs.sort_values("occurrences", ascending=False).head(8)),
            "top_heat": table_rows(hs.sort_values("peak_heat", ascending=False).head(8)),
        },
        "notes": [
            "推文集按 179 个疫情关键词筛选，非疫情类热搜（如体育、娱乐）在推文侧没有对应文本，"
            "因此相关性被系统性削弱，结论只在疫情话题范围内成立。",
            "热搜散点使用双对数坐标；每个点是一个同时登上热搜、并在推文中出现的话题。",
        ],
    }


def topic_daily(topic):
    daily = topic_daily_frame(topic)
    rows = [
        {"day": _day(row.day), "occurrences": _int(row.occurrences), "users": _int(row.users)}
        for row in daily.itertuples(index=False)
    ]
    span = daily[daily["occurrences"] > 0]
    if len(span):
        peak = span.loc[span["occurrences"].idxmax()]
        caption = "首见 %s，末见 %s，共 %d 天有记录；峰值 %s（%s 次提及）" % (
            _day(span["day"].min()), _day(span["day"].max()), len(span),
            _day(peak["day"]), "{:,}".format(_int(peak["occurrences"])),
        )
    else:
        caption = "该话题没有逐日记录。"
    return {"topic": topic, "rows": rows, "caption": caption}


def cascade():
    casc = cascade_frame()
    growth = cascade_growth_frame()
    users = graph_users()
    big = int((casc["reposters"] >= 1000).sum())
    edges = np.array([1, 2, 3, 6, 11, 21, 51, 101, 501, 1001, 5001, 60000])
    labels = ["%s~%s" % (edges[i], edges[i + 1] - 1) for i in range(len(edges) - 1)]
    counts = np.histogram(casc["reposters"], bins=edges)[0]

    have_growth = set(growth["orig_id"])
    cand = casc[casc["orig_id"].isin(have_growth)].sort_values("reposters", ascending=False).head(20)
    candidates = [
        {
            "orig_id": _text(row.orig_id),
            "reposters": _int(row.reposters),
            "label": "%s · %s 人转发" % (_text(row.orig_id), "{:,}".format(_int(row.reposters))),
        }
        for row in cand.itertuples(index=False)
    ]

    top = casc.sort_values("reposters", ascending=False).head(20).merge(
        users[["user_id", "fans_num", "province", "city"]],
        left_on="target_user", right_on="user_id", how="left",
    )
    wanted = set(top["target_user"].astype(str))
    fans_rank = users["fans_num"].rank(ascending=False, method="min").astype("int64")
    rank_map = dict(zip(
        users.loc[users["user_id"].isin(wanted), "user_id"],
        fans_rank[users["user_id"].isin(wanted)],
    ))

    rows = []
    for row in top.itertuples(index=False):
        rows.append({
            "orig_id": _text(row.orig_id),
            "reposters": _int(row.reposters),
            "target_user": _text(row.target_user),
            "fans_num": _nullable_int(row.fans_num),
            "fans_rank": rank_map.get(_text(row.target_user)),
            "province": _text(row.province),
        })

    pol = polarity_frame()
    order = {"正面": 0, "中性": 1, "负面": 2}
    pol = pol.sort_values("polarity", key=lambda s: s.map(order))
    polarity = [
        {
            "polarity": _text(row.polarity),
            "posts": _int(row.posts),
            "avg_reposts": _float(row.avg_reposts, 2),
            "posts_ge_100": _int(row.posts_ge_100),
            "posts_ge_1000": _int(row.posts_ge_1000),
        }
        for row in pol.itertuples(index=False)
    ]
    buck = bucket_frame()
    buckets = [
        {
            "polarity": _text(row.polarity),
            "bucket": _text(row.bucket),
            "posts": _int(row.posts),
            "share": _float(row.share, 6),
        }
        for row in buck.itertuples(index=False)
    ]

    return {
        "kpis": [
            _kpi("转发级联", "{:,}".format(len(casc)), "按被转发微博聚合"),
            _kpi("最大级联", "{:,}".format(_int(casc["reposters"].max())), "单条微博的转发者人数"),
            _kpi("转发破千的微博", "{:,}".format(big),
                 "占全部级联 %.2f%%" % (big / len(casc) * 100)),
            _kpi("平均规模", "%.2f" % float(casc["reposters"].mean()), "平均每条微博的转发者人数"),
        ],
        "bins": [{"label": labels[i], "count": _int(counts[i])} for i in range(len(labels))],
        "candidates": candidates,
        "top": rows,
        "sentiment": {"polarity": polarity, "buckets": buckets},
        "notes": [
            "粉丝数是起点，不是传播的保证。",
            "词典法读不懂反讽与语境（全国哀悼日当天正面占比反而最高）；“加油、致敬”这类动员型内容本身更容易被转发，"
            "所以结论应限定在疫情动员语境下。",
        ],
    }


def cascade_growth(orig_id):
    growth = cascade_growth_frame()
    series = growth[growth["orig_id"] == orig_id].sort_values("hour")
    rows = [
        {"hour": _time(row.hour), "new_reposters": _int(row.new_reposters)}
        for row in series.itertuples(index=False)
    ]
    if len(series):
        peak = series.loc[series["new_reposters"].idxmax()]
        elapsed = (pd.Timestamp(peak["hour"]) - pd.Timestamp(series["hour"].min())).total_seconds() / 3600
        caption = "峰值出现在 %s，距首次转发仅 %.0f 小时；爆发式传播通常在两小时内达峰，随后单调衰减——即热点的“黄金两小时”窗口。" % (
            str(peak["hour"])[:16], elapsed,
        )
    else:
        caption = "该微博没有逐小时转发记录。"
    return {"orig_id": orig_id, "rows": rows, "caption": caption}


def influence():
    users = graph_users()
    zero_in = int((users["in_degree"] == 0).sum())
    ranked = users.sort_values("pagerank", ascending=False).reset_index(drop=True)
    top20 = ranked.head(20)
    sample = users.sample(n=30000, random_state=7) if len(users) > 30000 else users
    top100 = ranked.head(100)
    wanted = set(top20["user_id"].astype(str)) | set(top100["user_id"].astype(str))
    mask = users["user_id"].isin(wanted)
    fans_rank = users["fans_num"].rank(ascending=False, method="min").astype("int64")
    rank_map = dict(zip(users.loc[mask, "user_id"], fans_rank[mask]))

    def scatter_rows(frame, include_id=False):
        rows = []
        for row in frame.itertuples(index=False):
            item = {
                "fans_num": max(_int(row.fans_num), 1),
                "pagerank": _float(row.pagerank, 6),
            }
            if include_id:
                item.update({
                    "user_id": _text(row.user_id),
                    "in_degree": _int(row.in_degree),
                    "fans_rank": int(rank_map.get(_text(row.user_id), 0)),
                })
            rows.append(item)
        return rows

    sizes = users["leiden"].value_counts().head(20)
    communities = [{"id": int(cid), "size": _int(size)} for cid, size in sizes.items()]

    return {
        "kpis": [
            _kpi("转发图节点", "{:,}".format(len(users)), "有转发关系的用户"),
            _kpi("社区数量", "{:,}".format(users["leiden"].nunique()), "Leiden 划分，模块度 0.7985"),
            _kpi("最大入度", "{:,}".format(_int(users["in_degree"].max())), "被最多人转发的用户"),
            _kpi("零入度用户", "{:,}".format(zero_in),
                 "占 %.1f%%，只转发、不被转发" % (zero_in / len(users) * 100)),
        ],
        "top20": [
            {
                "user_id": _text(row.user_id),
                "pagerank": _float(row.pagerank, 6),
                "in_degree": _int(row.in_degree),
                "out_degree": _int(row.out_degree),
                "fans_num": _int(row.fans_num),
                "fans_rank": int(rank_map.get(_text(row.user_id), 0)),
                "province": _text(row.province),
                "city": _text(row.city),
                "community": _int(row.leiden),
            }
            for row in top20.itertuples(index=False)
        ],
        "scatter": {
            "sample": scatter_rows(sample),
            "top100": scatter_rows(top100, include_id=True),
        },
        "communities": communities,
        "default_community": communities[0]["id"] if communities else None,
        "community": community(communities[0]["id"]) if communities else None,
    }


def community(cid):
    users = graph_users()
    part = users[users["leiden"] == cid]
    if part.empty:
        return None
    gender = part["gender"].fillna("未知").replace("", "未知").value_counts().head(5)
    province = part["province"].fillna("未知").replace("", "未知").value_counts().head(5)
    return {
        "id": int(cid),
        "size": _int(len(part)),
        "avg_fans": round(float(part["fans_num"].mean()), 0),
        "gender": [{"key": _text(k), "count": _int(v)} for k, v in gender.items()],
        "province": [{"key": _text(k), "count": _int(v)} for k, v in province.items()],
    }


def profile(user_id):
    prof = profile_frame(user_id)
    row = graph_user(user_id)
    if prof.empty and row.empty:
        return {
            "status": "invalid",
            "profile": None,
            "graph": None,
            "out": {"count": 0, "rows": []},
            "in": {"count": 0, "rows": []},
            "message": "用户画像与转发图中都没有这个 id。注意 id 是 16 位十六进制字符串。",
        }

    profile_obj = None
    if not prof.empty:
        p = prof.iloc[0]
        profile_obj = {
            "user_id": _text(p["user_id"]),
            "fans_num": _int(p["fans_num"]),
            "gender": _text(p["gender"]),
            "province": _text(p["province"]),
            "city": _text(p["city"]),
            "vip_level": _text(p["vip_level"]),
        }

    graph_obj = None
    if not row.empty:
        r = row.iloc[0]
        graph_obj = {
            "in_degree": _int(r["in_degree"]),
            "out_degree": _int(r["out_degree"]),
            "pagerank": _float(r["pagerank"], 6),
            "leiden": _int(r["leiden"]),
        }

    edges = edges_of(user_id)
    out_edges = edges[edges["source_user"] == user_id]
    in_edges = edges[edges["target_user"] == user_id]

    def grouped(frame, key):
        if frame.empty:
            return []
        grouped_frame = (
            frame.groupby(key)
            .agg(count=("weight", "max"), first_time=("first_time", "min"))
            .sort_values("count", ascending=False)
            .head(10)
        )
        return [
            {
                "user_id": _text(idx),
                "count": _int(item.count),
                "first_time": _time(item.first_time),
            }
            for idx, item in grouped_frame.iterrows()
        ]

    return {
        "status": "ok",
        "profile": profile_obj,
        "graph": graph_obj,
        "out": {"count": _int(len(out_edges)), "rows": grouped(out_edges, "target_user")},
        "in": {"count": _int(len(in_edges)), "rows": grouped(in_edges, "source_user")},
        "message": "",
    }


@lru_cache(maxsize=1)
def pagerank_ids():
    ranked = graph_users().sort_values("pagerank", ascending=False)
    return ranked["user_id"].tolist()


@lru_cache(maxsize=1)
def simulate_seeds():
    users = graph_users().sort_values("pagerank", ascending=False).head(30)
    return [
        {
            "user_id": _text(row.user_id),
            "label": "%s · 粉丝 %s · 被转发 %s 人" % (
                _text(row.user_id), "{:,}".format(_int(row.fans_num)),
                "{:,}".format(_int(row.in_degree)),
            ),
        }
        for row in users.itertuples(index=False)
    ]


@lru_cache(maxsize=1)
def probe_user_ids():
    users = graph_users().sort_values("in_degree", ascending=False).reset_index(drop=True)
    return [_text(users.iloc[i]["user_id"]) for i in (0, 1000, 50000)]


def relation_rows(path):
    rows = []
    for seq, user_id in enumerate(path):
        info = graph_user(user_id)
        item = {
            "seq": seq,
            "user_id": user_id,
            "fans_num": None,
            "in_degree": None,
            "pagerank": None,
            "province": None,
            "community": None,
        }
        if not info.empty:
            p = info.iloc[0]
            item.update({
                "fans_num": _nullable_int(p["fans_num"]),
                "in_degree": _nullable_int(p["in_degree"]),
                "pagerank": _nullable_float(p["pagerank"], 6),
                "province": _text(p["province"]),
                "community": _nullable_int(p["leiden"]),
            })
        rows.append(item)
    return rows


def one_hop(user_id):
    info = graph_user(user_id)
    if info.empty:
        return {"reposters": 0, "follows": 0}
    row = info.iloc[0]
    return {"reposters": _int(row["in_degree"]), "follows": _int(row["out_degree"])}