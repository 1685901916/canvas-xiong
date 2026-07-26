#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import sys
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
PROGRESS_PATH = ROOT / "output" / "codex_meiji_gyoen_backgrounds_progress.json"

BATCH_ID = "codex-meiji-gyoen-indoor-outdoor-20260611"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"
SUBMIT_WORKERS = 8
POLL_WORKERS = 8
MAX_REFILL_ROUNDS = 4
TASK_DEADLINE_SECONDS = 1800
POLL_INTERVAL_SECONDS = 2.0

ATTACHED_REFS = [
    {
        "key": "meiji_gyoen_context",
        "path": r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-1516541b-edbe-4ed5-ae17-85d64315ff3d.png",
        "name": "明治神宫御苑参考图｜截图上下文",
        "role": "用户提供参考：明治神宫御苑整体结构和项目画风确认，含 UI 截图边框；不要照抄白边。",
        "w": 260,
        "h": 195,
    },
    {
        "key": "meiji_gyoen_clean_ref",
        "path": r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-351a59df-b647-4ea7-a05b-05b389b46d4c.png",
        "name": "明治神宫御苑参考图｜纯图",
        "role": "主要参考：Aiko Tokyo v2 御苑子地图画风、绿意、木建筑、鸟居、池塘和庭园色彩；只作风格/地点参考。",
        "w": 300,
        "h": 225,
    },
]

PROVIDER_POOL = [
    {"id": "custom-api-2", "name": "65535", "model": "gpt-image-2"},
    {"id": "custom-api-3", "name": "nexus", "model": "gpt-image-2"},
]

SCENES = [
    {
        "key": "meiji_gyoen_outdoor",
        "title": "明治神宫御苑｜室外背景图",
        "kind": "outdoor",
        "prompt": (
            "任务：生成《明治神宫御苑｜室外背景图》。这是 Aiko Tokyo v2 项目里的 galgame 约会地点背景图，"
            "不是子地图，不是鸟瞰，不是远景地标总览。\n"
            "地点定位：明治神宫御苑内部的局部室外体验场景，可在南池水边、菖蒲田边、清正井附近步道、"
            "隔雲亭茶室外缘之间取景；要像角色走进御苑后站在可停留的庭园位置。\n"
            "必须包含：近景下方有干净的碎石路、石板步道或木栏边，留人物立绘站位；中景有池塘水面、"
            "木桥/矮栏/岸边岩石/灌木层次；可以有小面积花菖蒲或季节花丛；远景有深绿森林和传统茶室/休憩亭外观，"
            "不要把御社殿或大鸟居当主角。\n"
            "镜头与构图：竖版 9:16 手机背景；人视角，平视或略高于人眼；前景可站人，中景可进入，"
            "远景只保留地点识别；空间从步道到池水再到树影自然递进。\n"
            "画风：参考组内图片的 Aiko Tokyo v2 柔和小插画感、清晰线稿、干净块面、细致绿意、"
            "温暖但克制的色彩、低噪点、高清完成度；只学习画风和明治神宫御苑元素，不照抄参考图的俯视地图构图。\n"
            "光线：明亮柔和的白天或轻微下午感，整体清爽，不要太黄，不要太暗，不偏紫，阴影轻。\n"
            "质量要求：能直接放到游戏对话界面里，水面、树影、步道和庭园层次清楚，边缘干净，空间透视稳定。\n"
            "禁止：不要宏观地图，不要等距/斜俯视地图，不要大鸟居主视觉，不要完整神社建筑正面远景，不要游客人群，"
            "不要人物角色，不要真实品牌文字，不要可读招牌字，不要 logo，不要水印，不要乱码，不要樱花泛滥，"
            "不要赛博朋克，不要写实照片。"
        ),
    },
    {
        "key": "meiji_gyoen_indoor",
        "title": "明治神宫御苑｜室内背景图",
        "kind": "indoor",
        "prompt": (
            "任务：生成《明治神宫御苑｜室内背景图》。这是 Aiko Tokyo v2 项目里的 galgame 室内/半室内背景图，"
            "不是子地图，不是室外地图，不是现代咖啡店。\n"
            "地点定位：明治神宫御苑的隔雲亭茶室或传统休憩亭内部，角色在茶室/亭内休息，"
            "通过拉门、窗、縁侧或开口看见御苑庭园绿意、南池水面或菖蒲田。\n"
            "必须包含：木质茶室内部、榻榻米或干净木地板、低桌/坐垫/木柱/纸拉门或格子窗；"
            "窗外或门外可见御苑步道、灌木、池塘水面或季节花丛；前景下方留人物立绘站位；"
            "室内到室外的空间层次要自然。\n"
            "镜头与构图：竖版 9:16 手机背景；镜头在室内，平视或略高于人眼；前景是可站人的室内地面，"
            "中景是茶室木结构和低桌，远景通过开口看到庭园。不要只画窗外庭园，也不要只画封闭房间。\n"
            "画风：沿用参考图的 Aiko Tokyo v2 柔和小插画感、清晰线稿、干净块面、温暖克制色彩、"
            "细致但不杂乱的木材和绿意；参考图只用于项目画风和御苑元素，不照抄外景地图构图。\n"
            "光线：柔和自然光从侧面进入，室内明亮干净，木色温暖但不要发黄，不要阴暗，不偏紫，阴影轻。\n"
            "质量要求：能直接放到游戏对话界面里，室内透视稳定，前景可读，窗外庭园有地点识别但不抢画面。\n"
            "禁止：不要纯室外庭园，不要宏观地图，不要鸟瞰，不要现代咖啡店，不要旅馆房间，不要神像佛像特写，"
            "不要人物角色，不要真实品牌文字，不要可读招牌字，不要 logo，不要水印，不要乱码，不要樱花泛滥，"
            "不要赛博朋克，不要写实照片。"
        ),
    },
]

append_lock = threading.Lock()
progress_lock = threading.Lock()


def now_ms() -> int:
    return int(time.time() * 1000)


def http_json(method: str, path: str, payload=None, timeout: int = 120, extra_headers=None):
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


def write_progress(progress: dict):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def safe_write_progress(progress: dict):
    with progress_lock:
        write_progress(progress)


def load_canvas() -> dict:
    return http_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]


def save_canvas(canvas: dict, client_id: str) -> dict:
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


def import_local_image(path: Path):
    data = http_json(
        "POST",
        "/api/ai/import-local-image",
        {"path": str(path)},
        timeout=180,
        extra_headers={"Origin": BASE, "Referer": f"{BASE}/static/canvas.html"},
    )
    files = data.get("files") or []
    if not files:
        raise RuntimeError(f"本地图片导入失败: {path}")
    return files[0]


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def node_map(canvas: dict) -> dict:
    return {n.get("id"): n for n in canvas.get("nodes") or [] if n.get("id")}


def output_url_value(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("url") or item.get("src") or ""
    return ""


def visible_images(output_node: dict) -> list:
    return [
        item
        for item in output_node.get("images") or []
        if (url := output_url_value(item)) and not url.startswith(("failed://", "pending://"))
    ]


def append_unique_output(output_node: dict, additions: list) -> int:
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


def connect(connections: list, from_id: str, to_id: str):
    if not any(c.get("from") == from_id and c.get("to") == to_id for c in connections):
        connections.append({"id": f"conn_{from_id}_{to_id}", "from": from_id, "to": to_id})


def backup_canvas() -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-meiji-gyoen-backgrounds-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(CANVAS_PATH, backup_path)
    return str(backup_path)


def create_board(canvas: dict, imported_refs: list) -> tuple[dict, list]:
    if canvas.get("title") != "背景图":
        raise RuntimeError(f"目标画布不匹配：期望 背景图，实际 {canvas.get('title')}")

    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    right = max(float(n.get("x") or 0) + float(n.get("w") or 0) for n in nodes)
    top = min(float(n.get("y") or 0) for n in nodes)
    origin_x = right + 1100
    origin_y = min(top, -2200)

    group_w = 1320
    group_h = 650
    row_h = 900
    gen_w = 380
    output_w = 820
    output_h = 700

    created = {"groups": [], "outputs": [], "generators": [], "images": [], "prompts": []}
    run_plan = []

    brief = (
        "生成简报：目标画布=背景图；任务=明治神宫御苑背景图；需求=室外5张、室内5张，总目标10张。"
        "参考图角色=项目画风/地点元素参考，不做精确差分，不照抄俯视地图。"
        "室外锚点=南池、菖蒲田、清正井附近步道、隔雲亭外缘；室内锚点=隔雲亭茶室/休憩亭内部望向庭园。"
        "验收=9:16、galgame 对话背景、人视角、前景可站人物、无人物、无可读文字/logo/水印、不过黄不过暗。"
    )
    brief_node = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 260,
        "w": 1320,
        "h": 190,
        "name": "明治神宫御苑｜室内室外背景图 生成简报",
        "text": brief,
        "codexBatchId": BATCH_ID,
    }
    nodes.append(brief_node)
    created["prompts"].append(brief_node["id"])

    for row, scene in enumerate(SCENES):
        y = origin_y + row * row_h
        image_ids = []
        for idx, ref in enumerate(imported_refs):
            img = {
                "id": uid("img"),
                "type": "image",
                "x": origin_x + 34,
                "y": y + 70 + idx * 255,
                "url": ref["url"],
                "name": ref["name"],
                "role": ref["role"],
                "w": ref["w"],
                "h": ref["h"],
                "codexBatchId": BATCH_ID,
                "codexRequirementKey": scene["key"],
            }
            nodes.append(img)
            image_ids.append(img["id"])
            created["images"].append(img["id"])

        prompt = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": origin_x + 380,
            "y": y + 70,
            "w": 880,
            "h": 500,
            "name": f"{scene['title']} 提示词",
            "text": scene["prompt"],
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": scene["key"],
        }
        group = {
            "id": uid("grp"),
            "type": "group",
            "x": origin_x,
            "y": y,
            "w": group_w,
            "h": group_h,
            "items": [*image_ids, prompt["id"]],
            "name": f"{scene['title']} 输入｜目标5张",
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": scene["key"],
        }
        gen = {
            "id": uid("gen"),
            "type": "generator",
            "x": origin_x + group_w + 140,
            "y": y + 38,
            "w": gen_w,
            "h": 0,
            "apiProvider": PROVIDER_POOL[0]["id"],
            "model": PROVIDER_POOL[0]["model"],
            "ratio": "portrait916",
            "resolution": "1k",
            "quality": QUALITY,
            "customRatio": "",
            "customSize": "",
            "customRatioWidth": "",
            "customRatioHeight": "",
            "customWidth": "",
            "customHeight": "",
            "inputs": [*(f"{group['id']}:{img_id}" for img_id in image_ids), f"{group['id']}:prompts"],
            "count": TARGET_COUNT,
            "forceFill": True,
            "apiDefaultsVersion": 2,
            "runStatus": "queued",
            "runError": "",
            "name": f"{scene['title']} / 单API可调",
            "poolTargetCount": TARGET_COUNT,
            "targetOutputId": "",
            "canvasProviderMode": "single-visible-api-node",
            "providerPoolCandidates": [
                {"apiProvider": p["id"], "providerName": p["name"], "model": p["model"]} for p in PROVIDER_POOL
            ],
            "generatedOutputs": [],
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": scene["key"],
        }
        out = {
            "id": uid("out"),
            "type": "output",
            "x": gen["x"] + gen_w + 140,
            "y": y + 18,
            "w": output_w,
            "h": output_h,
            "images": [],
            "name": f"{scene['title']} 输出｜目标5张",
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": scene["key"],
        }
        gen["targetOutputId"] = out["id"]

        nodes.extend([prompt, group, gen, out])
        created["prompts"].append(prompt["id"])
        created["groups"].append(group["id"])
        created["generators"].append(gen["id"])
        created["outputs"].append(out["id"])
        connect(connections, group["id"], gen["id"])
        connect(connections, gen["id"], out["id"])

        refs = [{"url": ref["url"], "name": ref["name"], "role": ref["role"]} for ref in imported_refs]
        run_plan.append(
            {
                "requirement_key": scene["key"],
                "target_title": scene["title"],
                "kind": scene["kind"],
                "prompt": scene["prompt"],
                "size": SIZE,
                "quality": QUALITY,
                "reference_images": refs,
                "reference_count": len(refs),
                "target": TARGET_COUNT,
                "generator_id": gen["id"],
                "output_id": out["id"],
            }
        )

    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_meiji_gyoen_plan_{now_ms()}",
            "createdAt": now_ms(),
            "status": "info",
            "nodeType": "canvas-agent",
            "model": "codex_run_meiji_gyoen_backgrounds",
            "prompt": brief,
            "outputs": [],
            "error": "",
            "platform": "codex",
            "request": {
                "batch_id": BATCH_ID,
                "target_canvas": "背景图",
                "target_per_requirement": TARGET_COUNT,
                "requirements": [scene["key"] for scene in SCENES],
            },
        },
    )
    canvas["logs"] = canvas["logs"][:500]
    return created, run_plan


def submit_task(plan: dict, provider: dict) -> dict:
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
    if not task.get("task_id"):
        raise RuntimeError("创建生图任务失败：返回中没有 task_id")
    return task


def poll_task(task_id: str) -> dict:
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


def append_result_to_canvas(plan: dict, provider: dict, task: dict, progress: dict) -> tuple[int, int]:
    with append_lock:
        latest = load_canvas()
        by = node_map(latest)
        out = by.get(plan["output_id"])
        gen = by.get(plan["generator_id"])
        status = str(task.get("status") or "").lower()
        urls = (task.get("result") or {}).get("images") or []
        added = 0
        if out is not None and status == "succeeded" and urls:
            additions = [
                {
                    "url": url,
                    "kind": "image",
                    "viewed": False,
                    "source": "codex_meiji_gyoen_backgrounds",
                    "provider_id": provider["id"],
                    "provider_name": provider["name"],
                    "model": provider["model"],
                    "task_id": task.get("id") or task.get("task_id") or "",
                    "requirement_key": plan["requirement_key"],
                    "scene_kind": plan["kind"],
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
            elif status not in {"still_pending_after_deadline"}:
                gen["runStatus"] = "failed"
                gen["runError"] = str(task.get("error") or task.get("status") or "任务失败")[:500]
            gen.setdefault("generatedOutputs", [])
            for url in urls:
                if url not in gen["generatedOutputs"]:
                    gen["generatedOutputs"].append(url)
        latest.setdefault("logs", []).insert(
            0,
            {
                "id": f"codex_meiji_gyoen_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
                    "target_title": plan["target_title"],
                    "provider_id": provider["id"],
                    "model": provider["model"],
                    "size": plan["size"],
                    "quality": plan["quality"],
                    "reference_count": plan["reference_count"],
                    "queue_ms": task.get("queue_ms"),
                    "run_ms": task.get("run_ms"),
                },
            },
        )
        latest["logs"] = latest["logs"][:500]
        save_canvas(latest, "codex-meiji-gyoen-backgrounds-append")
        with progress_lock:
            progress["appended"] += added
        return added, accepted


def current_count(output_id: str) -> int:
    canvas = load_canvas()
    return len(visible_images(node_map(canvas).get(output_id) or {}))


def plans_for_remaining(run_plan: list) -> tuple[list, dict]:
    attempts = []
    counts = {}
    for plan in run_plan:
        current = current_count(plan["output_id"])
        counts[plan["requirement_key"]] = current
        for _ in range(max(0, plan["target"] - current)):
            attempts.append(dict(plan))
    return attempts, counts


def run_attempt_round(run_plan: list, progress: dict, round_no: int) -> int:
    attempts, counts_before = plans_for_remaining(run_plan)
    round_info = {
        "round": round_no,
        "started_at": now_ms(),
        "attempt_count": len(attempts),
        "counts_before": counts_before,
    }
    progress.setdefault("rounds", []).append(round_info)
    safe_write_progress(progress)
    if not attempts:
        round_info["finished_at"] = now_ms()
        safe_write_progress(progress)
        return 0

    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=SUBMIT_WORKERS) as pool:
        future_map = {}
        for index, plan in enumerate(attempts):
            provider = PROVIDER_POOL[(round_no + index) % len(PROVIDER_POOL)]
            future_map[pool.submit(submit_task, plan, provider)] = (plan, provider)
        for future in concurrent.futures.as_completed(future_map):
            plan, provider = future_map[future]
            key = f"{plan['requirement_key']}::{provider['name']}::r{round_no}::{uuid.uuid4().hex[:6]}"
            try:
                task = future.result()
                task_id = task.get("task_id")
                with progress_lock:
                    progress["submitted"] += 1
                    progress["tasks"][key] = {
                        "requirement_key": plan["requirement_key"],
                        "target_title": plan["target_title"],
                        "provider_name": provider["name"],
                        "provider_id": provider["id"],
                        "model": provider["model"],
                        "round": round_no,
                        "task_id": task_id,
                        "submit_status": task.get("status"),
                    }
                if task_id:
                    submissions.append((key, plan, provider, task_id))
            except Exception as exc:
                with progress_lock:
                    progress["failed"] += 1
                    progress["tasks"][key] = {
                        "requirement_key": plan["requirement_key"],
                        "target_title": plan["target_title"],
                        "provider_name": provider["name"],
                        "provider_id": provider["id"],
                        "model": provider["model"],
                        "round": round_no,
                        "status": "submit_failed",
                        "error": str(exc),
                    }
            safe_write_progress(progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=POLL_WORKERS) as pool:
        future_map = {pool.submit(poll_task, task_id): (key, plan, provider, task_id) for key, plan, provider, task_id in submissions}
        for future in concurrent.futures.as_completed(future_map):
            key, plan, provider, task_id = future_map[future]
            try:
                task = future.result()
                status = str(task.get("status") or "").lower()
                urls = (task.get("result") or {}).get("images") or []
                if status == "succeeded" and urls:
                    with progress_lock:
                        progress["succeeded"] += 1
                else:
                    with progress_lock:
                        progress["failed"] += 1
                added, accepted = append_result_to_canvas(plan, provider, task, progress)
                with progress_lock:
                    progress["tasks"][key].update(
                        {
                            "status": status,
                            "queue_ms": task.get("queue_ms"),
                            "run_ms": task.get("run_ms"),
                            "total_ms": task.get("total_ms"),
                            "error": task.get("error") or "",
                            "result": task.get("result") or None,
                            "appended": added,
                            "accepted_after_append": accepted,
                        }
                    )
            except Exception as exc:
                with progress_lock:
                    progress["failed"] += 1
                    progress["tasks"][key].update({"status": "poll_failed", "error": str(exc)})
            safe_write_progress(progress)

    _, counts_after = plans_for_remaining(run_plan)
    round_info["finished_at"] = now_ms()
    round_info["counts_after"] = counts_after
    safe_write_progress(progress)
    return len(attempts)


def verify_structure(run_plan: list) -> dict:
    canvas = load_canvas()
    by = node_map(canvas)
    outputs = {}
    bad = []
    for plan in run_plan:
        out = by.get(plan["output_id"])
        gen = by.get(plan["generator_id"])
        group = next((n for n in canvas.get("nodes") or [] if n.get("type") == "group" and n.get("codexRequirementKey") == plan["requirement_key"]), None)
        count = len(visible_images(out or {}))
        outputs[plan["requirement_key"]] = {
            "title": plan["target_title"],
            "output_id": plan["output_id"],
            "output_name": (out or {}).get("name"),
            "real_images": count,
            "total_items": len((out or {}).get("images") or []),
            "generator_id": plan["generator_id"],
            "generator_count": 1 if gen else 0,
            "group_id": (group or {}).get("id"),
            "group_items": len((group or {}).get("items") or []),
            "x": (out or {}).get("x"),
            "y": (out or {}).get("y"),
            "w": (out or {}).get("w"),
            "h": (out or {}).get("h"),
        }
        if not out or not gen or not group:
            bad.append(f"{plan['requirement_key']}: missing workflow node")
        if count < TARGET_COUNT:
            bad.append(f"{plan['requirement_key']}: only {count}/{TARGET_COUNT}")
    return {
        "canvas_id": canvas.get("id"),
        "canvas_title": canvas.get("title"),
        "batch_id": BATCH_ID,
        "workflow_count": len(run_plan),
        "outputs": outputs,
        "errors": bad,
    }


def main():
    resume = "--resume" in sys.argv
    if resume:
        progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        run_plan = progress["run_plan"]
        progress.setdefault("resumed_at", []).append(now_ms())
    else:
        progress = {
            "started_at": now_ms(),
            "canvas_id": CANVAS_ID,
            "target_canvas_title": "背景图",
            "batch_id": BATCH_ID,
            "target_count_per_requirement": TARGET_COUNT,
            "requirements": [scene["key"] for scene in SCENES],
            "submitted": 0,
            "succeeded": 0,
            "failed": 0,
            "appended": 0,
            "tasks": {},
            "rounds": [],
        }
        write_progress(progress)

        for ref in ATTACHED_REFS:
            if not Path(ref["path"]).exists():
                raise FileNotFoundError(ref["path"])
        imported_refs = []
        for ref in ATTACHED_REFS:
            imported = import_local_image(Path(ref["path"]))
            imported_refs.append({**ref, "url": imported.get("url")})
        progress["imported_refs"] = imported_refs
        progress["backup"] = backup_canvas()

        canvas = load_canvas()
        created, run_plan = create_board(canvas, imported_refs)
        saved = save_canvas(canvas, "codex-meiji-gyoen-backgrounds-create")
        progress["created"] = created
        progress["run_plan"] = run_plan
        progress["canvas_updated_at"] = saved.get("updated_at")
        safe_write_progress(progress)

    start_round = len(progress.get("rounds") or []) + 1
    for round_no in range(start_round, start_round + MAX_REFILL_ROUNDS):
        _, counts = plans_for_remaining(run_plan)
        if all(count >= TARGET_COUNT for count in counts.values()):
            break
        attempts = run_attempt_round(run_plan, progress, round_no)
        if attempts <= 0:
            break

    progress["verification"] = verify_structure(run_plan)
    progress["finished_at"] = now_ms()
    safe_write_progress(progress)
    print(json.dumps(progress["verification"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
