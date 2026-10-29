"""影响力与社区：PageRank 排序、粉丝数与影响力的背离，以及社区结构。"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import common as C

C.page_header(
    "影响力与社区",
    "在 234 万节点的转发关系图上计算 PageRank 影响力，并用 Louvain / Leiden 划分社区",
)

users = C.load_graph_users()
zero_in = int((users["in_degree"] == 0).sum())
C.kpi_row([
    ("转发图节点", "{:,}".format(len(users)), "有转发关系的用户"),
    ("社区数量", "{:,}".format(users["leiden"].nunique()), "Leiden 划分，模块度 0.7985"),
    ("最大入度", "{:,}".format(int(users["in_degree"].max())), "被最多人转发的用户"),
    ("零入度用户", "{:,}".format(zero_in), "占 %.1f%%，只转发、不被转发" % (zero_in / len(users) * 100)),
])

ranked = users.sort_values("pagerank", ascending=False).reset_index(drop=True)
ranked["粉丝排名"] = ranked["fans_num"].rank(ascending=False, method="min").astype(int)

C.section("PageRank 影响力 Top 20", "影响力由转发关系决定，与粉丝数无关")
show = ranked.head(20)[["user_id", "pagerank", "in_degree", "out_degree", "fans_num",
                        "粉丝排名", "province", "city", "leiden"]]
st.dataframe(
    show.rename(columns={"user_id": "用户", "pagerank": "PageRank", "in_degree": "被转发",
                         "out_degree": "转发", "fans_num": "粉丝数", "province": "省份",
                         "city": "城市", "leiden": "社区"}),
    width="stretch", hide_index=True,
)

C.section("粉丝数与影响力的背离", "横轴为粉丝数，纵轴为 PageRank，红点为影响力前 100 名")
sample = users.sample(n=30000, random_state=7) if len(users) > 30000 else users
top100 = ranked.head(100)
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=np.maximum(sample["fans_num"], 1), y=sample["pagerank"], mode="markers",
    marker=dict(size=5, color="rgba(31,58,95,0.28)", line=dict(width=0)),
    name="全部用户（抽样 3 万）",
    hovertemplate="粉丝 %{x:,}<br>PageRank %{y:.4f}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=np.maximum(top100["fans_num"], 1), y=top100["pagerank"], mode="markers",
    marker=dict(size=8, color=C.PALETTE["primary"], line=dict(width=0)),
    name="影响力前 100",
    customdata=top100[["user_id", "in_degree", "粉丝排名"]].to_numpy(),
    hovertemplate="%{customdata[0]}<br>粉丝 %{x:,}（第 %{customdata[2]} 名）"
                  "<br>被转发 %{customdata[1]:,}<br>PageRank %{y:.4f}<extra></extra>",
))
fig.add_vline(x=1e4, line=dict(color=C.PALETTE["accent"], width=1.5, dash="dash"),
              annotation_text="1 万粉丝", annotation_position="top")
fig.update_layout(
    xaxis=dict(title="粉丝数（对数）", type="log"),
    yaxis=dict(title="PageRank", type="log"),
)
C.style_fig(fig, height=460)
st.plotly_chart(fig, width="stretch")

low_fans = top100[top100["粉丝排名"] > 10000]
st.caption(
    "影响力前 100 名里有 %d 人粉丝排名在 1 万名之外。粉丝是账面数字，"
    "真正决定影响力的是谁愿意转发你。" % len(low_fans)
)

C.section("社区结构", "Leiden 划分出的 41,837 个社区，规模高度不均")
sizes = users["leiden"].value_counts().head(20).iloc[::-1]
fig = go.Figure(go.Bar(
    x=sizes.values, y=["社区 %s" % i for i in sizes.index], orientation="h",
    marker=dict(color=C.PALETTE["secondary"]),
))
fig.update_layout(xaxis=dict(title="节点数"))
C.style_fig(fig, height=560, legend=False)
st.plotly_chart(fig, width="stretch")

C.section("社区画像", "看某个社区里的人来自哪里、有什么特征")
comm = st.selectbox("社区", sizes.index[::-1], format_func=lambda i: "社区 %s（%s 人）"
                    % (i, "{:,}".format(int((users["leiden"] == i).sum()))))
part = users[users["leiden"] == comm]
left, mid, right = st.columns(3)
with left:
    st.metric("社区规模", "{:,}".format(len(part)))
    st.metric("平均粉丝数", "{:,.0f}".format(part["fans_num"].mean()))
with mid:
    gender = part["gender"].value_counts().head(5)
    fig = go.Figure(go.Bar(
        x=gender.values, y=gender.index, orientation="h",
        marker=dict(color=[C.PALETTE["primary"], C.PALETTE["secondary"], C.PALETTE["muted"],
                           C.PALETTE["accent"], C.PALETTE["positive"]][:len(gender)]),
    ))
    fig.update_layout(margin=dict(l=60))
    C.style_fig(fig, height=280, title="性别构成", legend=False)
    st.plotly_chart(fig, width="stretch")
with right:
    prov = part["province"].value_counts().head(5)
    fig = go.Figure(go.Bar(
        x=prov.values, y=prov.index, orientation="h",
        marker=dict(color=C.PALETTE["secondary"]),
    ))
    fig.update_layout(margin=dict(l=60))
    C.style_fig(fig, height=280, title="省份构成 Top 5", legend=False)
    st.plotly_chart(fig, width="stretch")
