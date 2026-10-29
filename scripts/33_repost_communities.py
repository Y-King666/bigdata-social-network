"""转发网络的社区发现。

转发图方向性极强（强连通分量几乎全是单点），社区结构要看无向投影。
同时保留 Louvain 与 Leiden 的算法对比数据。
"""

import os
import sys
import time

import igraph as ig
import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

import spark_env

EDGES_USER = os.path.join(spark_env.DATA_DIR, "repost_user_edges_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")
MEMBERSHIP = os.path.join(OUT_DIR, "repost_communities.parquet")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    t0 = time.time()
    table = ds.dataset(EDGES_USER, format="parquet").to_table(
        columns=["source_user", "target_user"]
    )
    src = table["source_user"].to_pylist()
    dst = table["target_user"].to_pylist()
    keep = [(a, b) for a, b in zip(src, dst) if a != b]
    nodes = sorted({a for a, b in keep} | {b for a, b in keep})
    index = {u: i for i, u in enumerate(nodes)}
    edges = [(index[a], index[b]) for a, b in keep]
    print(f"[load] {time.time() - t0:.1f}s  nodes={len(nodes):,}  edges={len(edges):,}", flush=True)

    t0 = time.time()
    g = ig.Graph(n=len(nodes), edges=edges, directed=False)
    print(f"[igraph] {time.time() - t0:.1f}s", flush=True)

    t0 = time.time()
    louvain = g.community_multilevel()
    print(f"[louvain] {time.time() - t0:.1f}s  communities={len(louvain):,}  "
          f"modularity={louvain.modularity:.4f}", flush=True)

    t0 = time.time()
    leiden = g.community_leiden(objective_function="modularity")
    print(f"[leiden] {time.time() - t0:.1f}s  communities={len(leiden):,}  "
          f"modularity={leiden.modularity:.4f}", flush=True)

    sizes = np.bincount(np.asarray(louvain.membership))
    print(f"[louvain sizes] top10={sorted(sizes, reverse=True)[:10]}", flush=True)
    print(f"[louvain sizes] singleton communities={int((sizes == 1).sum()):,} / {len(sizes):,}", flush=True)
    big = np.argsort(sizes)[::-1][:15]
    print("[top-15 communities: id, size]", flush=True)
    for c in big:
        print(f"   community {int(c):>6}  size={int(sizes[c]):>9,}", flush=True)

    table_out = pa.table(
        {
            "user_id": pa.array(nodes, type=pa.string()),
            "louvain": pa.array(np.asarray(louvain.membership), type=pa.int32()),
            "leiden": pa.array(np.asarray(leiden.membership), type=pa.int32()),
        }
    )
    pq.write_table(table_out, MEMBERSHIP)
    print(f"[export] -> {MEMBERSHIP}", flush=True)
    print("REPOST_COMMUNITIES_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
