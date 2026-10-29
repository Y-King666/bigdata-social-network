"""Spark 环境冒烟测试：验证 SparkSession 能否启动、本地文件能否读写。"""

import os
import sys

import spark_env


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("00-smoke-test", driver_memory="4g")

    print("SPARK_VERSION:", spark.version)
    print("JAVA_VERSION:", spark.sparkContext._jvm.System.getProperty("java.version"))
    print("DEFAULT_PARALLELISM:", spark.sparkContext.defaultParallelism)

    df = spark.range(0, 1000)
    print("COUNT:", df.count())

    out = os.path.join(spark_env.PROJECT_ROOT, "_smoke_out")
    df.write.mode("overwrite").parquet(out)
    print("PARQUET_WRITE_OK:", os.path.isdir(out))
    print("PARQUET_READ_BACK:", spark.read.parquet(out).count())

    spark.stop()
    print("SMOKE_TEST_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
