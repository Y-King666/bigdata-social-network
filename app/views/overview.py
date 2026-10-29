"""数据概览：项目规模、时间跨度与数据集构成。"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import common as C

C.page_header(
    "数据概览",
    "Weibo-COV：新冠疫情期间的公开微博数据，涵盖推文原文、用户画像、"
    "地理标签、话题与转发关系五个部分",
)

inv = C.dataset_inventory()
rows = dict(zip(inv["数据集"], inv["记录数"]))

daily = C.load_sentiment_daily().assign(day=lambda d: pd.to_datetime(d["day"]))
span = "%s 至 %s" % (str(daily["day"].min())[:10], str(daily["day"].max())[:10])

C.kpi_row([
    ("微博推文", C.human(rows["推文原文"]), span),
    ("用户画像", C.human(rows["用户画像"]), "性别 / 地区 / 生日 / 粉丝数"),
    ("带坐标推文", C.human(rows["带坐标推文"]), "含 GPS 标签，可做空间分析"),
    ("用户级转发边", C.human(rows["用户级转发边"]), "转发关系图的有向边"),
])

# 全量采集起点：此前每日样本量仅数千条，占比在 30%~80% 间剧烈跳动，不参与展示
FULL_SCALE_DAY = "2020-01-20"
full = daily[daily["day"] >= FULL_SCALE_DAY]

C.section(
    "时间跨度与情感基调",
    "全部 %d 天（2019-12-01 至 2020-04-30）；下图自 2020-01-20 全量采集起点起，"
    "共 %d 天，正面占比稳定在 65%% 以上" % (len(daily), len(full)),
)

fig = go.Figure()
fig.add_trace(go.Bar(
    x=full["day"], y=full["posts"], name="每日推文量",
    marker=dict(color="rgba(31,58,95,0.55)"), yaxis="y",
))
fig.add_trace(go.Scatter(
    x=full["day"], y=full["positive_share"] * 100, name="正面推文占比（右轴）",
    line=dict(color=C.PALETTE["primary"], width=2.4), yaxis="y2",
))
fig.update_layout(
    yaxis=dict(title="每日推文量"),
    yaxis2=dict(title="正面占比 (%)", overlaying="y", side="right",
                showgrid=False, range=[60, 92], ticksuffix="%"),
    bargap=0.1,
)
C.style_fig(fig, height=400)
st.plotly_chart(fig, width="stretch")

C.section("数据集清单")
st.dataframe(
    inv.assign(记录数=inv["记录数"].map(lambda v: "{:,}".format(int(v)))),
    width="stretch", hide_index=True,
)

C.section("系统架构", "从数据接入到交互应用的四层结构")
layers = [
    ("数据接入层", "公开数据集 Weibo-COV 与热搜榜单 CSV\n统一解析为 Parquet 列式存储"),
    ("计算层", "Spark 分布式聚合（4.1 亿次话题提及归并）\nPython 多进程词典情感打分\nLouvain / Leiden 社区发现、PageRank"),
    ("存储层", "Parquet 分片存储 + 面向查询的服务层索引\n按 user_id 范围重排，支持毫秒级单用户检索"),
    ("应用层", "本系统：8 个交互页面\n覆盖空间、话题、传播、关系与模拟"),
]
cols = st.columns(4)
for col, (name, desc) in zip(cols, layers):
    col.markdown(
        '<div style="background:#F7F9FC;border-top:3px solid %s;border-radius:4px;'
        'padding:12px 14px;height:150px">'
        '<div style="font-weight:600;color:%s;margin-bottom:6px">%s</div>'
        '<div style="font-size:13px;color:%s;white-space:pre-line;line-height:1.7">%s</div></div>'
        % (C.PALETTE["primary"], C.PALETTE["secondary"], name, C.PALETTE["muted"], desc),
        unsafe_allow_html=True,
    )
