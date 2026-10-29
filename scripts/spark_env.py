"""所有分析脚本共用的 Spark 运行环境。

Windows 上没有独立安装 Hadoop，Spark 仍会经 winutils.exe 访问 FileSystem API，
所以必须在 JVM 启动前把 HADOOP_HOME 指向项目内置的 hadoop 目录。
"""

import os
import sys

from pyspark.sql import SparkSession

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
HADOOP_HOME = os.path.join(PROJECT_ROOT, "hadoop")


def setup_hadoop_home() -> None:
    """注册项目内置的 winutils，供 Spark 访问本地文件系统。"""
    os.environ["HADOOP_HOME"] = HADOOP_HOME
    os.environ["PATH"] = os.path.join(HADOOP_HOME, "bin") + os.pathsep + os.environ.get("PATH", "")


def setup_python_worker() -> None:
    """把 Spark worker 用的解释器钉死到当前虚拟环境。

    Windows 上 `python` 会命中应用商店的占位程序，worker 进程随之启动失败
    （报错为 "Timed out while waiting for the Python worker to connect back"）。
    """
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


def build_spark(app_name: str, driver_memory: str = "8g") -> SparkSession:
    """创建本机 local[*] 模式的 SparkSession。

    本地模式下 driver 与 executor 同处一个 JVM，故用 shuffle 分区数匹配核心数，
    避免默认的 200 分区在本机产生大量空任务。
    """
    setup_python_worker()
    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", driver_memory)
        .config("spark.sql.warehouse.dir", os.path.join(PROJECT_ROOT, "spark-warehouse"))
        .config("spark.local.dir", os.path.join(PROJECT_ROOT, "spark-tmp"))
        .config("spark.sql.shuffle.partitions", str(os.cpu_count() or 4))
        # Python worker 崩溃时默认只报 "worker exited unexpectedly"，
        # 打开 faulthandler 才能拿到真正的 Python 堆栈。
        .config("spark.python.worker.faulthandler.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
