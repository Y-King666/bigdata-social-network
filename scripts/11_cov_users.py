"""Weibo-COV 用户画像（2000 万行）的规模核查。

这份数据只有属性、没有关系边，先确认它能否被 Spark 正常解析，
并统计性别、地域、年龄、粉丝数分布，同时落成 Parquet 供应用层查询。
"""

import os
import sys
import time

from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

import spark_env

COV_PATH = os.path.join(spark_env.DATA_DIR, "COV-Weibo2.0", "user.csv")
OUT_DIR = os.path.join(spark_env.DATA_DIR, "cov_users_parquet")

USER_SCHEMA = StructType(
    [
        StructField("user_id", StringType(), False),
        StructField("gender", StringType(), True),
        StructField("province", StringType(), True),
        StructField("city", StringType(), True),
        StructField("birthday", StringType(), True),
        StructField("fans_num", IntegerType(), True),
        StructField("vip_level", StringType(), True),
        StructField("crawl_time", IntegerType(), True),
    ]
)


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("11-cov-users")
    try:
        t0 = time.time()
        users = (
            spark.read.schema(USER_SCHEMA)
            .option("header", True)
            .option("multiLine", False)
            .csv(COV_PATH)
        )
        n = users.count()
        print(f"[load] {time.time() - t0:.1f}s  rows={n:,}", flush=True)

        print("[gender]", flush=True)
        users.groupBy("gender").count().orderBy(F.desc("count")).show(10, truncate=False)

        print("[top-15 province]", flush=True)
        users.groupBy("province").count().orderBy(F.desc("count")).show(15, truncate=False)

        print("[fans_num]", flush=True)
        users.agg(
            F.min("fans_num"),
            F.max("fans_num"),
            F.avg("fans_num"),
            F.expr("percentile_approx(fans_num, array(0.5, 0.9, 0.99))"),
        ).show(truncate=False)

        print("[fans_num == 0]", flush=True)
        users.filter(F.col("fans_num") <= 0).count()

        # birthday 里混有 0001-00-00 这类占位值，需要先剔除再算年龄。
        birth_year = F.when(
            F.col("birthday").rlike(r"^(19|20)\d{2}-\d{2}-\d{2}$"),
            F.substring("birthday", 1, 4).cast("int"),
        )
        valid = users.filter(birth_year.isNotNull())
        print(f"[birthday] 有效生日 {valid.count():,} / {n:,}", flush=True)
        valid.select(birth_year.alias("by")).groupBy("by").count().orderBy("by").show(60, truncate=False)

        t0 = time.time()
        users.write.mode("overwrite").parquet(OUT_DIR)
        print(f"[write-parquet] {time.time() - t0:.1f}s -> {OUT_DIR}", flush=True)
        print("COV_USERS_DONE")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
