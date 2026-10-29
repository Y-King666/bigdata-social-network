"""核心图算法：社区发现与影响力排序。

先用 igraph 的 C 实现复用 03 产出的 CSR 图，验证这两个模块在
3062 万边规模下的耗时与内存；同时把结果落盘供应用层查询。
"""

import os
import sys
import time

import igraph as ig
import numpy as np
import psutil
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from scipy.sparse import load_npz, triu

import spark_env

OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")
GRAPH_PATH = os.path.join(OUT_DIR, "graph_undirected.npz")
PARQUET_PATH = os.path.join(spark_env.DATA_DIR, "edges_parquet")
RESULT_PATH = os.path.join(OUT_DIR, "node_metrics.parquet")


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / (1024 * 1024)


def load_igraph() -> ig.Graph:
    """CSR 中每条边存了两个方向，取上三角还原成无向图，避免重复计边。"""
    csr = load_npz(GRAPH_PATH)
    upper = triu(csr, k=1).tocoo()
    edges = np.column_stack([upper.row, upper.col]).astype(np.int32)
    return ig.Graph(n=int(csr.shape[0]), edges=edges, directed=False)


def rank_report(name: str, scores: np.ndarray, top_ids: np.ndarray, in_degree: np.ndarray) -> None:
    top = np.argsort(scores)[::-1][:10]
    print(f"[{name} top-10]")
    print("     node       score    followers   rank_by_followers")
    order_by_followers = np.argsort(in_degree)[::-1]
    follower_rank = np.empty_like(order_by_followers)
    follower_rank[order_by_followers] = np.arange(len(order_by_followers))
    for node in top:
        print(f"  {node:>9,}  {scores[node]:>10.6f}  {in_degree[node]:>10,}  {follower_rank[node] + 1:>10,}")


def main() -> int:
    print(f"[rss] start {rss_mb():.0f} MB")

    t0 = time.time()
    g = load_igraph()
    print(f"[build-igraph] {time.time() - t0:.1f}s  v={g.vcount():,}  e={g.ecount():,}  rss={rss_mb():.0f} MB")

    t0 = time.time()
    comps = g.connected_components()
    print(f"[components] {time.time() - t0:.1f}s  count={len(comps):,}  giant={comps.giant().vcount():,}")

    # 先在小规模诱导子图上试跑，用耗时曲线判断全图是否可接受。
    for size in (100_000, 400_000):
        sub = g.induced_subgraph(range(size))
        t0 = time.time()
        sub_result = sub.community_multilevel()
        print(
            f"[probe louvain] n={size:,}  e={sub.ecount():,}  {time.time() - t0:.1f}s  "
            f"communities={len(sub_result):,}",
            flush=True,
        )

    t0 = time.time()
    louvain = g.community_multilevel()
    print(
        f"[louvain] {time.time() - t0:.1f}s  communities={len(louvain):,}  "
        f"modularity={louvain.modularity:.4f}  rss={rss_mb():.0f} MB",
        flush=True,
    )

    try:
        t0 = time.time()
        leiden = g.community_leiden(objective_function="modularity")
        print(
            f"[leiden] {time.time() - t0:.1f}s  communities={len(leiden):,}  "
            f"modularity={leiden.modularity:.4f}",
            flush=True,
        )
    except Exception as exc:  # Leiden 在某些 igraph 构建中不可用
        print(f"[leiden] unavailable: {exc}", flush=True)

    t0 = time.time()
    pagerank = np.asarray(g.pagerank(directed=False))
    print(f"[pagerank] {time.time() - t0:.1f}s  rss={rss_mb():.0f} MB")

    t0 = time.time()
    dst = ds.dataset(PARQUET_PATH, format="parquet").to_table(columns=["dst"])["dst"].to_numpy()
    in_degree = np.bincount(dst, minlength=g.vcount()).astype(np.int32)
    del dst
    print(f"[in-degree] {time.time() - t0:.1f}s")

    rank_report("pagerank", pagerank, None, in_degree)
    rank_report("in-degree", in_degree.astype(np.float64), None, in_degree)

    sizes = np.bincount(np.asarray(louvain.membership), minlength=len(louvain))
    print(f"[louvain sizes] largest 5 = {sorted(sizes, reverse=True)[:5]}")
    print(f"[louvain sizes] singletons = {int((sizes == 1).sum()):,} / {len(sizes):,}")

    t0 = time.time()
    table = pa.table(
        {
            "node": np.arange(g.vcount(), dtype=np.int32),
            "community": np.asarray(louvain.membership, dtype=np.int32),
            "pagerank": pagerank.astype(np.float64),
            "in_degree": in_degree,
        }
    )
    pq.write_table(table, RESULT_PATH)
    print(f"[export] {time.time() - t0:.1f}s -> {RESULT_PATH}")
    print(f"[rss] end {rss_mb():.0f} MB")
    print("COMMUNITY_INFLUENCE_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
