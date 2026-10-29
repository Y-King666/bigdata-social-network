"""传播模拟：以转发关系图为接触网络，用独立级联模型模拟信息扩散。"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import common as C
import graphlib as G

C.page_header(
    "传播模拟",
    "把转发关系图当作接触网络，用独立级联模型模拟一条微博从某个用户开始的扩散过程",
)

users = C.load_graph_users()
ranked = users.sort_values("pagerank", ascending=False).reset_index(drop=True)

labels = {
    r.user_id: "%s · 粉丝 %s · 被转发 %s 人"
    % (r.user_id, "{:,}".format(int(r.fans_num)), "{:,}".format(int(r.in_degree)))
    for r in ranked.head(30).itertuples()
}
seed_id = st.selectbox("起始用户", list(labels), format_func=lambda u: labels[u])

col1, col2 = st.columns(2)
prob = col1.slider("每条边的传播概率", 0.01, 0.30, 0.05, 0.01,
                   help="一个用户看到微博后转发它的概率")
rounds = col2.slider("模拟轮数", 1, 15, 8, help="一轮代表一次转发扩散")

result = G.simulate(seed_id, prob, rounds)
if result is None:
    st.warning("这个 id 不在转发关系图中。")
    st.stop()

growth = result["growth"]
total_nodes = len(users)
observed = int(ranked.loc[ranked["user_id"] == seed_id, "in_degree"].iloc[0])
peak = int(np.argmax(growth))

C.kpi_row([
    ("最终感染人数", "{:,}".format(result["infected"]),
     "占全网 %.3f%%" % (result["infected"] / total_nodes * 100)),
    ("峰值轮次", "第 %d 轮" % peak, "单轮新增最多的一轮"),
    ("实测被转发", "{:,}".format(observed), "该用户在原数据中的真实转发量"),
    ("传播概率", "%.2f" % prob, "每条边的独立激活概率"),
])

C.section("逐轮扩散规模")
fig = go.Figure()
fig.add_trace(go.Bar(
    x=list(range(len(growth))), y=growth, name="本轮新增感染",
    marker=dict(color="rgba(192,57,43,0.8)"),
))
fig.add_trace(go.Scatter(
    x=list(range(len(growth))), y=np.cumsum(growth), name="累计感染（右轴）", yaxis="y2",
    line=dict(color=C.PALETTE["secondary"], width=2.4),
))
fig.update_layout(
    xaxis=dict(title="轮次", dtick=1),
    yaxis=dict(title="本轮新增", rangemode="tozero"),
    yaxis2=dict(title="累计感染", overlaying="y", side="right", showgrid=False,
                range=[0, float(np.cumsum(growth).max()) * 1.08]),
    bargap=0.25,
)
C.style_fig(fig, height=420)
st.plotly_chart(fig, width="stretch")

C.section("传播概率的敏感性", "同一个起点、同一个随机种子，只改变每条边的传播概率")
probs = [0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.18, 0.25]
finals = [G.simulate(seed_id, p, rounds)["infected"] for p in probs]
fig = go.Figure(go.Scatter(
    x=probs, y=finals, mode="lines+markers",
    line=dict(color=C.PALETTE["primary"], width=2.4), marker=dict(size=8),
))
fig.add_vline(x=prob, line=dict(color=C.PALETTE["accent"], width=1.5, dash="dash"),
              annotation_text="当前设置", annotation_position="top")
fig.update_layout(
    xaxis=dict(title="每条边的传播概率", tickformat=".0%"),
    yaxis=dict(title="最终感染人数"),
)
C.style_fig(fig, height=400, legend=False)
st.plotly_chart(fig, width="stretch")

C.section("不同起点的扩散规模", "传播概率固定为当前设置，只改变起点")
by_degree = ranked.sort_values("in_degree", ascending=False).reset_index(drop=True)
probe = by_degree.iloc[[0, 1000, 50000]]
probe_rows = []
for r in probe.itertuples():
    res = G.simulate(r.user_id, prob, rounds)
    probe_rows.append({
        "起点用户": r.user_id,
        "被转发人数": int(r.in_degree),
        "粉丝数": int(r.fans_num),
        "最终感染": res["infected"] if res else 0,
    })
st.dataframe(probe_rows, width="stretch", hide_index=True)
st.caption(
    "起点差距悬殊：被转发最多的用户一轮即可激活数万人，而被转发量中等的用户几乎无法扩散。"
    "原因是转发关系图呈星形结构——94.2% 的节点只转发、从未被转发，"
    "所以传播几乎全在“超级节点 → 普通用户”这一层内完成，二跳扩散极少。"
)

st.caption(
    "模型要点：独立级联（Independent Cascade）假设每条边以相同概率独立激活一次，"
    "被 k 个已激活用户指向的节点被激活概率为 1-(1-p)^k。"
    "它只依赖网络结构，不考虑内容质量、时间衰减与平台推荐，"
    "因此结果应与实测数据分析对照阅读——真实传播中“粉丝数相差 45 万倍、传播规模却相当”"
    "正说明结构之外的偶然因素同样重要。"
)
