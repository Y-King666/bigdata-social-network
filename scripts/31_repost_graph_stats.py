"""转发网络的结构指标。

转发图与好友图性质完全不同：少数账号被大量转发，多数人只转发别人，
因此入度分布才是影响力所在，自环（转发自己的微博）需要单独剔除。
"""

import os
import sys
import time

import igraph as ig
import numpy as np
import pyarrow.dataset as ds
import pyarrow as pa
import pyarrow.parquet as pq

import spark_env

EDGES_USER = os.path.join(spark_env.DATA_DIR, "repost_user_edges_parquet")
OUT_DIR = os.path.join(spark_env.PROJECT_ROOT, "output")
METRICS = os.path.join(OUT_DIR, "repost_node_metrics.parquet")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    t0 = time.time()
    table = ds.dataset(EDGES_USER, format="parquet").to_table(
        columns=["source_user", "target_user", "weight"]
    )
    src = table["source_user"].to_pylist()
    dst = table["target_user"].to_pylist()
    weight = table["weight"].to_numpy()
    print(f"[load] {time.time() - t0:.1f}s  raw edges={len(src):,}", flush=True)

    self_loops = sum(1 for a, b in zip(src, dst) if a == b)
    print(f"[self-loops] {self_loops:,} ({self_loops / len(src):.2%})", flush=True)

    keep = [i for i, (a, b) in enumerate(zip(src, dst)) if a != b]
    nodes = sorted({src[i] for i in keep} | {dst[i] for i in keep})
    index = {u: i for i, u in enumerate(nodes)}
    edges = [(index[src[i]], index[dst[i]]) for i in keep]
    print(f"[graph] nodes={len(nodes):,}  edges={len(edges):,}", flush=True)

    t0 = time.time()
    g = ig.Graph(n=len(nodes), edges=edges, directed=True)
    print(f"[igraph] {time.time() - t0:.1f}s  v={g.vcount():,}  e={g.ecount():,}", flush=True)

    t0 = time.time()
    wcc = g.connected_components(mode="weak")
    scc = g.connected_components(mode="strong")
    print(f"[components] {time.time() - t0:.1f}s  weak={len(wcc):,} (giant {wcc.giant().vcount():,})  "
          f"strong={len(scc):,} (giant {scc.giant().vcount():,})", flush=True)

    indeg = np.array(g.degree(mode="in"))
    outdeg = np.array(g.degree(mode="out"))
    for name, d in (("in-degree", indeg), ("out-degree", outdeg)):
        print(f"[{name}] max={d.max():,}  mean={d.mean():.2f}  median={np.median(d):.0f}  "
              f"p99={np.percentile(d, 99):.0f}  zero={int((d == 0).sum()):,}", flush=True)

    t0 = time.time()
    pagerank = np.asarray(g.pagerank(directed=True))
    print(f"[pagerank] {time.time() - t0:.1f}s", flush=True)

    print("[top-10 by in-degree (被转发最多)]", flush=True)
    for i in np.argsort(indeg)[::-1][:10]:
        print(f"   {nodes[i]:<18} in={indeg[i]:>7,}  out={outdeg[i]:>6,}  pr={pagerank[i]:.3e}", flush=True)

    print("[top-10 by PageRank]", flush=True)
    for i in np.argsort(pagerank)[::-1][:10]:
        print(f"   {nodes[i]:<18} pr={pagerank[i]:.3e}  in={indeg[i]:>7,}  out={outdeg[i]:>6,}", flush=True)

    table_out = pa.table(
        {
            "user_id": pa.array(nodes, type=pa.string()),
            "in_degree": pa.array(indeg, type=pa.int32()),
            "out_degree": pa.array(outdeg, type=pa.int32()),
            "pagerank": pa.array(pagerank, type=pa.float64()),
            "wcc_id": pa.array(np.asarray(wcc.membership), type=pa.int32()),
        }
    )
    pq.write_table(table_out, METRICS)
    print(f"[export] -> {METRICS}", flush=True)
    print("REPOST_GRAPH_STATS_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
