"""导出交互界面直接读取的服务层表。

界面按 user_id 做即席查询，而原始用户表未按 user_id 排序，PyArrow 无法用
行组统计裁剪数据，每次查询都要扫全表。这里重排一次，让查询只读命中的分片。
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import spark_env

USER_COLS = ["user_id", "gender", "province", "city", "birthday", "fans_num", "vip_level"]


def export_user_index(spark):
    """全量用户画像按 user_id 范围分区重排，供界面做单用户查询。"""
    users = spark.read.parquet(
        os.path.join(spark_env.DATA_DIR, "cov_users_parquet")
    ).select(*USER_COLS)
    out = os.path.join(spark_env.PROJECT_ROOT, "output", "ui_user_index_parquet")
    (
        users.repartitionByRange(40, "user_id")
        .sortWithinPartitions("user_id")
        .write.mode("overwrite")
        .parquet(out)
    )
    print("[user_index] -> %s" % out, flush=True)


def export_graph_users(spark):
    """转发关系图的节点、社区划分与用户画像合并成一张宽表。"""
    root = spark_env.PROJECT_ROOT
    metrics = spark.read.parquet(os.path.join(root, "output", "repost_node_metrics.parquet"))
    comm = spark.read.parquet(os.path.join(root, "output", "repost_communities.parquet"))
    prof = spark.read.parquet(
        os.path.join(spark_env.DATA_DIR, "cov_users_parquet")
    ).select(*USER_COLS)
    out = os.path.join(root, "output", "ui_graph_users_parquet")
    (
        metrics.join(comm, on="user_id", how="left")
        .join(prof, on="user_id", how="left")
        .write.mode("overwrite")
        .parquet(out)
    )
    print("[graph_users] -> %s" % out, flush=True)


def main():
    t0 = time.time()
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("export_ui_tables", driver_memory="7g")
    spark.conf.set("spark.sql.shuffle.partitions", "120")
    export_user_index(spark)
    export_graph_users(spark)
    spark.stop()
    print("[done] %.1fs" % (time.time() - t0), flush=True)
    print("EXPORT_UI_DONE", flush=True)


if __name__ == "__main__":
    main()
