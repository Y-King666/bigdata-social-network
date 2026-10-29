"""地理分布分析：坐标解析、热点网格与省份时序。

geo_info 字段是 "经度,纬度" 字符串，需要先拆成数值并剔除越界值。
省份维度来自用户画像表（推文表本身只有坐标，没有行政区划）。
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import spark_env
from pyspark.sql import functions as F

# 主要城市坐标，用于把热点网格标注成可读地名
CITIES = {
    "北京": (116.41, 39.90), "上海": (121.47, 31.23), "广州": (113.26, 23.13),
    "深圳": (114.06, 22.55), "武汉": (114.30, 30.59), "成都": (104.07, 30.67),
    "重庆": (106.55, 29.56), "杭州": (120.15, 30.27), "南京": (118.80, 32.06),
    "西安": (108.94, 34.34), "天津": (117.20, 39.13), "苏州": (120.58, 31.30),
    "郑州": (113.63, 34.75), "长沙": (112.94, 28.23), "沈阳": (123.43, 41.80),
    "青岛": (120.38, 36.07), "哈尔滨": (126.53, 45.80), "长春": (125.32, 43.82),
    "大连": (121.61, 38.91), "济南": (117.00, 36.65), "合肥": (117.28, 31.86),
    "福州": (119.30, 26.08), "厦门": (118.09, 24.48), "南昌": (115.89, 28.68),
    "昆明": (102.71, 25.05), "贵阳": (106.63, 26.65), "南宁": (108.32, 22.82),
    "海口": (110.20, 20.04), "兰州": (103.83, 36.06), "太原": (112.55, 37.87),
    "石家庄": (114.51, 38.04), "乌鲁木齐": (87.62, 43.82), "呼和浩特": (111.66, 40.84),
    "银川": (106.28, 38.49), "西宁": (101.78, 36.62), "拉萨": (91.14, 29.65),
    "香港": (114.17, 22.32), "澳门": (113.55, 22.20), "台北": (121.56, 25.03),
}


def nearest_city(lon, lat):
    """返回距离该坐标最近的城市名，用于给热点网格加可读标注。"""
    best, name = 1e18, ""
    for city, (clon, clat) in CITIES.items():
        # 等距圆柱近似，中低纬度误差可忽略
        d = ((lon - clon) * 0.85) ** 2 + (lat - clat) ** 2
        if d < best:
            best, name = d, city
    return name


def main():
    t0 = time.time()
    spark_env.setup_hadoop_home()
    spark = spark_env.build_spark("geo_analysis", driver_memory="8g")
    # 单表 4590 万行的聚合会把哈希表撑大：默认 20 个分区（等于核数）时
    # 每个任务要扛 230 万行，实测触发 AGGREGATE_OUT_OF_MEMORY，故提到 120。
    spark.conf.set("spark.sql.shuffle.partitions", "120")

    geo_dir = os.path.join(spark_env.DATA_DIR, "cov_geo_parquet")
    users_dir = os.path.join(spark_env.DATA_DIR, "cov_users_parquet")
    grid_dir = os.path.join(spark_env.DATA_DIR, "geo_grid_parquet")
    prov_dir = os.path.join(spark_env.DATA_DIR, "geo_prov_parquet")

    geo = spark.read.parquet(geo_dir).select(
        "user_id", "created_at", "geo_info", "repost_num"
    )
    total_rows = geo.count()
    print("[load] %s rows  (%.1fs)" % (f"{total_rows:,}", time.time() - t0), flush=True)

    # 拆经纬度并剔除越界值：geo_info 存在缺失与异常坐标
    parsed = (
        geo.withColumn("lon", F.split(F.col("geo_info"), ",").getItem(0).cast("double"))
        .withColumn("lat", F.split(F.col("geo_info"), ",").getItem(1).cast("double"))
        .filter(
            F.col("lon").isNotNull()
            & F.col("lat").isNotNull()
            & (F.col("lon").between(-180, 180))
            & (F.col("lat").between(-90, 90))
            & ~((F.col("lon") == 0) & (F.col("lat") == 0))
        )
        .select("user_id", "created_at", "repost_num", "lon", "lat")
    )
    n_valid = parsed.count()
    print(
        "[valid] %s / %s = %.2f%%"
        % (f"{n_valid:,}", f"{total_rows:,}", n_valid / total_rows * 100),
        flush=True,
    )

    # ---- 1. 0.25 度网格热点 ----
    grid = (
        parsed.withColumn("glon", F.round(F.col("lon") * 4) / 4)
        .withColumn("glat", F.round(F.col("lat") * 4) / 4)
        .groupBy("glon", "glat")
        .agg(
            F.count("*").alias("posts"),
            F.countDistinct("user_id").alias("users"),
            F.sum("repost_num").alias("reposts"),
        )
    )
    grid.write.mode("overwrite").parquet(grid_dir)

    print("")
    print("[top-25 热点网格]  城市 / 经度 / 纬度 / 推文数 / 用户数", flush=True)
    for r in grid.orderBy(F.desc("posts")).limit(25).collect():
        print(
            "  %-6s %8.2f %7.2f %12s %10s"
            % (
                nearest_city(r["glon"], r["glat"]),
                r["glon"],
                r["glat"],
                f"{r['posts']:,}",
                f"{r['users']:,}",
            ),
            flush=True,
        )

    # ---- 2. 省份维度（坐标无行政区划，借用用户画像的省份字段） ----
    profiles = (
        spark.read.parquet(users_dir)
        .select("user_id", "province")
        .filter(F.col("province").isNotNull() & (F.length("province") > 0))
        .dropDuplicates(["user_id"])
    )
    parsed.join(profiles, on="user_id", how="inner").write.mode("overwrite").parquet(
        prov_dir
    )

    prov = spark.read.parquet(prov_dir)
    by_prov = (
        prov.groupBy("province")
        .agg(
            F.count("*").alias("posts"),
            F.countDistinct("user_id").alias("users"),
            F.round(F.avg("repost_num"), 2).alias("avg_reposts"),
        )
        .withColumn("posts_per_user", F.round(F.col("posts") / F.col("users"), 2))
        .orderBy(F.desc("posts"))
    )
    by_prov.write.mode("overwrite").parquet(
        os.path.join(spark_env.DATA_DIR, "geo_province_parquet")
    )
    print("")
    print("[按省份推文量 top-15]", flush=True)
    by_prov.limit(15).show(15, truncate=False)

    # ---- 3. 重点省份的逐日时序 ----
    focus = ["湖北", "广东", "北京", "上海", "浙江", "海外"]
    daily = (
        prov.filter(F.col("province").isin(focus))
        .withColumn("day", F.to_date("created_at"))
        .groupBy("province", "day")
        .agg(F.count("*").alias("posts"))
        .orderBy("province", "day")
    )
    daily.write.mode("overwrite").parquet(
        os.path.join(spark_env.DATA_DIR, "geo_province_daily_parquet")
    )
    print("")
    print("[湖北推文量最高的 5 天]", flush=True)
    daily.filter(F.col("province") == "湖北").orderBy(F.desc("posts")).limit(5).show(
        5, truncate=False
    )

    # ---- 4. 境外占比（用网格汇总反推，避免再扫一遍原始表） ----
    cn = grid.filter(
        F.col("glon").between(73, 136) & F.col("glat").between(3, 54)
    ).agg(F.sum("posts").alias("posts"))
    cn_posts = cn.collect()[0]["posts"] or 0
    print("")
    print(
        "[coverage] 网格落在中国境内 %s / %s = %.2f%%"
        % (f"{cn_posts:,}", f"{n_valid:,}", cn_posts / n_valid * 100),
        flush=True,
    )

    spark.stop()
    print("")
    print("[done] 用时 %.1fs" % (time.time() - t0), flush=True)
    print("GEO_ANALYSIS_DONE", flush=True)


if __name__ == "__main__":
    main()
