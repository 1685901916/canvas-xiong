import concurrent.futures
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "0872cb9368c440bcbca49eb43110652c"
ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = ROOT / "output" / "codex_submap_batch_progress.json"

GENERATOR_IDS = [
    "gen_e04b6d6884a8_1780761114068",
    "gen_799ca9f42bc0_1780761114092",
    "gen_bfaa20e3e1c6_1780761114116",
    "gen_9d18067973ef_1780761114142",
    "gen_62f0a645f2c8_1780761114167",
    "gen_a82c36a4d2ed_1780761114192",
    "gen_838f34db9a6d_1780761114219",
    "gen_6fa0938c77f9_1780761114245",
    "gen_8a3e921991ca_1780761114267",
]


def http_json(method, path, payload=None, timeout=60):
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:800]}") from exc


def now_ms():
    return int(time.time() * 1000)


def load_canvas():
    return http_json("GET", f"/api/canvases/{CANVAS_ID}")["canvas"]


def save_canvas(canvas, client_id):
    payload = {
        "title": canvas.get("title") or "未命名画布",
        "icon": canvas.get("icon") or "🗺️",
        "nodes": canvas.get("nodes") or [],
        "connections": canvas.get("connections") or [],
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": (canvas.get("logs") or [])[-500:],
        "settings": canvas.get("settings") or {},
        "client_id": client_id,
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=90)["canvas"]


def node_map(canvas):
    return {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}


def output_value(item):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("url") or ""
    return ""


def unique_append(items, additions):
    seen = {output_value(item) for item in items if output_value(item)}
    added = 0
    for item in additions:
        url = output_value(item)
        if not url or url in seen:
            continue
        items.append(item)
        seen.add(url)
        added += 1
    return added


def input_parts(input_id):
    if ":" not in input_id:
        return "", input_id
    group_id, child = input_id.split(":", 1)
    return group_id, child


def refs_and_prompt(canvas, gen):
    by = node_map(canvas)
    prompts = []
    refs = []
    for input_id in gen.get("inputs") or []:
        group_id, child = input_parts(input_id)
        if child == "prompts" and group_id in by:
            for item_id in by[group_id].get("items") or []:
                node = by.get(item_id)
                if node and node.get("type") == "prompt" and node.get("text"):
                    prompts.append(node.get("text"))
        else:
            node = by.get(child or input_id)
            if node and node.get("type") == "prompt" and node.get("text"):
                prompts.append(node.get("text"))
            if node and node.get("type") == "image" and node.get("url"):
                refs.append({
                    "url": node.get("url"),
                    "name": node.get("name") or "",
                    "role": node.get("role") or "",
                })
    prompt = "\n\n".join(text for text in prompts if text).strip() or "Edit the reference images."
    return prompt, refs


def output_for_generator(canvas, gen_id):
    by = node_map(canvas)
    for conn in canvas.get("connections") or []:
        if conn.get("from") == gen_id and by.get(conn.get("to"), {}).get("type") == "output":
            return by.get(conn.get("to"))
    return None


def request_size(gen):
    # Matches the current 4:3 / 1k generator setting on the canvas.
    if gen.get("ratio") == "landscape43":
        return "1344x1008"
    return "1024x1024"


def write_progress(progress):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def submit_task(payload):
    return http_json("POST", "/api/canvas-image-tasks", payload, timeout=60)


def poll_task(task_id):
    while True:
        task = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=30)
        status = task.get("status")
        if status in {"succeeded", "failed", "jimeng_pending"}:
            return task
        time.sleep(2.0)


def main():
    canvas = load_canvas()
    by = node_map(canvas)
    progress = {
        "started_at": now_ms(),
        "canvas_id": CANVAS_ID,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "generators": {},
        "tasks": {},
    }
    write_progress(progress)

    submissions = []
    for gen_id in GENERATOR_IDS:
        gen = by[gen_id]
        prompt, refs = refs_and_prompt(canvas, gen)
        payload = {
            "prompt": prompt,
            "provider_id": gen.get("apiProvider") or "custom-api-2",
            "model": gen.get("model") or "gpt-image-2",
            "size": request_size(gen),
            "quality": gen.get("quality") or "auto",
            "reference_images": refs,
        }
        count = max(1, min(8, int(gen.get("count") or 1)))
        out = output_for_generator(canvas, gen_id)
        progress["generators"][gen_id] = {
            "name": gen.get("name") or gen_id,
            "count": count,
            "output_id": out.get("id") if out else "",
            "before": len(out.get("images") or []) if out else 0,
            "provider_id": payload["provider_id"],
            "model": payload["model"],
            "size": payload["size"],
            "reference_count": len(refs),
        }
        for index in range(count):
            submissions.append((gen_id, index + 1, payload))

    with concurrent.futures.ThreadPoolExecutor(max_workers=18) as pool:
        future_map = {pool.submit(submit_task, payload): (gen_id, index) for gen_id, index, payload in submissions}
        for future in concurrent.futures.as_completed(future_map):
            gen_id, index = future_map[future]
            task_key = f"{gen_id}#{index}"
            try:
                task = future.result()
                progress["submitted"] += 1
                progress["tasks"][task_key] = {
                    "task_id": task.get("task_id"),
                    "gen_id": gen_id,
                    "submit_status": task.get("status"),
                    "request": task.get("request") or {},
                    "resolved": task.get("resolved") or {},
                }
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][task_key] = {"gen_id": gen_id, "submit_error": str(exc)}
            write_progress(progress)

    poll_items = [(key, item["task_id"]) for key, item in progress["tasks"].items() if item.get("task_id")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=18) as pool:
        future_map = {pool.submit(poll_task, task_id): (key, task_id) for key, task_id in poll_items}
        for future in concurrent.futures.as_completed(future_map):
            key, task_id = future_map[future]
            try:
                task = future.result()
                progress["tasks"][key].update({
                    "status": task.get("status"),
                    "queue_ms": task.get("queue_ms"),
                    "run_ms": task.get("run_ms"),
                    "total_ms": task.get("total_ms"),
                    "error": task.get("error") or "",
                    "result": task.get("result") or None,
                })
                if task.get("status") == "succeeded":
                    progress["succeeded"] += 1
                else:
                    progress["failed"] += 1
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key].update({"status": "failed", "error": str(exc)})
            write_progress(progress)

    latest = load_canvas()
    latest_by = node_map(latest)
    for key, task in progress["tasks"].items():
        if task.get("status") != "succeeded":
            continue
        gen_id = task.get("gen_id") or key.split("#", 1)[0]
        gen = latest_by.get(gen_id)
        out = output_for_generator(latest, gen_id)
        result = task.get("result") or {}
        images = result.get("images") or []
        if not gen or not out or not images:
            continue
        run_meta = {
            "nodeType": "generator",
            "node": {
                "id": gen.get("id"),
                "name": gen.get("name") or "",
                "type": "generator",
                "apiProvider": gen.get("apiProvider") or "",
                "model": gen.get("model") or "",
            },
            "prompt": result.get("prompt") or "",
            "refs": (result.get("params") or {}).get("reference_images") or [],
            "request": result.get("request") or {},
        }
        additions = []
        for url in images:
            additions.append({
                "url": url,
                "viewed": False,
                "runMs": task.get("run_ms") or task.get("total_ms") or 0,
                "run": run_meta,
            })
        progress["appended"] += unique_append(out.setdefault("images", []), additions)
        unique_append(gen.setdefault("generatedOutputs", []), images)

    latest.setdefault("logs", [])
    for key, task in progress["tasks"].items():
        if task.get("status") != "succeeded":
            continue
        result = task.get("result") or {}
        latest["logs"].insert(0, {
            "id": f"codex_submap_{key}_{now_ms()}",
            "createdAt": now_ms(),
            "status": "done",
            "platform": result.get("provider_name") or "",
            "nodeType": "generator",
            "model": result.get("model") or "",
            "prompt": result.get("prompt") or "",
            "outputs": result.get("images") or [],
            "runMs": task.get("run_ms") or 0,
            "error": "",
            "request": result.get("resolved") or result.get("request") or {},
        })
    latest["logs"] = latest["logs"][:500]
    latest = save_canvas(latest, "codex-submap-batch-append")

    latest_by = node_map(latest)
    for gen_id, info in progress["generators"].items():
        out_id = info.get("output_id")
        out = latest_by.get(out_id) if out_id else None
        info["after"] = len(out.get("images") or []) if out else 0
    progress["finished_at"] = now_ms()
    progress["canvas_updated_at"] = latest.get("updated_at")
    write_progress(progress)
    print(json.dumps({
        "submitted": progress["submitted"],
        "succeeded": progress["succeeded"],
        "failed": progress["failed"],
        "appended": progress["appended"],
        "progress": str(PROGRESS_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
