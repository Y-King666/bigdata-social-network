"""Dashboard 数据路径；与 Streamlit 的 app/common.py 解耦。"""

import os

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(DASHBOARD_DIR)
DATA = os.path.join(PROJECT_ROOT, "data")
OUTPUT = os.path.join(PROJECT_ROOT, "output")
STREAM = os.path.join(PROJECT_ROOT, "stream")
WEB_DIR = os.path.join(DASHBOARD_DIR, "web")

SENTIMENT_DAILY = os.path.join(OUTPUT, "sentiment_daily_parquet")
GEO_GRID = os.path.join(DATA, "geo_grid_parquet")
GEO_PROVINCE = os.path.join(DATA, "geo_province_parquet")
GEO_SHARE = os.path.join(DATA, "geo_share_daily.csv")
TOPIC_STATS = os.path.join(DATA, "topic_stats_parquet")
TOPIC_DAILY = os.path.join(DATA, "topic_daily_parquet")
CASCADE_STATS = os.path.join(OUTPUT, "cascade_stats.parquet")
CASCADE_GROWTH = os.path.join(OUTPUT, "cascade_growth_parquet")
HOTSEARCH_COMPARE = os.path.join(OUTPUT, "hotsearch_vs_topic.csv")
SENTIMENT_POLARITY = os.path.join(OUTPUT, "sentiment_by_polarity.csv")
SENTIMENT_BUCKETS = os.path.join(OUTPUT, "sentiment_repost_buckets.csv")
GRAPH_USERS = os.path.join(OUTPUT, "ui_graph_users_parquet")
USER_INDEX = os.path.join(OUTPUT, "ui_user_index_parquet")
USER_EDGES = os.path.join(DATA, "repost_user_edges_parquet")

INVENTORY = [
    ("推文原文", os.path.join(DATA, "cov_posts_parquet")),
    ("带坐标推文", os.path.join(DATA, "cov_geo_parquet")),
    ("用户画像", os.path.join(DATA, "cov_users_parquet")),
    ("转发明细边", os.path.join(DATA, "repost_edges_parquet")),
    ("用户级转发边", os.path.join(DATA, "repost_user_edges_parquet")),
    ("话题统计", os.path.join(DATA, "topic_stats_parquet")),
    ("情感标注", os.path.join(OUTPUT, "sentiment_parquet")),
    ("级联统计", os.path.join(OUTPUT, "cascade_stats.parquet")),
]
