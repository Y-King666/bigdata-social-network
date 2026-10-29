"""核查从公开仓库获取的微博数据。

三份数据来自不同研究者，字段含义和时间范围均不一致。
脚本用于检查各自规模、字段完整度与关联条件。
"""

import glob
import os
import re
import sys

import pandas as pd

import spark_env

WEIBO_DIR = os.path.join(spark_env.DATA_DIR, "weibo")
POSTS_PATH = os.path.join(WEIBO_DIR, "weibo_posts.csv")
USERS_PATH = os.path.join(WEIBO_DIR, "weibo_users.csv")
HASHTAG_RE = re.compile(r"#([^#\[\]]{1,30})#")


def read_csv(path: str) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            print(f"  ({os.path.basename(path)} not {enc}, retrying)")
    raise RuntimeError(f"cannot decode {path}")


def describe_posts() -> pd.DataFrame:
    posts = read_csv(POSTS_PATH)
    print("=== weibo_posts.csv ===", flush=True)
    print("shape:", posts.shape)
    print("columns:", list(posts.columns))
    print("created_at:", posts["created_at"].min(), "->", posts["created_at"].max())
    print("distinct users:", posts["user_id"].nunique())

    content = posts["content"].fillna("")
    has_tag = content.str.contains("#")
    print(f"posts containing '#': {has_tag.mean():.1%}")
    tags = content.str.findall(HASHTAG_RE)
    print("posts with a well-formed #topic#:", tags.str.len().gt(0).mean())
    print("top-10 hashtags:")
    for tag, n in tags.explode().dropna().value_counts().head(10).items():
        print(f"   {n:>7,}  {tag}")
    return posts


def describe_users(posts: pd.DataFrame) -> pd.DataFrame:
    users = read_csv(USERS_PATH)
    print("\n=== weibo_users.csv ===", flush=True)
    print("shape:", users.shape)
    print("columns:", list(users.columns))
    fill = (users.notna().mean().sort_values(ascending=False) * 100).round(1)
    print("fill rate (%):")
    for col, pct in fill.items():
        print(f"   {col:<22} {pct:>5.1f}")

    id_col = "_id" if "_id" in users.columns else users.columns[1]
    post_users = set(posts["user_id"].dropna().astype("int64"))
    table_users = set(pd.to_numeric(users[id_col], errors="coerce").dropna().astype("int64"))
    overlap = post_users & table_users
    print(f"\n=== 关联性 ===")
    print(f"posts 中的用户数      : {len(post_users):,}")
    print(f"users 表中的用户数    : {len(table_users):,}")
    print(f"两者交集             : {len(overlap):,}")
    if post_users:
        print(f"posts 用户被画像覆盖  : {len(overlap) / len(post_users):.1%}")
    return users


def describe_hotsearch() -> None:
    files = sorted(glob.glob(os.path.join(WEIBO_DIR, "hotsearch_*.csv")))
    frames = [read_csv(f) for f in files]
    hs = pd.concat(frames, ignore_index=True)
    print(f"\n=== 热搜榜（{len(files)} 个文件） ===", flush=True)
    print("shape:", hs.shape)
    print("columns:", list(hs.columns))
    print("时间范围:", hs["时间"].min(), "->", hs["时间"].max())
    print("distinct 关键词:", hs["关键词"].nunique())
    print("热搜条目示例热度统计:")
    print(hs["热度"].describe().round(0).to_string())
    print("特征标签分布:")
    print(hs["特征"].fillna("(空)").value_counts().to_string())


def main() -> int:
    posts = describe_posts()
    describe_users(posts)
    describe_hotsearch()
    print("\nWEIBO_OVERVIEW_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
