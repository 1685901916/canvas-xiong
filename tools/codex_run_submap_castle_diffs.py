#!/usr/bin/env python3
import concurrent.futures
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "0872cb9368c440bcbca49eb43110652c"
ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = ROOT / "output" / "codex_submap_castle_diffs_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
TARGET_COUNT = 7
SIZE = "1344x1008"
QUALITY = "auto"
MAX_ROUNDS = 4

INITIAL_PROVIDERS = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("apimart", "APIMart", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-5", "8yes", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api", "test", "gpt-image-2"),
    ("custom-api-7", "comfly", "gpt-image-2"),
]

REFILL_PROVIDERS = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("apimart", "APIMart", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-5", "8yes", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api", "test", "gpt-image-2"),
]

LOCAL_REFS = [
    {
        "key": "city_plaza",
        "title": "子地图1 商业广场",
        "path": r"D:\本地资源库\tokyo2\子地图\2\online_762a065a3f (1).png",
        "role": "商业广场早上基准图",
        "notes": "现代商业广场、圆形玻璃建筑、十字路口、犬像广场",
    },
    {
        "key": "game_street",
        "title": "子地图2 游戏街区",
        "path": r"D:\本地资源库\tokyo2\子地图\2\0.png",
        "role": "游戏街区早上基准图",
        "notes": "游戏中心、女仆咖啡、彩色商业楼、河道街区",
    },
    {
        "key": "tower_park",
        "title": "子地图3 东京塔公园",
        "path": r"D:\本地资源库\tokyo2\子地图\2\image (7).png",
        "role": "东京塔公园早上基准图",
        "notes": "东京塔、公园、水池、寺院和现代楼",
    },
]

CASTLE_BASE = {
    "key": "carousel_castle",
    "title": "旋转木马城堡",
    "url": "/assets/input/ai_ref_be92ecddf1ee.png",
    "name": "ai_ref_be92ecddf1ee.png",
    "role": "旋转木马城堡早上基准图",
    "notes": "旋转木马、城堡、水道、过山车",
}


def now_ms():
    return int(time.time() * 1000)


def http_json(method, path, payload=None, timeout=120, extra_headers=None):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} HTTP {exc.code}: {detail[:1000]}") from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def write_progress(progress):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def load_canvas():
    return http_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]


def save_canvas(canvas, client_id):
    payload = {
        "title": canvas.get("title") or "Aiko Tokyo v2 UI子地图｜无樱花画布批次",
        "icon": canvas.get("icon") or "🗺️",
        "nodes": canvas.get("nodes") or [],
        "connections": canvas.get("connections") or [],
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": (canvas.get("logs") or [])[:500],
        "settings": canvas.get("settings") or {},
        "client_id": client_id,
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)["canvas"]


def import_local_image(path):
    payload = {"path": str(path)}
    data = http_json(
        "POST",
        "/api/ai/import-local-image",
        payload,
        timeout=180,
        extra_headers={"Origin": BASE, "Referer": f"{BASE}/static/canvas.html"},
    )
    files = data.get("files") or []
    if not files:
        raise RuntimeError(f"本地图片导入失败: {path}")
    return files[0]


def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def connect(connections, from_id, to_id):
    cid = f"conn_{from_id}_{to_id}"
    if not any(c.get("from") == from_id and c.get("to") == to_id for c in connections):
        connections.append({"id": cid, "from": from_id, "to": to_id})


def afternoon_prompt(title, notes):
    return (
        f"任务：基于参考图生成《{title}》的下午差分图。\n"
        f"参考图内容：{notes}。\n"
        "必须保留：原图构图、俯视/斜俯视镜头、建筑位置、道路/水道/绿化/广场结构、主体比例、线稿粗细、galgame 子地图 UI 风格、清晰可读的二次元背景图质感。\n"
        "只改变：时间变成克制、温暖、干净的下午。光线柔和自然，亮度接近早上基准图，只允许轻微暖色偏移和很轻的下午阴影。\n"
        "避免：不要夕阳，不要金黄色/橙黄色，不要整体变黄，不要变暗，不要高对比，不要新增或删除建筑，不要移动主体，不要改成写实照片，不要人物，不要樱花，不要水印，不要文字乱码。"
    )


def night_prompt(title, notes):
    return (
        f"任务：基于参考图生成《{title}》的晚上/夜晚差分图。\n"
        f"参考图内容：{notes}。\n"
        "必须保留：原图构图、俯视/斜俯视镜头、建筑位置、道路/水道/绿化/广场结构、主体比例、线稿粗细、galgame 子地图 UI 风格、清晰可读的二次元背景图质感。\n"
        "只改变：时间变成明亮、干净、温暖但克制的夜晚。整体曝光仍要高，路面、建筑轮廓、水面和绿化都要看得清；允许少量柔和窗灯/路灯作为夜晚提示。\n"
        "避免：不要太黑，不要深蓝，不要偏紫，不要赛博霓虹，不要大面积发光，不要强烈灯牌，不要整体变黄，不要高对比，不要新增或删除建筑，不要移动主体，不要改成写实照片，不要人物，不要樱花，不要水印，不要文字乱码。"
    )


def build_requirements(refs):
    requirements = []
    for ref in refs:
        requirements.append({
            "key": f"{ref['key']}_afternoon",
            "title": f"{ref['title']}｜下午差分",
            "variant": "afternoon",
            "prompt": afternoon_prompt(ref["title"], ref["notes"]),
            "ref": ref,
        })
        requirements.append({
            "key": f"{ref['key']}_night",
            "title": f"{ref['title']}｜晚上差分",
            "variant": "night",
            "prompt": night_prompt(ref["title"], ref["notes"]),
            "ref": ref,
        })
    return requirements


def output_url_value(item):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("url") or ""
    return ""


def append_unique_output(out, additions):
    images = out.setdefault("images", [])
    seen = {output_url_value(item) for item in images if output_url_value(item)}
    added = 0
    for item in additions:
        url = output_url_value(item)
        if not url or url in seen:
            continue
        images.append(item)
        seen.add(url)
        added += 1
    return added


def create_board(canvas, requirements):
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    xs = [float(n.get("x") or 0) for n in nodes]
    ys = [float(n.get("y") or 0) for n in nodes]
    origin_x = (max(xs) if xs else 0) + 620
    origin_y = min(80, min(ys) if ys else 80)

    run_plan = []
    created = {"groups": [], "outputs": [], "generators": [], "images": [], "prompts": []}
    row_h = 780
    group_w = 940
    group_h = 520
    gen_x = origin_x + group_w + 80
    out_x = gen_x + 510

    for row, req in enumerate(requirements):
        y = origin_y + row * row_h
        ref = req["ref"]
        img = {
            "id": uid("img"),
            "type": "image",
            "x": origin_x + 36,
            "y": y + 90,
            "url": ref["url"],
            "name": ref.get("name") or f"{ref['key']}.png",
            "role": ref.get("role") or "reference",
            "w": 330,
            "h": 250,
        }
        prompt = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": origin_x + 405,
            "y": y + 90,
            "text": req["prompt"],
            "name": req["title"],
            "w": 480,
            "h": 340,
        }
        group = {
            "id": uid("grp"),
            "type": "group",
            "x": origin_x,
            "y": y,
            "w": group_w,
            "h": group_h,
            "items": [img["id"], prompt["id"]],
            "name": f"{req['title']} 输入",
        }
        output = {
            "id": uid("out"),
            "type": "output",
            "x": out_x,
            "y": y + 20,
            "w": 780,
            "h": 660,
            "images": [],
            "name": f"{req['title']} 输出｜目标7张",
        }
        nodes.extend([img, prompt, group, output])
        created["images"].append(img["id"])
        created["prompts"].append(prompt["id"])
        created["groups"].append(group["id"])
        created["outputs"].append(output["id"])

        for index, (provider_id, provider_name, model) in enumerate(INITIAL_PROVIDERS[:1]):
            col = index % 2
            subrow = index // 2
            gen = {
                "id": uid("gen"),
                "type": "generator",
                "x": gen_x + col * 235,
                "y": y + 35 + subrow * 118,
                "w": 380,
                "h": 0,
                "apiProvider": provider_id,
                "model": model,
                "ratio": "landscape43",
                "resolution": "1k",
                "quality": QUALITY,
                "customRatio": "",
                "customSize": "",
                "customRatioWidth": "",
                "customRatioHeight": "",
                "customWidth": "",
                "customHeight": "",
                "inputs": [f"{group['id']}:{img['id']}", f"{group['id']}:prompts"],
                "count": 1,
                "apiDefaultsVersion": 2,
                "runStatus": "queued",
                "runError": "",
                "name": f"{req['title']} / {provider_name}",
                "targetOutputId": output["id"],
                "poolTargetCount": TARGET_COUNT,
            }
            nodes.append(gen)
            created["generators"].append(gen["id"])
            connect(connections, group["id"], gen["id"])
            connect(connections, gen["id"], output["id"])
            run_plan.append({
                "requirement_key": req["key"],
                "target_title": req["title"],
                "variant": req["variant"],
                "prompt": req["prompt"],
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "size": SIZE,
                "quality": QUALITY,
                "reference_images": [{"url": ref["url"], "name": ref.get("name") or "", "role": ref.get("role") or ""}],
                "reference_count": 1,
                "generator_id": gen["id"],
                "output_id": output["id"],
                "round": 1,
            })
    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_submap_castle_plan_{now_ms()}",
        "createdAt": now_ms(),
        "status": "info",
        "nodeType": "canvas-agent",
        "model": "codex_submap_castle_diffs",
        "prompt": "3张子地图 + 旋转木马城堡早上基准；下午/晚上差分；每差分7张；多API池同组共享输出。",
        "outputs": [],
        "error": "",
        "platform": "codex",
    })
    canvas["logs"] = canvas["logs"][:500]
    return created, run_plan


def submit_task(plan):
    payload = {
        "prompt": plan["prompt"],
        "provider_id": plan["provider_id"],
        "model": plan["model"],
        "size": plan["size"],
        "quality": plan["quality"],
        "n": 1,
        "reference_images": plan["reference_images"],
    }
    task = http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
    return task


def poll_task(task_id):
    while True:
        task = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=40)
        status = str(task.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return task
        time.sleep(2.0)


def node_map(canvas):
    return {n.get("id"): n for n in canvas.get("nodes") or [] if n.get("id")}


def canvas_success_count(canvas, output_id):
    out = node_map(canvas).get(output_id) or {}
    return len([item for item in out.get("images") or [] if output_url_value(item)])


def append_result_to_canvas(plan, task, progress):
    latest = load_canvas()
    by = node_map(latest)
    out = by.get(plan["output_id"])
    gen = by.get(plan["generator_id"])
    status = str(task.get("status") or "").lower()
    result = task.get("result") or {}
    urls = result.get("images") or []
    added = 0
    if out is not None and status == "succeeded" and urls:
        additions = []
        for url in urls:
            additions.append({
                "url": url,
                "viewed": False,
                "source": "codex_submap_castle_diffs",
                "provider_id": plan["provider_id"],
                "provider_name": plan["provider_name"],
                "model": plan["model"],
                "task_id": task.get("id") or task.get("task_id") or "",
                "variant": plan["variant"],
                "createdAt": now_ms(),
                "runMs": task.get("run_ms") or task.get("total_ms") or 0,
            })
        added = append_unique_output(out, additions)
    if gen is not None:
        if status == "succeeded" and urls:
            gen["runStatus"] = "done"
            gen["runError"] = ""
            gen.setdefault("generatedOutputs", [])
            for url in urls:
                if url not in gen["generatedOutputs"]:
                    gen["generatedOutputs"].append(url)
        else:
            gen["runStatus"] = "failed"
            gen["runError"] = str(task.get("error") or "任务失败")[:500]
    latest.setdefault("logs", []).insert(0, {
        "id": f"codex_submap_castle_{uuid.uuid4().hex[:10]}_{now_ms()}",
        "createdAt": now_ms(),
        "status": "done" if status == "succeeded" and urls else "failed",
        "nodeType": "generator",
        "model": plan["model"],
        "prompt": plan["prompt"],
        "outputs": urls if status == "succeeded" else [],
        "error": "" if status == "succeeded" else str(task.get("error") or task.get("status") or "任务失败")[:1000],
        "platform": plan["provider_name"],
        "runMs": task.get("run_ms") or task.get("total_ms") or 0,
        "task_id": task.get("id") or task.get("task_id") or "",
        "request": {
            "requirement_key": plan["requirement_key"],
            "target_title": plan["target_title"],
            "provider_id": plan["provider_id"],
            "model": plan["model"],
            "size": plan["size"],
            "quality": plan["quality"],
            "reference_count": plan["reference_count"],
            "round": plan.get("round") or 1,
            "queue_ms": task.get("queue_ms"),
            "run_ms": task.get("run_ms"),
        },
    })
    latest["logs"] = latest["logs"][:500]
    saved = save_canvas(latest, "codex-submap-castle-diffs-append")
    progress["appended"] += added
    progress["canvas_updated_at"] = saved.get("updated_at")
    return added


def run_round(plans, round_no, progress, max_workers=18):
    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(submit_task, plan): plan for plan in plans}
        for future in concurrent.futures.as_completed(future_map):
            plan = future_map[future]
            key = f"{plan['requirement_key']}::{plan['provider_name']}::r{round_no}::{uuid.uuid4().hex[:6]}"
            try:
                task = future.result()
                task_id = task.get("task_id")
                progress["submitted"] += 1
                progress["tasks"][key] = {
                    "requirement_key": plan["requirement_key"],
                    "target_title": plan["target_title"],
                    "provider_name": plan["provider_name"],
                    "provider_id": plan["provider_id"],
                    "model": plan["model"],
                    "round": round_no,
                    "task_id": task_id,
                    "submit_status": task.get("status"),
                }
                if task_id:
                    submissions.append((key, plan, task_id))
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key] = {
                    "requirement_key": plan["requirement_key"],
                    "target_title": plan["target_title"],
                    "provider_name": plan["provider_name"],
                    "provider_id": plan["provider_id"],
                    "model": plan["model"],
                    "round": round_no,
                    "status": "submit_failed",
                    "error": str(exc),
                }
            write_progress(progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(poll_task, task_id): (key, plan, task_id) for key, plan, task_id in submissions}
        for future in concurrent.futures.as_completed(future_map):
            key, plan, task_id = future_map[future]
            try:
                task = future.result()
                status = str(task.get("status") or "").lower()
                progress["tasks"][key].update({
                    "status": status,
                    "queue_ms": task.get("queue_ms"),
                    "run_ms": task.get("run_ms"),
                    "total_ms": task.get("total_ms"),
                    "error": task.get("error") or "",
                    "result": task.get("result") or None,
                })
                if status == "succeeded":
                    progress["succeeded"] += 1
                else:
                    progress["failed"] += 1
                append_result_to_canvas(plan, task, progress)
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key].update({"status": "poll_failed", "error": str(exc)})
            write_progress(progress)


def refill_plans(requirements, base_plan_by_req, round_no):
    canvas = load_canvas()
    plans = []
    for req in requirements:
        base = base_plan_by_req[req["key"]]
        current = canvas_success_count(canvas, base["output_id"])
        remaining = max(0, TARGET_COUNT - current)
        for index in range(remaining):
            provider_id, provider_name, model = REFILL_PROVIDERS[(round_no + index) % len(REFILL_PROVIDERS)]
            plan = dict(base)
            plan.update({
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "round": round_no,
                "generator_id": base["generator_id"],
            })
            plans.append(plan)
    return plans


def main():
    progress = {
        "started_at": now_ms(),
        "canvas_id": CANVAS_ID,
        "target_count_per_requirement": TARGET_COUNT,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "requirements": {},
        "tasks": {},
    }
    write_progress(progress)

    imported_refs = []
    for ref in LOCAL_REFS:
        imported = import_local_image(ref["path"])
        imported_refs.append({
            **ref,
            "url": imported.get("url"),
            "name": imported.get("name") or os.path.basename(ref["path"]),
        })
    imported_refs.append(CASTLE_BASE)
    requirements = build_requirements(imported_refs)

    canvas_file = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-submap-castle-diffs-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(canvas_file, backup_path)
    progress["backup"] = str(backup_path)

    canvas = load_canvas()
    created, run_plan = create_board(canvas, requirements)
    canvas = save_canvas(canvas, "codex-submap-castle-diffs-board")
    progress["created"] = created
    progress["canvas_updated_at"] = canvas.get("updated_at")
    for req in requirements:
        progress["requirements"][req["key"]] = {
            "title": req["title"],
            "variant": req["variant"],
            "target": TARGET_COUNT,
            "reference": req["ref"].get("url"),
        }
    write_progress(progress)

    base_plan_by_req = {}
    for plan in run_plan:
        base_plan_by_req.setdefault(plan["requirement_key"], plan)

    run_round(run_plan, 1, progress, max_workers=18)
    for round_no in range(2, MAX_ROUNDS + 1):
        plans = refill_plans(requirements, base_plan_by_req, round_no)
        if not plans:
            break
        run_round(plans, round_no, progress, max_workers=12)

    final = load_canvas()
    by = node_map(final)
    for req_key, item in progress["requirements"].items():
        out_id = base_plan_by_req[req_key]["output_id"]
        out = by.get(out_id) or {}
        item["output_id"] = out_id
        item["accepted_success_count"] = len([x for x in out.get("images") or [] if output_url_value(x)])
    progress["finished_at"] = now_ms()
    progress["canvas_url"] = f"{BASE}/static/canvas.html?canvas={CANVAS_ID}"
    write_progress(progress)
    print(json.dumps({
        "canvas_id": CANVAS_ID,
        "canvas_url": progress["canvas_url"],
        "submitted": progress["submitted"],
        "succeeded": progress["succeeded"],
        "failed": progress["failed"],
        "appended": progress["appended"],
        "requirements": progress["requirements"],
        "progress": str(PROGRESS_PATH),
        "backup": str(backup_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
