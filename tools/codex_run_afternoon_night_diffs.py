#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import math
import shutil
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE = "http://127.0.0.1:3001"
TARGET_CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"  # 背景图
MAP_CANVAS_ID = "ed300ba67b364ed38573fb53ba4f690f"  # 地图
ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = ROOT / "output" / "codex_afternoon_night_diffs_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"

TARGET_COUNT = 5
MAX_ROUNDS = 4
QUALITY = "auto"

PROVIDER_POOL = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
]


def now_ms() -> int:
    return int(time.time() * 1000)


def http_json(method: str, path: str, payload=None, timeout=120, extra_headers=None):
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


def load_canvas(canvas_id: str):
    return http_json("GET", f"/api/canvases/{canvas_id}", timeout=60)["canvas"]


def save_target_canvas(canvas, client_id: str):
    payload = {
        "title": canvas.get("title") or "背景图",
        "icon": canvas.get("icon") or "image",
        "kind": canvas.get("kind") or "classic",
        "owner": canvas.get("owner") or "",
        "color": canvas.get("color") or "",
        "pinned": bool(canvas.get("pinned") or False),
        "nodes": canvas.get("nodes") or [],
        "connections": canvas.get("connections") or [],
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": (canvas.get("logs") or [])[:500],
        "settings": canvas.get("settings") or {},
        "client_id": client_id,
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{TARGET_CANVAS_ID}", payload, timeout=120)["canvas"]


def write_progress(progress):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def node_map(canvas):
    return {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}


def output_url_value(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("url") or item.get("src") or "")
    return ""


def visible_images(output_node):
    images = []
    for item in output_node.get("images") or []:
        url = output_url_value(item)
        if url and not url.startswith("failed://") and not url.startswith("pending://"):
            images.append(item)
    return images


def connect(connections, from_id: str, to_id: str):
    if any(c.get("from") == from_id and c.get("to") == to_id for c in connections):
        return
    connections.append({"id": f"conn_{from_id}_{to_id}", "from": from_id, "to": to_id})


def clean_title(name: str) -> str:
    text = str(name or "").strip()
    for marker in [" 输出", "｜输出", " | visible", "｜追加"]:
        if marker in text:
            text = text.split(marker, 1)[0]
    text = text.replace("｜目标5张", "").replace("目标5张", "").strip(" ｜|")
    return text or "未命名图"


def source_role(kind: str, title: str) -> str:
    if kind == "submap":
        return f"{title} 原本子地图基准图"
    return f"{title} 背景图基准图"


def collect_background_sources(canvas):
    outputs = [
        node
        for node in canvas.get("nodes") or []
        if node.get("type") == "output"
        and "全部生成结果" not in str(node.get("name") or "")
        and visible_images(node)
    ]
    sources = []
    for output in sorted(outputs, key=lambda n: (float(n.get("y") or 0), float(n.get("x") or 0))):
        imgs = visible_images(output)
        item = imgs[-1]
        url = output_url_value(item)
        title = clean_title(output.get("name") or output.get("id"))
        sources.append(
            {
                "key": f"bg_{output['id']}",
                "kind": "background",
                "title": title,
                "url": url,
                "name": Path(url).name,
                "role": source_role("background", title),
                "ratio": "portrait916",
                "size": "864x1536",
                "notes": "galgame 人视角/局部背景图，保持原构图和场景结构",
            }
        )
    return sources


def output_ids_for_group(canvas, group_id: str):
    by = node_map(canvas)
    output_ids = []
    for conn in canvas.get("connections") or []:
        if conn.get("from") == group_id and conn.get("to") in by and by[conn["to"]].get("type") == "generator":
            gen_id = conn["to"]
            for out_conn in canvas.get("connections") or []:
                if out_conn.get("from") == gen_id and out_conn.get("to") in by and by[out_conn["to"]].get("type") == "output":
                    output_ids.append(out_conn["to"])
    return output_ids


def collect_submap_sources(canvas):
    by = node_map(canvas)
    groups = [
        node
        for node in canvas.get("nodes") or []
        if node.get("type") == "group"
        and ("子地图" in str(node.get("name") or ""))
        and ("输入" in str(node.get("name") or ""))
    ]
    sources = []
    for group in sorted(groups, key=lambda n: (float(n.get("y") or 0), float(n.get("x") or 0))):
        candidate_outputs = []
        for output_id in output_ids_for_group(canvas, group["id"]):
            output = by.get(output_id)
            if output and visible_images(output):
                candidate_outputs.append(output)
        if not candidate_outputs:
            continue
        output = max(candidate_outputs, key=lambda n: len(visible_images(n)))
        item = visible_images(output)[-1]
        url = output_url_value(item)
        title = clean_title(group.get("name") or output.get("name") or group.get("id"))
        title = title.replace(" 输入", "").strip()
        sources.append(
            {
                "key": f"submap_{group['id']}",
                "kind": "submap",
                "title": title,
                "url": url,
                "name": Path(url).name,
                "role": source_role("submap", title),
                "ratio": "landscape43",
                "size": "1344x1008",
                "notes": "4:3 斜俯视/等距感 galgame UI 子地图，保持道路、地标、绿化、水体和可点击地点位置",
            }
        )
    return sources


def afternoon_prompt(source):
    if source["kind"] == "submap":
        keep_camera = "原图 4:3 斜俯视/等距感 UI 子地图视角"
        content = "道路、水体、地标建筑、可点击地点、绿化块、UI 地图构图"
    else:
        keep_camera = "原图竖版 galgame 背景图视角"
        content = "室内/室外局部场景、建筑位置、道路/步道/水面/栏杆/展柜/门廊等场景结构"
    return (
        f"将这张《{source['title']}》生成下午差分。\n"
        f"必须严格保留：{keep_camera}、画面比例、主体位置、镜头角度、{content}、线稿粗细、色块关系、Aiko Tokyo v2 的干净二次元 galgame 风格。\n"
        "只改变时间和光线：变成克制、温暖、明亮的下午。光线柔和自然，只允许轻微暖色偏移和很浅的下午阴影。\n"
        "不要太黄，不要太暗，不要夕阳，不要金黄色/橙黄色，不要整体变黄，不要高对比，不要新增或删除建筑，不要改变道路和物体位置，不要人物，不要樱花，不要文字乱码，不要水印。"
    )


def night_prompt(source):
    if source["kind"] == "submap":
        keep_camera = "原图 4:3 斜俯视/等距感 UI 子地图视角"
        content = "道路、水体、地标建筑、可点击地点、绿化块、UI 地图构图"
    else:
        keep_camera = "原图竖版 galgame 背景图视角"
        content = "室内/室外局部场景、建筑位置、道路/步道/水面/栏杆/展柜/门廊等场景结构"
    return (
        f"将这张《{source['title']}》生成晚上/夜晚差分。\n"
        f"必须严格保留：{keep_camera}、画面比例、主体位置、镜头角度、{content}、线稿粗细、色块关系、Aiko Tokyo v2 的干净二次元 galgame 风格。\n"
        "只改变时间和光线：变成明亮、干净、温暖但克制的夜晚。整体曝光仍要高，结构和色块要清楚；允许少量柔和窗灯/路灯作为夜晚提示。\n"
        "不要太黑，不要深蓝，不要偏紫，不要赛博霓虹，不要大面积发光，不要强烈灯牌，不要整体变黄，不要高对比，不要新增或删除建筑，不要改变道路和物体位置，不要人物，不要樱花，不要文字乱码，不要水印。"
    )


def build_requirements(sources):
    requirements = []
    for source in sources:
        requirements.append(
            {
                "key": f"{source['key']}_afternoon",
                "source": source,
                "variant": "afternoon",
                "title": f"{source['title']}｜下午差分",
                "prompt": afternoon_prompt(source),
            }
        )
        requirements.append(
            {
                "key": f"{source['key']}_night",
                "source": source,
                "variant": "night",
                "title": f"{source['title']}｜晚上差分",
                "prompt": night_prompt(source),
            }
        )
    return requirements


def create_board(canvas, requirements):
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    xs = [float(node.get("x") or 0) for node in nodes]
    ys = [float(node.get("y") or 0) for node in nodes]
    origin_x = (max(xs) if xs else 0) + 900
    origin_y = min(80, min(ys) if ys else 80)

    row_h = 760
    col_w = 2500
    rows_per_col = max(1, math.ceil(len(requirements) / 2))
    group_w = 940
    group_h = 520
    gen_w = 380
    output_w = 780
    output_h = 660

    summary = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 260,
        "w": 1700,
        "h": 190,
        "name": "下午/晚上差分｜生成简报",
        "text": (
            f"目标画布=背景图；源图={len(requirements)//2} 个，下午/晚上差分共 {len(requirements)} 个；每个差分目标 5 张。"
            "每个 workflow 只显示 1 个 API生成节点，多 API 仅作为后台失败补满候选。"
            "下午：温暖但不要太黄、不要太暗；晚上：明亮干净，不要太黑、不要偏紫。"
        ),
    }
    nodes.append(summary)

    created = {"groups": [], "images": [], "prompts": [summary["id"]], "generators": [], "outputs": []}
    run_plan = []
    for index, req in enumerate(requirements):
        col = index // rows_per_col
        row = index % rows_per_col
        x0 = origin_x + col * col_w
        y0 = origin_y + row * row_h
        source = req["source"]

        img = {
            "id": uid("img"),
            "type": "image",
            "x": x0 + 34,
            "y": y0 + 92,
            "url": source["url"],
            "name": source.get("name") or Path(source["url"]).name,
            "role": source["role"],
            "w": 320,
            "h": 250 if source["ratio"] == "landscape43" else 360,
        }
        prompt = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": x0 + 380,
            "y": y0 + 92,
            "text": req["prompt"],
            "name": f"{req['title']} 提示词",
            "w": 520,
            "h": 360,
        }
        group = {
            "id": uid("grp"),
            "type": "group",
            "x": x0,
            "y": y0,
            "w": group_w,
            "h": group_h,
            "items": [img["id"], prompt["id"]],
            "name": f"{req['title']} 输入｜目标5张",
        }
        gen = {
            "id": uid("gen"),
            "type": "generator",
            "x": x0 + group_w + 80,
            "y": y0 + 35,
            "w": gen_w,
            "h": 0,
            "apiProvider": PROVIDER_POOL[0][0],
            "model": PROVIDER_POOL[0][2],
            "ratio": source["ratio"],
            "resolution": "1k",
            "quality": QUALITY,
            "customRatio": "",
            "customSize": "",
            "customRatioWidth": "",
            "customRatioHeight": "",
            "customWidth": "",
            "customHeight": "",
            "inputs": [f"{group['id']}:{img['id']}", f"{group['id']}:prompts"],
            "count": TARGET_COUNT,
            "forceFill": True,
            "apiDefaultsVersion": 2,
            "runStatus": "queued",
            "runError": "",
            "name": f"{req['title']} / 单API可调",
            "poolTargetCount": TARGET_COUNT,
            "canvasProviderMode": "single-visible-api-node",
            "providerPoolCandidates": [
                {"apiProvider": pid, "providerName": pname, "model": model}
                for pid, pname, model in PROVIDER_POOL
            ],
        }
        out = {
            "id": uid("out"),
            "type": "output",
            "x": gen["x"] + gen_w + 80,
            "y": y0 + 20,
            "w": output_w,
            "h": output_h,
            "images": [],
            "name": f"{req['title']} 输出｜目标5张",
        }
        gen["targetOutputId"] = out["id"]

        nodes.extend([img, prompt, group, gen, out])
        created["images"].append(img["id"])
        created["prompts"].append(prompt["id"])
        created["groups"].append(group["id"])
        created["generators"].append(gen["id"])
        created["outputs"].append(out["id"])
        connect(connections, group["id"], gen["id"])
        connect(connections, gen["id"], out["id"])

        run_plan.append(
            {
                "requirement_key": req["key"],
                "title": req["title"],
                "variant": req["variant"],
                "source_kind": source["kind"],
                "prompt": req["prompt"],
                "reference_images": [{"url": source["url"], "name": source.get("name") or "", "role": source["role"]}],
                "size": source["size"],
                "quality": QUALITY,
                "generator_id": gen["id"],
                "output_id": out["id"],
                "target": TARGET_COUNT,
            }
        )

    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_afternoon_night_diffs_{now_ms()}",
            "createdAt": now_ms(),
            "status": "info",
            "nodeType": "canvas-agent",
            "model": "codex_run_afternoon_night_diffs",
            "prompt": summary["text"],
            "outputs": [],
            "error": "",
            "platform": "codex",
        },
    )
    canvas["logs"] = canvas["logs"][:500]
    return created, run_plan


def submit_task(plan, provider_index: int):
    provider_id, provider_name, model = PROVIDER_POOL[provider_index % len(PROVIDER_POOL)]
    payload = {
        "prompt": plan["prompt"],
        "provider_id": provider_id,
        "model": model,
        "size": plan["size"],
        "quality": plan["quality"],
        "n": 1,
        "reference_images": plan["reference_images"],
    }
    task = http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
    return provider_id, provider_name, model, task


def poll_task(task_id: str):
    while True:
        task = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=40)
        status = str(task.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return task
        time.sleep(2.0)


def append_unique_output(output_node, additions):
    images = output_node.setdefault("images", [])
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


def append_result_to_canvas(plan, provider_name, provider_id, model, task, progress):
    latest = load_canvas(TARGET_CANVAS_ID)
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
            additions.append(
                {
                    "url": url,
                    "viewed": False,
                    "source": "codex_afternoon_night_diffs",
                    "provider_id": provider_id,
                    "provider_name": provider_name,
                    "model": model,
                    "task_id": task.get("id") or task.get("task_id") or "",
                    "variant": plan["variant"],
                    "source_kind": plan["source_kind"],
                    "createdAt": now_ms(),
                    "runMs": task.get("run_ms") or task.get("total_ms") or 0,
                }
            )
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
            gen["runError"] = str(task.get("error") or task.get("status") or "任务失败")[:500]
    latest.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_diff_{uuid.uuid4().hex[:10]}_{now_ms()}",
            "createdAt": now_ms(),
            "status": "done" if status == "succeeded" and urls else "failed",
            "nodeType": "generator",
            "model": model,
            "prompt": plan["prompt"],
            "outputs": urls if status == "succeeded" else [],
            "error": "" if status == "succeeded" else str(task.get("error") or task.get("status") or "任务失败")[:1000],
            "platform": provider_name,
            "runMs": task.get("run_ms") or task.get("total_ms") or 0,
            "task_id": task.get("id") or task.get("task_id") or "",
            "request": {
                "requirement_key": plan["requirement_key"],
                "target_title": plan["title"],
                "provider_id": provider_id,
                "model": model,
                "size": plan["size"],
                "quality": plan["quality"],
                "variant": plan["variant"],
                "queue_ms": task.get("queue_ms"),
                "run_ms": task.get("run_ms"),
            },
        },
    )
    latest["logs"] = latest["logs"][:500]
    saved = save_target_canvas(latest, "codex-afternoon-night-diffs-append")
    progress["appended"] += added
    progress["canvas_updated_at"] = saved.get("updated_at")
    return added


def canvas_success_count(output_id: str) -> int:
    canvas = load_canvas(TARGET_CANVAS_ID)
    out = node_map(canvas).get(output_id) or {}
    return len(visible_images(out))


def run_attempts(plans, progress, round_no: int, max_workers=10):
    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {}
        for index, plan in enumerate(plans):
            future = pool.submit(submit_task, plan, round_no + index)
            future_map[future] = plan
        for future in concurrent.futures.as_completed(future_map):
            plan = future_map[future]
            task_key = f"{plan['requirement_key']}::r{round_no}::{uuid.uuid4().hex[:8]}"
            try:
                provider_id, provider_name, model, task = future.result()
                task_id = task.get("task_id")
                progress["submitted"] += 1
                progress["tasks"][task_key] = {
                    "requirement_key": plan["requirement_key"],
                    "title": plan["title"],
                    "variant": plan["variant"],
                    "provider_id": provider_id,
                    "provider_name": provider_name,
                    "model": model,
                    "round": round_no,
                    "task_id": task_id,
                    "submit_status": task.get("status"),
                }
                if task_id:
                    submissions.append((task_key, plan, provider_id, provider_name, model, task_id))
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][task_key] = {
                    "requirement_key": plan["requirement_key"],
                    "title": plan["title"],
                    "variant": plan["variant"],
                    "round": round_no,
                    "status": "submit_failed",
                    "error": str(exc),
                }
            write_progress(progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(poll_task, task_id): (task_key, plan, provider_id, provider_name, model)
            for task_key, plan, provider_id, provider_name, model, task_id in submissions
        }
        for future in concurrent.futures.as_completed(future_map):
            task_key, plan, provider_id, provider_name, model = future_map[future]
            try:
                task = future.result()
                status = str(task.get("status") or "").lower()
                progress["tasks"][task_key].update(
                    {
                        "status": status,
                        "queue_ms": task.get("queue_ms"),
                        "run_ms": task.get("run_ms"),
                        "total_ms": task.get("total_ms"),
                        "error": task.get("error") or "",
                        "result": task.get("result") or None,
                    }
                )
                if status == "succeeded":
                    progress["succeeded"] += 1
                else:
                    progress["failed"] += 1
                append_result_to_canvas(plan, provider_name, provider_id, model, task, progress)
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][task_key].update({"status": "poll_failed", "error": str(exc)})
            write_progress(progress)


def plans_for_remaining(base_plans, round_no: int):
    plans = []
    for plan in base_plans:
        current = canvas_success_count(plan["output_id"])
        remaining = max(0, plan["target"] - current)
        for _ in range(remaining):
            refill = dict(plan)
            refill["round"] = round_no
            plans.append(refill)
    return plans


def main():
    resume = False
    progress = None
    if PROGRESS_PATH.exists():
        existing = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        if existing.get("created") and not existing.get("finished_at"):
            resume = True
            progress = existing

    if resume:
        sources = progress["sources"]
        requirements = build_requirements(sources)
        req_by_key = {req["key"]: req for req in requirements}
        run_plan = []
        for req_key, item in progress["requirements"].items():
            req = req_by_key[req_key]
            source = req["source"]
            run_plan.append(
                {
                    "requirement_key": req_key,
                    "title": item["title"],
                    "variant": item["variant"],
                    "source_kind": item["source_kind"],
                    "prompt": req["prompt"],
                    "reference_images": [{"url": source["url"], "name": source.get("name") or "", "role": source["role"]}],
                    "size": item["size"],
                    "quality": QUALITY,
                    "generator_id": item["generator_id"],
                    "output_id": item["output_id"],
                    "target": item["target"],
                }
            )
        progress["resumed_at"] = now_ms()
        write_progress(progress)
        for round_no in range(2, MAX_ROUNDS + 4):
            remaining = plans_for_remaining(run_plan, round_no)
            if not remaining:
                break
            run_attempts(remaining, progress, round_no=round_no, max_workers=8)
    else:
        target_canvas = load_canvas(TARGET_CANVAS_ID)
        map_canvas = load_canvas(MAP_CANVAS_ID)
        background_sources = collect_background_sources(target_canvas)
        submap_sources = collect_submap_sources(map_canvas)
        sources = background_sources + submap_sources
        requirements = build_requirements(sources)

        progress = {
            "started_at": now_ms(),
            "target_canvas_id": TARGET_CANVAS_ID,
            "map_canvas_id": MAP_CANVAS_ID,
            "target_count_per_diff": TARGET_COUNT,
            "source_count": len(sources),
            "diff_requirement_count": len(requirements),
            "submitted": 0,
            "succeeded": 0,
            "failed": 0,
            "appended": 0,
            "sources": sources,
            "requirements": {},
            "tasks": {},
        }
        write_progress(progress)

        canvas_file = ROOT / "data" / "canvases" / f"{TARGET_CANVAS_ID}.json"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / f"{TARGET_CANVAS_ID}.before-afternoon-night-diffs-{time.strftime('%Y%m%d-%H%M%S')}.bak"
        shutil.copy2(canvas_file, backup_path)
        progress["backup"] = str(backup_path)

        created, run_plan = create_board(target_canvas, requirements)
        saved = save_target_canvas(target_canvas, "codex-afternoon-night-diffs-board")
        progress["created"] = created
        progress["canvas_updated_at"] = saved.get("updated_at")
        for plan in run_plan:
            progress["requirements"][plan["requirement_key"]] = {
                "title": plan["title"],
                "variant": plan["variant"],
                "source_kind": plan["source_kind"],
                "target": plan["target"],
                "output_id": plan["output_id"],
                "generator_id": plan["generator_id"],
                "size": plan["size"],
            }
        write_progress(progress)

        chunk_size = 8
        for start in range(0, len(run_plan), chunk_size):
            chunk = run_plan[start : start + chunk_size]
            initial = []
            for plan in chunk:
                for _ in range(TARGET_COUNT):
                    initial.append(dict(plan))
            run_attempts(initial, progress, round_no=1, max_workers=10)
            for round_no in range(2, MAX_ROUNDS + 1):
                remaining = plans_for_remaining(chunk, round_no)
                if not remaining:
                    break
                run_attempts(remaining, progress, round_no=round_no, max_workers=8)

    final_canvas = load_canvas(TARGET_CANVAS_ID)
    by = node_map(final_canvas)
    for req_key, item in progress["requirements"].items():
        out = by.get(item["output_id"]) or {}
        item["accepted_success_count"] = len(visible_images(out))
    progress["finished_at"] = now_ms()
    progress["canvas_url"] = f"{BASE}/static/canvas.html?canvas={TARGET_CANVAS_ID}"
    write_progress(progress)

    print(
        json.dumps(
            {
                "canvas_id": TARGET_CANVAS_ID,
                "canvas_url": progress["canvas_url"],
                "source_count": progress["source_count"],
                "diff_requirement_count": progress["diff_requirement_count"],
                "submitted": progress["submitted"],
                "succeeded": progress["succeeded"],
                "failed": progress["failed"],
                "appended": progress["appended"],
                "progress": str(PROGRESS_PATH),
                "backup": str(backup_path),
                "requirements": progress["requirements"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
