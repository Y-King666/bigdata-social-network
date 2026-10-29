"""传播分析：转发级联的规模分布、扩散节奏与作者影响力对照。"""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import common as C

C.page_header(
    "传播分析",
    "把同一条微博的所有转发聚合成级联，观察它的规模分布与扩散节奏",
)

casc = C.load_cascade_stats()
growth = C.load_cascade_growth()
big = int((casc["reposters"] >= 1000).sum())

C.kpi_row([
    ("转发级联", "{:,}".format(len(casc)), "按被转发微博聚合"),
    ("最大级联", "{:,}".format(int(casc["reposters"].max())), "单条微博的转发者人数"),
    ("转发破千的微博", "{:,}".format(big), "占全部级联 %.2f%%" % (big / len(casc) * 100)),
    ("平均规模", "%.2f" % casc["reposters"].mean(), "平均每条微博的转发者人数"),
])

C.section("级联规模分布", "绝大多数转发集中在少数几条微博上")
edges = np.array([1, 2, 3, 6, 11, 21, 51, 101, 501, 1001, 5001, 60000])
labels = ["%s~%s" % (edges[i], edges[i + 1] - 1) for i in range(len(edges) - 1)]
counts = np.histogram(casc["reposters"], bins=edges)[0]
fig = go.Figure(go.Bar(
    x=labels, y=counts, marker=dict(color=C.PALETTE["secondary"]),
    text=["{:,}".format(c) for c in counts], textposition="outside",
))
fig.update_layout(xaxis=dict(title="转发者人数"), yaxis=dict(title="微博条数（对数）", type="log"))
C.style_fig(fig, height=400, legend=False)
st.plotly_chart(fig, width="stretch")

C.section("扩散节奏", "选择一条微博，看它逐小时新增的转发量")
have_growth = set(growth["orig_id"])
cand = casc[casc["orig_id"].isin(have_growth)].sort_values("reposters", ascending=False).head(20)
labels_map = {r.orig_id: "%s · %s 人转发" % (r.orig_id, "{:,}".format(int(r.reposters)))
              for r in cand.itertuples()}
picked = st.selectbox("被转发微博", list(labels_map), format_func=lambda k: labels_map[k])
series = growth[growth["orig_id"] == picked].sort_values("hour")
figure = go.Figure()
figure.add_trace(go.Bar(
    x=series["hour"], y=series["new_reposters"], name="每小时新增转发",
    marker=dict(color="rgba(192,57,43,0.8)"),
))
figure.add_trace(go.Scatter(
    x=series["hour"], y=series["new_reposters"].cumsum(), name="累计转发（右轴）", yaxis="y2",
    line=dict(color=C.PALETTE["secondary"], width=2.4),
))
figure.update_layout(
    xaxis=dict(title="时间"),
    yaxis=dict(title="每小时新增转发"),
    yaxis2=dict(title="累计转发", overlaying="y", side="right", showgrid=False),
    bargap=0.2,
)
C.style_fig(figure, height=420)
st.plotly_chart(figure, width="stretch")
peak_at = series.loc[series["new_reposters"].idxmax(), "hour"]
elapsed = (peak_at - series["hour"].min()).total_seconds() / 3600
st.caption(
    "峰值出现在 %s，距首次转发仅 %.0f 小时；爆发式传播通常在两小时内达峰，随后单调衰减——"
    "即热点的“黄金两小时”窗口。" % (str(peak_at)[:16], elapsed)
)

C.section("粉丝多 ≠ 传播广", "把转发量最高的 20 条微博与原作者粉丝数对照")
users = C.load_graph_users()[["user_id", "fans_num", "province", "city"]].copy()
users["粉丝排名"] = users["fans_num"].rank(ascending=False, method="min").astype(int)
top = casc.sort_values("reposters", ascending=False).head(20)
joined = top.merge(users, left_on="target_user", right_on="user_id", how="left")
table = joined[["orig_id", "reposters", "target_user", "fans_num", "粉丝排名", "province"]].rename(
    columns={"orig_id": "微博", "reposters": "转发者人数", "target_user": "原作者",
             "fans_num": "粉丝数", "province": "省份"}
)
st.dataframe(table, width="stretch", hide_index=True)
fans_span = table["粉丝数"].max() / max(table["粉丝数"].min(), 1)
st.caption(
    "这 %d 条微博的传播规模相当（%s~%s 人转发），但作者粉丝数相差 %.0f 倍（%s ~ %s）。"
    "粉丝数是起点，不是传播的保证。"
    % (len(table), "{:,}".format(int(table["转发者人数"].min())),
       "{:,}".format(int(table["转发者人数"].max())), fans_span,
       "{:,}".format(int(table["粉丝数"].min())), "{:,}".format(int(table["粉丝数"].max())))
)

C.section("情感倾向与传播规模", "对 4,089 万条推文逐条打分后的结果")
pol = pd.read_csv(os.path.join(C.OUTPUT, "sentiment_by_polarity.csv"))
buck = pd.read_csv(os.path.join(C.OUTPUT, "sentiment_repost_buckets.csv"))
order = {"正面": 0, "中性": 1, "负面": 2}
pol = pol.sort_values("polarity", key=lambda s: s.map(order))

left, right = st.columns([1, 1.3])
with left:
    fig = go.Figure(go.Bar(
        x=pol["polarity"], y=pol["avg_reposts"],
        marker=dict(color=[C.PALETTE["positive"], C.PALETTE["neutral"], C.PALETTE["negative"]]),
        text=["%.2f" % v for v in pol["avg_reposts"]], textposition="outside",
    ))
    fig.update_layout(yaxis=dict(title="平均被转发次数"))
    C.style_fig(fig, height=380, title="各极性推文的平均转发量", legend=False)
    st.plotly_chart(fig, width="stretch")
with right:
    fig = go.Figure()
    for i, name in enumerate(["正面", "中性", "负面"]):
        part = buck[buck["polarity"] == name]
        fig.add_trace(go.Scatter(
            x=part["bucket"], y=part["share"] * 100, name=name, mode="lines+markers",
            line=dict(color=[C.PALETTE["positive"], C.PALETTE["neutral"],
                             C.PALETTE["negative"]][i], width=2.2),
        ))
    fig.update_layout(xaxis=dict(title="被转发次数区间"),
                      yaxis=dict(title="该区间推文占比 (%)", type="log"),
                      title="各极性推文在转发量区间上的分布")
    C.style_fig(fig, height=380, title="各极性推文在转发量区间上的分布")
    st.plotly_chart(fig, width="stretch")

st.dataframe(
    pol.rename(columns={"polarity": "极性", "posts": "推文数", "avg_reposts": "平均转发",
                        "posts_ge_100": "转发≥100", "posts_ge_1000": "转发≥1000"}),
    width="stretch", hide_index=True,
)
st.caption(
    "正面的平均转发量是负面的 2.96 倍，转发破千的微博里正面与负面之比约 8:1。"
    "注意两点局限：词典法读不懂反讽与语境（全国哀悼日当天正面占比反而最高）；"
    "“加油、致敬”这类动员型内容本身更容易被转发，所以结论应限定在疫情动员语境下。"
)
