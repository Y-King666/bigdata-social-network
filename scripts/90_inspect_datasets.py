import os, glob
import pyarrow.parquet as pq
import spark_env

targets = [
    ("data", "cov_posts_parquet"), ("data", "cov_geo_parquet"), ("data", "cov_users_parquet"),
    ("data", "edges_parquet"), ("data", "repost_edges_parquet"), ("data", "repost_user_edges_parquet"),
    ("data", "topic_stats_parquet"), ("data", "topic_daily_parquet"),
    ("data", "geo_grid_parquet"), ("data", "geo_province_parquet"),
    ("data", "geo_province_daily_parquet"), ("data", "geo_daily_total_parquet"),
    ("output", "repost_communities.parquet"), ("output", "repost_node_metrics.parquet"),
    ("output", "cascade_stats.parquet"), ("output", "cascade_growth_parquet"),
    ("output", "sentiment_parquet"), ("output", "sentiment_daily_parquet"),
]
for root, name in targets:
    d = os.path.join(spark_env.PROJECT_ROOT, root, name)
    if not os.path.exists(d):
        print("%-34s MISSING" % name); continue
    files = glob.glob(os.path.join(d, "*.parquet")) or [d]
    md = pq.ParquetFile(files[0]).metadata
    sch = pq.ParquetFile(files[0]).schema_arrow
    tot_mb = sum(os.path.getsize(f) for f in files) / 1e6
    print("%-34s files=%-3d rows=%-12s %.1fMB" % (name, len(files), f"{md.num_rows:,}", tot_mb))
    print("    " + ", ".join("%s:%s" % (f.name, f.type) for f in sch))
