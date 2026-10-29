"""转发级联分析。

origin_weibo 记录的是"转发的根微博"，所以每条转发直接指向原帖，
级联是星形而非树——深度恒为 1。因此这里分析的是级联的"宽度"与"节奏"：
有多少人参与、扩散多快、原作者是谁。
"""

import os
import sys
import time

from pyspark.sql import functions as F

import spark_env

EDGES_DETAIL = os.path.join(spark_env.DATA_DIR, "repost_edges_parquet")
USERS = os.path.join(spark_env.DATA_DIR, "cov_users_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")
CASCADE_STATS = os.path.join(OUT_DIR, "cascade_stats.parquet")
CASCADE_GROWTH = os.path.join(OUT_DIR, "cascade_growth_parquet")


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("34-cascade", driver_memory="10g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")
    try:
        edges = spark.read.parquet(EDGES_DETAIL)

        t0 = time.time()
        cascades = edges.groupBy("orig_id", "target_user").agg(
            F.countDistinct("source_user").alias("reposters"),
            F.max("orig_repost_num").alias("declared_repost_num"),
            F.min("repost_time").alias("first_repost"),
            F.max("repost_time").alias("last_repost"),
        )
        cascades.cache()
        n = cascades.count()
        print(f"[cascades] {n:,}  ({time.time() - t0:.1f}s)", flush=True)

        print("[cascade size distribution]", flush=True)
        cascades.agg(
            F.min("reposters").alias("min"),
            F.avg("reposters").alias("mean"),
            F.max("reposters").alias("max"),
            F.expr("percentile_approx(reposters, array(0.5, 0.9, 0.99, 0.999))").alias("pct"),
            F.sum(F.when(F.col("reposters") >= 1000, 1).otherwise(0)).alias("ge_1000"),
            F.sum(F.when(F.col("reposters") >= 100, 1).otherwise(0)).alias("ge_100"),
        ).show(truncate=False)

        # 解析出的转发人数与原帖自带转发数对比，用来衡量级联重构的完整度。
        print("[reconstruction coverage]", flush=True)
        cascades.agg(
            F.sum("reposters").alias("resolved_edges"),
            F.sum("declared_repost_num").alias("declared_reposts"),
        ).withColumn(
            "coverage", F.col("resolved_edges") / F.col("declared_reposts")
        ).show(truncate=False)

        users = spark.read.parquet(USERS).select(
            F.col("user_id").alias("target_user"), "gender", "province", "fans_num"
        )
        top = (
            cascades.orderBy(F.desc("reposters"))
            .limit(20)
            .join(users, on="target_user", how="left")
        )
        print("[top-20 cascades]", flush=True)
        top.select(
            "orig_id", "reposters", "declared_repost_num",
            "gender", "province", "fans_num", "first_repost", "last_repost",
        ).show(20, truncate=False)

        cascades.write.mode("overwrite").parquet(CASCADE_STATS)

        # 头部级联的扩散节奏：按小时统计新增转发数。
        top_ids = [r["orig_id"] for r in top.select("orig_id").collect()]
        growth = (
            edges.filter(F.col("orig_id").isin(top_ids))
            .withColumn("hour", F.date_trunc("hour", "repost_time"))
            .groupBy("orig_id", "hour")
            .agg(F.countDistinct("source_user").alias("new_reposters"))
            .orderBy("orig_id", "hour")
        )
        growth.write.mode("overwrite").parquet(CASCADE_GROWTH)
        print("[growth sample: 最大级联的前 15 小时]", flush=True)
        growth.filter(F.col("orig_id") == top_ids[0]).limit(15).show(truncate=False)

        print("CASCADE_ANALYSIS_DONE", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
