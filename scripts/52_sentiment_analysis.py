"""情感打分结果的统计：总体倾向、时间演化、以及与传播量的关系。

情感分是词典加权的计数（否定词翻转、程度副词加权），
因此用"正面分 - 负面分"的符号定极性，用绝对值大小衡量强度。
"""

import os
import sys
import time

from pyspark.sql import functions as F

import spark_env

SENTIMENT = os.path.join(spark_env.PROJECT_ROOT, "output", "sentiment_parquet")
USERS = os.path.join(spark_env.DATA_DIR, "cov_users_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")


def polarity(col_pos, col_neg):
    return (
        F.when(col_pos > col_neg, "正面")
        .when(col_pos < col_neg, "负面")
        .otherwise("中性")
    )


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("52-sentiment-stats", driver_memory="8g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")
    try:
        df = spark.read.parquet(SENTIMENT)
        df.cache()
        n = df.count()
        print(f"[rows] {n:,}", flush=True)

        labeled = df.withColumn("polarity", polarity(F.col("pos"), F.col("neg")))

        print("\n=== 总体情感分布 ===", flush=True)
        labeled.groupBy("polarity").agg(
            F.count("*").alias("posts"),
            F.avg("pos").alias("avg_pos"),
            F.avg("neg").alias("avg_neg"),
        ).withColumn("share", F.col("posts") / n).orderBy(F.desc("posts")).show(truncate=False)

        print("=== 有情感极性的占比 ===", flush=True)
        labeled.agg(
            F.avg(F.when((F.col("pos") + F.col("neg")) > 0, 1.0).otherwise(0.0)).alias("has_signal")
        ).show(truncate=False)

        print("=== 按日情感倾向 ===", flush=True)
        daily = (
            labeled.withColumn("day", F.to_date(F.to_timestamp("created_at")))
            .groupBy("day")
            .agg(
                F.count("*").alias("posts"),
                F.sum(F.when(F.col("polarity") == "正面", 1).otherwise(0)).alias("positive"),
                F.sum(F.when(F.col("polarity") == "负面", 1).otherwise(0)).alias("negative"),
            )
            .withColumn("positive_share", F.col("positive") / F.col("posts"))
            .orderBy("day")
        )
        daily.write.mode("overwrite").parquet(os.path.join(OUT_DIR, "sentiment_daily_parquet"))
        daily.filter(F.col("posts") > 20000).orderBy(F.asc("positive_share")).show(8, truncate=False)
        print("  ↑ 正面占比最低的 8 天", flush=True)
        daily.filter(F.col("posts") > 20000).orderBy(F.desc("positive_share")).show(8, truncate=False)
        print("  ↑ 正面占比最高的 8 天", flush=True)

        print("=== 情感与传播量 ===", flush=True)
        labeled.groupBy("polarity").agg(
            F.avg("repost_num").alias("avg_reposts"),
            F.expr("percentile_approx(repost_num, 0.5)").alias("median_reposts"),
            F.expr("percentile_approx(repost_num, 0.99)").alias("p99_reposts"),
            F.max("repost_num").alias("max_reposts"),
        ).show(truncate=False)

        print("=== 转发过千的微博里情感分布 ===", flush=True)
        labeled.filter(F.col("repost_num") >= 1000).groupBy("polarity").agg(
            F.count("*").alias("posts")
        ).orderBy(F.desc("posts")).show(truncate=False)

        print("=== 情感的地区差异（按省份，取推文量前 12 省）===", flush=True)
        users = spark.read.parquet(USERS).select(
            "user_id",
            F.when(F.length(F.trim("province")) > 0, F.trim("province")).alias("province"),
        )
        (
            labeled.select("user_id", "polarity")
            .join(users, on="user_id", how="inner")
            .filter(F.col("province").isNotNull())
            .groupBy("province")
            .agg(
                F.count("*").alias("posts"),
                F.avg(F.when(F.col("polarity") == "正面", 1.0).otherwise(0.0)).alias("positive_share"),
            )
            .filter(F.col("posts") > 100_000)
            .orderBy(F.desc("posts"))
            .show(12, truncate=False)
        )
        print("SENTIMENT_ANALYSIS_DONE", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
