#!/usr/bin/env python3
from __future__ import annotations

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
PROGRESS_PATH = ROOT / "output" / "codex_asakusa_disney_backgrounds_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"
MAX_ROUNDS = 5

ASAKUSA_REF_PATH = r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-bfa85c57-08b7-47d3-bb68-5e8999afa44d.png"
DISNEY_REF_PATH = r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-a8cea8ea-9a02-4583-8d09-7a786b86297f.png"

# Stable image providers from previous project runs. They are used as a pool to fill
# one shared output per requirement, not as per-provider comparisons.
PROVIDER_POOL = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("apimart", "APIMart", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-5", "8yes", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
]
REFILL_POOL = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("apimart", "APIMart", "gpt-image-2"),
    ("custom-api-5", "8yes", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
]

NEW_SCENES = [
    {
        "key": "asakusa_kaminarimon",
        "title": "浅草寺｜雷门门下街景背景图",
        "ref_key": "asakusa",
        "place": "浅草寺雷门门下到仲见世入口的局部人视角场景",
        "must": "近景有石板路和门柱边缘；中景是巨大红灯笼下方、朱红木柱、暗色屋檐、仲见世入口的一部分；两侧可以有抽象店铺暖帘和灯笼，但不能有可读真实文字",
        "camera": "站在雷门门洞下或刚穿过雷门的人视角，平视或略高于人眼，不要正面远距离广场总览",
        "mood": "传统浅草入口，明亮、热闹但干净，适合 galgame 对话背景",
        "avoid": "不要鸟瞰寺院地图，不要完整远景大门明信片，不要游客人群，不要可读文字，不要真实商标",
    },
    {
        "key": "asakusa_imado_shrine",
        "title": "浅草｜今户神社姻缘局部背景图",
        "ref_key": "asakusa",
        "place": "浅草今户神社里面的姻缘参拜局部场景",
        "must": "近景有石板路、绘马架或手水舍；中景是小型拜殿/社务所檐下、成对招财猫或猫形绘马元素；两侧是安静住宅区神社庭院、木牌、低矮树木",
        "camera": "站在神社小庭院里的人视角，前景下方留人物站位，背景有绘马和招财猫作为地点识别",
        "mood": "安静、可爱、温暖的姻缘神社氛围，不幼稚不过粉",
        "avoid": "不要宏大神社总览，不要室内房间，不要神像特写，不要真实文字，不要游客，不要过多粉色爱心",
    },
    {
        "key": "asakusa_five_story_pagoda",
        "title": "浅草寺｜五重塔旁庭院背景图",
        "ref_key": "asakusa",
        "place": "浅草寺五重塔旁边可停留的庭院、廊下或宝藏门附近局部场景",
        "must": "近景有石板步道、栏杆、石灯笼或屋檐边；中景可见朱红柱子和五重塔的下层/侧面局部；远景让塔身向上延伸但不要占满画面",
        "camera": "在塔旁庭院或廊下往塔侧看的人视角，不进入塔内部，因为五重塔更适合作为外部地标",
        "mood": "传统寺院内的安静局部场景，明亮、稳重、可作为约会背景",
        "avoid": "不要鸟瞰寺院地图，不要塔的远景全身海报，不要进入塔内，不要佛像神像特写，不要可读文字",
    },
    {
        "key": "tdl_cinderella_castle",
        "title": "东京迪士尼乐园｜童话城堡广场背景图",
        "ref_key": "disney",
        "place": "东京迪士尼乐园童话城堡前广场或城堡门廊附近的局部体验场景",
        "must": "近景有浅色石板广场、花坛、低矮栏杆或桥边；中景是蓝顶白墙童话城堡的门廊/塔楼局部；远景有柔和天空和主题公园景深",
        "camera": "站在城堡广场或桥边的人视角，能让角色站在前景，不做远处完整城堡宣传照",
        "mood": "明亮、梦幻、温暖但克制的主题公园约会背景",
        "avoid": "不要迪士尼角色，不要复制官方 logo，不要可读园区文字，不要人群，不要宏观乐园总览，不要过度糖果色",
    },
    {
        "key": "tdl_pirate_ship",
        "title": "东京迪士尼乐园｜海盗船港湾背景图",
        "ref_key": "disney",
        "place": "东京迪士尼乐园冒险乐园海盗主题水边/码头/入口局部背景",
        "must": "近景有木栈道、绳索栏杆、木桶、灯笼或码头边；中景有装饰性海盗船侧面、船舷、桅杆或拱形入口；远景有水面和暖色冒险乐园建筑",
        "camera": "站在码头边或入口旁的人视角，局部可进入场景，不做游乐设施广告牌正面",
        "mood": "冒险、温暖、干净的海盗港湾氛围，不恐怖不阴暗",
        "avoid": "不要可读 Pirates/Caribbean 字样，不要官方 logo，不要电影角色，不要骷髅恐怖特写，不要人群，不要阴暗洞穴",
    },
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


def load_canvas():
    data = http_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)
    return data["canvas"]


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


def import_local_image(path):
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


def connect(connections, from_id, to_id):
    if not any(c.get("from") == from_id and c.get("to") == to_id for c in connections):
        connections.append({"id": f"conn_{from_id}_{to_id}", "from": from_id, "to": to_id})


def node_map(canvas):
    return {n.get("id"): n for n in canvas.get("nodes") or [] if n.get("id")}


def image_url(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("url") or ""
    return ""


def visible_image_count(canvas, output_id: str) -> int:
    out = node_map(canvas).get(output_id) or {}
    return len([item for item in out.get("images") or [] if image_url(item)])


def append_unique(out, additions):
    out.setdefault("images", [])
    seen = {image_url(item) for item in out["images"] if image_url(item)}
    added = 0
    for item in additions:
        url = image_url(item)
        if not url or url in seen:
            continue
        out["images"].append(item)
        seen.add(url)
        added += 1
    return added


def write_progress(progress):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def prompt_for_scene(scene):
    return (
        f"任务：生成《{scene['title']}》。这是 Aiko Tokyo v2 项目里的 galgame 背景图，要的是当地内部/局部体验场景，不是宏观地图，也不是子地图。\n"
        f"地点定位：{scene['place']}。\n"
        f"必须包含：{scene['must']}。\n"
        f"镜头与构图：{scene['camera']}。竖版 9:16；人视角、平视或略高于人眼；前景下方留人物立绘站位；中景是可进入/可停留的局部场景；远景只保留地点识别，不要做成地标总览。\n"
        f"情绪：{scene['mood']}。\n"
        "画风：参考图只用于 Aiko Tokyo v2 柔和小插画感、清晰线稿、干净块面、温暖但克制的色彩、低噪点、高清完成度；不要照抄参考图的俯视地图构图。\n"
        "光线：明亮、柔和、可读，温暖但不过黄，不暗、不偏紫；适合游戏对话界面。\n"
        "局部场景要求：要像角色真的走进这个地点后看到的背景，有地面/步道/栏杆/门口/窗边/店铺/码头/花坛等可站可停留元素。\n"
        f"禁止：{scene['avoid']}。不要 UI 标记，不要人物角色，不要人物特写，不要真实品牌文字，不要可读招牌字，不要 logo，不要水印，不要乱码，不要赛博朋克，不要写实照片。"
    )


def locate_existing_kabukicho(canvas):
    for node in canvas.get("nodes") or []:
        if node.get("type") == "output" and "歌舞伎町" in str(node.get("name") or ""):
            output_id = node.get("id")
            break
    else:
        return None
    by = node_map(canvas)
    connections = canvas.get("connections") or []
    gen_ids = [c.get("from") for c in connections if c.get("to") == output_id and by.get(c.get("from"), {}).get("type") == "generator"]
    group_ids = [c.get("from") for c in connections if c.get("to") in gen_ids and by.get(c.get("from"), {}).get("type") == "group"]
    group_id = group_ids[0] if group_ids else ""
    group = by.get(group_id) or {}
    prompt_ids = [item for item in (group.get("items") or []) if by.get(item, {}).get("type") == "prompt"]
    image_ids = [item for item in (group.get("items") or []) if by.get(item, {}).get("type") == "image"]
    if not (output_id and group_id and prompt_ids and image_ids):
        return None
    return {
        "output_id": output_id,
        "group_id": group_id,
        "prompt_id": prompt_ids[0],
        "image_id": image_ids[0],
        "generator_ids": gen_ids,
    }


def new_kabukicho_scene():
    return {
        "key": "shinjuku_kabukicho_street",
        "title": "新宿｜歌舞伎町街景背景图",
        "place": "歌舞伎町里面的街景局部场景，角色已经走进街区，不是入口远景",
        "must": "近景有干净人行道、店铺门口、自动贩卖机/游戏厅入口/窄巷转角之一；中景有抽象灯牌、橱窗和娱乐楼立面；远景只保留街道深度，不要只拍红色拱门",
        "camera": "站在歌舞伎町街道内侧的人视角，平视或略高，前景下方要有清晰站位",
        "mood": "都市夜前或傍晚约会街景，灯牌有氛围但整体明亮干净，不是成人街和赛博朋克",
        "avoid": "不要宏观街区地图，不要远处入口总览，不要红色拱门占满画面，不要成人店暗示，不要酒吧陪酒场景，不要可读文字",
    }


def build_board(progress):
    canvas_path = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{CANVAS_ID}.before-asakusa-disney-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(canvas_path, backup)
    progress["backup"] = str(backup)

    imported_refs = {}
    asakusa_file = Path(ASAKUSA_REF_PATH)
    disney_file = Path(DISNEY_REF_PATH)
    if not asakusa_file.exists():
        raise FileNotFoundError(str(asakusa_file))
    if not disney_file.exists():
        raise FileNotFoundError(str(disney_file))
    imported_refs["asakusa"] = {
        **import_local_image(asakusa_file),
        "role": "风格/地点结构参考：浅草寺、雷门、五重塔、神社元素。只参考色彩和建筑语言，不照抄俯视地图构图。",
    }
    imported_refs["disney"] = {
        **import_local_image(disney_file),
        "role": "风格/地点结构参考：主题公园、童话城堡、旋转木马、海盗船氛围。只参考明亮主题公园画风，不复制官方文字和角色。",
    }
    progress["imported_refs"] = imported_refs

    canvas = load_canvas()
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    by = node_map(canvas)

    xs = [float(n.get("x") or 0) for n in nodes]
    ys = [float(n.get("y") or 0) for n in nodes]
    origin_x = (max(xs) if xs else 0) + 850
    origin_y = min(80, min(ys) if ys else 80)

    run_plan = []
    workflows = {}

    existing = locate_existing_kabukicho(canvas)
    kab_scene = new_kabukicho_scene()
    if existing:
        group = by[existing["group_id"]]
        prompt = by[existing["prompt_id"]]
        output = by[existing["output_id"]]
        prompt_text = prompt_for_scene(kab_scene)
        prompt["text"] = prompt_text
        prompt["name"] = f"{kab_scene['title']} 提示词｜追加街景"
        group["name"] = f"{kab_scene['title']} 输入｜追加街景5张"
        output["name"] = f"{output.get('name') or kab_scene['title']}｜追加街景5张"
        output["w"] = output.get("w") or 760
        output["h"] = output.get("h") or 680
        ref_node = by[existing["image_id"]]
        refs = [{"url": ref_node.get("url"), "name": ref_node.get("name") or "kabukicho-style-reference.png", "role": ref_node.get("role") or "歌舞伎町项目画风参考"}]
        gen_ids = list(existing["generator_ids"] or [])
        while len(gen_ids) < 1:
            gen = {
                "id": uid("gen"),
                "type": "generator",
                "x": float(group.get("x") or 0) + float(group.get("w") or 1120) + 80 + (len(gen_ids) % 2) * 235,
                "y": float(group.get("y") or 0) + 35 + (len(gen_ids) // 2) * 118,
                "w": 380,
                "h": 0,
                "inputs": [f"{group['id']}:{ref_node['id']}", f"{group['id']}:prompts"],
                "count": 1,
                "apiDefaultsVersion": 2,
                "targetOutputId": output["id"],
                "poolTargetCount": TARGET_COUNT,
            }
            nodes.append(gen)
            connect(connections, group["id"], gen["id"])
            connect(connections, gen["id"], output["id"])
            gen_ids.append(gen["id"])
        for index, (provider_id, provider_name, model) in enumerate(PROVIDER_POOL[:1]):
            gen = by.get(gen_ids[index]) or next(n for n in nodes if n.get("id") == gen_ids[index])
            gen.update({
                "apiProvider": provider_id,
                "model": model,
                "ratio": "portrait916",
                "resolution": "1k",
                "quality": QUALITY,
                "count": 1,
                "runStatus": "queued",
                "runError": "",
                "name": f"{kab_scene['title']} / {provider_name}",
                "targetOutputId": output["id"],
                "poolTargetCount": TARGET_COUNT,
            })
            run_plan.append({
                "scene_key": kab_scene["key"],
                "target_title": kab_scene["title"],
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
                "baseline_visible_count": len(output.get("images") or []),
            })
        workflows[kab_scene["key"]] = {
            **existing,
            "title": kab_scene["title"],
            "baseline_visible_count": len(output.get("images") or []),
            "target_new_count": TARGET_COUNT,
            "mode": "append_to_existing",
        }

    group_w = 1120
    group_h = 540
    row_h = 820
    gen_x = origin_x + group_w + 80
    out_x = gen_x + 520
    summary = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 250,
        "w": 1180,
        "h": 190,
        "name": "浅草寺/迪士尼背景图｜生成简报",
        "text": (
            "目标画布=背景图。新增浅草寺雷门、今户神社姻缘、浅草寺五重塔旁、东京迪士尼童话城堡广场、海盗船港湾；"
            "每个需求 5 张 accepted images。歌舞伎町复用现有 workflow 追加街景5张，不隐藏旧图。"
            "浅草五重塔判断为塔旁庭院/廊下局部，不进塔内部。迪士尼只做原创主题公园背景，避免角色、logo、可读文字。"
        ),
    }
    nodes.append(summary)

    for row, scene in enumerate(NEW_SCENES):
        y = origin_y + row * row_h
        ref = imported_refs[scene["ref_key"]]
        img = {
            "id": uid("img"),
            "type": "image",
            "x": origin_x + 36,
            "y": y + 88,
            "url": ref.get("url"),
            "name": ref.get("name") or f"{scene['ref_key']}-reference.png",
            "role": ref.get("role") or "",
            "w": 330,
            "h": 250,
        }
        prompt_text = prompt_for_scene(scene)
        prompt = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": origin_x + 405,
            "y": y + 88,
            "text": prompt_text,
            "name": f"{scene['title']} 提示词",
            "w": 660,
            "h": 360,
        }
        group = {
            "id": uid("grp"),
            "type": "group",
            "x": origin_x,
            "y": y,
            "w": group_w,
            "h": group_h,
            "items": [img["id"], prompt["id"]],
            "name": f"{scene['title']} 输入｜目标5张",
        }
        output = {
            "id": uid("out"),
            "type": "output",
            "x": out_x,
            "y": y + 18,
            "w": 760,
            "h": 680,
            "images": [],
            "name": f"{scene['title']} 输出｜目标5张",
        }
        nodes.extend([img, prompt, group, output])
        refs = [{"url": img["url"], "name": img["name"], "role": img["role"]}]
        gen_ids = []
        for index, (provider_id, provider_name, model) in enumerate(PROVIDER_POOL[:1]):
            gen = {
                "id": uid("gen"),
                "type": "generator",
                "x": gen_x + (index % 2) * 235,
                "y": y + 35 + (index // 2) * 118,
                "w": 380,
                "h": 0,
                "apiProvider": provider_id,
                "model": model,
                "ratio": "portrait916",
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
                "name": f"{scene['title']} / {provider_name}",
                "targetOutputId": output["id"],
                "poolTargetCount": TARGET_COUNT,
            }
            nodes.append(gen)
            gen_ids.append(gen["id"])
            connect(connections, group["id"], gen["id"])
            connect(connections, gen["id"], output["id"])
            run_plan.append({
                "scene_key": scene["key"],
                "target_title": scene["title"],
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
                "baseline_visible_count": 0,
            })
        workflows[scene["key"]] = {
            "title": scene["title"],
            "group_id": group["id"],
            "prompt_id": prompt["id"],
            "image_id": img["id"],
            "generator_ids": gen_ids,
            "output_id": output["id"],
            "baseline_visible_count": 0,
            "target_new_count": TARGET_COUNT,
            "mode": "new_workflow",
        }

    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_asakusa_disney_plan_{now_ms()}",
        "createdAt": now_ms(),
        "status": "info",
        "nodeType": "canvas-agent",
        "model": "codex_asakusa_disney_backgrounds",
        "prompt": "歌舞伎町追加街景；浅草寺雷门、今户神社姻缘、五重塔旁；东京迪士尼童话城堡广场、海盗船港湾。每个需求补5张，旧图保持可见。",
        "outputs": [],
        "error": "",
        "platform": "codex",
    })
    canvas["logs"] = canvas["logs"][:500]
    saved = save_canvas(canvas, "codex-asakusa-disney-board")
    progress["canvas_updated_at"] = saved.get("updated_at")
    progress["workflows"] = workflows
    return run_plan


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
        status = str(task.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return task
        time.sleep(2)


def append_result(plan, task, progress):
    canvas = load_canvas()
    by = node_map(canvas)
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
            "source": "codex_asakusa_disney_backgrounds",
            "provider_id": plan["provider_id"],
            "provider_name": plan["provider_name"],
            "model": plan["model"],
            "task_id": task.get("id") or task.get("task_id") or "",
            "scene_key": plan["scene_key"],
            "createdAt": now_ms(),
            "runMs": task.get("run_ms") or task.get("total_ms") or 0,
        } for url in urls]
        added = append_unique(out, additions)
    if gen is not None:
        gen["runStatus"] = "done" if added else "failed"
        gen["runError"] = "" if added else str(task.get("error") or task.get("status") or "任务失败")[:500]
        if added:
            gen.setdefault("generatedOutputs", [])
            for url in urls:
                if url not in gen["generatedOutputs"]:
                    gen["generatedOutputs"].append(url)
    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_asakusa_disney_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
    saved = save_canvas(canvas, "codex-asakusa-disney-append")
    progress["appended"] += added
    progress["canvas_updated_at"] = saved.get("updated_at")
    return added


def run_round(plans, progress, round_index, max_workers=8):
    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(plans)))) as pool:
        future_map = {pool.submit(submit_task, plan): plan for plan in plans}
        for future in concurrent.futures.as_completed(future_map):
            plan = future_map[future]
            key = f"{plan['scene_key']}::{plan['provider_name']}::r{round_index}::{uuid.uuid4().hex[:6]}"
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
                    "round": round_index,
                    "task_id": task_id,
                    "submit_status": task.get("status"),
                }
                if task_id:
                    submissions.append((key, plan, task_id))
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key] = {"scene_key": plan["scene_key"], "target_title": plan["target_title"], "status": "submit_failed", "error": str(exc)}
            write_progress(progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(submissions)))) as pool:
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
                append_result(plan, task, progress)
            except Exception as exc:
                progress["failed"] += 1
                progress["tasks"][key].update({"status": "poll_failed", "error": str(exc)})
            write_progress(progress)


def build_refill_plans(progress, base_plan_by_scene, round_index):
    canvas = load_canvas()
    plans = []
    for scene_key, wf in progress["workflows"].items():
        current = visible_image_count(canvas, wf["output_id"])
        baseline = int(wf.get("baseline_visible_count") or 0)
        new_count = max(0, current - baseline)
        progress["scenes"][scene_key]["visible_total"] = current
        progress["scenes"][scene_key]["new_success_count"] = new_count
        missing = TARGET_COUNT - new_count
        if missing <= 0:
            continue
        base = base_plan_by_scene[scene_key]
        for i in range(missing):
            provider_id, provider_name, model = REFILL_POOL[(round_index + i) % len(REFILL_POOL)]
            plan = dict(base)
            plan.update({
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "round": round_index,
                "generator_id": wf["generator_ids"][i % len(wf["generator_ids"])],
            })
            plans.append(plan)
    return plans


def main():
    progress = {
        "started_at": now_ms(),
        "canvas_id": CANVAS_ID,
        "target_canvas_title": "背景图",
        "target_new_count_per_scene": TARGET_COUNT,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "tasks": {},
        "scenes": {},
        "research_notes": {
            "sensoji": "Senso-ji has Kaminarimon and a five-storied pagoda; use local human-scale scenes, not aerial maps.",
            "imado": "Imado Shrine is an Asakusa matchmaking shrine associated with maneki-neko; use ema/cat/shrine courtyard anchors.",
            "tokyo_disney": "Tokyo Disneyland has Cinderella Castle/Fairy Tale Hall and Pirates of the Caribbean; generate original park-like backgrounds without characters, logos, or readable signs.",
        },
    }
    write_progress(progress)
    plans = build_board(progress)
    for key, wf in progress["workflows"].items():
        progress["scenes"][key] = {
            "title": wf["title"],
            "target_new": TARGET_COUNT,
            "baseline_visible_count": wf.get("baseline_visible_count", 0),
            "output_id": wf["output_id"],
            "mode": wf["mode"],
        }
    write_progress(progress)

    base_plan_by_scene = {}
    for plan in plans:
        base_plan_by_scene.setdefault(plan["scene_key"], plan)

    run_round(plans, progress, 1, max_workers=8)
    for round_index in range(2, MAX_ROUNDS + 1):
        refill = build_refill_plans(progress, base_plan_by_scene, round_index)
        if not refill:
            break
        progress.setdefault("refill_rounds", []).append({"round": round_index, "planned": len(refill)})
        write_progress(progress)
        run_round(refill, progress, round_index, max_workers=6)

    build_refill_plans(progress, base_plan_by_scene, MAX_ROUNDS + 1)
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
        "scenes": progress["scenes"],
        "progress": str(PROGRESS_PATH),
        "backup": progress.get("backup"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
