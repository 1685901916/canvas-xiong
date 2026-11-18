"""画布平移/缩放帧时间测量（只读、轻量）。

- 只开一个无头 Chromium，测完就关；不加任何关闭节流的参数。
- 页面发出的所有非 GET 的 /api 请求（保存、touch、建节点……）一律拦下并回假的 200，
  所以可以直接打开真实画布测，不会改到任何数据。只放行只读的 /api/canvas-assets/check。
- --rev 可以把 canvas.js / canvas.css 换成某个 git 提交里的版本，用来做前后对比；
  不给 --rev 就用服务器当前提供的版本。

用法：
  python tools/canvas_perf_bench.py --canvas c1f6e9608e044f5584becd10c2198c99 --rev 9569007~1 --label before
  python tools/canvas_perf_bench.py --canvas c1f6e9608e044f5584becd10c2198c99 --label after
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:3001"
READ_ONLY_POSTS = ("/api/canvas-assets/check",)

FRAME_RECORDER = """
(() => {
  if (window.__bench) return;
  const b = window.__bench = {frames: [], rec: false, loaf: []};
  const loop = t => { if (b.rec) b.frames.push(t); requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
  try {
    new PerformanceObserver(list => {
      if (!b.rec) return;
      for (const e of list.getEntries()) b.loaf.push({d: e.duration, block: e.blockingDuration || 0,
        style: e.styleAndLayoutStart ? (e.startTime + e.duration - e.styleAndLayoutStart) : 0});
    }).observe({type: 'long-animation-frame', buffered: false});
  } catch (e) {}
})();
"""


def git_show(rev, path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, check=True).stdout


def summarize(frames):
    iv = [b - a for a, b in zip(frames, frames[1:])]
    if not iv:
        return {"frames": 0}
    iv_sorted = sorted(iv)
    q = lambda p: iv_sorted[min(len(iv_sorted) - 1, int(p * len(iv_sorted)))]
    return {
        "frames": len(frames),
        "p50_ms": round(q(0.50), 1),
        "p90_ms": round(q(0.90), 1),
        "p99_ms": round(q(0.99), 1),
        "max_ms": round(iv_sorted[-1], 1),
        "over_20ms": sum(1 for x in iv if x > 20),
        "over_50ms": sum(1 for x in iv if x > 50),
        "mean_ms": round(statistics.mean(iv), 1),
    }


def metrics(cdp):
    m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    keys = ("TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "LayoutCount", "RecalcStyleCount", "JSHeapUsedSize", "Nodes")
    return {k: m.get(k, 0) for k in keys}


def delta(a, b):
    out = {}
    for k in ("TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration"):
        out[k.replace("Duration", "_ms")] = round((b[k] - a[k]) * 1000, 0)
    out["layouts"] = int(b["LayoutCount"] - a["LayoutCount"])
    out["styles"] = int(b["RecalcStyleCount"] - a["RecalcStyleCount"])
    return out


def measure(page, cdp, name, action):
    page.evaluate("() => { __bench.frames = []; __bench.loaf = []; __bench.rec = true; }")
    m0 = metrics(cdp)
    t0 = time.perf_counter()
    action()
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    wall = time.perf_counter() - t0
    m1 = metrics(cdp)
    data = page.evaluate("() => { __bench.rec = false; return {frames: __bench.frames, loaf: __bench.loaf}; }")
    res = {"scenario": name, "wall_s": round(wall, 2), **summarize(data["frames"]), **delta(m0, m1)}
    loaf = data["loaf"]
    res["long_frames"] = len(loaf)
    res["long_frame_total_ms"] = round(sum(x["d"] for x in loaf), 0)
    return res


def profiled(page, cdp, action, top=25):
    """同时抓主线程 trace（按事件名汇总自耗时）和 JS 采样（按函数汇总自耗时）。"""
    events = []
    done = {"v": False}
    cdp.on("Tracing.dataCollected", lambda e: events.extend(e["value"]))
    cdp.on("Tracing.tracingComplete", lambda e: done.__setitem__("v", True))
    cdp.send("Profiler.enable")
    cdp.send("Profiler.setSamplingInterval", {"interval": 200})
    cdp.send("Tracing.start", {"categories": "devtools.timeline,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.invalidationTracking,blink,cc,gpu", "transferMode": "ReportEvents"})
    cdp.send("Profiler.start")
    action()
    prof = cdp.send("Profiler.stop")["profile"]
    cdp.send("Tracing.end")
    for _ in range(200):
        if done["v"]:
            break
        page.wait_for_timeout(50)
    # 主线程：找 CrRendererMain
    main_tid = None
    for e in events:
        if e.get("ph") == "M" and e.get("name") == "thread_name" and e.get("args", {}).get("name") == "CrRendererMain":
            main_tid = (e["pid"], e["tid"])
    by_name = {}
    stack = []
    xs = sorted([e for e in events if (e.get("pid"), e.get("tid")) == main_tid and e.get("ph") == "X" and "dur" in e], key=lambda e: (e["ts"], -e["dur"]))
    # 自耗时 = 自身时长 - 直接子事件时长
    for e in xs:
        while stack and stack[-1]["ts"] + stack[-1]["dur"] <= e["ts"]:
            stack.pop()
        if stack:
            stack[-1]["_child"] = stack[-1].get("_child", 0) + e["dur"]
        stack.append(e)
    for e in xs:
        self_us = e["dur"] - e.get("_child", 0)
        by_name[e["name"]] = by_name.get(e["name"], 0) + self_us
    trace_top = sorted(((round(v / 1000), k) for k, v in by_name.items()), reverse=True)[:top]
    # JS 采样
    nodes = {n["id"]: n for n in prof["nodes"]}
    counts = {}
    for sid in prof.get("samples", []):
        n = nodes[sid]
        cf = n["callFrame"]
        key = f"{cf['functionName'] or '(anon)'} {os.path.basename(cf['url'].split('?')[0])}:{cf['lineNumber'] + 1}"
        counts[key] = counts.get(key, 0) + 1
    total = max(1, len(prof.get("samples", [])))
    dt = (prof["endTime"] - prof["startTime"]) / 1000 / total
    js_top = sorted(((round(c * dt), k) for k, c in counts.items()), reverse=True)[:top]
    inval = {}
    for e in events:
        if e.get("name") in ("PaintInvalidationTracking", "LayoutInvalidationTracking", "StyleRecalcInvalidationTracking", "ScheduleStyleInvalidationTracking"):
            d = (e.get("args") or {}).get("data") or {}
            key = f"{e['name']}: {d.get('reason') or d.get('changedClass') or d.get('changedAttribute') or ''} @ {d.get('nodeName') or ''}"
            inval[key] = inval.get(key, 0) + 1
    paints = [((e.get("args") or {}).get("data") or {}) for e in events if e.get("name") == "Paint"]
    return {"trace_self_ms": trace_top, "js_self_ms": js_top, "paint_events": len(paints),
            "invalidations": sorted(((n, k) for k, n in inval.items()), reverse=True)[:top]}


def run(canvas_id, rev, label, step_sleep, profile_scenario="", inject_css="", only=""):
    blocked = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page = ctx.new_page()

            def api_route(route, request):
                url = request.url
                if request.method != "GET" and not any(s in url for s in READ_ONLY_POSTS):
                    blocked.append(f"{request.method} {url.split('?')[0].replace(BASE, '')}")
                    return route.fulfill(status=200, content_type="application/json", body="{}")
                return route.continue_()

            page.route("**/api/**", api_route)
            if rev:
                js, css = git_show(rev, "static/js/canvas.js"), git_show(rev, "static/css/canvas.css")
                page.route("**/static/js/canvas.js*", lambda r: r.fulfill(status=200, content_type="application/javascript", body=js))
                page.route("**/static/css/canvas.css*", lambda r: r.fulfill(status=200, content_type="text/css", body=css))
            page.add_init_script(FRAME_RECORDER)
            cdp = ctx.new_cdp_session(page)
            cdp.send("Performance.enable")

            t0 = time.perf_counter()
            page.goto(f"{BASE}/static/canvas.html?id={canvas_id}", wait_until="load")
            page.wait_for_function("() => typeof nodes !== 'undefined' && nodes.length > 0 && document.querySelectorAll('#nodes > .node').length >= nodes.length", timeout=60000)
            load_s = time.perf_counter() - t0
            page.wait_for_timeout(5000)  # 让视野内缩略图加载完
            info = page.evaluate("() => ({nodes: nodes.length, connections: connections.length, culled: document.querySelectorAll('#nodes > .node.is-culled').length, imgs: document.querySelectorAll('#nodes img').length, imgsLoaded: [...document.querySelectorAll('#nodes img')].filter(i => i.complete && i.naturalWidth).length, domNodes: document.getElementsByTagName('*').length})")
            if inject_css:
                page.add_style_tag(content=inject_css)
                page.wait_for_timeout(500)
            mm = page.evaluate("() => { if (typeof renderMinimap !== 'function') return null; const t = performance.now(); for (let i = 0; i < 10; i++) renderMinimap(); return +((performance.now() - t) / 10).toFixed(2); }")

            results = []
            cx, cy = 720, 450

            def pan(dx, dy, steps, regrab=30):
                def act():
                    page.mouse.move(cx, cy)
                    page.mouse.down(button="middle")
                    x, y = cx, cy
                    for i in range(steps):
                        x += dx
                        y += dy
                        page.mouse.move(x, y)
                        time.sleep(step_sleep)
                        if regrab and (i + 1) % regrab == 0:  # 鼠标拉回中心继续拖（松开再按）
                            page.mouse.up(button="middle")
                            page.mouse.move(cx, cy)
                            page.mouse.down(button="middle")
                            x, y = cx, cy
                    page.mouse.up(button="middle")
                return act

            def grab_release(times):
                def act():
                    page.mouse.move(cx, cy)
                    for _ in range(times):
                        page.mouse.down(button="middle")
                        time.sleep(0.1)
                        page.mouse.up(button="middle")
                        time.sleep(0.1)
                return act

            def zoom(direction, steps):
                def act():
                    page.mouse.move(cx, cy)
                    for _ in range(steps):
                        page.mouse.wheel(0, 100 * direction)
                        time.sleep(step_sleep * 2)
                return act

            scenarios = [
                ("pan@1x", pan(-20, -4, 240)),
                ("zoom out", zoom(1, 18)),
                ("pan zoomed-out", pan(-20, -6, 180)),
                # 原路拖回来：这一段的图都已加载过，看的是「稳定状态」而不是首次加载图片
                ("pan zoomed-out back", pan(20, 6, 180)),
                # 一次按住不松、慢慢拖：只看拖动中的每帧开销
                ("pan zoomed-out 1 grab", pan(-4, -2, 180, regrab=0)),
                # 只按下/松开 10 次不移动：看「开始/结束拖动」本身的卡顿
                ("grab/release x10", grab_release(10)),
                ("zoom in", zoom(-1, 18)),
            ]
            profile = None
            if only:
                keep = set(x.strip() for x in only.split(","))
                scenarios = [x for x in scenarios if x[0] in keep]
            for name, act in scenarios:
                if name == profile_scenario:
                    profile = profiled(page, cdp, act)
                else:
                    results.append(measure(page, cdp, name, act))
            if profile:
                return {"label": label, "profile_of": profile_scenario, **profile}
            info["viewport_end"] = page.evaluate("() => ({...viewport})")
            return {"label": label, "rev": rev or "served", "load_s": round(load_s, 2), "minimap_render_ms": mm, **info,
                    "blocked_writes": sorted(set(blocked)), "results": results}
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canvas", required=True)
    ap.add_argument("--rev", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--step-sleep", type=float, default=0.016)
    ap.add_argument("--out", default="")
    ap.add_argument("--profile", default="", help="对某个场景抓 trace + JS 采样，例如 'pan zoomed-out'")
    ap.add_argument("--css", default="", help="载入后额外注入的 CSS（只用于对比实验）")
    ap.add_argument("--only", default="", help="只跑这些场景（逗号分隔）")
    a = ap.parse_args()
    res = run(a.canvas, a.rev, a.label or a.rev or "served", a.step_sleep, a.profile, a.css, a.only)
    text = json.dumps(res, ensure_ascii=False, indent=1)
    print(text)
    if a.out:
        with open(a.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    sys.exit(main())
