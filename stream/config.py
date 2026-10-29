"""回放链路的共用路径与默认参数。

三个进程（回放器、流计算、大屏后端）都以这里为唯一约定：
回放器读 data/stream_events，往 stream/spool 投递事件；
流计算读 spool，把分钟级聚合写到 stream/hot；
大屏后端只读 stream/hot 与 state.json，不碰原始数据。
"""

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
EVENTS = os.path.join(DATA, "stream_events")

STREAM_DIR = os.path.join(ROOT, "stream")
SPOOL = os.path.join(STREAM_DIR, "spool")
HOT = os.path.join(STREAM_DIR, "hot")
CONTROL = os.path.join(STREAM_DIR, "control.json")
STATE = os.path.join(STREAM_DIR, "state.json")
ACK = os.path.join(STREAM_DIR, "ack.json")
ACKS = os.path.join(HOT, "alert_acks.json")

CONTROL_SCHEMA = 2
DEFAULT_START = "2020-01-22T00:00:00"
DEFAULT_SPEED = 1.0

TICK_SECONDS = 0.5      # 回放器每 0.5 秒真实时间推进一次虚拟时钟
MAX_LAG_MINUTES = 3     # 回放领先流任务太多时停钟，避免大屏“瞬移”
HISTORY_MINUTES = 300   # 热层保留的模拟分钟数（5 小时）
RANK_MINUTES = 60       # 排名与告警的滚动窗口（60 分钟）

DEFAULT_CONTROL = {
    "schema": CONTROL_SCHEMA,
    "speed": DEFAULT_SPEED,   # 1 秒真实时间推进多少模拟分钟
    "paused": False,
    "start_time": DEFAULT_START,
    "run_id": 0,              # 每次重置加一，回放器与流任务据此清空重来
}


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return dict(default)


def write_json(path, payload, attempts=20):
    """原子替换；Windows 上读取方持有句柄时 os.replace 可能短暂失败。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.05)


def read_control():
    """读取控制文件；旧版按天回放的字段在这里一次性迁移到倍速语义。"""
    ctl = read_json(CONTROL, DEFAULT_CONTROL)
    if ctl.get("schema") != CONTROL_SCHEMA:
        old_run = int(ctl.get("run_id", 0))
        old_start = ctl.get("start_day")
        ctl = dict(DEFAULT_CONTROL)
        ctl["run_id"] = old_run
        if old_start:
            ctl["start_time"] = str(old_start) + "T00:00:00"
        write_json(CONTROL, ctl)
    ctl["run_id"] = int(ctl.get("run_id", 0))
    ctl["speed"] = float(ctl.get("speed", DEFAULT_SPEED))
    ctl["paused"] = bool(ctl.get("paused", False))
    ctl["start_time"] = str(ctl.get("start_time") or DEFAULT_START)
    return ctl
