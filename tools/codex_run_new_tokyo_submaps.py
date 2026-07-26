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
PROGRESS_PATH = ROOT / "output" / "codex_new_tokyo_submaps_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
TARGET_COUNT = 10
SIZE = "1344x1008"
QUALITY = "auto"
MAX_ROUNDS = 5

STYLE_REFS = {
    "city_plaza": {
        "url": "/assets/input/ai_ref_b6354833d2cd.png",
        "name": "style-city-plaza.png",
        "role": "统一画风参考：东京商业广场4:3子地图",
    },
    "game_street": {
        "url": "/assets/input/ai_ref_d6a5e5ca085e.png",
        "name": "style-game-street.png",
        "role": "统一画风参考：东京商业街区4:3子地图",
    },
    "tower_park": {
        "url": "/assets/input/ai_ref_e7fca788ac5f.png",
        "name": "style-tower-park.png",
        "role": "统一画风参考：东京塔公园4:3子地图",
    },
    "castle": {
        "url": "/assets/input/ai_ref_be92ecddf1ee.png",
        "name": "style-castle-themepark.png",
        "role": "统一画风参考：旋转木马城堡4:3子地图",
    },
}

PROVIDERS = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-2", "65535", "gpt-image-2"),
]


LOCATIONS = [
    {
        "key": "asakusa_sensoji",
        "title": "浅草寺",
        "style_refs": ["tower_park", "city_plaza"],
        "landmarks": [
            "雷门与大红灯笼作为入口识别点",
            "仲见世商店街轴线",
            "宝藏门、五重塔和本堂",
            "抽签/御守小摊与姻缘神社小角落",
            "浅草传统街区和少量现代街道",
        ],
        "music_mood": "热闹但温柔的传统约会地点，适合抽签、御守和街边小吃",
    },
    {
        "key": "tokyo_disneyland",
        "title": "东京迪士尼乐园",
        "style_refs": ["castle", "city_plaza"],
        "landmarks": [
            "灰姑娘城堡作为中心地标",
            "旋转木马和梦幻乐园广场",
            "拱廊式入口商业街/世界市集感",
            "花坛、喷泉、游行路线和梦幻步道",
            "远处摩天轮/游乐设施轮廓，可爱但不出现受保护角色",
        ],
        "music_mood": "梦幻、八音盒、明亮主题乐园约会感",
    },
    {
        "key": "meiji_jingu",
        "title": "明治神宫",
        "style_refs": ["tower_park", "city_plaza"],
        "landmarks": [
            "巨大木制鸟居",
            "森林参道与碎石路",
            "明治神宫本殿和神社院落",
            "明治神宫御苑、池塘、花菖蒲/庭园",
            "外苑银杏大道作为金绿色通道点",
        ],
        "music_mood": "安静、清澈、森林散步和庭园约会感",
    },
    {
        "key": "shinjuku",
        "title": "新宿",
        "style_refs": ["city_plaza", "game_street"],
        "landmarks": [
            "东京都厅双塔高楼作为西口地标",
            "新宿站前道路与人行横道",
            "家庭餐厅/约会餐厅街角",
            "回忆横丁式小巷和歌舞伎町风娱乐街区",
            "霓虹招牌只做色块氛围，不写真实品牌文字",
        ],
        "music_mood": "都市、餐厅、夜生活入口，但仍保持白天清爽子地图",
    },
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


def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def connect(connections, from_id, to_id):
    if not any(c.get("from") == from_id and c.get("to") == to_id for c in connections):
        connections.append({"id": f"conn_{from_id}_{to_id}", "from": from_id, "to": to_id})


def location_prompt(location):
    landmarks = "；".join(location["landmarks"])
    return (
        f"任务：生成《{location['title']}》的东京 v2 子地图，4:3 横版斜俯视 UI 地图。\n"
        f"地点地标必须包含：{landmarks}。\n"
        f"情绪：{location['music_mood']}。\n"
        "统一画风：参考组内已有东京子地图，只学习画风、镜头、线稿、材质、色彩密度和 UI 地图读图方式；不要复制参考图里的原地点布局。\n"
        "画面要求：galgame 地图分支用的4:3地点子地图；斜俯视/等距感，清晰道路和可点击小标入口，建筑和地标位置易识别，色彩明亮清爽，细线稿，柔和赛璐璐上色，干净低噪声，上午到中午的自然光。\n"
        "构图要求：中心或黄金分割位置放最有辨识度的主地标；周围安排2-4个可点子地点；道路/步道自然连通；保留足够地图阅读空间，不要做成单张竖版背景。\n"
        "避免：不要夜景，不要夕阳，不要太黄，不要太暗，不要写实照片，不要人物特写，不要真实品牌文字，不要水印，不要樱花，不要乱字，不要复制迪士尼受保护角色或商标图案。"
    )


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


def create_board(canvas):
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    xs = [float(n.get("x") or 0) for n in nodes]
    ys = [float(n.get("y") or 0) for n in nodes]
    origin_x = (max(xs) if xs else 0) + 640
    origin_y = min(80, min(ys) if ys else 80)

    created = {"groups": [], "outputs": [], "generators": [], "images": [], "prompts": []}
    run_plan = []
    row_h = 820
    group_w = 1180
    group_h = 560
    gen_x = origin_x + group_w + 80
    out_x = gen_x + 520

    style_summary_text = (
        "统一画风分析：东京 v2 子地图使用4:3横版斜俯视/等距感地图；明亮清爽、细线稿、柔和赛璐璐上色；"
        "画面要像可点击地图，不是单张人物背景。每张图必须有主地标、2-4个次级可点地点、连通道路/步道、清晰空间层级。"
        "避免夜景、夕阳、过黄、过暗、写实照片、真实品牌文字、受保护角色、樱花。"
    )
    summary = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 260,
        "text": style_summary_text,
        "name": "浅草寺/迪士尼/明治神宫/新宿｜统一画风与地标分析",
        "w": 1180,
        "h": 180,
    }
    nodes.append(summary)
    created["prompts"].append(summary["id"])

    for row, location in enumerate(LOCATIONS):
        y = origin_y + row * row_h
        style_nodes = []
        for index, ref_key in enumerate(location["style_refs"]):
            ref = STYLE_REFS[ref_key]
            img = {
                "id": uid("img"),
                "type": "image",
                "x": origin_x + 36 + index * 260,
                "y": y + 88,
                "url": ref["url"],
                "name": ref["name"],
                "role": ref["role"],
                "w": 230,
                "h": 180,
            }
            nodes.append(img)
            style_nodes.append(img)
            created["images"].append(img["id"])
        prompt_text = location_prompt(location)
        prompt = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": origin_x + 560,
            "y": y + 88,
            "text": prompt_text,
            "name": f"{location['title']} 子地图提示词",
            "w": 570,
            "h": 380,
        }
        group = {
            "id": uid("grp"),
            "type": "group",
            "x": origin_x,
            "y": y,
            "w": group_w,
            "h": group_h,
            "items": [n["id"] for n in style_nodes] + [prompt["id"]],
            "name": f"{location['title']} 子地图输入｜目标10张",
        }
        output = {
            "id": uid("out"),
            "type": "output",
            "x": out_x,
            "y": y + 28,
            "w": 820,
            "h": 680,
            "images": [],
            "name": f"{location['title']} 子地图输出｜目标10张",
        }
        nodes.extend([prompt, group, output])
        created["prompts"].append(prompt["id"])
        created["groups"].append(group["id"])
        created["outputs"].append(output["id"])
        refs = [{"url": n["url"], "name": n["name"], "role": n["role"]} for n in style_nodes]

        for index, (provider_id, provider_name, model) in enumerate(PROVIDERS[:1]):
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
                "inputs": [*[f"{group['id']}:{n['id']}" for n in style_nodes], f"{group['id']}:prompts"],
                "count": 1,
                "apiDefaultsVersion": 2,
                "runStatus": "queued",
                "runError": "",
                "name": f"{location['title']} 子地图 / {provider_name}",
                "targetOutputId": output["id"],
                "poolTargetCount": TARGET_COUNT,
            }
            nodes.append(gen)
            created["generators"].append(gen["id"])
            connect(connections, group["id"], gen["id"])
            connect(connections, gen["id"], output["id"])
            run_plan.append({
                "location_key": location["key"],
                "target_title": location["title"],
                "prompt": prompt_text,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "size": SIZE,
                "quality": QUALITY,
                "reference_images": refs,
                "reference_count": len(refs),
                "generator_id": gen["id"],
                "output_id": output["id"],
                "round": 1,
            })
    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_new_tokyo_submaps_plan_{now_ms()}",
        "createdAt": now_ms(),
        "status": "info",
        "nodeType": "canvas-agent",
        "model": "codex_new_tokyo_submaps",
        "prompt": "浅草寺、东京迪士尼乐园、明治神宫、新宿：统一东京v2子地图画风，每地点10张。",
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
    return http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)


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
        additions = [{
            "url": url,
            "viewed": False,
            "source": "codex_new_tokyo_submaps",
            "provider_id": plan["provider_id"],
            "provider_name": plan["provider_name"],
            "model": plan["model"],
            "task_id": task.get("id") or task.get("task_id") or "",
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
        "id": f"codex_new_tokyo_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
            "location_key": plan["location_key"],
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
    saved = save_canvas(latest, "codex-new-tokyo-submaps-append")
    progress["appended"] += added
    progress["canvas_updated_at"] = saved.get("updated_at")


def run_round(plans, round_no, progress, max_workers=12):
    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(submit_task, plan): plan for plan in plans}
        for future in concurrent.futures.as_completed(future_map):
            plan = future_map[future]
            key = f"{plan['location_key']}::{plan['provider_name']}::r{round_no}::{uuid.uuid4().hex[:6]}"
            try:
                task = future.result()
                task_id = task.get("task_id")
                progress["submitted"] += 1
                progress["tasks"][key] = {
                    "location_key": plan["location_key"],
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
                    "location_key": plan["location_key"],
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


def refill_plans(locations, base_plan_by_location, round_no):
    canvas = load_canvas()
    plans = []
    for loc in locations:
        base = base_plan_by_location[loc["key"]]
        current = canvas_success_count(canvas, base["output_id"])
        remaining = max(0, TARGET_COUNT - current)
        for index in range(remaining):
            provider_id, provider_name, model = PROVIDERS[(round_no + index) % len(PROVIDERS)]
            plan = dict(base)
            plan.update({
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "round": round_no,
            })
            plans.append(plan)
    return plans


def main():
    progress = {
        "started_at": now_ms(),
        "canvas_id": CANVAS_ID,
        "target_count_per_location": TARGET_COUNT,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "locations": {},
        "tasks": {},
    }
    write_progress(progress)
    canvas_file = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-new-tokyo-submaps-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(canvas_file, backup_path)
    progress["backup"] = str(backup_path)

    canvas = load_canvas()
    created, run_plan = create_board(canvas)
    canvas = save_canvas(canvas, "codex-new-tokyo-submaps-board")
    progress["created"] = created
    progress["canvas_updated_at"] = canvas.get("updated_at")
    for loc in LOCATIONS:
        progress["locations"][loc["key"]] = {
            "title": loc["title"],
            "target": TARGET_COUNT,
            "landmarks": loc["landmarks"],
            "style_refs": loc["style_refs"],
        }
    write_progress(progress)

    base_plan_by_location = {}
    for plan in run_plan:
        base_plan_by_location.setdefault(plan["location_key"], plan)

    run_round(run_plan, 1, progress, max_workers=12)
    for round_no in range(2, MAX_ROUNDS + 1):
        plans = refill_plans(LOCATIONS, base_plan_by_location, round_no)
        if not plans:
            break
        run_round(plans, round_no, progress, max_workers=10)

    final = load_canvas()
    by = node_map(final)
    for loc_key, item in progress["locations"].items():
        out_id = base_plan_by_location[loc_key]["output_id"]
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
        "locations": progress["locations"],
        "progress": str(PROGRESS_PATH),
        "backup": str(backup_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
