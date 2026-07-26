#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import math
import shutil
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
ROOT = Path(__file__).resolve().parents[1]
CANVAS_PATH = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
PROGRESS_PATH = ROOT / "output" / "codex_redbox_whitelist_diffs_progress.json"

BATCH_ID = "codex-redbox-whitelist-afternoon-night-20260610"
TARGET_COUNT = 5
MAX_REFILL_ROUNDS = 5
SUBMIT_WORKERS = 10
POLL_WORKERS = 10
TASK_DEADLINE_SECONDS = 1800
POLL_INTERVAL_SECONDS = 2.0

QUALITY = "auto"

PROVIDER_POOL = [
    {"id": "custom-api-2", "name": "65535", "model": "gpt-image-2"},
    {"id": "apimart", "name": "APIMart", "model": "gpt-image-2"},
    {"id": "custom-api-6", "name": "mikoto", "model": "gpt-image-2"},
    {"id": "custom-api-5", "name": "8yes", "model": "gpt-image-2"},
    {"id": "custom-api-3", "name": "nexus", "model": "gpt-image-2"},
]

SOURCE_WHITELIST = [
    {
        "key": "submap_asakusa",
        "kind": "submap",
        "title": "子地图1｜浅草寺",
        "node_id": "img_9be8ded303765_1781095776093",
        "url": "/assets/input/ai_ref_5a16103defd1.png",
        "ratio": "source",
        "size": "1344x1008",
        "display_h": 250,
    },
    {
        "key": "submap_shinjuku",
        "kind": "submap",
        "title": "子地图2｜新宿",
        "node_id": "img_6d0326e8b7de38_1781095820965",
        "url": "/assets/input/ai_ref_f04f7bf365a7.png",
        "ratio": "source",
        "size": "1344x1008",
        "display_h": 250,
    },
    {
        "key": "submap_disney",
        "kind": "submap",
        "title": "子地图3｜东京迪士尼乐园",
        "node_id": "img_8fe19e896bd5d_1781095785365",
        "url": "/assets/input/ai_ref_8d3270352732.png",
        "ratio": "source",
        "size": "1344x1008",
        "display_h": 250,
    },
    {
        "key": "submap_meiji",
        "kind": "submap",
        "title": "子地图4｜明治神宫",
        "node_id": "img_b590ec432eeb3_1781095850555",
        "url": "/assets/input/ai_ref_c7607d2d164f.png",
        "ratio": "source",
        "size": "1344x1008",
        "display_h": 250,
    },
    {
        "key": "submap_ueno",
        "kind": "submap",
        "title": "子地图5｜上野公园",
        "node_id": "img_19d920d107a1a8_1781095843105",
        "url": "/assets/input/ai_ref_8898460a40d7.png",
        "ratio": "source",
        "size": "1344x1008",
        "display_h": 250,
    },
    {
        "key": "bg_kabukicho",
        "kind": "background",
        "title": "背景1｜歌舞伎町入口街景",
        "node_id": "img_849ee6bf7bf488_1781089370610",
        "url": "/assets/input/ai_ref_18754341586f.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_tocho_inside",
        "kind": "background",
        "title": "背景2｜东京都厅展望室内部",
        "node_id": "img_722cb8b9be81e8_1781089390359",
        "url": "/assets/input/ai_ref_1c74a4c9207e.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_kaminarimon",
        "kind": "background",
        "title": "背景3｜浅草寺雷门门下街景",
        "node_id": "img_c54e54d53f024_1781089285342",
        "url": "/assets/input/ai_ref_4699cbe0eed5.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_imado",
        "kind": "background",
        "title": "背景4｜今户神社姻缘局部",
        "node_id": "img_8b1421a03cf558_1781089042574",
        "url": "/assets/input/ai_ref_5bdb646d0872.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_sensoji_pagoda",
        "kind": "background",
        "title": "背景5｜浅草寺五重塔旁庭院",
        "node_id": "img_ea8f79369dc26_1781089066011",
        "url": "/assets/input/ai_ref_662ee8287fe6.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_shinobazu",
        "kind": "background",
        "title": "背景6｜上野不忍池池边",
        "node_id": "img_34679b515395e8_1781089420479",
        "url": "/assets/input/ai_ref_5562503a77ba.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_tokyo_museum",
        "kind": "background",
        "title": "背景7｜东京国立博物馆展厅",
        "node_id": "img_fd5d8fcc1c50c8_1781089484690",
        "url": "/assets/input/ai_ref_cd9f02874a9c.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_meiji_gyoen_pond",
        "kind": "background",
        "title": "背景8｜明治神宫御苑池塘水边",
        "node_id": "img_a0def5d3db3d6_1781089663521",
        "url": "/assets/input/ai_ref_9bce1890496c.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_disney_castle",
        "kind": "background",
        "title": "背景9｜迪士尼童话城堡广场",
        "node_id": "img_b6a8bddbbfc4d_1781089095667",
        "url": "/assets/input/ai_ref_b55248fdbf12.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_disney_carousel",
        "kind": "background",
        "title": "背景10｜迪士尼旋转木马",
        "node_id": "img_c329ec063fe0c_1781089674066",
        "url": "/assets/input/ai_ref_8ce46140a1b9.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
    {
        "key": "bg_disney_pirate_ship",
        "kind": "background",
        "title": "背景11｜迪士尼海盗船港湾",
        "node_id": "img_26d14fd1540eb_1781089273408",
        "url": "/assets/input/ai_ref_bae4f2d55c4f.png",
        "ratio": "source",
        "size": "864x1536",
        "display_h": 360,
    },
]

append_lock = threading.Lock()
progress_lock = threading.Lock()


def now_ms() -> int:
    return int(time.time() * 1000)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def http_json(method: str, path: str, payload=None, timeout=120):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} HTTP {exc.code}: {detail[:1000]}") from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def load_canvas():
    return http_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]


def save_canvas(canvas, client_id: str):
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
    return http_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)["canvas"]


def write_progress(progress):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def safe_write_progress(progress):
    with progress_lock:
        write_progress(progress)


def node_map(canvas):
    return {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}


def output_url_value(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("url") or item.get("src") or "")
    return ""


def visible_images(output_node):
    return [
        item
        for item in (output_node.get("images") or [])
        if output_url_value(item)
        and not output_url_value(item).startswith("failed://")
        and not output_url_value(item).startswith("pending://")
    ]


def connect(connections, from_id: str, to_id: str):
    if not any(c.get("from") == from_id and c.get("to") == to_id for c in connections):
        connections.append({"id": f"conn_{from_id}_{to_id}", "from": from_id, "to": to_id})


def available_provider_pool():
    providers = http_json("GET", "/api/providers", timeout=30).get("providers") or []
    by_id = {p.get("id"): p for p in providers}
    pool = []
    for item in PROVIDER_POOL:
        provider = by_id.get(item["id"]) or {}
        models = provider.get("image_models") or []
        has_key = bool(provider.get("has_key") or provider.get("has_wallet_key") or provider.get("api_key") or provider.get("key"))
        if provider.get("enabled", True) and has_key and item["model"] in models:
            pool.append(item)
    if not pool:
        raise RuntimeError("没有可用的稳定生图 API provider。")
    return pool


def verify_sources(canvas):
    by = node_map(canvas)
    missing = []
    mismatches = []
    sources = []
    for source in SOURCE_WHITELIST:
        node = by.get(source["node_id"])
        if not node or node.get("type") != "image":
            missing.append(source["node_id"])
            continue
        if node.get("url") != source["url"]:
            mismatches.append({"node_id": source["node_id"], "expected": source["url"], "actual": node.get("url")})
        source = dict(source)
        source["x"] = float(node.get("x") or 0)
        source["y"] = float(node.get("y") or 0)
        sources.append(source)
    if missing:
        raise RuntimeError("白名单源图节点缺失：" + ", ".join(missing))
    if mismatches:
        raise RuntimeError("白名单源图 URL 已变化：" + json.dumps(mismatches, ensure_ascii=False))
    return sources


def prompt_for(source, variant: str) -> str:
    is_submap = source["kind"] == "submap"
    if is_submap:
        keep = (
            "严格保留原图 4:3 斜俯视/等距感 UI 子地图构图、道路走向、水体形状、绿化块、"
            "地标建筑位置、可点击地点关系、建筑比例、线稿粗细、色块关系和 Aiko Tokyo v2 干净二次元 UI 地图风格。"
        )
    else:
        keep = (
            "严格保留原图竖版 galgame 背景图构图、镜头角度、人物立绘站位空间、主体位置、前景/中景/背景层次、"
            "道路/步道/栏杆/水面/展柜/门廊/建筑等局部场景结构、线稿粗细、色块关系和 Aiko Tokyo v2 干净二次元背景风格。"
        )
    if variant == "afternoon":
        return (
            f"将这张《{source['title']}》生成下午差分。\n"
            f"{keep}\n"
            "只改变时间与光线：克制、温暖、明亮的下午，自然柔和侧上方光，轻微暖色偏移，阴影很浅。"
            "整体要清爽，不是夕阳，不是黄昏。\n"
            "禁止：改变构图、改变镜头、重画成新地点、增删主体建筑、移动道路/物体位置、加入人物、加入樱花、文字乱码、logo、水印。"
            "不要太黄，不要太暗，不要金黄色，不要橙黄色，不要整体变黄，不要高对比，不要强烈夕阳。"
        )
    return (
        f"将这张《{source['title']}》生成晚上/夜晚差分。\n"
        f"{keep}\n"
        "只改变时间与光线：明亮、干净、温暖但克制的夜晚，整体曝光仍然高，结构和色块清楚可读。"
        "允许少量柔和窗灯/路灯作为夜晚提示，但不能抢画面。\n"
        "禁止：改变构图、改变镜头、重画成新地点、增删主体建筑、移动道路/物体位置、加入人物、加入樱花、文字乱码、logo、水印。"
        "不要太黑，不要深蓝，不要偏紫，不要赛博霓虹，不要大面积发光，不要强烈灯牌，不要整体变黄，不要高对比。"
    )


def build_requirements(sources):
    requirements = []
    for source in sources:
        for variant, label in (("afternoon", "下午差分"), ("night", "晚上差分")):
            requirements.append(
                {
                    "key": f"{source['key']}__{variant}",
                    "variant": variant,
                    "label": label,
                    "title": f"{source['title']}｜{label}",
                    "source": source,
                    "prompt": prompt_for(source, variant),
                }
            )
    return requirements


def board_origin(sources):
    min_y = min(source["y"] for source in sources)
    max_x = max(source["x"] for source in sources)
    return max_x + 3800, min_y - 360


def existing_node(canvas, req_key: str, node_type: str):
    for node in canvas.get("nodes") or []:
        if node.get("type") == node_type and node.get("codexBatchId") == BATCH_ID and node.get("codexRequirementKey") == req_key:
            return node
    return None


def create_or_update_board(canvas, requirements, provider_pool):
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    sources = [req["source"] for req in requirements]
    origin_x, origin_y = board_origin(sources)

    columns = 4
    row_h = 1000
    rows_per_col = math.ceil(len(requirements) / columns)
    col_w = 3400
    group_w = 1120
    group_h = 560
    gen_w = 380
    output_w = 820
    output_h = 700

    summary = next(
        (
            node
            for node in nodes
            if node.get("type") == "prompt" and node.get("codexBatchId") == BATCH_ID and node.get("codexSummary")
        ),
        None,
    )
    summary_text = (
        "生成简报：目标画布=背景图；只使用用户确认红框白名单源图 16 张；"
        "每张做下午/晚上两个差分，共 32 个 workflow；每个差分目标 5 张 accepted images。"
        "可见结构固定为 Group(source image + prompt) -> one API生成 -> Output；"
        "多 API 只作为后台补满池，不增加可见 API 节点。"
    )
    if summary:
        summary.update({"x": origin_x, "y": origin_y - 260, "w": 2200, "h": 190, "text": summary_text})
    else:
        summary = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": origin_x,
            "y": origin_y - 260,
            "w": 2200,
            "h": 190,
            "name": "红框源图｜下午/晚上差分生成简报",
            "text": summary_text,
            "codexBatchId": BATCH_ID,
            "codexSummary": True,
        }
        nodes.append(summary)

    created = {"summary_id": summary["id"], "groups": [], "images": [], "prompts": [], "generators": [], "outputs": [], "reused": []}
    run_plan = []
    for index, req in enumerate(requirements):
        col = index // rows_per_col
        row = index % rows_per_col
        x0 = origin_x + col * col_w
        y0 = origin_y + row * row_h
        source = req["source"]

        image_node = existing_node(canvas, req["key"], "image")
        prompt_node = existing_node(canvas, req["key"], "prompt")
        group_node = existing_node(canvas, req["key"], "group")
        generator_node = existing_node(canvas, req["key"], "generator")
        output_node = existing_node(canvas, req["key"], "output")

        if image_node and prompt_node and group_node and generator_node and output_node:
            created["reused"].append(req["key"])
        else:
            image_node = {
                "id": uid("img"),
                "type": "image",
                "codexBatchId": BATCH_ID,
                "codexRequirementKey": req["key"],
            }
            prompt_node = {
                "id": uid("prompt"),
                "type": "prompt",
                "codexBatchId": BATCH_ID,
                "codexRequirementKey": req["key"],
            }
            group_node = {
                "id": uid("grp"),
                "type": "group",
                "codexBatchId": BATCH_ID,
                "codexRequirementKey": req["key"],
            }
            generator_node = {
                "id": uid("gen"),
                "type": "generator",
                "codexBatchId": BATCH_ID,
                "codexRequirementKey": req["key"],
            }
            output_node = {
                "id": uid("out"),
                "type": "output",
                "codexBatchId": BATCH_ID,
                "codexRequirementKey": req["key"],
            }
            nodes.extend([image_node, prompt_node, group_node, generator_node, output_node])
            created["images"].append(image_node["id"])
            created["prompts"].append(prompt_node["id"])
            created["groups"].append(group_node["id"])
            created["generators"].append(generator_node["id"])
            created["outputs"].append(output_node["id"])

        image_node.update(
            {
                "x": x0 + 34,
                "y": y0 + 92,
                "url": source["url"],
                "name": f"{source['title']} 源图",
                "role": "structure reference / exact asset to preserve",
                "sourceNodeId": source["node_id"],
                "w": 320,
                "h": source["display_h"],
            }
        )
        prompt_node.update(
            {
                "x": x0 + 400,
                "y": y0 + 92,
                "w": 660,
                "h": 390,
                "name": f"{req['title']} 提示词",
                "text": req["prompt"],
            }
        )
        group_node.update(
            {
                "x": x0,
                "y": y0,
                "w": group_w,
                "h": group_h,
                "name": f"{req['title']} 输入｜目标5张",
                "items": [image_node["id"], prompt_node["id"]],
            }
        )
        generator_node.update(
            {
                "x": x0 + group_w + 140,
                "y": y0 + 35,
                "w": gen_w,
                "h": 0,
                "apiProvider": provider_pool[0]["id"],
                "model": provider_pool[0]["model"],
                "ratio": source["ratio"],
                "resolution": "1k",
                "quality": QUALITY,
                "customRatio": "",
                "customSize": "",
                "customRatioWidth": "",
                "customRatioHeight": "",
                "customWidth": "",
                "customHeight": "",
                "inputs": [f"{group_node['id']}:{image_node['id']}", f"{group_node['id']}:prompts"],
                "count": TARGET_COUNT,
                "forceFill": True,
                "apiDefaultsVersion": 2,
                "runStatus": generator_node.get("runStatus") or "",
                "runError": generator_node.get("runError") or "",
                "name": f"{req['title']} / 单API可调",
                "poolTargetCount": TARGET_COUNT,
                "targetOutputId": output_node["id"],
                "canvasProviderMode": "single-visible-api-node",
                "providerPoolCandidates": [
                    {"apiProvider": p["id"], "providerName": p["name"], "model": p["model"]} for p in provider_pool
                ],
            }
        )
        output_node.update(
            {
                "x": generator_node["x"] + gen_w + 140,
                "y": y0 + 20,
                "w": output_w,
                "h": output_h,
                "name": f"{req['title']} 输出｜目标5张",
                "images": output_node.get("images") or [],
            }
        )
        connect(connections, group_node["id"], generator_node["id"])
        connect(connections, generator_node["id"], output_node["id"])
        run_plan.append(
            {
                "requirement_key": req["key"],
                "title": req["title"],
                "variant": req["variant"],
                "source_key": source["key"],
                "source_kind": source["kind"],
                "source_node_id": source["node_id"],
                "prompt": req["prompt"],
                "reference_images": [{"url": source["url"], "name": f"{source['title']}.png", "role": "structure reference"}],
                "size": source["size"],
                "quality": QUALITY,
                "target": TARGET_COUNT,
                "generator_id": generator_node["id"],
                "output_id": output_node["id"],
            }
        )

    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_redbox_diffs_board_{now_ms()}",
            "createdAt": now_ms(),
            "status": "info",
            "nodeType": "canvas-agent",
            "model": "codex_run_redbox_whitelist_diffs",
            "prompt": summary_text,
            "outputs": [],
            "error": "",
            "platform": "codex",
            "request": {
                "batch_id": BATCH_ID,
                "source_count": len(SOURCE_WHITELIST),
                "workflow_count": len(requirements),
                "target_per_output": TARGET_COUNT,
            },
        },
    )
    canvas["logs"] = canvas["logs"][:500]
    return created, run_plan


def submit_task(plan, provider):
    payload = {
        "prompt": plan["prompt"],
        "provider_id": provider["id"],
        "model": provider["model"],
        "size": plan["size"],
        "quality": plan["quality"],
        "n": 1,
        "reference_images": plan["reference_images"],
    }
    task = http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
    task_id = task.get("task_id")
    if not task_id:
        raise RuntimeError("创建生图任务失败：返回中没有 task_id")
    return task


def poll_task(task_id: str):
    deadline = time.time() + TASK_DEADLINE_SECONDS
    last = {}
    while True:
        try:
            last = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=40)
        except Exception as exc:
            return {"id": task_id, "status": "poll_failed", "error": str(exc)}
        status = str(last.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return last
        if time.time() >= deadline:
            last = dict(last)
            last["status"] = "still_pending_after_deadline"
            last["error"] = f"任务仍可轮询但已等待 {TASK_DEADLINE_SECONDS} 秒，本地停止等待；不计入成功。"
            return last
        time.sleep(POLL_INTERVAL_SECONDS)


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


def append_result_to_canvas(plan, provider, task, progress):
    with append_lock:
        latest = load_canvas()
        by = node_map(latest)
        out = by.get(plan["output_id"])
        gen = by.get(plan["generator_id"])
        status = str(task.get("status") or "").lower()
        result = task.get("result") or {}
        urls = result.get("images") or []
        added = 0
        if out is not None and status == "succeeded" and urls:
            additions = [
                {
                    "url": url,
                    "kind": "image",
                    "viewed": False,
                    "source": "codex_redbox_whitelist_diffs",
                    "provider_id": provider["id"],
                    "provider_name": provider["name"],
                    "model": provider["model"],
                    "task_id": task.get("id") or task.get("task_id") or "",
                    "variant": plan["variant"],
                    "source_kind": plan["source_kind"],
                    "source_node_id": plan["source_node_id"],
                    "createdAt": now_ms(),
                    "runMs": task.get("run_ms") or task.get("total_ms") or 0,
                    "reviewStatus": "needs_review",
                }
                for url in urls
            ]
            added = append_unique_output(out, additions)
        accepted = len(visible_images(out or {}))
        if gen is not None:
            if accepted >= plan["target"]:
                gen["runStatus"] = "done"
                gen["runError"] = ""
            elif added:
                gen["runStatus"] = "running"
                gen["runError"] = ""
            elif accepted <= 0 and status not in {"still_pending_after_deadline"}:
                gen["runStatus"] = "failed"
                gen["runError"] = str(task.get("error") or task.get("status") or "任务失败")[:500]
            gen.setdefault("generatedOutputs", [])
            for url in urls:
                if url not in gen["generatedOutputs"]:
                    gen["generatedOutputs"].append(url)
        latest.setdefault("logs", []).insert(
            0,
            {
                "id": f"codex_redbox_diff_{uuid.uuid4().hex[:10]}_{now_ms()}",
                "createdAt": now_ms(),
                "status": "done" if status == "succeeded" and urls else status or "failed",
                "nodeType": "generator",
                "model": provider["model"],
                "prompt": plan["prompt"],
                "outputs": urls if status == "succeeded" else [],
                "error": "" if status == "succeeded" else str(task.get("error") or task.get("status") or "任务失败")[:1000],
                "platform": provider["name"],
                "runMs": task.get("run_ms") or task.get("total_ms") or 0,
                "task_id": task.get("id") or task.get("task_id") or "",
                "request": {
                    "batch_id": BATCH_ID,
                    "requirement_key": plan["requirement_key"],
                    "target_title": plan["title"],
                    "provider_id": provider["id"],
                    "model": provider["model"],
                    "size": plan["size"],
                    "quality": plan["quality"],
                    "variant": plan["variant"],
                    "queue_ms": task.get("queue_ms"),
                    "run_ms": task.get("run_ms"),
                },
            },
        )
        latest["logs"] = latest["logs"][:500]
        save_canvas(latest, "codex-redbox-whitelist-diffs-append")
        with progress_lock:
            progress["appended"] += added
        return added, accepted


def canvas_success_count(output_id: str) -> int:
    canvas = load_canvas()
    return len(visible_images(node_map(canvas).get(output_id) or {}))


def plans_for_remaining(run_plan):
    plans = []
    counts = {}
    for plan in run_plan:
        current = canvas_success_count(plan["output_id"])
        counts[plan["requirement_key"]] = current
        for _ in range(max(0, plan["target"] - current)):
            plans.append(dict(plan))
    return plans, counts


def run_attempt_round(run_plan, provider_pool, progress, round_no: int):
    attempts, counts_before = plans_for_remaining(run_plan)
    progress.setdefault("rounds", []).append(
        {
            "round": round_no,
            "started_at": now_ms(),
            "attempt_count": len(attempts),
            "counts_before": counts_before,
        }
    )
    safe_write_progress(progress)
    if not attempts:
        progress["rounds"][-1]["finished_at"] = now_ms()
        progress["rounds"][-1]["attempt_count"] = 0
        safe_write_progress(progress)
        return 0

    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=SUBMIT_WORKERS) as pool:
        future_map = {}
        for index, plan in enumerate(attempts):
            provider = provider_pool[(round_no + index) % len(provider_pool)]
            future = pool.submit(submit_task, plan, provider)
            future_map[future] = (plan, provider)
        for future in concurrent.futures.as_completed(future_map):
            plan, provider = future_map[future]
            task_key = f"{plan['requirement_key']}::r{round_no}::{uuid.uuid4().hex[:8]}"
            try:
                task = future.result()
                task_id = task.get("task_id")
                with progress_lock:
                    progress["submitted"] += 1
                    progress["tasks"][task_key] = {
                        "requirement_key": plan["requirement_key"],
                        "title": plan["title"],
                        "variant": plan["variant"],
                        "provider_id": provider["id"],
                        "provider_name": provider["name"],
                        "model": provider["model"],
                        "round": round_no,
                        "task_id": task_id,
                        "submit_status": task.get("status"),
                    }
                if task_id:
                    submissions.append((task_key, plan, provider, task_id))
            except Exception as exc:
                with progress_lock:
                    progress["failed"] += 1
                    progress["tasks"][task_key] = {
                        "requirement_key": plan["requirement_key"],
                        "title": plan["title"],
                        "variant": plan["variant"],
                        "provider_id": provider["id"],
                        "provider_name": provider["name"],
                        "model": provider["model"],
                        "round": round_no,
                        "status": "submit_failed",
                        "error": str(exc),
                    }
            safe_write_progress(progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=POLL_WORKERS) as pool:
        future_map = {
            pool.submit(poll_task, task_id): (task_key, plan, provider)
            for task_key, plan, provider, task_id in submissions
        }
        for future in concurrent.futures.as_completed(future_map):
            task_key, plan, provider = future_map[future]
            try:
                task = future.result()
                status = str(task.get("status") or "").lower()
                with progress_lock:
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
                append_result_to_canvas(plan, provider, task, progress)
            except Exception as exc:
                with progress_lock:
                    progress["failed"] += 1
                    progress["tasks"].setdefault(task_key, {}).update({"status": "poll_or_append_failed", "error": str(exc)})
            safe_write_progress(progress)

    _, counts_after = plans_for_remaining(run_plan)
    progress["rounds"][-1]["finished_at"] = now_ms()
    progress["rounds"][-1]["counts_after"] = counts_after
    safe_write_progress(progress)
    return len(attempts)


def verify_structure(canvas, run_plan):
    by = node_map(canvas)
    connections = canvas.get("connections") or []
    errors = []
    for plan in run_plan:
        req_key = plan["requirement_key"]
        group = existing_node(canvas, req_key, "group")
        gen = by.get(plan["generator_id"])
        out = by.get(plan["output_id"])
        if not group or not gen or not out:
            errors.append(f"{req_key}: missing workflow node")
            continue
        if gen.get("x", 0) <= group.get("x", 0):
            errors.append(f"{req_key}: generator is not right of group")
        if out.get("x", 0) <= gen.get("x", 0):
            errors.append(f"{req_key}: output is not right of generator")
        upstream = [c for c in connections if c.get("from") == group["id"] and c.get("to") == gen["id"]]
        downstream = [c for c in connections if c.get("from") == gen["id"] and c.get("to") == out["id"]]
        if len(upstream) != 1 or len(downstream) != 1:
            errors.append(f"{req_key}: expected one group->gen and one gen->output connection")
        if not out.get("w") or not out.get("h"):
            errors.append(f"{req_key}: output is not fixed-size")
    return errors


def main():
    start = now_ms()
    provider_pool = available_provider_pool()
    canvas = load_canvas()
    if canvas.get("title") != "背景图" or canvas.get("id") != CANVAS_ID:
        raise RuntimeError(f"目标画布不匹配：{canvas.get('title')} {canvas.get('id')}")
    sources = verify_sources(canvas)
    requirements = build_requirements(sources)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-redbox-whitelist-diffs-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(CANVAS_PATH, backup_path)

    progress = {
        "batch_id": BATCH_ID,
        "started_at": start,
        "target_canvas_id": CANVAS_ID,
        "target_canvas_title": "背景图",
        "canvas_url": f"{BASE}/static/canvas.html?canvas={CANVAS_ID}",
        "backup": str(backup_path),
        "target_count_per_diff": TARGET_COUNT,
        "source_count": len(sources),
        "diff_requirement_count": len(requirements),
        "providers": provider_pool,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "requirements": {},
        "tasks": {},
        "rounds": [],
    }
    write_progress(progress)

    created, run_plan = create_or_update_board(canvas, requirements, provider_pool)
    saved = save_canvas(canvas, "codex-redbox-whitelist-diffs-board")
    progress["created"] = created
    progress["canvas_updated_at"] = saved.get("updated_at")
    for plan in run_plan:
        progress["requirements"][plan["requirement_key"]] = {
            "title": plan["title"],
            "variant": plan["variant"],
            "source_kind": plan["source_kind"],
            "source_node_id": plan["source_node_id"],
            "target": plan["target"],
            "output_id": plan["output_id"],
            "generator_id": plan["generator_id"],
            "size": plan["size"],
        }
    write_progress(progress)

    for round_no in range(1, MAX_REFILL_ROUNDS + 1):
        attempt_count = run_attempt_round(run_plan, provider_pool, progress, round_no)
        if attempt_count == 0:
            break

    final_canvas = load_canvas()
    by = node_map(final_canvas)
    deficits = {}
    for req_key, item in progress["requirements"].items():
        out = by.get(item["output_id"]) or {}
        accepted = len(visible_images(out))
        item["accepted_success_count"] = accepted
        item["deficit"] = max(0, item["target"] - accepted)
        if item["deficit"]:
            deficits[req_key] = item["deficit"]
    structure_errors = verify_structure(final_canvas, run_plan)
    progress["finished_at"] = now_ms()
    progress["deficits"] = deficits
    progress["structure_errors"] = structure_errors
    progress["status"] = "complete" if not deficits and not structure_errors else "complete_with_deficits_or_warnings"
    write_progress(progress)

    summary = {
        "canvas_id": CANVAS_ID,
        "canvas_title": "背景图",
        "canvas_url": progress["canvas_url"],
        "backup": str(backup_path),
        "progress": str(PROGRESS_PATH),
        "source_count": len(sources),
        "workflow_count": len(run_plan),
        "target_total": len(run_plan) * TARGET_COUNT,
        "submitted": progress["submitted"],
        "succeeded": progress["succeeded"],
        "failed": progress["failed"],
        "appended": progress["appended"],
        "deficit_total": sum(deficits.values()),
        "deficits": deficits,
        "structure_errors": structure_errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if structure_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
