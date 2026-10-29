"""热点话题：话题规模分布、单话题走势，以及热搜热度与站内发帖量的关系。"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import common as C

C.page_header(
    "热点话题",
    "从推文正文中抽取的话题标签，以及与热搜榜单的交叉对照",
)

stats = C.load_topic_stats().sort_values("occurrences", ascending=False).reset_index(drop=True)
hs = C.load_hotsearch_compare()

C.kpi_row([
    ("话题标签", "{:,}".format(len(stats)), "去重后的话题数"),
    ("话题提及", C.human(stats["occurrences"].sum()), "全部推文中的标签出现次数"),
    ("最热话题", stats.iloc[0]["topic"],
     "{:,} 次提及".format(int(stats.iloc[0]["occurrences"]))),
    ("登上热搜的话题", "{:,}".format(len(hs)), "站内话题与热搜榜的交集"),
])

C.section("话题规模 Top 20", "按全部推文中的提及次数排序")
top20 = stats.head(20).iloc[::-1]
fig = go.Figure(go.Bar(
    x=top20["occurrences"], y=top20["topic"], orientation="h",
    marker=dict(color=C.PALETTE["secondary"]),
    customdata=top20[["posts", "users"]].to_numpy(),
    hovertemplate="%{y}<br>提及 %{x:,}<br>帖子 %{customdata[0]:,}"
                  "<br>用户 %{customdata[1]:,}<extra></extra>",
))
fig.update_layout(xaxis=dict(title="提及次数"), margin=dict(l=240))
C.style_fig(fig, height=640, legend=False)
st.plotly_chart(fig, width="stretch")

C.section("单话题逐日走势", "选择话题查看它在疫情期间的热度变化")
options = stats.head(60)["topic"].tolist()
picked = st.selectbox("话题", options, index=1)
daily = C.load_topic_daily(picked)
fig = go.Figure()
fig.add_trace(go.Bar(
    x=daily["day"], y=daily["occurrences"], name="每日提及次数",
    marker=dict(color="rgba(192,57,43,0.75)"),
))
fig.add_trace(go.Scatter(
    x=daily["day"], y=daily["users"], name="参与用户数（右轴）", yaxis="y2",
    line=dict(color=C.PALETTE["secondary"], width=2),
))
fig.update_layout(
    yaxis=dict(title="提及次数"),
    yaxis2=dict(title="参与用户数", overlaying="y", side="right", showgrid=False),
    bargap=0.15,
)
C.style_fig(fig, height=400)
st.plotly_chart(fig, width="stretch")
span = daily[daily["occurrences"] > 0]
st.caption(
    "首见 %s，末见 %s，共 %d 天有记录；峰值 %s（%s 次提及）"
    % (str(span["day"].min())[:10], str(span["day"].max())[:10], len(span),
       str(span.loc[span["occurrences"].idxmax(), "day"])[:10],
       "{:,}".format(int(span["occurrences"].max())))
)

C.section("热搜热度与站内发帖量", "每个点是一个同时登上热搜、并在推文中出现的话题")
corr = {
    "峰值热度": np.corrcoef(hs["occurrences"], hs["peak_heat"])[0, 1],
    "上榜次数": np.corrcoef(hs["occurrences"], hs["appearances"])[0, 1],
    "最高排名": np.corrcoef(hs["occurrences"], hs["best_rank"])[0, 1],
}
fig = go.Figure(go.Scatter(
    x=hs["occurrences"], y=hs["peak_heat"], mode="markers",
    marker=dict(size=5, color="rgba(31,58,95,0.45)", line=dict(width=0)),
    customdata=hs[["topic", "appearances", "best_rank"]].to_numpy(),
    hovertemplate="%{customdata[0]}<br>推文提及 %{x:,}<br>峰值热度 %{y:,}"
                  "<br>上榜 %{customdata[1]} 次 / 最高第 %{customdata[2]} 名<extra></extra>",
))
fig.update_layout(
    xaxis=dict(title="推文提及次数（对数）", type="log"),
    yaxis=dict(title="热搜峰值热度（对数）", type="log"),
)
C.style_fig(fig, height=460, legend=False)
st.plotly_chart(fig, width="stretch")
st.markdown(
    "推文量与峰值热度的相关系数 **%.3f**，与上榜次数 **%.3f**，与最高排名 **%.3f**——"
    "三者都接近 0，说明在疫情话题范围内，站内发帖量无法预测热搜热度。"
    % (corr["峰值热度"], corr["上榜次数"], corr["最高排名"])
)
st.caption(
    "注意口径：推文集本身按 179 个疫情关键词筛选，非疫情类热搜（如体育、娱乐）在推文侧没有对应文本，"
    "因此相关性被系统性削弱，结论只在疫情话题范围内成立。"
)

C.section("两类反差话题", "发帖最多的话题未必最热，反之亦然")
left, right = st.columns(2)
cols_show = ["topic", "occurrences", "peak_heat", "best_rank"]
rename = {"topic": "话题", "occurrences": "推文提及", "peak_heat": "峰值热度", "best_rank": "最高排名"}
with left:
    st.markdown("**发帖量最高**")
    st.dataframe(
        hs.sort_values("occurrences", ascending=False).head(8)[cols_show].rename(columns=rename),
        width="stretch", hide_index=True,
    )
with right:
    st.markdown("**热搜热度最高**")
    st.dataframe(
        hs.sort_values("peak_heat", ascending=False).head(8)[cols_show].rename(columns=rename),
        width="stretch", hide_index=True,
    )
