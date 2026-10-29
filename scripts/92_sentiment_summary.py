"""情感极性与传播量的交叉汇总，供界面直接读取。

按批次扫描情感标注表，避免把 4089 万行一次性读入内存。
极性判定与 52_sentiment_analysis.py 一致：正负分比较，同分为中性。
"""

import os

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

import spark_env

SENTIMENT = os.path.join(spark_env.PROJECT_ROOT, "output", "sentiment_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")

LABELS = ["正面", "中性", "负面"]
EDGES = np.array([1, 2, 3, 6, 11, 51, 101, 1001])
BUCKET_NAMES = ["0", "1", "2", "3-5", "6-10", "11-50", "51-100", "101-1000", "1000+"]


def main():
    counts = {lab: 0 for lab in LABELS}
    sums = {lab: 0.0 for lab in LABELS}
    ge1000 = {lab: 0 for lab in LABELS}
    ge100 = {lab: 0 for lab in LABELS}
    buckets = {lab: np.zeros(len(BUCKET_NAMES), dtype=np.int64) for lab in LABELS}

    dataset = ds.dataset(SENTIMENT, format="parquet")
    scanner = dataset.scanner(columns=["repost_num", "pos", "neg"], batch_size=1_000_000)
    for batch in scanner.to_batches():
        repost = batch.column("repost_num").to_numpy(zero_copy_only=False).astype(np.int64)
        pos = batch.column("pos").to_numpy(zero_copy_only=False)
        neg = batch.column("neg").to_numpy(zero_copy_only=False)
        label = np.where(pos > neg, 0, np.where(pos < neg, 2, 1))
        idx = np.digitize(repost, EDGES)
        for code, lab in enumerate(LABELS):
            sel = label == code
            rep = repost[sel]
            counts[lab] += int(sel.sum())
            sums[lab] += float(rep.sum())
            ge1000[lab] += int((rep >= 1000).sum())
            ge100[lab] += int((rep >= 100).sum())
            buckets[lab] += np.bincount(idx[sel], minlength=len(BUCKET_NAMES))

    rows = []
    for lab in LABELS:
        n = counts[lab]
        rows.append(
            {
                "polarity": lab,
                "posts": n,
                "avg_reposts": sums[lab] / n if n else 0.0,
                "posts_ge_100": ge100[lab],
                "posts_ge_1000": ge1000[lab],
            }
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(os.path.join(OUT_DIR, "sentiment_by_polarity.csv"), index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False), flush=True)

    bucket_rows = []
    for lab in LABELS:
        total = max(counts[lab], 1)
        for name, value in zip(BUCKET_NAMES, buckets[lab]):
            bucket_rows.append(
                {"polarity": lab, "bucket": name, "posts": int(value), "share": float(value) / total}
            )
    pd.DataFrame(bucket_rows).to_csv(
        os.path.join(OUT_DIR, "sentiment_repost_buckets.csv"), index=False, encoding="utf-8-sig"
    )
    print("SENTIMENT_SUMMARY_DONE", flush=True)


if __name__ == "__main__":
    main()
