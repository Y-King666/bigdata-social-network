"""用户画像查询：输入任意用户 id，查看画像、图指标与转发行为。"""

import streamlit as st

import common as C

C.page_header("用户画像查询", "输入任意用户 id，从 2,000 万条用户画像和 326 万条转发关系中查询")

DEFAULT = "a7cc49c3878a4842"
uid = st.text_input("用户 id", value=DEFAULT, help="用户 id 是 16 位十六进制字符串").strip()


@st.cache_data(show_spinner=False)
def graph_row(uid):
    df = C.load_graph_users()
    return df[df["user_id"] == uid]


@st.cache_data(show_spinner=False)
def edges_of(uid):
    """该用户相关的一跳转发关系（用户级去重后的边）。"""
    edges = C.load_user_edges()
    return edges[(edges["source_user"] == uid) | (edges["target_user"] == uid)]


if not uid:
    st.info("请输入用户 id。可以先到「影响力与社区」页面复制一个 id。")
    st.stop()

profile = C.lookup_profile(uid)
row = graph_row(uid)

if profile.empty and row.empty:
    st.warning("用户画像与转发图中都没有这个 id。注意 id 是 16 位十六进制字符串。")
    st.stop()

if not profile.empty:
    p = profile.iloc[0]
    C.kpi_row([
        ("粉丝数", "{:,}".format(int(p["fans_num"])), "资料中记录的粉丝量"),
        ("性别", p["gender"] or "未知", "来自用户画像"),
        ("所在地", "%s %s" % (p["province"] or "未知", p["city"] or ""), "来自用户画像"),
        ("会员等级", "%s 级" % p["vip_level"], "微博会员等级"),
    ])
else:
    st.warning("该用户不在 2,000 万条画像样本中，只能展示转发图指标。")

if not row.empty:
    r = row.iloc[0]
    C.section("转发图指标", "来自 326 万条用户级转发边")
    C.kpi_row([
        ("被转发次数", "{:,}".format(int(r["in_degree"])), "有多少人转发过他"),
        ("转发次数", "{:,}".format(int(r["out_degree"])), "他转发过多少人"),
        ("PageRank", "%.6f" % r["pagerank"], "全图影响力得分"),
        ("所属社区", "%s" % r["leiden"], "Leiden 社区编号"),
    ])

C.section("转发行为")
edges = edges_of(uid)
out_edges = edges[edges["source_user"] == uid]
in_edges = edges[edges["target_user"] == uid]
left, right = st.columns(2)
with left:
    st.markdown("**他转发过谁**（共 %s 条）" % "{:,}".format(len(out_edges)))
    if len(out_edges):
        top_out = (out_edges.groupby("target_user")
                   .agg(次数=("weight", "max"), 首次=("first_time", "min"))
                   .sort_values("次数", ascending=False).head(10))
        st.dataframe(top_out, width="stretch")
    else:
        st.caption("没有他发出的转发记录。")
with right:
    st.markdown("**谁转发过他**（共 %s 条）" % "{:,}".format(len(in_edges)))
    if len(in_edges):
        top_in = (in_edges.groupby("source_user")
                  .agg(次数=("weight", "max"), 首次=("first_time", "min"))
                  .sort_values("次数", ascending=False).head(10))
        st.dataframe(top_in, width="stretch")
    else:
        st.caption("没有他被人转发的记录。")
