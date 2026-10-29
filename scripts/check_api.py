r"""对 8601 分析后端做契约回归；可在 dashboard 运行后重复执行。

用法：.venv\Scripts\python.exe scripts\check_api.py
"""

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8601"
FAILS = []


def call(path, params=None, timeout=40):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def wait_ready(path, params=None):
    deadline = time.time() + 40
    while time.time() < deadline:
        status, body = call(path, params)
        if status == 200:
            return body
        if status != 202:
            raise AssertionError("%s -> %s %s" % (path, status, body))
        time.sleep(1)
    raise AssertionError("%s 预热超过 40 秒" % path)


def check(cond, message):
    if not cond:
        FAILS.append(message)
        print("FAIL", message)
    else:
        print("ok  ", message)


def no_bad_numbers(value, path=""):
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        check(math.isfinite(value), "数字有限: %s" % (path or "root"))
    elif isinstance(value, dict):
        for key, item in value.items():
            no_bad_numbers(item, "%s.%s" % (path, key))
    elif isinstance(value, list):
        for i, item in enumerate(value[:50]):
            no_bad_numbers(item, "%s[%d]" % (path, i))


def get_page(path, params=None):
    body = wait_ready(path, params)
    no_bad_numbers(body, path)
    return body


def kpi(body, label):
    for item in body.get("kpis", []):
        if item.get("label") == label:
            return item
    raise AssertionError("缺少 KPI %s" % label)


def main():
    health = call("/api/health")[1]
    check(health.get("ok") is True, "health ok")
    print("health", health)

    overview = get_page("/api/overview")
    check(len(overview.get("daily", [])) == 102, "overview 102 天")
    check(kpi(overview, "微博推文")["value"] == "4089.4 万", "overview 推文基准")
    check(len(overview.get("inventory", [])) == 8, "overview 数据集 8 项")
    check(overview.get("span", {}).get("days") == 152, "overview span 152 天")

    geo = get_page("/api/geo")
    check(len(geo.get("grid", [])) == 26851, "geo 网格 26851")
    check(len(geo.get("province", [])) == 298, "geo 省份 298")
    check(kpi(geo, "覆盖网格")["value"] == "26,851", "geo 覆盖网格基准")
    check(len(geo.get("share", {}).get("rows", [])) == 912, "geo 占比 912 行")

    topics = get_page("/api/topics")
    check(len(topics.get("top20", [])) == 20, "topics Top20")
    check(len(topics.get("options", [])) == 60, "topics 选项 60")
    check(len(topics.get("scatter", [])) == 19064, "topics 热搜散点 19064")
    check(kpi(topics, "话题标签")["value"] == "564,870", "topics 话题基准")
    topic = topics["default_topic"]
    td = get_page("/api/topics/daily", {"topic": topic})
    check(td.get("topic") == topic and td.get("rows"), "topics daily")

    casc = get_page("/api/cascade")
    check(len(casc.get("bins", [])) == 11, "cascade 11 区间")
    check(kpi(casc, "转发级联")["value"] == "293,631", "cascade 基准")
    check(len(casc.get("top", [])) == 20, "cascade Top20")
    cg = get_page("/api/cascade/growth", {"orig_id": casc["candidates"][0]["orig_id"]})
    check(cg.get("rows"), "cascade growth")

    inf = get_page("/api/influence")
    check(kpi(inf, "转发图节点")["value"] == "2,336,558", "influence 节点基准")
    check(len(inf.get("communities", [])) == 20, "influence 社区 Top20")
    comm = get_page("/api/influence/community", {"id": inf["default_community"]})
    check(comm.get("size", 0) > 0 and comm.get("gender"), "influence community")

    prof = get_page("/api/profile", {"user_id": "a7cc49c3878a4842"})
    check(prof.get("status") == "ok", "profile 默认用户 ok")
    check(prof.get("profile") and prof.get("graph"), "profile 画像与图指标")
    bad = get_page("/api/profile", {"user_id": "0000000000000000"})
    check(bad.get("status") == "invalid", "profile 未知 id invalid")

    rel = get_page("/api/relations")
    check(rel.get("status") == "ok", "relations 默认 ok")
    check(len(rel.get("path", [])) >= 2 and rel.get("rows"), "relations 路径")
    check(rel.get("directions") and rel.get("one_hop"), "relations 方向与一跳")

    sim = get_page("/api/simulate")
    check(sim.get("seed") and sim.get("seeds"), "simulate 首包")
    check(len(sim.get("growth", [])) == 9, "simulate rounds=8 增长 9 点")
    sens = get_page("/api/simulate/sensitivity", {"seed": sim["seed"]})
    check(len(sens.get("probs", [])) == 8 and len(sens.get("finals", [])) == 8, "sensitivity 8 点")
    probe = get_page("/api/simulate/probe", {"seed": sim["seed"]})
    check(len(probe.get("rows", [])) == 3, "probe 3 起点")

    status, body = call("/api/topics/daily", {"topic": "__not_a_topic__"})
    check(status == 400 and body.get("ok") is False, "topics 非法 topic -> 400")
    status, body = call("/api/influence/community", {"id": 999999999})
    check(status == 400 and body.get("ok") is False, "community 非法 id -> 400")
    status, body = call("/api/relations", {"a": "x", "b": "y"})
    check(status in (200, 202) and body.get("status") in ("invalid", "warming"), "relations 未知 id")
    status, body = call("/api/not-exists")
    check(status == 404 and body.get("ok") is False, "未知 API -> 404")

    if FAILS:
        print("\n%d 项失败" % len(FAILS))
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())