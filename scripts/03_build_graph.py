"""把边表构造成常驻内存的图，供应用层做实时关系查询。

系统的"关系发现"功能要在用户点击时立刻算出两人之间的最短路径，
反复启动 Spark 不可行，因此把 3062 万条边压成 CSR 稀疏矩阵常驻内存，
并落盘为 npz，让应用启动时直接加载。
"""

import os
import sys
import time

import numpy as np
import psutil
import pyarrow.dataset as ds
from scipy.sparse import csr_matrix, save_npz
from scipy.sparse.csgraph import breadth_first_order, shortest_path

import spark_env

PARQUET_PATH = os.path.join(spark_env.DATA_DIR, "edges_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")
GRAPH_PATH = os.path.join(OUT_DIR, "graph_undirected.npz")

TOP_INFLUENCER = 5935


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / (1024 * 1024)


def load_edges() -> tuple[np.ndarray, np.ndarray]:
    table = ds.dataset(PARQUET_PATH, format="parquet").to_table(columns=["src", "dst"])
    src = table["src"].to_numpy().astype(np.int32, copy=False)
    dst = table["dst"].to_numpy().astype(np.int32, copy=False)
    return src, dst


def build_undirected(src: np.ndarray, dst: np.ndarray) -> csr_matrix:
    """好友关系是有向的，但"两人隔几个人"要按无向图计算，故双向各存一份。"""
    n_nodes = int(max(src.max(), dst.max())) + 1
    rows = np.concatenate((src, dst))
    cols = np.concatenate((dst, src))
    data = np.ones(rows.shape, dtype=np.int8)
    return csr_matrix((data, (rows, cols)), shape=(n_nodes, n_nodes), dtype=np.int8)


def probe_distances(graph: csr_matrix, start: int) -> None:
    degree = graph.indptr[start + 1] - graph.indptr[start]
    print(f"[node {start}] degree={degree}  dtype={graph.dtype}")

    t0 = time.time()
    order, _ = breadth_first_order(graph, start, directed=False, return_predecessors=True)
    print(f"[bfs-order] {time.time() - t0:.1f}s  reached={len(order):,} / {graph.shape[0]:,}")

    t0 = time.time()
    dist = shortest_path(graph, indices=np.array([start]), unweighted=True, directed=False)[0]
    elapsed = time.time() - t0
    reachable = np.isfinite(dist)
    print(f"[shortest_path] {elapsed:.1f}s  finite={int(reachable.sum()):,}  dist[start]={dist[start]}")
    if reachable.sum() == 0:
        return
    d = dist[reachable].astype(np.int32)
    print(f"      max_hops={d.max()}  mean_hops={d.mean():.2f}")
    within6 = float((d <= 6).sum()) / reachable.sum()
    print(f"      可达节点中 {within6:.1%} 在 6 跳以内")
    hist = np.bincount(d)
    for hops in range(1, min(len(hist), 12)):
        print(f"      {hops:>2} 跳: {hist[hops]:>10,}")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"[rss] start {rss_mb():.0f} MB")

    t0 = time.time()
    src, dst = load_edges()
    print(f"[load-edges] {time.time() - t0:.1f}s  edges={len(src):,}  rss={rss_mb():.0f} MB")

    t0 = time.time()
    graph = build_undirected(src, dst)
    del src, dst
    print(f"[build-csr] {time.time() - t0:.1f}s  nnz={graph.nnz:,}  rss={rss_mb():.0f} MB")

    probe_distances(graph, TOP_INFLUENCER)
    probe_distances(graph, 1_000_000)

    t0 = time.time()
    save_npz(GRAPH_PATH, graph, compressed=False)
    size_mb = os.path.getsize(GRAPH_PATH) / (1024 * 1024)
    print(f"[save-npz] {time.time() - t0:.1f}s -> {size_mb:.0f} MB")
    print(f"[rss] end {rss_mb():.0f} MB")
    print("BUILD_GRAPH_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
