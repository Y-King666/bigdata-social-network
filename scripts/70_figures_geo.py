"""生成地理分布分析图表，供分析页面复用。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.patheffects
import matplotlib.pyplot as plt
import pandas as pd
import spark_env

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150

FIG_DIR = os.path.join(spark_env.PROJECT_ROOT, "output", "figures")

# 城市 -> (经度, 纬度, 标注横向偏移, 纵向偏移)，偏移量用于避让相邻城市
LABEL_CITIES = {
    "上海": (121.47, 31.23, 10, -12),
    "北京": (116.41, 39.90, 10, 4),
    "广州": (113.26, 23.13, 12, -12),
    "深圳": (114.06, 22.55, 14, -26),
    "成都": (104.07, 30.57, -34, 6),
    "重庆": (106.55, 29.56, -20, -16),
    "杭州": (120.15, 30.28, 16, 4),
    "武汉": (114.30, 30.60, 10, 8),
    "西安": (108.94, 34.34, -34, 4),
    "南京": (118.80, 32.06, -6, 12),
    "郑州": (113.62, 34.75, 10, 10),
    "长沙": (112.94, 28.23, -34, 8),
}


def fig_hotspot():
    grid = pd.read_parquet(os.path.join(spark_env.DATA_DIR, "geo_grid_parquet"))
    grid = grid[grid["glon"].between(73, 136) & grid["glat"].between(3, 54)]
    grid = grid[grid["posts"] >= 500]

    fig, ax = plt.subplots(figsize=(9, 7))
    sizes = grid["posts"] / grid["posts"].max() * 900 + 4
    sc = ax.scatter(
        grid["glon"], grid["glat"], s=sizes, c=grid["posts"],
        cmap="YlOrRd", alpha=0.75, edgecolors="none",
        norm=matplotlib.colors.LogNorm(),
    )
    halo = [matplotlib.patheffects.withStroke(linewidth=2.6, foreground="white")]
    for name, (lon, lat, dx, dy) in LABEL_CITIES.items():
        ax.annotate(
            name, (lon, lat), xytext=(dx, dy), textcoords="offset points",
            fontsize=9, color="#1a3d6d", path_effects=halo,
        )
    ax.set_xlim(73, 136)
    ax.set_ylim(3, 54)
    ax.set_aspect(1 / 0.82)
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_title("带地理标签微博的空间热点分布（0.25° 网格，发帖量 ≥ 500）")
    fig.colorbar(sc, ax=ax, label="网格内推文数（对数色标）", shrink=0.8)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig_geo_hotspot.png")
    fig.savefig(out)
    plt.close(fig)
    print("[fig] " + out, flush=True)


def fig_province():
    prov = pd.read_parquet(os.path.join(spark_env.DATA_DIR, "geo_province_parquet"))
    prov = prov.head(15).iloc[::-1]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(prov["province"], prov["posts"] / 1e4, color="#c0392b", alpha=0.85)
    for y, (v, r) in enumerate(zip(prov["posts"] / 1e4, prov["avg_reposts"])):
        ax.text(v + 5, y, "转发均值 %.2f" % r, va="center", fontsize=8, color="#444")
    ax.set_xlabel("推文数（万条）")
    ax.set_xlim(0, prov["posts"].max() / 1e4 * 1.25)
    ax.set_title("各省份推文量（按用户资料省份归属）")
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig_geo_province.png")
    fig.savefig(out)
    plt.close(fig)
    print("[fig] " + out, flush=True)


def fig_share():
    share = pd.read_csv(os.path.join(spark_env.DATA_DIR, "geo_share_daily.csv"))
    share["day"] = pd.to_datetime(share["day"])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for p, g in share.groupby("province"):
        g = g.sort_values("day")
        ax.plot(g["day"], g["share"] * 100, linewidth=1.4, label=p)
    ax.axvspan(pd.Timestamp("2020-01-23"), pd.Timestamp("2020-04-08"),
               color="#f1c40f", alpha=0.15)
    ax.text(pd.Timestamp("2020-02-20"), 11.4, "武汉封城期", fontsize=9, color="#8a6d00")
    ax.set_ylabel("占当日全部带坐标推文的比例（%）")
    ax.set_title("省份发言占比（归一化后，已剥离采集量整体增长）")
    ax.legend(ncol=3, fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig_geo_share.png")
    fig.savefig(out)
    plt.close(fig)
    print("[fig] " + out, flush=True)


def fig_daily_total():
    total = pd.read_parquet(os.path.join(spark_env.DATA_DIR, "geo_daily_total_parquet"))
    total = total.sort_values("day")
    total["day"] = pd.to_datetime(total["day"])

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(total["day"], total["posts"] / 1e4, color="#2c3e50", linewidth=1.5)
    ax.set_ylabel("每日推文数（万条）")
    ax.set_title("带地理标签推文的逐日总量（数据集覆盖期 2019-12-01 ~ 2020-04-30）")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig_geo_daily_total.png")
    fig.savefig(out)
    plt.close(fig)
    print("[fig] " + out, flush=True)


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    fig_hotspot()
    fig_province()
    fig_share()
    fig_daily_total()
    print("GEO_FIGURES_DONE", flush=True)


if __name__ == "__main__":
    main()
