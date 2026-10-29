"""逐秒监测大屏入口。

大屏由 dashboard/server.py + dashboard/web 下的原生前端提供：逐秒数据、
60 秒滚动窗口和竞速榜单动画都在浏览器里完成。Streamlit 这一页负责
确保后端已启动，并把大屏嵌入当前页面；独立窗口更适合投屏。
"""

import os
import subprocess
import sys
import time
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

import common as C

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DASHBOARD_URL = "http://127.0.0.1:8601/"
SERVER = os.path.join(ROOT, "dashboard", "server.py")
LOG = os.path.join(ROOT, "dashboard", "server.log")

_started = False


def _healthy():
    try:
        with urllib.request.urlopen(DASHBOARD_URL + "api/health", timeout=0.8):
            return True
    except OSError:
        return False


def ensure_server():
    global _started
    if _healthy():
        return True
    if _started:
        return False
    _started = True
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    with open(LOG, "ab") as log:
        subprocess.Popen(
            [sys.executable, SERVER],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            **kwargs,
        )
    for _ in range(30):
        if _healthy():
            return True
        time.sleep(0.5)
    return False


C.page_header(
    "实时监测",
    "逐秒回放的监测大屏：1x / 2x / 5x / 10x 倍速，60 秒滚动窗口，"
    "发帖、情感、话题与省份排名按秒刷新",
)

st.markdown(
    """
    <style>
    [data-testid="stHeader"] { display: none; }
    [data-testid="stAppViewContainer"] .block-container { padding-top: 0.6rem; }
    [data-testid="stAppViewContainer"] iframe { border: 0; display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

if not ensure_server():
    st.error("逐秒大屏后端未启动。请检查 dashboard/server.log，或运行 stream/start_all.ps1。")
    st.stop()

st.link_button("在新窗口打开逐秒大屏（推荐投屏）", DASHBOARD_URL, width="stretch")
components.iframe(DASHBOARD_URL, height=820, scrolling=False)
