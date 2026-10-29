"""核查入库后的 Weibo-COV 推文：规模、时间跨度、以及转发关系能否连成边。

"传播路线"这个功能完全依赖 origin_weibo 能不能指回数据集内的原微博，
所以要把可解析的转发比例实测出来，而不是靠抽样估计。
"""

import os
import sys
import time

from pyspark.sql import functions as F

import spark_env

POSTS = os.path.join(spark_env.DATA_DIR, "cov_posts_parquet")
GEO = os.path.join(spark_env.DATA_DIR, "cov_geo_parquet")

def has_origin():
    """CSV 里缺失字段解析出来是空字符串而非 NULL，判断"有值"必须两者都考虑。"""
    return F.col("origin_weibo").isNotNull() & (F.length("origin_weibo") > 0)


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("23-cov-overview", driver_memory="10g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")
    try:
        posts = spark.read.parquet(POSTS).select(
            "_id", "user_id", "created_at", "like_num", "repost_num", "comment_num",
            F.col("origin_weibo"), F.col("content").isNotNull().alias("has_content"),
        )

        t0 = time.time()
        n = posts.count()
        print(f"[posts] {n:,} rows  ({time.time() - t0:.1f}s)", flush=True)

        t0 = time.time()
        posts.agg(
            F.min("created_at").alias("first"),
            F.max("created_at").alias("last"),
            F.countDistinct("user_id").alias("users"),
            F.sum(F.when(has_origin(), 1).otherwise(0)).alias("reposts"),
        ).show(truncate=False)
        print(f"[range/users/reposts] {time.time() - t0:.1f}s", flush=True)

        t0 = time.time()
        posts.agg(
            F.avg("like_num").alias("avg_like"),
            F.avg("repost_num").alias("avg_repost"),
            F.max("repost_num").alias("max_repost"),
            F.expr("percentile_approx(repost_num, array(0.5, 0.99, 0.999))").alias("repost_pct"),
        ).show(truncate=False)
        print(f"[engagement] {time.time() - t0:.1f}s", flush=True)

        # 转发能否解析成边：origin_weibo 是否命中数据集内的某条 _id。
        t0 = time.time()
        reposts = posts.filter(has_origin()).select("origin_weibo")
        ids = posts.select(F.col("_id").alias("orig_id")).distinct()
        resolvable = reposts.join(ids, reposts["origin_weibo"] == ids["orig_id"], "left_semi")
        n_res = resolvable.count()
        print(f"[resolvable reposts] {n_res:,}  ({time.time() - t0:.1f}s)", flush=True)

        geo = spark.read.parquet(GEO).select("_id", "user_id", "created_at", "geo_info")
        t0 = time.time()
        gn = geo.count()
        print(f"[geo posts] {gn:,} rows  ({time.time() - t0:.1f}s)", flush=True)
        geo.agg(
            F.min("created_at").alias("first"),
            F.max("created_at").alias("last"),
            F.countDistinct("user_id").alias("users"),
        ).show(truncate=False)

        print("COV_OVERVIEW_DONE", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
