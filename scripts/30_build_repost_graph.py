"""从推文里解析出转发网络。

每条转发记录只带原微博的 _id，要拿到"原博主是谁"必须回数据集里查这条 _id。
只有原微博也在数据集内的转发才能连成边，其余自然丢弃。
输出两份：带原微博 id 的明细边（供级联分析）、去重后的用户有向边（供图算法）。
"""

import os
import sys
import time

from pyspark.sql import functions as F

import spark_env

POSTS = os.path.join(spark_env.DATA_DIR, "cov_posts_parquet")
EDGES_DETAIL = os.path.join(spark_env.DATA_DIR, "repost_edges_parquet")
EDGES_USER = os.path.join(spark_env.DATA_DIR, "repost_user_edges_parquet")


def has_origin():
    return F.col("origin_weibo").isNotNull() & (F.length("origin_weibo") > 0)


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("30-repost-graph", driver_memory="10g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")
    try:
        posts = spark.read.parquet(POSTS).select(
            "_id", "user_id", "origin_weibo", "created_at", "repost_num"
        )

        # 原微博 -> 作者，用于给每条转发补上"转给了谁"。
        origins = posts.select(
            F.col("_id").alias("orig_id"),
            F.col("user_id").alias("target_user"),
            F.col("repost_num").alias("orig_repost_num"),
        )

        reposts = posts.filter(has_origin()).select(
            F.col("_id").alias("repost_id"),
            F.col("user_id").alias("source_user"),
            F.col("origin_weibo").alias("orig_id"),
            F.to_timestamp("created_at").alias("repost_time"),
        )

        t0 = time.time()
        edges = reposts.join(origins, on="orig_id", how="inner").select(
            "orig_id", "repost_id", "source_user", "target_user",
            "repost_time", "orig_repost_num",
        )
        edges.cache()
        n_edges = edges.count()
        print(f"[edges] {n_edges:,}  ({time.time() - t0:.1f}s)", flush=True)

        print("[edge sample]", flush=True)
        edges.select("orig_id", "source_user", "target_user", "repost_time").show(5, truncate=False)

        t0 = time.time()
        edges.write.mode("overwrite").parquet(EDGES_DETAIL)
        print(f"[write detail] {time.time() - t0:.1f}s -> {EDGES_DETAIL}", flush=True)

        # 同一对用户之间可能多次转发，聚合成带权重的有向边。
        t0 = time.time()
        user_edges = edges.groupBy("source_user", "target_user").agg(
            F.count("*").alias("weight"),
            F.min("repost_time").alias("first_time"),
            F.max("repost_time").alias("last_time"),
        )
        n_user_edges = user_edges.count()
        print(f"[user-edges] {n_user_edges:,}  ({time.time() - t0:.1f}s)", flush=True)

        user_edges.write.mode("overwrite").parquet(EDGES_USER)
        print(f"[write user-edges] -> {EDGES_USER}", flush=True)

        t0 = time.time()
        stats = edges.agg(
            F.countDistinct("source_user").alias("sources"),
            F.countDistinct("target_user").alias("targets"),
            F.countDistinct("orig_id").alias("distinct_originals"),
        ).first()
        nodes = edges.select(F.col("source_user").alias("u")).union(
            edges.select(F.col("target_user").alias("u"))
        ).distinct().count()
        print(
            f"[graph] nodes={nodes:,}  sources={stats['sources']:,}  "
            f"targets={stats['targets']:,}  originals={stats['distinct_originals']:,}  "
            f"({time.time() - t0:.1f}s)",
            flush=True,
        )

        print("[top-10 被转发最多的原微博]", flush=True)
        (
            edges.groupBy("orig_id", "target_user")
            .agg(F.countDistinct("source_user").alias("reposters"))
            .orderBy(F.desc("reposters"))
            .limit(10)
            .show(truncate=False)
        )
        print("BUILD_REPOST_GRAPH_DONE", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
