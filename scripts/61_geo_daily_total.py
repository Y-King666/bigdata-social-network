"""带地理标签推文的逐日总量，用于判断省份时序是否受采集节奏影响。"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import spark_env
from pyspark.sql import functions as F


def main():
    t0 = time.time()
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("geo_daily", driver_memory="6g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")

    daily = (
        spark.read.parquet(os.path.join(spark_env.DATA_DIR, "cov_geo_parquet"))
        .select(F.to_date("created_at").alias("day"))
        .groupBy("day")
        .count()
        .withColumnRenamed("count", "posts")
        .orderBy("day")
    )
    daily.write.mode("overwrite").parquet(
        os.path.join(spark_env.DATA_DIR, "geo_daily_total_parquet")
    )
    rows = daily.collect()
    print("[逐日总量] 天数 %d, 合计 %s" % (len(rows), f"{sum(r['posts'] for r in rows):,}"), flush=True)
    print("最高 5 天:", flush=True)
    for r in sorted(rows, key=lambda x: -x["posts"])[:5]:
        print("  %s  %s" % (r["day"], f"{r['posts']:,}"), flush=True)
    print("最低 5 天:", flush=True)
    for r in sorted(rows, key=lambda x: x["posts"])[:5]:
        print("  %s  %s" % (r["day"], f"{r['posts']:,}"), flush=True)
    spark.stop()
    print("[done] %.1fs" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
