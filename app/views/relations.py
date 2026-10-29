"""关系发现：任意两个用户之间通过转发关系的最短链路。"""

import pandas as pd
import streamlit as st

import common as C
import graphlib as G

C.page_header(
    "关系发现",
    "把 326 万条转发关系看成无向网络，寻找两个用户之间的最短链路",
)

users = C.load_graph_users().set_index("user_id")
ranked = users.sort_values("pagerank", ascending=False)
defaults = list(ranked.head(6).index)

col_a, col_b = st.columns(2)
a = col_a.text_input("用户 A", value=defaults[0]).strip()
b = col_b.text_input("用户 B", value=defaults[3]).strip()

if a and b:
    path = G.shortest_path(a, b)
    if path is None:
        st.warning("至少有一个 id 不在转发关系图中。注意 id 是 16 位十六进制字符串。")
    elif len(path) == 0:
        st.error(
            "这两个用户在转发网络中不连通——他们分属不同的弱连通分量。"
            "转发网络虽然只有 4.1 万个分量，但最大分量只覆盖了 96% 的节点。"
        )
    elif len(path) == 1:
        st.info("两个 id 相同，链路长度为 0。")
    else:
        hops = len(path) - 1
        C.kpi_row([
            ("链路长度", "%d 跳" % hops, "最少需要经过几次转发关系"),
            ("中间人", "%d 个" % (hops - 1), "链路上除两端之外的用户"),
            ("网络节点", "{:,}".format(len(users)), "最长链路的上限参考"),
        ])
        C.section("链路详情")
        rows = []
        for i, uid in enumerate(path):
            info = users.loc[uid] if uid in users.index else None
            rows.append({
                "序号": i,
                "用户": uid,
                "粉丝数": int(info["fans_num"]) if info is not None else None,
                "被转发": int(info["in_degree"]) if info is not None else None,
                "PageRank": round(float(info["pagerank"]), 6) if info is not None else None,
                "省份": info["province"] if info is not None else None,
                "社区": int(info["leiden"]) if info is not None else None,
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        ids, lookup, _, forward = G.build_index()
        C.section("每一跳的关系方向", "转发关系是有向的，方向说明信息从谁流向谁")
        for i in range(hops):
            u, v = path[i], path[i + 1]
            iu, iv = int(lookup[u]), int(lookup[v])
            if forward[iv, iu]:
                text = "%s 转发了 %s 的微博" % (u, v)
            else:
                text = "%s 转发了 %s 的微博" % (v, u)
            st.markdown("- 第 %d 跳：%s" % (i + 1, text))

    C.section("一跳关系", "两个用户各自的直接转发邻居")
    left, right = st.columns(2)
    with left:
        reposters, follows = G.direct_links(a)
        st.markdown("**%s**：被 %s 人转发过，转发过 %s 人"
                    % (a, "{:,}".format(len(reposters)), "{:,}".format(len(follows))))
    with right:
        reposters, follows = G.direct_links(b)
        st.markdown("**%s**：被 %s 人转发过，转发过 %s 人"
                    % (b, "{:,}".format(len(reposters)), "{:,}".format(len(follows))))
