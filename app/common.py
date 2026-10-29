"""界面共用的路径常量、数据加载与绘图样式。"""

import glob
import os

import pandas as pd
import plotly.graph_objects as go
import pyarrow.parquet as pq
import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
DATA = os.path.join(PROJECT_ROOT, "data")
OUTPUT = os.path.join(PROJECT_ROOT, "output")

PALETTE = {
    "primary": "#C0392B",
    "secondary": "#1F3A5F",
    "accent": "#E8A33D",
    "muted": "#6B7280",
    "positive": "#2E8B57",
    "negative": "#C0392B",
    "neutral": "#9AA5B1",
}
SERIES = ["#C0392B", "#1F3A5F", "#E8A33D", "#2E8B57", "#7D5BA6", "#0E8B8B"]


def parquet_row_count(path):
    """只读 Parquet 元数据统计行数，避免为展示规模去扫全表。"""
    files = glob.glob(os.path.join(path, "*.parquet"))
    return sum(pq.ParquetFile(f).metadata.num_rows for f in files)


@st.cache_data(show_spinner=False)
def dataset_inventory():
    names = {
        "推文原文": ("data", "cov_posts_parquet"),
        "带坐标推文": ("data", "cov_geo_parquet"),
        "用户画像": ("data", "cov_users_parquet"),
        "转发明细边": ("data", "repost_edges_parquet"),
        "用户级转发边": ("data", "repost_user_edges_parquet"),
        "话题统计": ("data", "topic_stats_parquet"),
        "情感标注": ("output", "sentiment_parquet"),
        "级联统计": ("output", "cascade_stats.parquet"),
    }
    rows = []
    for label, (root, name) in names.items():
        path = os.path.join(PROJECT_ROOT, root, name)
        files = glob.glob(os.path.join(path, "*.parquet"))
        size = sum(os.path.getsize(f) for f in files) / 1e6
        rows.append({"数据集": label, "记录数": parquet_row_count(path), "体积MB": round(size, 1)})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_grid():
    return pd.read_parquet(os.path.join(DATA, "geo_grid_parquet"))


@st.cache_data(show_spinner=False)
def load_province():
    return pd.read_parquet(os.path.join(DATA, "geo_province_parquet"))


@st.cache_data(show_spinner=False)
def load_share():
    df = pd.read_csv(os.path.join(DATA, "geo_share_daily.csv"))
    df["day"] = pd.to_datetime(df["day"])
    return df


@st.cache_data(show_spinner=False)
def load_daily_total():
    df = pd.read_parquet(os.path.join(DATA, "geo_daily_total_parquet"))
    df["day"] = pd.to_datetime(df["day"])
    return df.sort_values("day")


@st.cache_data(show_spinner=False)
def load_topic_stats():
    return pd.read_parquet(os.path.join(DATA, "topic_stats_parquet"))


@st.cache_data(show_spinner=False)
def load_topic_daily(topic):
    return pd.read_parquet(
        os.path.join(DATA, "topic_daily_parquet"), filters=[("topic", "==", topic)]
    ).sort_values("day")


@st.cache_data(show_spinner=False)
def load_cascade_stats():
    return pd.read_parquet(os.path.join(OUTPUT, "cascade_stats.parquet"))


@st.cache_data(show_spinner=False)
def load_cascade_growth():
    return pd.read_parquet(os.path.join(OUTPUT, "cascade_growth_parquet"))


@st.cache_data(show_spinner=False)
def load_sentiment_daily():
    df = pd.read_parquet(os.path.join(OUTPUT, "sentiment_daily_parquet"))
    df["day"] = pd.to_datetime(df["day"])
    return df.sort_values("day")


@st.cache_data(show_spinner=False)
def load_hotsearch_compare():
    return pd.read_csv(os.path.join(OUTPUT, "hotsearch_vs_topic.csv"))


@st.cache_data(show_spinner=False)
def load_hotsearch_raw():
    files = sorted(glob.glob(os.path.join(DATA, "weibo", "hotsearch_*.csv")))
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


@st.cache_data(show_spinner=False)
def load_graph_users():
    return pd.read_parquet(os.path.join(OUTPUT, "ui_graph_users_parquet"))


@st.cache_data(show_spinner=False)
def load_user_edges():
    return pd.read_parquet(os.path.join(DATA, "repost_user_edges_parquet"))


@st.cache_data(show_spinner=False)
def lookup_profile(user_id):
    """按 user_id 查询画像，依赖 ui_user_index_parquet 的范围分区做行组裁剪。"""
    table = pq.read_table(
        os.path.join(OUTPUT, "ui_user_index_parquet"), filters=[("user_id", "==", user_id)]
    )
    return table.to_pandas()


def style_fig(fig, height=420, title=None, legend=True):
    fig.update_layout(
        height=height,
        title=title,
        font=dict(family="Microsoft YaHei, SimHei", size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=30, t=60 if title else 20, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0) if legend else None,
        hoverlabel=dict(font_family="Microsoft YaHei"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)")
    return fig


def kpi_row(items):
    """一行指标卡片：items 为 (标题, 数值, 说明) 三元组列表。"""
    cols = st.columns(len(items))
    for col, (label, value, hint) in zip(cols, items):
        col.markdown(
            '<div style="border-left:3px solid %s;padding:2px 0 2px 12px">'
            '<div style="font-size:13px;color:%s">%s</div>'
            '<div style="font-size:26px;font-weight:700;color:%s;line-height:1.3">%s</div>'
            '<div style="font-size:12px;color:%s">%s</div></div>'
            % (PALETTE["primary"], PALETTE["muted"], label, PALETTE["secondary"], value,
               PALETTE["muted"], hint),
            unsafe_allow_html=True,
        )


def human(n):
    if n >= 1e8:
        return "%.2f 亿" % (n / 1e8)
    if n >= 1e4:
        return "%.1f 万" % (n / 1e4)
    return "{:,}".format(int(n))


CSS = (
    "<style>"
    ".block-container{padding-top:2.4rem;padding-bottom:2rem}"
    "h1{font-size:27px!important}"
    "h2{font-size:20px!important;margin-top:1.6rem}"
    "h3{font-size:17px!important}"
    'section[data-testid="stSidebar"]{background:#F5F7FA;border-right:1px solid #E3E8EF}'
    '[data-testid="stMetricValue"]{font-size:24px}'
    "</style>"
)


def page_header(title, subtitle=None):
    st.markdown(
        '<div style="border-bottom:2px solid %s;padding-bottom:10px;margin-bottom:8px">'
        '<span style="font-size:27px;font-weight:700;color:%s">%s</span></div>'
        % (PALETTE["primary"], PALETTE["secondary"], title),
        unsafe_allow_html=True,
    )
    if subtitle:
        st.caption(subtitle)


def section(title, note=None):
    st.markdown(
        '<div style="margin:22px 0 4px 0"><span style="font-size:18px;font-weight:600;color:%s">%s</span>'
        '%s</div>'
        % (PALETTE["secondary"], title,
           '<span style="font-size:13px;color:%s;margin-left:10px">%s</span>'
           % (PALETTE["muted"], note) if note else ""),
        unsafe_allow_html=True,
    )
