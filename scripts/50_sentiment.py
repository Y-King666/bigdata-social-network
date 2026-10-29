"""基于知网 HowNet 情感词典的中文情感打分。

cnsenti 每条约 1 毫秒，逐行 UDF 的 JVM/Python 往返开销会拖慢一个量级，
因此改用 mapPartitions：每个分区只初始化一次分词器与词典，按批返回。
"""

import glob
import os
import sys
import time

from pyspark.sql import Row
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

import spark_env

POSTS = os.path.join(spark_env.DATA_DIR, "cov_posts_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")

SCHEMA = StructType(
    [
        StructField("_id", StringType(), False),
        StructField("user_id", StringType(), False),
        StructField("created_at", StringType(), True),
        StructField("repost_num", IntegerType(), True),
        StructField("pos", IntegerType(), True),
        StructField("neg", IntegerType(), True),
    ]
)


def score_partition(rows):
    from cnsenti import Sentiment

    analyzer = Sentiment()
    out = []
    for r in rows:
        text = r["content"] or ""
        try:
            res = analyzer.sentiment_calculate(text)
            pos, neg = int(res["pos"]), int(res["neg"])
        except Exception:
            pos, neg = 0, 0
        out.append(Row(
            _id=r["_id"], user_id=r["user_id"], created_at=r["created_at"],
            repost_num=r["repost_num"], pos=pos, neg=neg,
        ))
        if len(out) >= 2000:
            yield from out
            out = []
    if out:
        yield from out


def main() -> int:
    n_parts = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    spark_env.setup_hadoop_home()
    # 这一步的计算全在 Python worker 里，JVM 只负责流式搬运，
    # 堆开大反而会把物理内存挤爆（20 个 worker + 大堆 = 超过 16GB）。
    spark = spark_env.build_spark("50-sentiment", driver_memory="2g")
    spark.conf.set("spark.sql.shuffle.partitions", "20")
    try:
        sources = sorted(glob.glob(os.path.join(POSTS, "part-*.parquet")))
        if n_parts:
            sources = sources[:n_parts]
        print(f"[input] {len(sources)} part files", flush=True)

        posts = spark.read.parquet(*sources).select(
            "_id", "user_id", "created_at", "repost_num", "content"
        )
        n = posts.count()
        print(f"[rows] {n:,}", flush=True)

        t0 = time.time()
        scored = posts.rdd.mapPartitions(score_partition)
        df = spark.createDataFrame(scored, schema=SCHEMA)
        out = os.path.join(OUT_DIR, "sentiment_parquet")
        (df.write.mode("overwrite").option("maxRecordsPerFile", 2_000_000)
           .parquet(out))
        elapsed = time.time() - t0
        print(f"[scored] {n:,} rows in {elapsed / 60:.1f} min "
              f"({n / elapsed:,.0f} rows/s)", flush=True)
        print(f"[export] -> {out}", flush=True)
        print("SENTIMENT_DONE", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
