#!/usr/bin/env python3
import concurrent.futures
import json
import shutil
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
ROOT = Path(__file__).resolve().parents[1]
SOURCE_PROGRESS = ROOT / "output" / "codex_background_scenes_progress.json"
PROGRESS_PATH = ROOT / "output" / "codex_tokyo_metropolitan_inside_fix_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"

SCENE_KEY = "shinjuku_tokyo_metropolitan_government"
TITLE = "新宿｜东京都厅大楼内部展望室背景图"
PROVIDERS = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
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


def write_progress(progress):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


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
    return {n.get("id"): n for n in canvas.get("nodes") or [] if n.get("id")}


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


def inside_prompt():
    return (
        "任务：修正生成《新宿｜东京都厅大楼内部展望室背景图》。这里要的是大楼里面的背景，不是大楼外观、不是外部广场。\n"
        "地点：东京都厅第一本厅舍 45 层展望室/观景层内部，适合作为 galgame 约会地点背景图。\n"
        "必须包含：室内展望层空间、大面积落地观景窗、窗外新宿城市高楼远景、展望室电梯厅或观景走廊、少量咖啡/纪念品店元素、干净地面和前景站位空间。\n"
        "镜头与构图：竖版 9:16 手机背景；镜头在室内，略高于人眼或平视；前景下方留给人物立绘站位；中景是展望室栏杆/地面/窗边座位；远景通过窗户看到城市天际线。\n"
        "画风：沿用 Aiko Tokyo v2 项目的柔和小插画感、清晰线稿、干净块面、温暖但克制的色彩、低噪点、高清完成度。参考图只作为项目画风和新宿色彩参考，不要复制外部街景构图。\n"
        "光线：明亮、柔和、室内自然采光；窗边有清爽天空光和轻微反射；整体不暗、不黄、不偏紫。\n"
        "空间氛围：安静、现代、适合约会看城市风景；不是办公区，不要政府办事大厅压迫感。\n"
        "禁止：不要建筑外观，不要双塔外景，不要外部广场，不要俯视地图，不要 UI 标记，不要人物角色，不要真实品牌文字，不要可读招牌字，不要 logo，不要水印，不要乱码，不要夜店霓虹，不要赛博朋克，不要太暗，不要太黄，不要写实照片，不要杂乱办公室格子间。"
    )


def locate_scene_ids(source):
    scene_keys = list(source["scenes"].keys())
    index = scene_keys.index(SCENE_KEY)
    return {
        "group_id": source["created"]["groups"][index],
        "output_id": source["created"]["outputs"][index],
        "prompt_id": source["created"]["prompts"][index + 1],
        "generator_ids": source["created"]["generators"][index * 5:(index + 1) * 5],
        "reference_url": source["imported_refs"][0]["url"],
        "reference_name": source["imported_refs"][0]["name"],
        "reference_role": source["imported_refs"][0]["role"],
    }


def prepare_workflow(progress):
    source = json.loads(SOURCE_PROGRESS.read_text(encoding="utf-8"))
    ids = locate_scene_ids(source)
    canvas_file = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-tokyo-metropolitan-inside-fix-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(canvas_file, backup_path)

    canvas = load_canvas()
    by = node_map(canvas)
    prompt_text = inside_prompt()
    prompt = by[ids["prompt_id"]]
    prompt["text"] = prompt_text
    prompt["name"] = f"{TITLE} 提示词"
    group = by[ids["group_id"]]
    group["name"] = f"{TITLE} 输入｜目标5张"
    out = by[ids["output_id"]]
    rejected = out.get("images") or []
    out["images"] = []
    out["name"] = f"{TITLE} 输出｜目标5张"
    out["rejectedImages"] = rejected
    out["rejectionReason"] = "用户修正：不要大楼外观背景，要大楼里面/展望室室内背景。"

    run_plan = []
    for idx, gen_id in enumerate(ids["generator_ids"]):
        provider_id, provider_name, model = PROVIDERS[idx]
        gen = by[gen_id]
        gen["apiProvider"] = provider_id
        gen["model"] = model
        gen["ratio"] = "portrait916"
        gen["resolution"] = "1k"
        gen["quality"] = QUALITY
        gen["count"] = 1
        gen["runStatus"] = "queued"
        gen["runError"] = ""
        gen["generatedOutputs"] = []
        gen["name"] = f"{TITLE} / {provider_name}"
        gen["targetOutputId"] = ids["output_id"]
        gen["poolTargetCount"] = TARGET_COUNT
        run_plan.append({
            "scene_key": SCENE_KEY,
            "target_title": TITLE,
            "prompt": prompt_text,
            "provider_id": provider_id,
            "provider_name": provider_name,
            "model": model,
            "size": SIZE,
            "quality": QUALITY,
            "reference_images": [{
                "url": ids["reference_url"],
                "name": ids["reference_name"],
                "role": ids["reference_role"],
            }],
            "reference_count": 1,
            "generator_id": gen_id,
            "output_id": ids["output_id"],
            "round": 1,
        })

    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_tokyo_metropolitan_inside_fix_plan_{now_ms()}",
        "createdAt": now_ms(),
        "status": "info",
        "nodeType": "canvas-agent",
        "model": "codex_tokyo_metropolitan_inside_fix",
        "prompt": "修正东京都厅大楼背景图：用户要求大楼里面的背景，改为45层展望室/观景层室内背景；原外观图移入 rejectedImages，重新生成5张。",
        "outputs": [],
        "error": "",
        "platform": "codex",
    })
    canvas["logs"] = canvas["logs"][:500]
    saved = save_canvas(canvas, "codex-tokyo-metropolitan-inside-board")
    progress.update({
        "backup": str(backup_path),
        "workflow": ids,
        "rejected_previous_count": len(rejected),
        "created_or_reused": {
            "group_id": ids["group_id"],
            "prompt_id": ids["prompt_id"],
            "output_id": ids["output_id"],
            "generator_ids": ids["generator_ids"],
        },
        "canvas_updated_at": saved.get("updated_at"),
    })
    return run_plan


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
    return http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)


def poll_task(task_id):
    while True:
        task = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=40)
        status = str(task.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return task
        time.sleep(2)


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
        additions = [{
            "url": url,
            "viewed": False,
            "source": "codex_tokyo_metropolitan_inside_fix",
            "provider_id": plan["provider_id"],
            "provider_name": plan["provider_name"],
            "model": plan["model"],
            "task_id": task.get("id") or task.get("task_id") or "",
            "scene_key": plan["scene_key"],
            "createdAt": now_ms(),
            "runMs": task.get("run_ms") or task.get("total_ms") or 0,
        } for url in urls]
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
        "id": f"codex_tokyo_inside_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
            "scene_key": plan["scene_key"],
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
    saved = save_canvas(latest, "codex-tokyo-metropolitan-inside-append")
    progress["appended"] += added
    progress["canvas_updated_at"] = saved.get("updated_at")


def run_round(plans, progress):
    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        future_map = {pool.submit(submit_task, plan): plan for plan in plans}
        for future in concurrent.futures.as_completed(future_map):
            plan = future_map[future]
            key = f"{plan['scene_key']}::{plan['provider_name']}::r1::{uuid.uuid4().hex[:6]}"
            try:
                task = future.result()
                task_id = task.get("task_id")
                progress["submitted"] += 1
                progress["tasks"][key] = {
                    "scene_key": plan["scene_key"],
                    "target_title": plan["target_title"],
                    "provider_name": plan["provider_name"],
                    "provider_id": plan["provider_id"],
                    "model": plan["model"],
                    "round": 1,
                    "task_id": task_id,
                    "submit_status": task.get("status"),
                }
                if task_id:
                    submissions.append((key, plan, task_id))
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key] = {
                    "scene_key": plan["scene_key"],
                    "target_title": plan["target_title"],
                    "provider_name": plan["provider_name"],
                    "provider_id": plan["provider_id"],
                    "model": plan["model"],
                    "round": 1,
                    "status": "submit_failed",
                    "error": str(exc),
                }
            write_progress(progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
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


def main():
    progress = {
        "started_at": now_ms(),
        "canvas_id": CANVAS_ID,
        "target_canvas_title": "背景图",
        "target_title": TITLE,
        "target_count": TARGET_COUNT,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "tasks": {},
        "diagnosis": "上一轮把用户说的大楼理解成外观大楼广场；本轮修正为大楼内部/45层展望室背景。",
    }
    write_progress(progress)
    plans = prepare_workflow(progress)
    write_progress(progress)
    run_round(plans, progress)

    final = load_canvas()
    out = node_map(final).get(progress["workflow"]["output_id"]) or {}
    progress["accepted_success_count"] = len([x for x in out.get("images") or [] if output_url_value(x)])
    progress["finished_at"] = now_ms()
    progress["canvas_url"] = f"{BASE}/static/canvas.html?canvas={CANVAS_ID}"
    write_progress(progress)
    print(json.dumps(progress, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
