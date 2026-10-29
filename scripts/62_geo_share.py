"""省份占比归一化：把省份逐日绝对量换算为占当日全量的比例，剥离采集节奏带来的整体增长。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import spark_env


def main():
    prov_daily = pd.read_parquet(
        os.path.join(spark_env.DATA_DIR, "geo_province_daily_parquet")
    )
    total = pd.read_parquet(os.path.join(spark_env.DATA_DIR, "geo_daily_total_parquet"))
    total = total.rename(columns={"posts": "total"})

    df = prov_daily.merge(total, on="day", how="left")
    df["share"] = df["posts"] / df["total"]
    df = df.sort_values(["province", "day"])
    df.to_csv(
        os.path.join(spark_env.DATA_DIR, "geo_share_daily.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    print("[全量逐日] 首日 %s %s 末日 %s %s 最高 %s %s" % (
        df["day"].min(), f"{df[df['day'] == df['day'].min()]['total'].iat[0]:,}",
        df["day"].max(), f"{df[df['day'] == df['day'].max()]['total'].iat[0]:,}",
        df.loc[df["total"].idxmax(), "day"], f"{df['total'].max():,}",
    ), flush=True)

    for p in df["province"].unique():
        sub = df[df["province"] == p]
        first7 = sub.head(7)["share"].mean()
        last7 = sub.tail(7)["share"].mean()
        print("")
        print("== %s == 前期占比 %.4f  末期占比 %.4f" % (p, first7, last7), flush=True)
        top = sub.nlargest(5, "share")[["day", "posts", "share"]]
        for _, r in top.iterrows():
            print("   占比最高 %s  %8s  %.4f" % (r["day"], f"{r['posts']:,}", r["share"]), flush=True)

    print("")
    print("GEO_SHARE_DONE", flush=True)


if __name__ == "__main__":
    main()
