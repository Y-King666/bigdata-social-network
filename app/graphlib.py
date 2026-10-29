"""转发图的邻接结构与图算法，供关系发现与传播模拟共用。"""

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse import csgraph
import streamlit as st

import common as C


@st.cache_resource(show_spinner="正在读取转发关系边…")
def load_edges():
    edges = C.load_user_edges()
    edges["source_user"] = edges["source_user"].astype(str)
    edges["target_user"] = edges["target_user"].astype(str)
    return edges


@st.cache_resource(show_spinner="正在构建图索引（约 234 万节点）…")
def build_index():
    """返回 (节点 id 数组, id->下标 映射, 无向邻接, 传播方向邻接)。

    边的存储方向是"转发者 -> 被转发者"；传播时信息沿相反方向流动，
    因此 forward 按"被转发者 -> 转发者"建边。
    """
    edges = load_edges()
    ids = pd.unique(pd.concat([edges["source_user"], edges["target_user"]], ignore_index=True))
    lookup = pd.Series(np.arange(len(ids), dtype=np.int32), index=ids)
    src = lookup.reindex(edges["source_user"]).to_numpy()
    dst = lookup.reindex(edges["target_user"]).to_numpy()
    n = len(ids)
    undirected = sp.csr_matrix(
        (np.ones(2 * len(src), dtype=np.int8), (np.r_[src, dst], np.r_[dst, src])),
        shape=(n, n),
    )
    forward = sp.csr_matrix((np.ones(len(src), dtype=np.int8), (dst, src)), shape=(n, n))
    return ids, lookup, undirected, forward


def shortest_path(a_id, b_id):
    """无向最短转发链路，返回用户 id 列表；不可达返回 []，节点不存在返回 None。"""
    ids, lookup, undirected, _ = build_index()
    if a_id not in lookup.index or b_id not in lookup.index:
        return None
    src = int(lookup[a_id])
    dst = int(lookup[b_id])
    dist, pred = csgraph.shortest_path(
        undirected, method="D", unweighted=True, directed=False,
        indices=[src], return_predecessors=True,
    )
    if not np.isfinite(dist[0, dst]):
        return []
    path = [dst]
    node = dst
    while node != src:
        node = int(pred[0, node])
        path.append(node)
    path.reverse()
    return [ids[i] for i in path]


def direct_links(user_id):
    """该用户的一跳邻居：转发过他的人、以及他转发过的人。"""
    ids, lookup, _, forward = build_index()
    if user_id not in lookup.index:
        return [], []
    node = int(lookup[user_id])
    reposters = [ids[i] for i in forward.indices[forward.indptr[node]:forward.indptr[node + 1]]]
    edges = load_edges()
    follows = edges.loc[edges["source_user"] == user_id, "target_user"].tolist()
    return reposters, follows


def simulate(seed_id, prob, rounds, seed=42):
    """独立级联模型：每条边以 prob 独立激活一次，返回逐轮新增规模。"""
    ids, lookup, _, forward = build_index()
    if seed_id not in lookup.index:
        return None
    rng = np.random.default_rng(seed)
    n = len(ids)
    active = np.zeros(n, dtype=bool)
    start = int(lookup[seed_id])
    active[start] = True
    frontier = np.array([start], dtype=np.int64)
    growth = [1]
    for _ in range(int(rounds)):
        if frontier.size == 0:
            growth.append(0)
            continue
        cand = np.concatenate(
            [forward.indices[forward.indptr[u]:forward.indptr[u + 1]] for u in frontier]
        ).astype(np.int64)
        cand = cand[~active[cand]]
        if cand.size == 0:
            growth.append(0)
            continue
        uniq, counts = np.unique(cand, return_counts=True)
        # 每条入边独立尝试一次，被 k 条边指向的节点激活概率为 1-(1-p)^k
        hit = 1.0 - (1.0 - prob) ** counts
        new_nodes = uniq[rng.random(uniq.size) < hit]
        active[new_nodes] = True
        frontier = new_nodes
        growth.append(int(new_nodes.size))
    return {"infected": int(active.sum()) - 1, "growth": growth}
