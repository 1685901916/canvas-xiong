#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import os
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
PROGRESS_PATH = ROOT / "output" / "codex_single_bg_afternoon_night_diff_progress.json"

BATCH_ID = "codex-single-bg-afternoon-night-20260611"
SOURCE_PATH = Path(r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-ea9fe319-fc98-414c-953e-03a5c4158b26.png")
SOURCE_TITLE = "明治神宫御苑茶室室内背景图"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"
MAX_REFILL_ROUNDS = 4
SUBMIT_WORKERS = 6
POLL_WORKERS = 6
TASK_DEADLINE_SECONDS = 1800
POLL_INTERVAL_SECONDS = 2.0

PROVIDER_POOL = [
    {"id": "custom-api-2", "name": "65535", "model": "gpt-image-2"},
    {"id": "custom-api-3", "name": "nexus", "model": "gpt-image-2"},
]

VARIANTS = [
    {
        "key": "single_bg_gyoen_tea_room_afternoon",
        "variant": "afternoon",
        "title": f"{SOURCE_TITLE}｜下午差分",
        "prompt": (
            f"将这张《{SOURCE_TITLE}》生成下午差分。\n"
            "严格保留原图竖版 9:16 构图、镜头位置、透视、木质茶室结构、梁柱、天花板、格子窗、纸拉门、"
            "竹帘、吊灯、桌子、坐垫、榻榻米、木地板、窗外庭园池塘和绿植位置、线稿粗细、色块关系，"
            "保持 Aiko Tokyo v2 干净二次元 galgame 背景图风格。\n"
            "只改变时间和光线：变成克制、温暖、明亮的下午。窗外自然光柔和，室内木色只允许轻微暖色偏移，"
            "地板和榻榻米有浅浅下午光影，但不要强烈夕阳。\n"
            "不要太黄，不要太暗，不要金黄色，不要橙黄色，不要整体变黄，不要高对比，不要重画成新房间，"
            "不要移动柱子/窗户/桌垫/庭园位置，不要新增人物，不要文字乱码，不要水印。"
        ),
    },
    {
        "key": "single_bg_gyoen_tea_room_night",
        "variant": "night",
        "title": f"{SOURCE_TITLE}｜晚上差分",
        "prompt": (
            f"将这张《{SOURCE_TITLE}》生成晚上/夜晚差分。\n"
            "严格保留原图竖版 9:16 构图、镜头位置、透视、木质茶室结构、梁柱、天花板、格子窗、纸拉门、"
            "竹帘、吊灯、桌子、坐垫、榻榻米、木地板、窗外庭园池塘和绿植位置、线稿粗细、色块关系，"
            "保持 Aiko Tokyo v2 干净二次元 galgame 背景图风格。\n"
            "只改变时间和光线：变成明亮、干净、温暖但克制的夜晚。室内吊灯和窗边灯光柔和，木地板仍然可读，"
            "窗外是清晰的夜色庭园和水面暗蓝灰层次，整体曝光不要太低。\n"
            "不要太黑，不要深蓝压暗，不要偏紫，不要赛博霓虹，不要大面积强光，不要整体变黄，不要高对比，"
            "不要重画成新房间，不要移动柱子/窗户/桌垫/庭园位置，不要新增人物，不要文字乱码，不要水印。"
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


def write_progress(progress: dict):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def safe_write_progress(progress: dict):
    with progress_lock:
        write_progress(progress)


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


def backup_canvas() -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{CANVAS_ID}.before-single-bg-afternoon-night-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(CANVAS_PATH, backup)
    return str(backup)


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


def create_board(canvas: dict, source_url: str) -> tuple[dict, list]:
    if canvas.get("title") != "背景图":
        raise RuntimeError(f"目标画布不匹配：期望 背景图，实际 {canvas.get('title')}")
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    right = max(float(n.get("x") or 0) + float(n.get("w") or 0) for n in nodes)
    top = min(float(n.get("y") or 0) for n in nodes)
    origin_x = right + 1100
    origin_y = min(top, -2200)

    group_w = 1240
    group_h = 760
    row_h = 1020
    gen_w = 380
    out_w = 820
    out_h = 700

    brief_text = (
        f"生成简报：目标画布=背景图；源图={SOURCE_TITLE}；任务=下午差分5张、晚上差分5张。"
        "参考角色=精确源图，必须保留构图、室内结构、家具、窗外庭园和画风；只改时间/光线。"
        "下午=克制明亮轻暖，不要太黄；晚上=明亮可读温暖干净，不要太黑/偏紫/霓虹。"
    )
    brief = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 250,
        "w": 1240,
        "h": 170,
        "name": f"{SOURCE_TITLE}｜下午晚上差分 生成简报",
        "text": brief_text,
        "codexBatchId": BATCH_ID,
    }
    nodes.append(brief)

    created = {"groups": [], "outputs": [], "generators": [], "images": [], "prompts": [brief["id"]]}
    run_plan = []
    for row, variant in enumerate(VARIANTS):
        y = origin_y + row * row_h
        img = {
            "id": uid("img"),
            "type": "image",
            "x": origin_x + 34,
            "y": y + 80,
            "url": source_url,
            "name": f"{SOURCE_TITLE} 源图",
            "role": "精确结构参考：保留原图构图、茶室室内结构、家具、窗外庭园，只改时间和光线。",
            "w": 300,
            "h": 533,
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        prompt = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": origin_x + 380,
            "y": y + 80,
            "w": 800,
            "h": 540,
            "name": f"{variant['title']} 提示词",
            "text": variant["prompt"],
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        group = {
            "id": uid("grp"),
            "type": "group",
            "x": origin_x,
            "y": y,
            "w": group_w,
            "h": group_h,
            "items": [img["id"], prompt["id"]],
            "name": f"{variant['title']} 输入｜目标5张",
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": variant["key"],
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
            "ratio": "source",
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
            "name": f"{variant['title']} / 单API可调",
            "poolTargetCount": TARGET_COUNT,
            "targetOutputId": "",
            "canvasProviderMode": "single-visible-api-node",
            "providerPoolCandidates": [
                {"apiProvider": p["id"], "providerName": p["name"], "model": p["model"]} for p in PROVIDER_POOL
            ],
            "generatedOutputs": [],
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        out = {
            "id": uid("out"),
            "type": "output",
            "x": gen["x"] + gen_w + 140,
            "y": y + 18,
            "w": out_w,
            "h": out_h,
            "images": [],
            "name": f"{variant['title']} 输出｜目标5张",
            "codexBatchId": BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        gen["targetOutputId"] = out["id"]

        nodes.extend([img, prompt, group, gen, out])
        connect(connections, group["id"], gen["id"])
        connect(connections, gen["id"], out["id"])
        created["images"].append(img["id"])
        created["prompts"].append(prompt["id"])
        created["groups"].append(group["id"])
        created["generators"].append(gen["id"])
        created["outputs"].append(out["id"])
        run_plan.append(
            {
                "requirement_key": variant["key"],
                "target_title": variant["title"],
                "variant": variant["variant"],
                "prompt": variant["prompt"],
                "size": SIZE,
                "quality": QUALITY,
                "reference_images": [{"url": source_url, "name": f"{SOURCE_TITLE}.png", "role": "exact source image"}],
                "target": TARGET_COUNT,
                "generator_id": gen["id"],
                "output_id": out["id"],
            }
        )

    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_single_bg_diff_plan_{now_ms()}",
            "createdAt": now_ms(),
            "status": "info",
            "nodeType": "canvas-agent",
            "model": "codex_run_single_bg_afternoon_night_diff",
            "prompt": brief_text,
            "outputs": [],
            "error": "",
            "platform": "codex",
            "request": {"batch_id": BATCH_ID, "target_per_requirement": TARGET_COUNT},
        },
    )
    canvas["logs"] = canvas["logs"][:500]
    return created, run_plan


def submit_task(plan: dict, provider: dict) -> dict:
    task = http_json(
        "POST",
        "/api/canvas-image-tasks",
        {
            "prompt": plan["prompt"],
            "provider_id": provider["id"],
            "model": provider["model"],
            "size": plan["size"],
            "quality": plan["quality"],
            "n": 1,
            "reference_images": plan["reference_images"],
        },
        timeout=90,
    )
    if not task.get("task_id"):
        raise RuntimeError("创建生图任务失败：返回中没有 task_id")
    return task


def poll_task(task_id: str) -> dict:
    deadline = time.time() + TASK_DEADLINE_SECONDS
    while True:
        try:
            task = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=40)
        except Exception as exc:
            return {"id": task_id, "status": "poll_failed", "error": str(exc)}
        status = str(task.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return task
        if time.time() >= deadline:
            task = dict(task)
            task["status"] = "still_pending_after_deadline"
            task["error"] = f"任务仍可轮询但已等待 {TASK_DEADLINE_SECONDS} 秒，本地停止等待；不计入成功。"
            return task
        time.sleep(POLL_INTERVAL_SECONDS)


def append_result_to_canvas(plan: dict, provider: dict, task: dict, progress: dict) -> tuple[int, int]:
    with append_lock:
        canvas = load_canvas()
        by = node_map(canvas)
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
                    "source": "codex_single_bg_afternoon_night_diff",
                    "provider_id": provider["id"],
                    "provider_name": provider["name"],
                    "model": provider["model"],
                    "task_id": task.get("id") or task.get("task_id") or "",
                    "variant": plan["variant"],
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
        canvas.setdefault("logs", []).insert(
            0,
            {
                "id": f"codex_single_bg_diff_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
                    "queue_ms": task.get("queue_ms"),
                    "run_ms": task.get("run_ms"),
                },
            },
        )
        canvas["logs"] = canvas["logs"][:500]
        save_canvas(canvas, "codex-single-bg-diff-append")
        with progress_lock:
            progress["appended"] += added
        return added, accepted


def current_count(output_id: str) -> int:
    canvas = load_canvas()
    return len(visible_images(node_map(canvas).get(output_id) or {}))


def remaining_plans(run_plan: list) -> tuple[list, dict]:
    attempts = []
    counts = {}
    for plan in run_plan:
        count = current_count(plan["output_id"])
        counts[plan["requirement_key"]] = count
        for _ in range(max(0, plan["target"] - count)):
            attempts.append(dict(plan))
    return attempts, counts


def run_round(run_plan: list, progress: dict, round_no: int) -> int:
    attempts, counts_before = remaining_plans(run_plan)
    round_info = {"round": round_no, "started_at": now_ms(), "attempt_count": len(attempts), "counts_before": counts_before}
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
        future_map = {pool.submit(poll_task, task_id): (key, plan, provider) for key, plan, provider, task_id in submissions}
        for future in concurrent.futures.as_completed(future_map):
            key, plan, provider = future_map[future]
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

    _, counts_after = remaining_plans(run_plan)
    round_info["finished_at"] = now_ms()
    round_info["counts_after"] = counts_after
    safe_write_progress(progress)
    return len(attempts)


def verify(run_plan: list) -> dict:
    canvas = load_canvas()
    by = node_map(canvas)
    result = {"canvas_id": canvas.get("id"), "canvas_title": canvas.get("title"), "batch_id": BATCH_ID, "outputs": {}, "errors": []}
    for plan in run_plan:
        out = by.get(plan["output_id"]) or {}
        gen = by.get(plan["generator_id"]) or {}
        group = next((n for n in canvas.get("nodes") or [] if n.get("type") == "group" and n.get("codexRequirementKey") == plan["requirement_key"]), {})
        urls = []
        missing = []
        for item in visible_images(out):
            url = output_url_value(item)
            urls.append(url)
            if url.startswith("/assets/") and not (ROOT / url.lstrip("/").replace("/", os.sep)).exists():
                missing.append(url)
        result["outputs"][plan["requirement_key"]] = {
            "title": plan["target_title"],
            "output_id": plan["output_id"],
            "output_name": out.get("name"),
            "real_images": len(urls),
            "missing_files": len(missing),
            "group_id": group.get("id"),
            "generator_id": gen.get("id"),
            "x": out.get("x"),
            "y": out.get("y"),
            "w": out.get("w"),
            "h": out.get("h"),
            "urls": urls,
        }
        if len(urls) != TARGET_COUNT:
            result["errors"].append(f"{plan['requirement_key']}: {len(urls)}/{TARGET_COUNT}")
        if missing:
            result["errors"].append(f"{plan['requirement_key']}: missing files {missing}")
        if not group or not gen or not out:
            result["errors"].append(f"{plan['requirement_key']}: missing workflow node")
    return result


def main():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(SOURCE_PATH)
    progress = {
        "started_at": now_ms(),
        "canvas_id": CANVAS_ID,
        "target_canvas_title": "背景图",
        "batch_id": BATCH_ID,
        "source_path": str(SOURCE_PATH),
        "target_count_per_requirement": TARGET_COUNT,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "tasks": {},
        "rounds": [],
    }
    write_progress(progress)
    imported = import_local_image(SOURCE_PATH)
    progress["source_url"] = imported.get("url")
    progress["backup"] = backup_canvas()

    canvas = load_canvas()
    created, run_plan = create_board(canvas, progress["source_url"])
    saved = save_canvas(canvas, "codex-single-bg-diff-create")
    progress["created"] = created
    progress["run_plan"] = run_plan
    progress["canvas_updated_at"] = saved.get("updated_at")
    safe_write_progress(progress)

    for round_no in range(1, MAX_REFILL_ROUNDS + 1):
        _, counts = remaining_plans(run_plan)
        if all(count >= TARGET_COUNT for count in counts.values()):
            break
        attempts = run_round(run_plan, progress, round_no)
        if attempts <= 0:
            break

    progress["verification"] = verify(run_plan)
    progress["finished_at"] = now_ms()
    safe_write_progress(progress)
    print(json.dumps(progress["verification"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
