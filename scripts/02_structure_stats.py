"""soc-Pokec 的基础结构指标。

Pokec 的好友关系是有向的，因此出度刻画"关注了多少人"，
入度刻画"被多少人关注"，后者才是社交影响力的直接代理。
"""

import os
import sys
import time

from pyspark.sql import functions as F

import spark_env

PARQUET_PATH = os.path.join(spark_env.DATA_DIR, "edges_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")


def degree_histogram(edges, key: str, alias: str):
    """把每个节点的度数聚合成 "度数 -> 节点数" 的直方图。"""
    degrees = edges.groupBy(key).agg(F.count("*").alias(alias))
    hist = degrees.groupBy(alias).agg(F.count("*").alias("node_count")).orderBy(alias)
    return degrees, hist


def summarize(name: str, degrees, alias: str) -> None:
    t0 = time.time()
    row = degrees.agg(
        F.count("*").alias("nodes"),
        F.sum(alias).alias("total"),
        F.max(alias).alias("max"),
        F.avg(alias).alias("mean"),
        F.expr(f"percentile_approx({alias}, 0.5)").alias("median"),
        F.expr(f"sum(case when {alias} = 1 then 1 else 0 end)").alias("deg_one"),
    ).first()
    frac_one = row["deg_one"] / row["nodes"]
    print(
        f"[{name}] {time.time() - t0:.1f}s  nodes={row['nodes']:,}  max={row['max']:,}  "
        f"mean={row['mean']:.2f}  median={row['median']}  degree==1: {frac_one:.1%}"
    )


def main() -> int:
    spark_env.setup_hadoop_home()
    os.makedirs(OUT_DIR, exist_ok=True)
    spark = spark_env.build_spark("02-structure-stats")
    try:
        edges = spark.read.parquet(PARQUET_PATH)

        t0 = time.time()
        n_edges = edges.count()
        n_nodes = edges.select("src").union(edges.select("dst")).distinct().count()
        density = n_edges / (n_nodes * (n_nodes - 1))
        print(
            f"[graph] {time.time() - t0:.1f}s  edges={n_edges:,}  nodes={n_nodes:,}  "
            f"avg_out_degree={n_edges / n_nodes:.2f}  density={density:.3e}"
        )

        out_deg, out_hist = degree_histogram(edges, "src", "out_degree")
        in_deg, in_hist = degree_histogram(edges, "dst", "in_degree")
        summarize("out-degree", out_deg, "out_degree")
        summarize("in-degree", in_deg, "in_degree")

        print("[top-10 most followed nodes]")
        for r in in_deg.orderBy(F.desc("in_degree")).limit(10).collect():
            print(f"   node {r['dst']:>9,}  followers={r['in_degree']:,}")

        t0 = time.time()
        out_hist.coalesce(1).write.mode("overwrite").option("header", True).csv(
            os.path.join(OUT_DIR, "out_degree_hist")
        )
        in_hist.coalesce(1).write.mode("overwrite").option("header", True).csv(
            os.path.join(OUT_DIR, "in_degree_hist")
        )
        print(f"[export] {time.time() - t0:.1f}s -> {OUT_DIR}")

        print("STRUCTURE_STATS_DONE")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
