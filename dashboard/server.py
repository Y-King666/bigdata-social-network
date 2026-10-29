"""监测大屏后端：只读 stream/hot 的分钟级快照，并把控制指令写回 control.json。

浏览器端每 0.5 秒拉取一次 /api/snapshot；快照只包含最近 60 分钟的稠密分钟序列，
这样前端滚动图表和分钟表时不需要自己处理空洞。
"""

import json
import mimetypes
import os
import sys
import threading
import time
import traceback
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stream"))
import config
import graph
import history

HOST = "127.0.0.1"
PORT = 8601
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
WINDOW_MINUTES = 60
ALERT_HISTORY_MINUTES = 300
ALLOWED_SPEEDS = {1.0, 2.0, 5.0, 10.0}
ALERT_STATUSES = {"新", "已确认", "已忽略"}

_CONTROL_LOCK = threading.Lock()
_ACK_LOCK = threading.Lock()


def _read_json(path, default):
    for _ in range(3):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            time.sleep(0.02)
    return dict(default)


def _file_age(path):
    try:
        return round(time.time() - os.path.getmtime(path), 2)
    except OSError:
        return -1.0


def _epoch(value):
    """把 naive 时间（北京墙钟）当作 UTC 的 epoch 秒，前端用 getUTC* 还原显示。"""
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    return int(ts.value // 1_000_000_000)


def _clean(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _int(value, default=0):
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parquet(name):
    path = os.path.join(config.HOT, name)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pq.read_table(path).to_pandas()
    except Exception:
        traceback.print_exc()
        return pd.DataFrame()


def _load_acks():
    return _read_json(config.ACKS, {})


def _dense_minutes(rows, start_ts, sim_ts):
    if sim_ts is None:
        return []
    end = (int(sim_ts) // 60) * 60
    begin = max((int(start_ts) // 60) * 60, end - (WINDOW_MINUTES - 1) * 60)
    if begin > end:
        return []

    by_t = {}
    if not rows.empty and "minute" in rows.columns:
        for row in rows.itertuples(index=False):
            t = _epoch(row.minute)
            if t is not None:
                by_t[t] = row

    out = []
    for t in range(begin, end + 1, 60):
        row = by_t.get(t)
        if row is None:
            out.append({
                "t": t,
                "posts": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "reposts": 0,
                "top_topic": "",
                "top_region": "",
                "has_data": False,
            })
        else:
            out.append({
                "t": t,
                "posts": _int(getattr(row, "posts", 0)),
                "positive": _int(getattr(row, "positive", 0)),
                "negative": _int(getattr(row, "negative", 0)),
                "neutral": _int(getattr(row, "neutral", 0)),
                "reposts": _int(getattr(row, "reposts", 0)),
                "top_topic": _clean(getattr(row, "top_topic", "")),
                "top_region": _clean(getattr(row, "top_region", "")),
                "has_data": True,
            })
    return out


def _rank(rows, key_col, sim_ts, drop_unknown=False):
    if rows.empty or key_col not in rows.columns or "minute" not in rows.columns:
        return []
    cutoff = int(sim_ts) - (WINDOW_MINUTES - 1) * 60
    counts = {}
    for row in rows.itertuples(index=False):
        t = _epoch(getattr(row, "minute", None))
        if t is None or t < cutoff:
            continue
        key = _clean(getattr(row, key_col, ""))
        if not key or (drop_unknown and key in ("未知", "其他")):
            continue
        counts[key] = counts.get(key, 0) + _int(getattr(row, "cnt", 0))
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]
    return [{"key": key, "count": count} for key, count in ordered]


def _alerts(rows, sim_ts, acks):
    if rows.empty:
        return []
    cutoff = int(sim_ts) - ALERT_HISTORY_MINUTES * 60
    items = []
    for row in rows.itertuples(index=False):
        t = _epoch(getattr(row, "t", None))
        if t is None or t < cutoff:
            continue
        alert_id = _clean(getattr(row, "id", ""))
        items.append({
            "id": alert_id,
            "t": t,
            "type": _clean(getattr(row, "type", "")),
            "key": _clean(getattr(row, "key", "")),
            "value": _float(getattr(row, "value", 0.0)),
            "baseline": _float(getattr(row, "baseline", 0.0)),
            "level": _clean(getattr(row, "level", "")),
            "status": acks.get(alert_id, "新") if alert_id else "新",
        })
    items.sort(key=lambda item: item["t"], reverse=True)
    return items[:12]


def _phase(ctl, meta, state, meta_match, state_match, stream_age):
    if ctl.get("paused"):
        return "paused"
    if not meta_match:
        if state_match and state.get("phase") in ("waiting", "running", "catchup", "finished"):
            return "waiting"
        return "resetting"
    if state_match and state.get("phase") == "catchup":
        return "catchup"
    if state_match and state.get("phase") == "finished":
        return "finished"
    if stream_age is None or stream_age > 6:
        return "stalled"
    return "running"


def snapshot():
    ctl = config.read_control()
    run_id = _int(ctl.get("run_id"), 0)
    start_ts = _epoch(ctl.get("start_time")) or 0
    meta = _read_json(os.path.join(config.HOT, "live_meta.json"), {})
    state = _read_json(config.STATE, {})

    meta_match = bool(meta) and _int(meta.get("run_id"), -1) == run_id
    state_match = bool(state) and _int(state.get("run_id"), -1) == run_id
    stream_age = _file_age(os.path.join(config.HOT, "live_meta.json"))
    replay_age = _file_age(config.STATE)

    if meta_match:
        sim_ts = _epoch(meta.get("sim_time")) or start_ts
    else:
        sim_ts = start_ts

    minutes = []
    topics = []
    regions = []
    alerts = []
    if meta_match:
        minutes = _dense_minutes(_parquet("live_minutes.parquet"), start_ts, sim_ts)
        topics = _rank(_parquet("live_topic_minutes.parquet"), "topic", sim_ts)
        regions = _rank(_parquet("live_region_minutes.parquet"), "region", sim_ts, drop_unknown=True)
        alerts = _alerts(_parquet("live_alerts.parquet"), sim_ts, _load_acks())

    if meta_match:
        kpi = {
            "sim_time": sim_ts,
            "total_posts": _int(meta.get("total_posts")),
            "rate": _int(meta.get("rate")),
            "positive_share": _float(meta.get("positive_share")),
            "negative_share": _float(meta.get("negative_share")),
            "neutral": _int(meta.get("neutral")),
            "reposts": _int(meta.get("reposts")),
            "alerts": _int(meta.get("alerts")),
            "backlog": _int(meta.get("backlog")),
            "batch": _int(meta.get("batch")),
            "batch_posts": _int(meta.get("batch_posts")),
            "batch_seconds": _float(meta.get("batch_seconds")),
        }
    else:
        kpi = {
            "sim_time": start_ts,
            "total_posts": 0,
            "rate": 0,
            "positive_share": 0.0,
            "negative_share": 0.0,
            "neutral": 0,
            "reposts": 0,
            "alerts": 0,
            "backlog": 0,
            "batch": 0,
            "batch_posts": 0,
            "batch_seconds": 0.0,
        }

    phase = _phase(ctl, meta, state, meta_match, state_match, stream_age)

    return {
        "run_id": run_id,
        "start_ts": start_ts,
        "phase": phase,
        "window_minutes": WINDOW_MINUTES,
        "server_time": round(time.time(), 3),
        "minutes": minutes,
        "rank": {"topics": topics, "regions": regions},
        "alerts": alerts,
        "kpi": kpi,
        "status": {
            "speed": _float(ctl.get("speed"), 1.0),
            "paused": bool(ctl.get("paused", False)),
            "start_time": _clean(ctl.get("start_time")),
            "backlog": _int(meta.get("backlog")) if meta_match else 0,
            "replay_age": replay_age,
            "stream_age": stream_age,
            "replay_phase": _clean(state.get("phase", "offline")),
            "replay_sim_time": _clean(state.get("sim_time", "")),
        },
    }


@lru_cache(maxsize=64)
def _simulate_cached(seed, prob, rounds):
    return graph.simulate(seed, prob, rounds)


@lru_cache(maxsize=64)
def _sensitivity_cached(seed, rounds, probs):
    return graph.sensitivity(seed, list(probs), rounds)


@lru_cache(maxsize=64)
def _probe_cached(prob, rounds):
    result = graph.probe(history.probe_user_ids(), prob, rounds)
    if result is None:
        return None
    rows = []
    for item in result["rows"]:
        info = history.graph_user(item["user_id"])
        if info.empty:
            rows.append({"user_id": item["user_id"], "reposters": 0,
                         "fans_num": 0, "infected": item["infected"]})
            continue
        row = info.iloc[0]
        rows.append({
            "user_id": item["user_id"],
            "reposters": _int(row["in_degree"]),
            "fans_num": _int(row["fans_num"]),
            "infected": item["infected"],
        })
    return rows


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 1_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}

    def _static(self, path):
        rel = unquote(path).lstrip("/\\")
        if not rel:
            rel = "index.html"
        full = os.path.abspath(os.path.join(WEB_DIR, rel))
        if os.path.commonpath([WEB_DIR, full]) != WEB_DIR:
            self._send(404, b"Not Found", "text/plain; charset=utf-8")
            return
        if not os.path.isfile(full):
            if "." in os.path.basename(rel):
                self._send(404, b"Not Found", "text/plain; charset=utf-8")
                return
            full = os.path.join(WEB_DIR, "index.html")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(full, "rb") as fh:
            body = fh.read()
        self._send(200, body, ctype)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/snapshot":
            try:
                self._json(200, snapshot())
            except Exception as exc:
                traceback.print_exc()
                self._json(500, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/health":
            self._json(200, {
                "ok": True,
                "time": time.time(),
                "phase": snapshot()["phase"],
                "graph_ready": graph.ready(),
                "graph_building": graph.building(),
            })
            return
        if parsed.path.startswith("/api/"):
            self._history_get(parsed)
            return
        self._static(parsed.path)

    def do_HEAD(self):
        self.do_GET()

    def _history_get(self, parsed):
        query = parse_qs(parsed.query)
        path = parsed.path
        try:
            if path == "/api/overview":
                self._json(200, history.overview())
                return
            if path == "/api/geo":
                self._json(200, history.geo())
                return
            if path == "/api/topics":
                self._json(200, history.topics())
                return
            if path == "/api/topics/daily":
                topic = (query.get("topic") or [""])[0]
                if topic not in history.topic_options():
                    self._json(400, {"ok": False, "error": "unknown topic"})
                    return
                self._json(200, history.topic_daily(topic))
                return
            if path == "/api/cascade":
                self._json(200, history.cascade())
                return
            if path == "/api/cascade/growth":
                orig_id = (query.get("orig_id") or [""])[0]
                if not orig_id:
                    self._json(400, {"ok": False, "error": "orig_id is required"})
                    return
                self._json(200, history.cascade_growth(orig_id))
                return
            if path == "/api/influence":
                self._json(200, history.influence())
                return
            if path == "/api/influence/community":
                try:
                    cid = int((query.get("id") or [""])[0])
                except ValueError:
                    self._json(400, {"ok": False, "error": "id must be an integer"})
                    return
                body = history.community(cid)
                if body is None:
                    self._json(400, {"ok": False, "error": "unknown community"})
                    return
                self._json(200, body)
                return
            if path == "/api/profile":
                user_id = (query.get("user_id") or [""])[0].strip()
                if not user_id:
                    self._json(400, {"ok": False, "error": "user_id is required"})
                    return
                self._json(200, history.profile(user_id))
                return
            if path == "/api/relations":
                a = (query.get("a") or [""])[0].strip()
                b = (query.get("b") or [""])[0].strip()
                defaults = history.pagerank_ids()
                a = a or defaults[0]
                b = b or defaults[3]
                body = graph.relations(a, b)
                if body["status"] == "graph_not_ready":
                    self._json(202, {"ok": False, "status": "warming", "retry_after": 1})
                    return
                body.update({"defaults": [defaults[0], defaults[3]], "a": a, "b": b})
                self._json(200, body)
                return
            if path == "/api/simulate":
                body = self._simulate(query)
                if body is None:
                    return
                self._json(200, body)
                return
            if path == "/api/simulate/sensitivity":
                body = self._sensitivity(query)
                if body is None:
                    return
                self._json(200, body)
                return
            if path == "/api/simulate/probe":
                body = self._probe(query)
                if body is None:
                    return
                self._json(200, body)
                return
            self._json(404, {"ok": False, "error": "unknown api"})
        except Exception as exc:
            traceback.print_exc()
            self._json(500, {"ok": False, "error": str(exc)})

    def _params(self, query):
        seed = (query.get("seed") or [""])[0].strip()
        try:
            prob = float((query.get("prob") or ["0.05"])[0])
            rounds = int((query.get("rounds") or ["8"])[0])
        except ValueError:
            self._json(400, {"ok": False, "error": "prob/rounds must be numeric"})
            return None
        if not 0.01 <= prob <= 0.30 or not 1 <= rounds <= 15:
            self._json(400, {"ok": False, "error": "prob must be 0.01-0.30 and rounds 1-15"})
            return None
        if not seed:
            seed = history.simulate_seeds()[0]["user_id"]
        if not graph.ready():
            self._json(202, {"ok": False, "status": "warming", "retry_after": 1})
            return None
        return seed, prob, rounds

    def _simulate(self, query):
        params = self._params(query)
        if params is None:
            return None
        seed, prob, rounds = params
        result = _simulate_cached(seed, prob, rounds)
        if result is None:
            self._json(400, {"ok": False, "error": "seed is not in the graph"})
            return None
        growth = result["growth"]
        cumulative = []
        running = 0
        for i, value in enumerate(growth):
            running += value
            cumulative.append(running)
        peak = int(max(range(len(growth)), key=lambda i: growth[i]))
        row = history.graph_user(seed)
        observed = _int(row.iloc[0]["in_degree"]) if not row.empty else 0
        return {
            "seed": seed,
            "seeds": history.simulate_seeds(),
            "prob": prob,
            "rounds": rounds,
            "kpis": [
                {"label": "最终感染人数", "value": "{:,}".format(result["infected"]),
                 "hint": "占全网 %.3f%%" % (result["infected"] / 2359438 * 100)},
                {"label": "峰值轮次", "value": "第 %d 轮" % peak,
                 "hint": "单轮新增最多的一轮"},
                {"label": "实测被转发", "value": "{:,}".format(observed),
                 "hint": "该用户在原数据中的真实转发量"},
                {"label": "传播概率", "value": "%.2f" % prob,
                 "hint": "每条边的独立激活概率"},
            ],
            "growth": [
                {"round": i, "new": value, "cumulative": cumulative[i]}
                for i, value in enumerate(growth)
            ],
            "notes": [
                "起点差距悬殊：被转发最多的用户一轮即可激活数万人，而被转发量中等的用户几乎无法扩散。"
                "原因是转发关系图呈星形结构——94.2% 的节点只转发、从未被转发，"
                "所以传播几乎全在“超级节点 → 普通用户”这一层内完成，二跳扩散极少。",
                "模型要点：独立级联（Independent Cascade）假设每条边以相同概率独立激活一次，"
                "被 k 个已激活用户指向的节点被激活概率为 1-(1-p)^k。"
                "它只依赖网络结构，不考虑内容质量、时间衰减与平台推荐，"
                "因此结果应与实测数据分析对照阅读——真实传播中“粉丝数相差 45 万倍、传播规模却相当”"
                "正说明结构之外的偶然因素同样重要。",
            ],
            "caption": "",
        }

    def _sensitivity(self, query):
        params = self._params(query)
        if params is None:
            return None
        seed, prob, rounds = params
        probs = [0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.18, 0.25]
        result = _sensitivity_cached(seed, rounds, tuple(probs))
        if result is None:
            self._json(400, {"ok": False, "error": "seed is not in the graph"})
            return None
        result["current"] = prob
        return result

    def _probe(self, query):
        params = self._params(query)
        if params is None:
            return None
        seed, prob, rounds = params
        rows = _probe_cached(prob, rounds)
        if rows is None:
            self._json(400, {"ok": False, "error": "probe failed"})
            return None
        return {"rows": rows}

    def do_POST(self):
        payload = self._body()
        parsed = urlparse(self.path)
        if parsed.path == "/api/control":
            speed = payload.get("speed")
            paused = payload.get("paused")
            if speed is not None and float(speed) not in ALLOWED_SPEEDS:
                self._json(400, {"ok": False, "error": "speed must be 1/2/5/10"})
                return
            if paused is not None and not isinstance(paused, bool):
                self._json(400, {"ok": False, "error": "paused must be boolean"})
                return
            with _CONTROL_LOCK:
                ctl = config.read_control()
                if speed is not None:
                    ctl["speed"] = float(speed)
                if paused is not None:
                    ctl["paused"] = paused
                config.write_json(config.CONTROL, ctl)
            self._json(200, {"ok": True, "control": ctl})
            return

        if parsed.path == "/api/reset":
            with _CONTROL_LOCK:
                ctl = config.read_control()
                ctl["schema"] = config.CONTROL_SCHEMA
                ctl["run_id"] = _int(ctl.get("run_id"), 0) + 1
                ctl["start_time"] = config.DEFAULT_START
                ctl["paused"] = False
                config.write_json(config.CONTROL, ctl)
                try:
                    os.remove(config.ACKS)
                except OSError:
                    pass
            self._json(200, {"ok": True, "run_id": ctl["run_id"],
                             "start_ts": _epoch(config.DEFAULT_START)})
            return

        if parsed.path == "/api/ack":
            alert_id = str(payload.get("id") or "")
            status = str(payload.get("status") or "")
            if not alert_id or status not in ALERT_STATUSES:
                self._json(400, {"ok": False, "error": "invalid id or status"})
                return
            with _ACK_LOCK:
                acks = _load_acks()
                if not isinstance(acks, dict):
                    acks = {}
                acks[alert_id] = status
                config.write_json(config.ACKS, acks)
            self._json(200, {"ok": True, "id": alert_id, "status": status})
            return

        self._json(404, {"ok": False, "error": "unknown api"})


def main():
    os.makedirs(config.HOT, exist_ok=True)
    graph.start_warmup()
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer.daemon_threads = True
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("DASHBOARD_READY http://%s:%d" % (HOST, PORT), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()