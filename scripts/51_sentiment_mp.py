"""多进程跑全量情感打分。

这一步的算力全在 Python 侧，Spark 的 Python worker 在 20 进程并发时会被系统
静默杀掉（内存压力）。改用 multiprocessing 自行管理进程池，按 Parquet 行组
切分任务，逐块落盘。
"""

import glob
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import spark_env  # noqa: E402

POSTS = os.path.join(spark_env.DATA_DIR, "cov_posts_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output", "sentiment_parquet")

OUT_SCHEMA = pa.schema(
    [
        ("_id", pa.string()),
        ("user_id", pa.string()),
        ("created_at", pa.string()),
        ("repost_num", pa.int32()),
        ("pos", pa.float32()),
        ("neg", pa.float32()),
    ]
)


def score_chunk(task: tuple) -> tuple:
    """任务粒度是一个 Parquet 行组，避免进程间再传大对象。"""
    part_path, row_group, out_path = task
    import sentiment_lexicon

    table = pq.ParquetFile(part_path).read_row_group(
        row_group, columns=["_id", "user_id", "created_at", "repost_num", "content"]
    )
    ids = table["_id"].to_pylist()
    users = table["user_id"].to_pylist()
    times = table["created_at"].to_pylist()
    reposts = table["repost_num"].to_pylist()
    contents = table["content"].to_pylist()

    pos_list, neg_list = [], []
    for text in contents:
        p, n = sentiment_lexicon.score(text or "")
        pos_list.append(p)
        neg_list.append(n)

    out = pa.table(
        {
            "_id": ids,
            "user_id": users,
            "created_at": times,
            "repost_num": repost_int(reposts),
            "pos": pa.array(pos_list, type=pa.float32()),
            "neg": pa.array(neg_list, type=pa.float32()),
        },
        schema=OUT_SCHEMA,
    )
    pq.write_table(out, out_path, compression="snappy")
    return (len(ids), out_path)


def repost_int(values):
    return pa.array([v if v is not None else 0 for v in values], type=pa.int32())


def main() -> int:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    os.makedirs(OUT_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(OUT_DIR, "*.parquet")):
        os.remove(old)

    tasks = []
    for part in sorted(glob.glob(os.path.join(POSTS, "part-*.parquet"))):
        n_groups = pq.ParquetFile(part).num_row_groups
        stem = os.path.splitext(os.path.basename(part))[0]
        for rg in range(n_groups):
            tasks.append((part, rg, os.path.join(OUT_DIR, f"{stem}-rg{rg:03d}.parquet")))
    print(f"[tasks] {len(tasks)} 个行组, 并发 {workers}", flush=True)

    total = 0
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(score_chunk, t): t for t in tasks}
        for done, fut in enumerate(as_completed(futures), 1):
            n, path = fut.result()
            total += n
            elapsed = time.time() - t0
            print(f"[{done}/{len(tasks)}] +{n:,}  累计 {total:,}  "
                  f"({total / elapsed:,.0f} rows/s, 已用 {elapsed / 60:.1f} min)", flush=True)

    print(f"[done] {total:,} 行, 用时 {(time.time() - t0) / 60:.1f} min", flush=True)
    print("SENTIMENT_MP_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
