"""转发网络的属性同质性分析。

同质性＝"有连接的两人是否比随机配对更相似"。随机配对的期望值可以直接由
属性边缘分布推出（P(同值) = Σp²），所以不需要构造随机图做对照，
观察值 / 期望值即为同质性强度。
"""

import os
import sys
import time

from pyspark.sql import Window
from pyspark.sql import functions as F

import spark_env

EDGES_USER = os.path.join(spark_env.DATA_DIR, "repost_user_edges_parquet")
USERS = os.path.join(spark_env.DATA_DIR, "cov_users_parquet")

VALID_BIRTHDAY = r"^(19|20)\d{2}-\d{2}-\d{2}$"


def both_not_null(a: str, b: str):
    return F.col(a).isNotNull() & F.col(b).isNotNull()


def same_share(a: str, b: str):
    """在双方属性都非空的边上，同值所占的比例。"""
    valid = both_not_null(a, b)
    equal = valid & (F.col(a) == F.col(b))
    return F.sum(F.when(equal, 1).otherwise(0)) / F.sum(F.when(valid, 1).otherwise(0))


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("35-homophily", driver_memory="10g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")
    try:
        edges = spark.read.parquet(EDGES_USER).select("source_user", "target_user")
        users = spark.read.parquet(USERS).select(
            "user_id",
            "gender",
            F.when(F.length(F.trim("province")) > 0, F.trim("province")).alias("province"),
            F.when(
                F.col("birthday").rlike(VALID_BIRTHDAY),
                F.substring("birthday", 1, 4).cast("int"),
            ).alias("birth_year"),
            "fans_num",
        )

        # 只保留出现在转发图里的用户，避免 2000 万沉默用户稀释边缘分布。
        graph_users = (
            edges.select(F.col("source_user").alias("user_id"))
            .union(edges.select(F.col("target_user").alias("user_id")))
            .distinct()
            .join(users, on="user_id", how="left")
        )
        graph_users.cache()
        print(f"[graph users] {graph_users.count():,}", flush=True)

        print("\n=== 性别分布 ===", flush=True)
        gender_dist = (
            graph_users.filter(F.col("gender").isNotNull())
            .groupBy("gender")
            .agg(F.count("*").alias("n"))
            .withColumn("p", F.col("n") / F.sum("n").over(Window.partitionBy()))
        )
        gender_dist.show(truncate=False)

        print("=== 省份分布 top-15 ===", flush=True)
        prov_dist = (
            graph_users.filter(F.col("province").isNotNull())
            .groupBy("province")
            .agg(F.count("*").alias("n"))
            .orderBy(F.desc("n"))
        )
        prov_dist.show(15, truncate=False)

        # 转发图的出边方（众多普通用户）与入边方（少数被转发账号）人群构成差别很大，
        # 因此随机配对的基准必须用两侧分布的交叉乘积 Σ p_src(a)·p_dst(a)，
        # 用合并总体算 Σp² 会把两侧的构成差异误读成连接偏好。
        src_users = (
            edges.select(F.col("source_user").alias("user_id"))
            .distinct().join(users, on="user_id", how="inner")
        )
        dst_users = (
            edges.select(F.col("target_user").alias("user_id"))
            .distinct().join(users, on="user_id", how="inner")
        )

        def bipartite_null(column: str) -> float:
            s = (
                src_users.filter(F.col(column).isNotNull())
                .groupBy(column).agg(F.count("*").alias("n_src"))
                .withColumn("p_src", F.col("n_src") / F.sum("n_src").over(Window.partitionBy()))
            )
            t = (
                dst_users.filter(F.col(column).isNotNull())
                .groupBy(column).agg(F.count("*").alias("n_dst"))
                .withColumn("p_dst", F.col("n_dst") / F.sum("n_dst").over(Window.partitionBy()))
            )
            return s.join(t, on=column).agg(F.sum(F.col("p_src") * F.col("p_dst"))).first()[0]

        g_expected = bipartite_null("gender")
        p_expected = bipartite_null("province")
        print(f"[null] 随机配对的同性别概率 = {g_expected:.4f}", flush=True)
        print(f"[null] 随机配对的同省份概率 = {p_expected:.4f}", flush=True)

        t0 = time.time()
        src = users.select(
            F.col("user_id").alias("source_user"),
            F.col("gender").alias("s_gender"),
            F.col("province").alias("s_province"),
            F.col("birth_year").alias("s_year"),
        )
        dst = users.select(
            F.col("user_id").alias("target_user"),
            F.col("gender").alias("t_gender"),
            F.col("province").alias("t_province"),
            F.col("birth_year").alias("t_year"),
        )
        full = edges.join(src, on="source_user", how="inner").join(dst, on="target_user", how="inner")
        full.cache()
        print(f"\n[matched edges] {full.count():,}  ({time.time() - t0:.1f}s)", flush=True)

        t0 = time.time()
        obs = full.agg(
            same_share("s_gender", "t_gender").alias("same_gender"),
            same_share("s_province", "t_province").alias("same_province"),
            F.avg(
                F.when(
                    both_not_null("s_year", "t_year"),
                    F.abs(F.col("s_year") - F.col("t_year")),
                )
            ).alias("mean_age_gap"),
        ).first()
        print(f"[observed] {time.time() - t0:.1f}s", flush=True)

        print("\n=== 同质性结果 ===", flush=True)
        print(f"同性别边占比 : 观察 {obs['same_gender']:.4f}  随机基准 {g_expected:.4f}  "
              f"提升 {obs['same_gender'] / g_expected:.2f} 倍", flush=True)
        print(f"同省份边占比 : 观察 {obs['same_province']:.4f}  随机基准 {p_expected:.4f}  "
              f"提升 {obs['same_province'] / p_expected:.2f} 倍", flush=True)
        print(f"平均年龄差   : {obs['mean_age_gap']:.2f} 岁", flush=True)

        print("\n=== 性别组合 ===", flush=True)
        (
            full.filter(both_not_null("s_gender", "t_gender"))
            .groupBy("s_gender", "t_gender")
            .agg(F.count("*").alias("edges"))
            .orderBy(F.desc("edges"))
            .show(truncate=False)
        )

        # 转发是"多数人 -> 少数账号"的单向结构，两侧人群构成差异很大，
        # 因此同质性必须分侧看，否则会把两侧的构成差异误读成连接偏好。
        print("\n=== 转发者一侧的性别构成 ===", flush=True)
        (
            edges.select("source_user").distinct()
            .join(users, edges["source_user"] == users["user_id"], "inner")
            .groupBy("gender").agg(F.count("*").alias("users"))
            .orderBy(F.desc("users")).show(6, truncate=False)
        )
        print("=== 被转发者一侧的性别构成 ===", flush=True)
        (
            edges.select("target_user").distinct()
            .join(users, edges["target_user"] == users["user_id"], "inner")
            .groupBy("gender").agg(F.count("*").alias("users"))
            .orderBy(F.desc("users")).show(6, truncate=False)
        )

        # 画像 CSV 若某行字段数异常，末列 crawl_time 会解析失败而变成 null。
        raw = spark.read.option("header", True).csv(
            os.path.join(spark_env.DATA_DIR, "COV-Weibo2.0", "user.csv")
        )
        total = raw.count()
        bad = raw.filter(F.col("crawl_time").cast("int").isNull()).count()
        print(f"\n[profile quality] 字段错位行 = {bad:,} / {total:,} ({bad / total:.4%})", flush=True)
        print("HOMOPHILY_DONE", flush=True)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
