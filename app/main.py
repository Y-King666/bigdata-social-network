"""社交网络分析系统 —— 界面入口。

用 st.navigation 组织多页，页面的公共依赖由 common.py 提供。
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as C  # noqa: E402

st.set_page_config(
    page_title="社交网络分析系统",
    page_icon=":material/hub:",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(C.CSS, unsafe_allow_html=True)

PAGES = {
    "实时监测": [
        st.Page("views/live.py", title="监测大屏", icon=":material/sensors:"),
    ],
    "历史分析": [
        st.Page("views/overview.py", title="数据概览", icon=":material/insights:", default=True),
        st.Page("views/geo.py", title="空间热点", icon=":material/place:"),
        st.Page("views/topics.py", title="热点话题", icon=":material/local_fire_department:"),
        st.Page("views/cascade.py", title="传播分析", icon=":material/bolt:"),
        st.Page("views/influence.py", title="影响力与社区", icon=":material/hub:"),
        st.Page("views/profile.py", title="用户画像查询", icon=":material/person_search:"),
        st.Page("views/relations.py", title="关系发现", icon=":material/route:"),
        st.Page("views/simulate.py", title="传播模拟", icon=":material/science:"),
    ],
}

st.sidebar.markdown(
    '<div style="padding:4px 0 12px 0">'
    '<div style="font-size:17px;font-weight:700;color:%s">社交网络分析系统</div>'
    '<div style="font-size:12px;color:%s">Weibo-COV · 新冠疫情期间微博数据</div>'
    "</div>" % (C.PALETTE["secondary"], C.PALETTE["muted"]),
    unsafe_allow_html=True,
)

st.navigation(PAGES).run()