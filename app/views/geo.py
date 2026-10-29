"""空间热点：带地理标签微博的分布与省份发言占比。"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import common as C

C.page_header(
    "空间热点",
    "带 GPS 坐标的微博按 0.25° 网格聚合后的分布，以及剥离采集节奏后的省份发言占比",
)

grid = C.load_grid()
prov = C.load_province()
share = C.load_share()

inland = grid[(grid["glon"] >= 73) & (grid["glon"] <= 136) & (grid["glat"] >= 3) & (grid["glat"] <= 54)]
inland_share = inland["posts"].sum() / grid["posts"].sum()
top_cell = grid.sort_values("posts", ascending=False).iloc[0]

C.kpi_row([
    ("覆盖网格", "{:,}".format(len(grid)), "0.25° × 0.25° 经纬网格"),
    ("最热网格发帖量", C.human(top_cell["posts"]),
     "%.2f°E / %.2f°N" % (top_cell["glon"], top_cell["glat"])),
    ("用户省份取值", "{:,}".format(len(prov)), "用户资料省份字段去重后的取值数"),
    ("境内推文占比", "%.2f%%" % (inland_share * 100), "经纬度落在国境范围内"),
])

C.section("空间热点分布", "仅展示发帖量 ≥ 500 的网格；点面积为对数发帖量，颜色越深表示越密集")
hot = grid[grid["posts"] >= 500].copy()
hot["v"] = np.log10(hot["posts"])
fig = go.Figure(go.Scattergeo(
    lon=hot["glon"], lat=hot["glat"], mode="markers",
    marker=dict(
        size=(hot["v"] - hot["v"].min() + 0.6) * 4.5,
        color=hot["v"],
        colorscale=[[0, "#FFF6D6"], [0.35, "#FBD27A"], [0.62, "#F2913F"],
                    [0.82, "#D6453C"], [1, "#7E1B1B"]],
        showscale=True, colorbar=dict(title="log₁₀ 发帖量", thickness=13, len=0.62),
        line=dict(width=0), opacity=0.85,
    ),
    customdata=np.stack([hot["posts"], hot["users"], hot["reposts"]], axis=-1),
    hovertemplate="%.2f°E / %.2f°N<br>发帖 %{customdata[0]:,}<br>用户 %{customdata[1]:,}"
                  "<br>转发 %{customdata[2]:,}<extra></extra>".replace("%.2f", "%{lon:.2f}"),
))
fig.update_geos(
    scope="asia", projection_type="mercator",
    lataxis_range=[16, 54], lonaxis_range=[74, 135],
    showland=True, landcolor="#F4F6F8", showcountries=True, countrycolor="#D8DEE6",
    showocean=True, oceancolor="#FFFFFF", showcoastlines=True, coastlinecolor="#D8DEE6",
    showframe=False, bgcolor="rgba(0,0,0,0)",
)
C.style_fig(fig, height=620, legend=False)
st.plotly_chart(fig, width="stretch")

C.section("省份推文量与传播强度", "按用户资料省份归属统计，条形末尾为平均转发量")
top = prov.sort_values("posts", ascending=False).head(15).iloc[::-1]
fig = go.Figure(go.Bar(
    x=top["posts"], y=top["province"], orientation="h",
    marker=dict(color=C.PALETTE["primary"]),
    text=["平均转发 %.2f" % v for v in top["avg_reposts"]],
    textposition="outside", cliponaxis=False,
))
fig.update_layout(xaxis=dict(title="推文数（条）"), margin=dict(r=110))
C.style_fig(fig, height=520, legend=False)
st.plotly_chart(fig, width="stretch")

C.section("省份发言占比（归一化）", "除以当日全量推文量，剥离采集规模的整体增长")
available = sorted(share["province"].unique())
picked = st.multiselect(
    "选择省份", available,
    default=[p for p in ["湖北", "广东", "北京", "上海", "浙江", "海外"] if p in available],
)
if picked:
    sub = share[share["province"].isin(picked)]
    fig = go.Figure()
    for i, name in enumerate(picked):
        part = sub[sub["province"] == name]
        fig.add_trace(go.Scatter(
            x=part["day"], y=part["share"] * 100, name=name, mode="lines",
            line=dict(color=C.SERIES[i % len(C.SERIES)], width=2),
        ))
    fig.add_vrect(x0="2020-01-23", x1="2020-04-08", fillcolor="#E8A33D",
                  opacity=0.12, line_width=0, annotation_text="武汉封城期",
                  annotation_position="top left")
    fig.update_layout(yaxis=dict(title="占当日全部带坐标推文的比例 (%)", ticksuffix="%"))
    C.style_fig(fig, height=440)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "湖北的绝对发帖量最高值出现在 4 月，但如果看占比，峰值恰好落在封城窗口内——"
        "归一化纠正了采集节奏造成的假象。"
    )
