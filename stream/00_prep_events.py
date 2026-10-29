"""把历史推文整理成按天分区的回放事件。

每行是一条推文事件，供回放器按时间顺序重放到 spool 目录：
ts / repost_num / pos / neg / topics / region。
情绪值取自已经算好的情感表，话题标签在这里一次性抽好，正文随后丢弃，
回放时每个事件只有几百字节，才能按"每秒若干万条"的速率推出去。
"""

import os
import sys
import time

from pyspark.sql import functions as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import spark_env

POSTS = os.path.join(spark_env.DATA_DIR, "cov_posts_parquet")
SENTI = os.path.join(ROOT, "output", "sentiment_parquet")
# 推文的 geo_info 全为空串，坐标表又是另一批推文（按 _id 只交集 2.9%），
# 地域维度因此取用户画像里的省份
USERS = os.path.join(spark_env.DATA_DIR, "cov_users_parquet")
OUT = os.path.join(spark_env.DATA_DIR, "stream_events")

# 与 32_extract_topics.py 保持同一套话题写法，保证回放统计和历史分析口径一致
TAG_PATTERN = r"#([^#\[\]\s]{2,30})#"


def main() -> int:
    t0 = time.time()
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("00-prep-events", driver_memory="8g")
    spark.conf.set("spark.sql.shuffle.partitions", "160")

    posts = spark.read.parquet(POSTS).select(
        "_id", "user_id", "created_at", "repost_num", "content"
    )
    senti = spark.read.parquet(SENTI).select("_id", "pos", "neg")
    users = (
        spark.read.parquet(USERS).select("user_id", "province")
        .filter(F.col("province").isNotNull())
        .dropDuplicates(["user_id"])
    )
    print("[read] %.1fs" % (time.time() - t0), flush=True)

    t0 = time.time()
    joined = (
        posts.join(senti, on="_id", how="left")
        .join(users, on="user_id", how="left")
    )
    print("[join] %.1fs" % (time.time() - t0), flush=True)

    t0 = time.time()
    events = (
        joined.withColumn("ts", F.to_timestamp("created_at"))
        .withColumn("day", F.to_date("ts"))
        .withColumn("topics", F.regexp_extract_all(F.col("content"), F.lit(TAG_PATTERN), 1))
        .filter(F.col("ts").isNotNull())
        .withColumn("region", F.coalesce(F.col("province"), F.lit("未知")))
        .select("day", "ts", "repost_num", "pos", "neg", "topics", "region")
    )
    print("[extract] %.1fs" % (time.time() - t0), flush=True)

    t0 = time.time()
    n = events.cache().count()
    print("[count] %s rows  (%.1fs)" % (f"{n:,}", time.time() - t0), flush=True)

    t0 = time.time()
    # 一天一个输出分区：回放器按目录名顺序读取即可，不需要再全局排序
    events.repartition(F.col("day")).write.mode("overwrite").partitionBy("day").parquet(OUT)
    print("[write] %.1fs -> %s" % (time.time() - t0, OUT), flush=True)

    spark.read.parquet(OUT).groupBy("day").count().orderBy("day").show(5, truncate=False)
    print("PREP_EVENTS_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
