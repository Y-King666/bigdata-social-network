"""转发关系图：CSR 索引、最短链路、一跳邻居与独立级联模拟。"""

import threading

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse import csgraph

try:
    from . import history, paths
except ImportError:
    import history
    import paths

_LOCK = threading.Lock()
_STATE = {"started": False, "building": False, "ready": False, "error": None}
_INDEX = None


def ready():
    return _STATE["ready"]


def building():
    return _STATE["building"]


def error():
    return _STATE["error"]


def _build():
    global _INDEX
    try:
        edges = pd.read_parquet(
            paths.USER_EDGES, columns=["source_user", "target_user"]
        )
        edges["source_user"] = edges["source_user"].astype(str)
        edges["target_user"] = edges["target_user"].astype(str)
        edges = edges.drop_duplicates(subset=["source_user", "target_user"])
        ids = pd.unique(
            pd.concat([edges["source_user"], edges["target_user"]], ignore_index=True)
        )
        lookup = pd.Series(np.arange(len(ids), dtype=np.int32), index=ids)
        src = lookup.reindex(edges["source_user"]).to_numpy()
        dst = lookup.reindex(edges["target_user"]).to_numpy()
        n = len(ids)
        undirected = sp.csr_matrix(
            (np.ones(2 * len(src), dtype=np.int8), (np.r_[src, dst], np.r_[dst, src])),
            shape=(n, n),
        )
        forward = sp.csr_matrix(
            (np.ones(len(src), dtype=np.int8), (dst, src)), shape=(n, n)
        )
        _INDEX = (ids, lookup, undirected, forward, src, dst)
        _STATE["ready"] = True
    except Exception as exc:  # 保留错误，下一次请求可重试
        _STATE["error"] = "%s: %s" % (type(exc).__name__, exc)
    finally:
        _STATE["building"] = False


def start_warmup():
    with _LOCK:
        if _STATE["ready"] or _STATE["building"]:
            return
        _STATE["started"] = True
        _STATE["building"] = True
        _STATE["error"] = None
        threading.Thread(target=_build, name="graph-warmup", daemon=True).start()


def _index():
    if _STATE["ready"]:
        return _INDEX
    start_warmup()
    return None


def _node(lookup, user_id):
    try:
        return int(lookup[user_id])
    except KeyError:
        return None


def _one_hop(index, node):
    ids, lookup, _, forward, src, dst = index
    reposters = np.unique(src[dst == node]).size
    follows = np.unique(dst[src == node]).size
    return {"reposters": int(reposters), "follows": int(follows)}


def relations(a_id, b_id):
    index = _index()
    if index is None:
        return {"status": "graph_not_ready", "message": "正在构建转发图索引…"}
    ids, lookup, undirected, forward, src, dst = index
    a = _node(lookup, a_id)
    b = _node(lookup, b_id)
    if a is None or b is None:
        message = "至少有一个 id 不在转发关系图中。注意 id 是 16 位十六进制字符串。"
        return {"status": "invalid", "path": [], "rows": [], "directions": [],
                "one_hop": {"a": {"reposters": 0, "follows": 0},
                            "b": {"reposters": 0, "follows": 0}},
                "message": message}

    dist, pred = csgraph.shortest_path(
        undirected, method="D", unweighted=True, directed=False,
        indices=[a], return_predecessors=True,
    )
    if not np.isfinite(dist[0, b]):
        message = ("这两个用户在转发网络中不连通——他们分属不同的弱连通分量。"
                   "转发网络虽然只有 4.1 万个分量，但最大分量只覆盖了 96% 的节点。")
        return {"status": "disconnected", "path": [], "rows": [], "directions": [],
                "one_hop": {"a": _one_hop(index, a), "b": _one_hop(index, b)},
                "message": message}

    path_nodes = [b]
    node = b
    while node != a:
        node = int(pred[0, node])
        path_nodes.append(node)
    path_nodes.reverse()
    path = [str(ids[i]) for i in path_nodes]
    rows = history.relation_rows(path)

    directions = []
    for hop in range(len(path_nodes) - 1):
        u, v = path_nodes[hop], path_nodes[hop + 1]
        if forward[v, u]:
            text = "%s 转发了 %s 的微博" % (path[hop], path[hop + 1])
        else:
            text = "%s 转发了 %s 的微博" % (path[hop + 1], path[hop])
        directions.append({"hop": hop + 1, "text": text})

    message = "" if len(path_nodes) > 1 else "两个 id 相同，链路长度为 0。"
    return {
        "status": "ok" if len(path_nodes) > 1 else "same",
        "path": path,
        "rows": rows,
        "directions": directions,
        "one_hop": {"a": _one_hop(index, a), "b": _one_hop(index, b)},
        "message": message,
    }


def _run(seed_node, forward, prob, rounds, seed):
    rng = np.random.default_rng(seed)
    n = forward.shape[0]
    active = np.zeros(n, dtype=bool)
    active[seed_node] = True
    frontier = np.array([seed_node], dtype=np.int64)
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
        hit = 1.0 - (1.0 - prob) ** counts
        new_nodes = uniq[rng.random(uniq.size) < hit]
        active[new_nodes] = True
        frontier = new_nodes
        growth.append(int(new_nodes.size))
    return int(active.sum()) - 1, growth


def simulate(seed_id, prob=0.05, rounds=8, seed=42):
    index = _index()
    if index is None:
        return None
    ids, lookup, _, forward, _, _ = index
    node = _node(lookup, seed_id)
    if node is None:
        return None
    infected, growth = _run(node, forward, float(prob), int(rounds), int(seed))
    return {"seed": seed_id, "prob": float(prob), "rounds": int(rounds),
            "infected": infected, "growth": growth}


def sensitivity(seed_id, probs, rounds, seed=42):
    index = _index()
    if index is None:
        return None
    ids, lookup, _, forward, _, _ = index
    node = _node(lookup, seed_id)
    if node is None:
        return None
    finals = [_run(node, forward, float(p), int(rounds), int(seed))[0] for p in probs]
    return {"probs": list(probs), "finals": finals}


def probe(seed_ids, prob, rounds, seed=42):
    index = _index()
    if index is None:
        return None
    ids, lookup, _, forward, _, _ = index
    rows = []
    for user_id in seed_ids:
        node = _node(lookup, user_id)
        if node is None:
            rows.append({"user_id": user_id, "infected": 0})
            continue
        infected, _ = _run(node, forward, float(prob), int(rounds), int(seed))
        rows.append({"user_id": user_id, "infected": infected})
    return {"rows": rows}
