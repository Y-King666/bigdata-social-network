"""把 SNAP soc-Pokec 的边表落成 Parquet。

原始文件是 gzip 压缩的 TSV（每行 src<TAB>dst）。gzip 不可切分，Spark 读取时
只能落在单一分区，因此先转成 Parquet，供后续所有分析步骤复用。
"""

import gzip
import os
import shutil
import sys
import time

from pyspark.sql.types import IntegerType, StructField, StructType

import spark_env

GZ_PATH = os.path.join(spark_env.DATA_DIR, "soc-pokec-relationships.txt.gz")
TXT_PATH = os.path.join(spark_env.DATA_DIR, "soc-pokec-relationships.txt")
PARQUET_PATH = os.path.join(spark_env.DATA_DIR, "edges_parquet")

EDGE_SCHEMA = StructType(
    [
        StructField("src", IntegerType(), False),
        StructField("dst", IntegerType(), False),
    ]
)


def gunzip() -> None:
    if os.path.exists(TXT_PATH):
        print("[gunzip] skip, already extracted")
        return
    t0 = time.time()
    with gzip.open(GZ_PATH, "rb") as fin, open(TXT_PATH, "wb") as fout:
        shutil.copyfileobj(fin, fout, length=1 << 22)
    print(f"[gunzip] {time.time() - t0:.1f}s -> {os.path.getsize(TXT_PATH):,} bytes")


def main() -> int:
    spark_env.setup_hadoop_home()
    if not os.path.exists(GZ_PATH):
        print(f"missing input: {GZ_PATH}")
        return 1

    gunzip()
    spark = spark_env.build_spark("01-prepare-data")
    try:
        t0 = time.time()
        edges = spark.read.option("sep", "\t").schema(EDGE_SCHEMA).csv(TXT_PATH)
        n_edges = edges.count()
        print(f"[read-tsv] {time.time() - t0:.1f}s  edges={n_edges:,}")

        t0 = time.time()
        n_nodes = edges.select("src").union(edges.select("dst")).distinct().count()
        print(f"[distinct-nodes] {time.time() - t0:.1f}s  nodes={n_nodes:,}")

        t0 = time.time()
        edges.write.mode("overwrite").parquet(PARQUET_PATH)
        print(f"[write-parquet] {time.time() - t0:.1f}s -> {PARQUET_PATH}")

        t0 = time.time()
        n_back = spark.read.parquet(PARQUET_PATH).count()
        print(f"[read-parquet] {time.time() - t0:.1f}s  edges={n_back:,}")

        print("PREPARE_DATA_DONE")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
