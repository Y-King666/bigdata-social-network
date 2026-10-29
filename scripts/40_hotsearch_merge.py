"""把微博热搜榜与推文话题体系统一起来。

热搜榜是"平台推给你看的"，推文话题是"用户自己写的"。两者是否重合，
用于衡量热搜榜与站内讨论的对应关系。
"""

import glob
import os
import sys
import time

import pandas as pd
import pyarrow.dataset as ds

import spark_env

WEIBO_DIR = os.path.join(spark_env.DATA_DIR, "weibo")
TOPIC_STATS = os.path.join(spark_env.DATA_DIR, "topic_stats_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")
MERGED = os.path.join(OUT_DIR, "hotsearch_vs_topic.csv")


def read_hotsearch() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(WEIBO_DIR, "hotsearch_*.csv")))
    frames = [pd.read_csv(f, encoding="utf-8") for f in files]
    hs = pd.concat(frames, ignore_index=True)
    hs["时间"] = pd.to_datetime(hs["时间"], errors="coerce")
    return hs


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    t0 = time.time()
    hs = read_hotsearch()
    print(f"[hotsearch] {len(hs):,} 条记录, {hs['关键词'].nunique():,} 个关键词  "
          f"({time.time() - t0:.1f}s)", flush=True)
    print(f"  时间范围: {hs['时间'].min()} -> {hs['时间'].max()}", flush=True)

    # 同一关键词会在榜单上反复出现，压成一条：出现次数、最高热度、最好名次。
    agg = (
        hs.groupby("关键词")
        .agg(
            appearances=("new_rank", "size"),
            best_rank=("new_rank", "min"),
            peak_heat=("热度", "max"),
            hs_first=("时间", "min"),
            hs_last=("时间", "max"),
        )
        .reset_index()
        .rename(columns={"关键词": "topic"})
    )
    print(f"[hotsearch agg] {len(agg):,} 个去重话题, 平均上榜 {agg['appearances'].mean():.1f} 次", flush=True)
    print("\n[热搜榜 top-10（按最高热度）]", flush=True)
    print(agg.nlargest(10, "peak_heat")[["topic", "appearances", "best_rank", "peak_heat"]].to_string(index=False), flush=True)

    t0 = time.time()
    topics = ds.dataset(TOPIC_STATS, format="parquet").to_table().to_pandas()
    print(f"\n[topics] {len(topics):,} 个推文话题  ({time.time() - t0:.1f}s)", flush=True)

    merged = topics.merge(agg, on="topic", how="inner")
    print(f"\n=== 重合度 ===", flush=True)
    print(f"推文话题数            : {len(topics):,}", flush=True)
    print(f"热搜话题数            : {len(agg):,}", flush=True)
    print(f"两者都出现            : {len(merged):,}", flush=True)
    print(f"热搜话题被推文覆盖    : {len(merged) / len(agg):.2%}", flush=True)
    print(f"推文话题上了热搜      : {len(merged) / len(topics):.2%}", flush=True)

    print("\n[同时出现在推文与热搜、且推文量最高的 20 个话题]", flush=True)
    cols = ["topic", "occurrences", "users", "peak_heat", "best_rank", "appearances",
            "first_seen", "last_seen", "hs_first", "hs_last"]
    print(merged.nlargest(20, "occurrences")[cols].to_string(index=False), flush=True)

    corr = merged[["occurrences", "peak_heat", "appearances", "best_rank"]].corr()
    print("\n[相关性：推文量与热搜指标]", flush=True)
    print(corr.round(3).to_string(), flush=True)

    merged.to_csv(MERGED, index=False, encoding="utf-8-sig")
    print(f"\n[export] -> {MERGED}", flush=True)
    print("HOTSEARCH_MERGE_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
