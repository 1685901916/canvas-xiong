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
PROGRESS_PATH = ROOT / "output" / "codex_other_backgrounds_local_scenes_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"
PROVIDERS = [
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
]

LOCAL_SCENES = {
    "shinjuku_kabukicho": {
        "title": "新宿｜歌舞伎町局部娱乐街背景图",
        "place": "歌舞伎町内部街区的人视角局部场景，可以是店铺门口、游戏中心入口、窄巷转角或室内外过渡的商店街",
        "must": "街面或店内入口在近中景，抽象灯牌、橱窗、街机/夹娃娃机或娱乐楼入口，干净地面和角色站位",
        "avoid": "不要鸟瞰地图，不要远处街区总览，不要只拍红色拱门，不要成人店/酒吧陪酒场景，不要可读文字",
    },
    "ueno_shinobazu_pond": {
        "title": "上野公园｜不忍池池边局部背景图",
        "place": "不忍池里面可停留的池边步道/桥边/弁天堂入口附近局部场景，不是宏观湖面地图",
        "must": "近景有栏杆、石板路、木桥或长椅；中景有莲叶、水面反光；远景隐约有弁天堂或池边树影",
        "avoid": "不要鸟瞰池塘，不要大范围湖面全景，不要寺院室内房间，不要佛像神像特写",
    },
    "ueno_tokyo_national_museum": {
        "title": "上野公园｜东京国立博物馆展厅局部背景图",
        "place": "东京国立博物馆本馆里面可对话的展厅/走廊/楼梯转角局部场景",
        "must": "展柜、拱门、柱子、木质或石质地面、暖色展厅灯光，前景留人物站位",
        "avoid": "不要外立面总览，不要入口广场，不要宏观博物馆地图，不要可读展签文字",
    },
    "meiji_otorii": {
        "title": "明治神宫｜大鸟居下参道局部背景图",
        "place": "明治神宫大鸟居下方或穿过鸟居后的参道局部场景，人站在参道上的视角",
        "must": "近景碎石参道和木栅栏，中景是大鸟居柱脚或门框一部分，两侧森林、石灯笼或木牌点缀",
        "avoid": "不要鸟瞰森林地图，不要远距离完整大鸟居明信片，不要神社室内房间，不要游客人群",
    },
    "meiji_inner_garden": {
        "title": "明治神宫｜御苑庭园局部背景图",
        "place": "明治神宫御苑里面可散步停留的庭园路径/茶亭檐下/花菖蒲田边局部场景",
        "must": "近景庭园步道、木栏或茶亭檐下，中景灌木、花丛或小桥，远景深绿树影",
        "avoid": "不要鸟瞰庭园地图，不要纯室内茶室房间，不要开阔草地总览，不要现代咖啡店",
    },
    "meiji_gyoen_pond": {
        "title": "明治神宫｜御苑池塘水边局部背景图",
        "place": "御苑池塘边可停留的水边步道、栏杆、矮桥或茶亭檐下局部场景",
        "must": "近景栏杆/木地板/石岸，中景池水反光和树影，远景岸边岩石、灌木或小亭",
        "avoid": "不要鸟瞰池塘地图，不要只在室内看窗外，不要阴暗木屋，不要大范围水面全景",
    },
}


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
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def prompt_for(scene):
    return (
        f"任务：生成《{scene['title']}》。这是 Aiko Tokyo v2 项目里的 galgame 背景图，要的是当地内部/局部体验场景，不是宏观地图，也不一定是室内房间。\n"
        f"地点定位：{scene['place']}。\n"
        f"必须包含：{scene['must']}。\n"
        "镜头与构图：竖版 9:16；人视角、平视或略高于人眼；前景下方留人物立绘站位；中景是可进入/可停留的局部场景；远景只保留地点识别，不要做成地标总览。\n"
        "画风：沿用项目参考图的 Aiko Tokyo v2 柔和小插画感、清晰线稿、干净块面、温暖但克制的色彩、低噪点、高清完成度。参考图只用于画风和地点色彩，不要照抄俯视地图构图。\n"
        "光线：明亮、柔和、可读，温暖但不过黄，不暗、不偏紫；适合游戏对话界面。\n"
        "局部场景要求：要像角色真的走进这个地点后看到的背景，有地面/步道/栏杆/门口/窗边/展柜/座位等可站可停留元素。\n"
        f"禁止：{scene['avoid']}。不要 UI 标记，不要人物角色，不要人物特写，不要真实品牌文字，不要可读招牌字，不要 logo，不要水印，不要乱码，不要赛博朋克，不要写实照片。"
    )


def locate_ids(source, scene_key):
    keys = list(source["scenes"].keys())
    idx = keys.index(scene_key)
    return {
        "group_id": source["created"]["groups"][idx],
        "output_id": source["created"]["outputs"][idx],
        "prompt_id": source["created"]["prompts"][idx + 1],
        "generator_ids": source["created"]["generators"][idx * 5:(idx + 1) * 5],
        "scene_index": idx,
    }


def prepare(progress):
    source = json.loads(SOURCE_PROGRESS.read_text(encoding="utf-8"))
    canvas_file = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{CANVAS_ID}.before-local-scenes-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(canvas_file, backup)

    canvas = load_canvas()
    by = node_map(canvas)
    progress["backup"] = str(backup)
    progress["workflows"] = {}
    plans = []
    for scene_key, scene in LOCAL_SCENES.items():
        ids = locate_ids(source, scene_key)
        ref_key = source["scenes"][scene_key]["ref_key"]
        ref = next(item for item in source["imported_refs"] if item["key"] == ref_key)
        group = by[ids["group_id"]]
        output = by[ids["output_id"]]
        prompt = by[ids["prompt_id"]]
        old_images = output.get("images") or []
        old_rejected = output.get("rejectedImages") or []
        text = prompt_for(scene)
        group["name"] = f"{scene['title']} 输入｜目标5张"
        prompt["name"] = f"{scene['title']} 提示词"
        prompt["text"] = text
        output["name"] = f"{scene['title']} 输出｜目标5张"
        output["images"] = []
        output["rejectedImages"] = old_rejected + old_images
        output["rejectionReason"] = "用户修正：内部场景不是全部室内房间，而是当地局部/人视角体验场景；上一轮过度室内化结果移入 rejectedImages。"
        group_x = float(group.get("x") or 0)
        group_y = float(group.get("y") or 0)
        group_w = float(group.get("w") or 1120)
        output["x"] = group_x + group_w + 600
        output["y"] = group_y + 18
        output["w"] = 760
        output["h"] = 680
        for i, gen_id in enumerate(ids["generator_ids"][:1]):
            provider_id, provider_name, model = PROVIDERS[i]
            gen = by[gen_id]
            gen["x"] = group_x + group_w + 80 + (i % 2) * 235
            gen["y"] = group_y + 35 + (i // 2) * 118
            gen["w"] = 380
            gen["h"] = 0
            gen["apiProvider"] = provider_id
            gen["model"] = model
            gen["ratio"] = "portrait916"
            gen["resolution"] = "1k"
            gen["quality"] = QUALITY
            gen["count"] = 1
            gen["runStatus"] = "queued"
            gen["runError"] = ""
            gen["generatedOutputs"] = []
            gen["name"] = f"{scene['title']} / {provider_name}"
            gen["targetOutputId"] = ids["output_id"]
            gen["poolTargetCount"] = TARGET_COUNT
            gen["inputs"] = [f"{ids['group_id']}:{group.get('items', [''])[0]}", f"{ids['group_id']}:prompts"]
            plans.append({
                "scene_key": scene_key,
                "target_title": scene["title"],
                "prompt": text,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "size": SIZE,
                "quality": QUALITY,
                "reference_images": [{"url": ref["url"], "name": ref["name"], "role": ref["role"]}],
                "reference_count": 1,
                "generator_id": gen_id,
                "output_id": ids["output_id"],
                "round": 1,
            })
        progress["workflows"][scene_key] = {**ids, "title": scene["title"], "old_images_moved_to_rejected": len(old_images), "target_count": TARGET_COUNT}

    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_local_scenes_plan_{now_ms()}",
        "createdAt": now_ms(),
        "status": "info",
        "nodeType": "canvas-agent",
        "model": "codex_other_backgrounds_local_scenes",
        "prompt": "修正生成口径：内部场景=当地局部/人视角体验场景，不是宏观地图，也不强制室内房间；复用旧6组重新生成。",
        "outputs": [],
        "error": "",
        "platform": "codex",
    })
    canvas["logs"] = canvas["logs"][:500]
    saved = save_canvas(canvas, "codex-local-scenes-prepare")
    progress["canvas_updated_at"] = saved.get("updated_at")
    return plans


def submit_task(plan):
    return http_json("POST", "/api/canvas-image-tasks", {
        "prompt": plan["prompt"],
        "provider_id": plan["provider_id"],
        "model": plan["model"],
        "size": plan["size"],
        "quality": plan["quality"],
        "n": 1,
        "reference_images": plan["reference_images"],
    }, timeout=90)


def poll_task(task_id):
    while True:
        task = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=40)
        if str(task.get("status") or "").lower() in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return task
        time.sleep(2)


def append_result(plan, task, progress):
    canvas = load_canvas()
    by = node_map(canvas)
    output = by.get(plan["output_id"])
    gen = by.get(plan["generator_id"])
    status = str(task.get("status") or "").lower()
    result = task.get("result") or {}
    urls = result.get("images") or []
    added = 0
    if output is not None and status == "succeeded" and urls:
        existing = {output_url_value(item) for item in output.get("images") or [] if output_url_value(item)}
        for url in urls:
            if not url or url in existing:
                continue
            output.setdefault("images", []).append({
                "url": url,
                "viewed": False,
                "source": "codex_other_backgrounds_local_scenes",
                "provider_id": plan["provider_id"],
                "provider_name": plan["provider_name"],
                "model": plan["model"],
                "task_id": task.get("id") or task.get("task_id") or "",
                "scene_key": plan["scene_key"],
                "createdAt": now_ms(),
                "runMs": task.get("run_ms") or task.get("total_ms") or 0,
            })
            existing.add(url)
            added += 1
    if gen is not None:
        gen["runStatus"] = "done" if added else "failed"
        gen["runError"] = "" if added else str(task.get("error") or task.get("status") or "任务失败")[:500]
        if added:
            generated = gen.setdefault("generatedOutputs", [])
            for url in urls:
                if url not in generated:
                    generated.append(url)
    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_local_scene_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
            "scene_key": plan["scene_key"],
            "target_title": plan["target_title"],
            "provider_id": plan["provider_id"],
            "model": plan["model"],
            "size": plan["size"],
            "quality": plan["quality"],
            "reference_count": plan["reference_count"],
            "round": plan["round"],
            "queue_ms": task.get("queue_ms"),
            "run_ms": task.get("run_ms"),
        },
    })
    canvas["logs"] = canvas["logs"][:500]
    save_canvas(canvas, "codex-local-scenes-append")
    progress["appended"] += added


def accepted_count(output_id):
    canvas = load_canvas()
    output = node_map(canvas).get(output_id) or {}
    return len([item for item in output.get("images") or [] if output_url_value(item)])


def run_plans(plans, progress, round_index):
    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(plans))) as pool:
        future_map = {pool.submit(submit_task, plan): plan for plan in plans}
        for future in concurrent.futures.as_completed(future_map):
            plan = future_map[future]
            key = f"{plan['scene_key']}::{plan['provider_name']}::r{round_index}::{uuid.uuid4().hex[:6]}"
            try:
                task = future.result()
                task_id = task.get("task_id")
                progress["submitted"] += 1
                progress["tasks"][key] = {"scene_key": plan["scene_key"], "target_title": plan["target_title"], "provider_name": plan["provider_name"], "provider_id": plan["provider_id"], "model": plan["model"], "round": round_index, "task_id": task_id, "submit_status": task.get("status")}
                if task_id:
                    submissions.append((key, plan, task_id))
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key] = {"status": "submit_failed", "error": str(exc)}
            write_progress(progress)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(submissions))) as pool:
        future_map = {pool.submit(poll_task, task_id): (key, plan, task_id) for key, plan, task_id in submissions}
        for future in concurrent.futures.as_completed(future_map):
            key, plan, task_id = future_map[future]
            try:
                task = future.result()
                status = str(task.get("status") or "").lower()
                progress["tasks"][key].update({"status": status, "queue_ms": task.get("queue_ms"), "run_ms": task.get("run_ms"), "total_ms": task.get("total_ms"), "error": task.get("error") or "", "result": task.get("result") or None})
                if status == "succeeded":
                    progress["succeeded"] += 1
                else:
                    progress["failed"] += 1
                append_result(plan, task, progress)
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key].update({"status": "poll_failed", "error": str(exc)})
            write_progress(progress)


def build_refill(progress, round_index):
    source = json.loads(SOURCE_PROGRESS.read_text(encoding="utf-8"))
    canvas = load_canvas()
    by = node_map(canvas)
    plans = []
    for scene_key, wf in progress["workflows"].items():
        current = accepted_count(wf["output_id"])
        progress["scenes"][scene_key]["accepted_success_count"] = current
        missing = TARGET_COUNT - current
        if missing <= 0:
            continue
        ref_key = source["scenes"][scene_key]["ref_key"]
        ref = next(item for item in source["imported_refs"] if item["key"] == ref_key)
        prompt = by[wf["prompt_id"]]["text"]
        for i in range(missing):
            provider_id, provider_name, model = PROVIDERS[(round_index + i) % len(PROVIDERS)]
            plans.append({"scene_key": scene_key, "target_title": wf["title"], "prompt": prompt, "provider_id": provider_id, "provider_name": provider_name, "model": model, "size": SIZE, "quality": QUALITY, "reference_images": [{"url": ref["url"], "name": ref["name"], "role": ref["role"]}], "reference_count": 1, "generator_id": wf["generator_ids"][i % len(wf["generator_ids"])], "output_id": wf["output_id"], "round": round_index})
    return plans


def main():
    progress = {
        "started_at": now_ms(),
        "canvas_id": CANVAS_ID,
        "target_canvas_title": "背景图",
        "target_count_per_scene": TARGET_COUNT,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "tasks": {},
        "scenes": {key: {"title": value["title"], "target": TARGET_COUNT, "accepted_success_count": 0} for key, value in LOCAL_SCENES.items()},
        "diagnosis": "用户修正：内部场景不是全部室内房间，而是当地局部/人视角体验场景；本轮避免宏观地图和远景总览。",
    }
    write_progress(progress)
    plans = prepare(progress)
    write_progress(progress)
    run_plans(plans, progress, 1)
    for round_index in range(2, 5):
        refill = build_refill(progress, round_index)
        if not refill:
            break
        progress.setdefault("refill_rounds", []).append({"round": round_index, "submitted_planned": len(refill)})
        write_progress(progress)
        run_plans(refill, progress, round_index)
    for scene_key, wf in progress["workflows"].items():
        progress["scenes"][scene_key]["accepted_success_count"] = accepted_count(wf["output_id"])
    progress["finished_at"] = now_ms()
    progress["canvas_url"] = f"{BASE}/static/canvas.html?canvas={CANVAS_ID}"
    write_progress(progress)
    print(json.dumps(progress, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
