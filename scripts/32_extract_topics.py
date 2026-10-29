"""从推文正文抽取 #话题#，生成话题统计与话题日趋势。

微博话题写在两个 # 之间（如 #聚焦新冠肺炎疫情#）。话题是连接"文本"与
"网络"的桥梁：既能统计热度演化，也能按话题切出发言用户的子图。
"""

import os
import sys
import time

from pyspark.sql import functions as F

import spark_env

POSTS = os.path.join(spark_env.DATA_DIR, "cov_posts_parquet")
TOPIC_STATS = os.path.join(spark_env.DATA_DIR, "topic_stats_parquet")
TOPIC_DAILY = os.path.join(spark_env.DATA_DIR, "topic_daily_parquet")

TAG_PATTERN = r"#([^#\[\]\s]{2,30})#"


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("32-topics", driver_memory="10g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")
    try:
        posts = spark.read.parquet(POSTS).select(
            F.col("_id").alias("post_id"),
            "user_id",
            "created_at",
            "repost_num",
            "content",
        )

        t0 = time.time()
        tagged = posts.withColumn(
            "topics",
            F.regexp_extract_all(F.col("content"), F.lit(TAG_PATTERN), 1),
        ).filter(F.size("topics") > 0)

        exploded = tagged.select(
            F.explode("topics").alias("topic"),
            "post_id",
            "user_id",
            "repost_num",
            F.to_date(F.to_timestamp("created_at")).alias("day"),
        )
        exploded.cache()
        n_occ = exploded.count()
        print(f"[tag occurrences] {n_occ:,}  ({time.time() - t0:.1f}s)", flush=True)

        t0 = time.time()
        stats = exploded.groupBy("topic").agg(
            F.count("*").alias("occurrences"),
            F.countDistinct("post_id").alias("posts"),
            F.countDistinct("user_id").alias("users"),
            F.sum("repost_num").alias("total_reposts"),
            F.min("day").alias("first_seen"),
            F.max("day").alias("last_seen"),
        )
        stats.write.mode("overwrite").parquet(TOPIC_STATS)
        n_topics = stats.count()
        print(f"[topics] {n_topics:,} distinct  ({time.time() - t0:.1f}s)", flush=True)

        print("[top-20 话题]", flush=True)
        stats.orderBy(F.desc("occurrences")).limit(20).show(truncate=False)

        t0 = time.time()
        daily = exploded.groupBy("topic", "day").agg(
            F.count("*").alias("occurrences"),
            F.countDistinct("user_id").alias("users"),
        )
        daily.write.mode("overwrite").parquet(TOPIC_DAILY)
        print(f"[topic-daily] {time.time() - t0:.1f}s -> {TOPIC_DAILY}", flush=True)

        print("EXTRACT_TOPICS_DONE", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
