#!/usr/bin/env python3
import concurrent.futures
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = ROOT / "output" / "codex_tokyo_metropolitan_inside_fix_progress.json"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"
SCENE_KEY = "shinjuku_tokyo_metropolitan_government"
TITLE = "新宿｜东京都厅大楼内部展望室背景图"
PROVIDERS = [
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
]


def now_ms():
    return int(time.time() * 1000)


def http_json(method, path, payload=None, timeout=120):
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


def save_canvas(canvas, client_id):
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


def node_map(canvas):
    return {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}


def output_url_value(item):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("url") or ""
    return ""


def write_progress(progress):
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def submit_task(plan):
    payload = {
        "prompt": plan["prompt"],
        "provider_id": plan["provider_id"],
        "model": plan["model"],
        "size": SIZE,
        "quality": QUALITY,
        "n": 1,
        "reference_images": plan["reference_images"],
    }
    return http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)


def poll_task(task_id):
    while True:
        task = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=40)
        status = str(task.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return task
        time.sleep(2)


def append_result(plan, task, progress):
    canvas = load_canvas()
    by = node_map(canvas)
    output = by[progress["workflow"]["output_id"]]
    generator = by.get(plan["generator_id"])
    status = str(task.get("status") or "").lower()
    result = task.get("result") or {}
    urls = result.get("images") or []
    added = 0
    if status == "succeeded" and urls:
        existing = {output_url_value(item) for item in output.get("images") or [] if output_url_value(item)}
        for url in urls:
            if url in existing:
                continue
            output.setdefault("images", []).append({
                "url": url,
                "viewed": False,
                "source": "codex_tokyo_metropolitan_inside_refill",
                "provider_id": plan["provider_id"],
                "provider_name": plan["provider_name"],
                "model": plan["model"],
                "task_id": task.get("id") or task.get("task_id") or "",
                "scene_key": SCENE_KEY,
                "createdAt": now_ms(),
                "runMs": task.get("run_ms") or task.get("total_ms") or 0,
            })
            existing.add(url)
            added += 1
    if generator is not None:
        generator["runStatus"] = "done" if added else "failed"
        generator["runError"] = "" if added else str(task.get("error") or task.get("status") or "任务失败")[:500]
        if added:
            generated = generator.setdefault("generatedOutputs", [])
            for url in urls:
                if url not in generated:
                    generated.append(url)
    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_tokyo_inside_refill_{uuid.uuid4().hex[:10]}_{now_ms()}",
        "createdAt": now_ms(),
        "status": "done" if added else "failed",
        "nodeType": "generator",
        "model": plan["model"],
        "prompt": plan["prompt"],
        "outputs": urls if added else [],
        "error": "" if added else str(task.get("error") or task.get("status") or "任务失败")[:1000],
        "platform": plan["provider_name"],
        "runMs": task.get("run_ms") or task.get("total_ms") or 0,
        "task_id": task.get("id") or task.get("task_id") or "",
        "request": {
            "scene_key": SCENE_KEY,
            "target_title": TITLE,
            "provider_id": plan["provider_id"],
            "model": plan["model"],
            "size": SIZE,
            "quality": QUALITY,
            "reference_count": len(plan["reference_images"]),
            "round": plan["round"],
            "queue_ms": task.get("queue_ms"),
            "run_ms": task.get("run_ms"),
        },
    })
    canvas["logs"] = canvas["logs"][:500]
    save_canvas(canvas, "codex-tokyo-metropolitan-inside-refill")
    progress["appended"] += added
    return added


def accepted_count(progress):
    canvas = load_canvas()
    output = node_map(canvas)[progress["workflow"]["output_id"]]
    return len([item for item in output.get("images") or [] if output_url_value(item)])


def main():
    progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    canvas = load_canvas()
    by = node_map(canvas)
    prompt = by[progress["workflow"]["prompt_id"]]["text"]
    reference = {
        "url": progress["workflow"]["reference_url"],
        "name": progress["workflow"]["reference_name"],
        "role": progress["workflow"]["reference_role"],
    }
    progress.setdefault("refill_rounds", [])

    round_index = len(progress["refill_rounds"]) + 2
    while accepted_count(progress) < TARGET_COUNT and round_index <= 5:
        missing = TARGET_COUNT - accepted_count(progress)
        plans = []
        for i in range(missing):
            provider_id, provider_name, model = PROVIDERS[i % len(PROVIDERS)]
            plans.append({
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "prompt": prompt,
                "reference_images": [reference],
                "generator_id": progress["workflow"]["generator_ids"][i % len(progress["workflow"]["generator_ids"])],
                "round": round_index,
            })
        round_record = {"round": round_index, "missing_before": missing, "submitted": 0, "succeeded": 0, "failed": 0}
        progress["refill_rounds"].append(round_record)
        submissions = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(2, len(plans))) as pool:
            future_map = {pool.submit(submit_task, plan): plan for plan in plans}
            for future in concurrent.futures.as_completed(future_map):
                plan = future_map[future]
                key = f"{SCENE_KEY}::{plan['provider_name']}::r{round_index}::{uuid.uuid4().hex[:6]}"
                try:
                    task = future.result()
                    task_id = task.get("task_id")
                    progress["submitted"] += 1
                    round_record["submitted"] += 1
                    progress["tasks"][key] = {
                        "scene_key": SCENE_KEY,
                        "target_title": TITLE,
                        "provider_name": plan["provider_name"],
                        "provider_id": plan["provider_id"],
                        "model": plan["model"],
                        "round": round_index,
                        "task_id": task_id,
                        "submit_status": task.get("status"),
                    }
                    if task_id:
                        submissions.append((key, plan, task_id))
                except Exception as exc:
                    progress["failed"] += 1
                    round_record["failed"] += 1
                    progress["tasks"][key] = {"status": "submit_failed", "error": str(exc)}
                write_progress(progress)

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(2, len(submissions))) as pool:
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
                        round_record["succeeded"] += 1
                    else:
                        progress["failed"] += 1
                        round_record["failed"] += 1
                    append_result(plan, task, progress)
                except Exception as exc:
                    progress["failed"] += 1
                    round_record["failed"] += 1
                    progress["tasks"][key].update({"status": "poll_failed", "error": str(exc)})
                progress["accepted_success_count"] = accepted_count(progress)
                write_progress(progress)
        round_record["accepted_after"] = accepted_count(progress)
        round_index += 1

    progress["accepted_success_count"] = accepted_count(progress)
    progress["finished_at"] = now_ms()
    progress["canvas_url"] = f"{BASE}/static/canvas.html?canvas={CANVAS_ID}"
    write_progress(progress)
    print(json.dumps(progress, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
