"""验证推文与用户画像能否按 user_id 关联。

用户池只存了哈希后的 user_id，必须确认它与推文里的 user_id 同源，
否则 2000 万条画像数据在系统里用不上。
"""

import os
import sys
import time

from pyspark.sql import functions as F

import spark_env

POSTS = os.path.join(spark_env.DATA_DIR, "cov_posts_parquet")
USERS = os.path.join(spark_env.DATA_DIR, "cov_users_parquet")


def main() -> int:
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("24-join-check", driver_memory="10g")
    spark.conf.set("spark.sql.shuffle.partitions", "60")
    try:
        post_users = (
            spark.read.parquet(POSTS).select("user_id").distinct()
        )
        profile_users = spark.read.parquet(USERS).select("user_id").distinct()

        t0 = time.time()
        n_post = post_users.count()
        n_prof = profile_users.count()
        print(f"[distinct] posts={n_post:,}  profiles={n_prof:,}  ({time.time() - t0:.1f}s)", flush=True)

        t0 = time.time()
        matched = post_users.join(profile_users, on="user_id", how="left_semi").count()
        print(f"[matched] {matched:,}  ({time.time() - t0:.1f}s)", flush=True)
        print(f"[coverage] 推文用户被画像覆盖: {matched / n_post:.2%}", flush=True)

        sample = (
            spark.read.parquet(POSTS).select("user_id", "content").limit(5)
            .join(spark.read.parquet(USERS), on="user_id", how="left")
        )
        print("[sample joined rows]", flush=True)
        sample.select("user_id", "gender", "province", "city", "fans_num").show(truncate=False)
    finally:
        spark.stop()
    print("JOIN_CHECK_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
