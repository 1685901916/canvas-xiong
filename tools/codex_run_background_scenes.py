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
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = ROOT / "output" / "codex_background_scenes_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"
MAX_ROUNDS = 5

ATTACHED_REFS = [
    {
        "key": "shinjuku_style",
        "path": r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-24374934-57a1-4d17-8cc8-9dbe8171b9b7.png",
        "name": "shinjuku-style-reference.png",
        "role": "风格参考：新宿城市、歌舞伎町入口、东京都厅大楼的项目画风",
    },
    {
        "key": "ueno_style",
        "path": r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-8feda336-d746-45b5-9b88-df0e25d85685.png",
        "name": "ueno-style-reference.png",
        "role": "风格参考：上野公园、不忍池、东京国立博物馆的项目画风",
    },
    {
        "key": "meiji_style",
        "path": r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-34cf8c43-f787-4f33-a888-bbe3c7f9ae02.png",
        "name": "meiji-style-reference.png",
        "role": "风格参考：明治神宫大鸟居、御苑和池塘的项目画风",
    },
]

PROVIDERS = [
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
]

REFILL_PROVIDERS = [
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-2", "65535", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
]

SCENES = [
    {
        "key": "shinjuku_kabukicho",
        "title": "新宿｜歌舞伎町背景图",
        "ref_key": "shinjuku_style",
        "subject": "新宿歌舞伎町入口街区",
        "must_include": [
            "红色拱门入口作为远处或中景识别点",
            "紧凑的娱乐街建筑立面和竖向灯箱招牌",
            "干净的人行道、路灯、少量街树和可进入的小巷",
            "招牌只用色块和抽象符号，不出现可读真实文字",
        ],
        "mood": "都市约会地点，明亮干净的傍晚到夜前氛围，有灯光但不赛博朋克",
        "camera": "街道入口视角，略高于人眼，画面下方留出角色站位空间",
    },
    {
        "key": "shinjuku_tokyo_metropolitan_government",
        "title": "新宿｜东京都厅大楼背景图",
        "ref_key": "shinjuku_style",
        "subject": "东京都厅双塔大楼与前方城市广场",
        "must_include": [
            "双塔高层建筑轮廓和竖向玻璃/石材线条",
            "大楼前的开阔广场、台阶、树池和路灯",
            "周围现代办公楼和宽阔道路",
            "干净城市天空和柔和日光",
        ],
        "mood": "安静、开阔、现代都市约会集合点，清爽不压迫",
        "camera": "仰视很轻的街景广角，能看清双塔与前景广场，下方留角色站位",
    },
    {
        "key": "ueno_shinobazu_pond",
        "title": "上野公园｜不忍池背景图",
        "ref_key": "ueno_style",
        "subject": "上野公园不忍池",
        "must_include": [
            "宽阔池水和莲叶荷花",
            "池中弁天堂或小亭作为远处地标",
            "木桥/石桥、栏杆、柳树和环池步道",
            "水面反光清澈，公园座椅和路灯点缀",
        ],
        "mood": "温柔安静的公园约会场景，水面明亮、绿意充足",
        "camera": "池边步道视角，前景有栏杆或路面，远景看见池心地标",
    },
    {
        "key": "ueno_tokyo_national_museum",
        "title": "上野公园｜东京国立博物馆背景图",
        "ref_key": "ueno_style",
        "subject": "东京国立博物馆本馆入口与庭园广场",
        "must_include": [
            "对称的博物馆主建筑、绿色屋顶和石质立面",
            "正面台阶、入口门廊、铺装广场",
            "修剪整齐的绿篱、花坛和上野公园树木",
            "庄重但温暖的文化约会地点氛围",
        ],
        "mood": "文化馆约会、安静、清爽、可靠，不要阴沉",
        "camera": "正面三分之二视角，建筑占中上部，前景广场留角色站位",
    },
    {
        "key": "meiji_otorii",
        "title": "明治神宫｜大鸟居背景图",
        "ref_key": "meiji_style",
        "subject": "明治神宫森林参道的大鸟居",
        "must_include": [
            "巨大木制鸟居作为主地标",
            "宽阔碎石参道向森林深处延伸",
            "两侧高大常绿树林、木栅栏和石灯笼",
            "柔和穿林光和安静神社氛围",
        ],
        "mood": "清澈、庄重、森林散步约会，空气感明亮",
        "camera": "参道正中略低视角，鸟居高大但不压迫，下方留角色站位",
    },
    {
        "key": "meiji_inner_garden",
        "title": "明治神宫｜御苑背景图",
        "ref_key": "meiji_style",
        "subject": "明治神宫御苑庭园",
        "must_include": [
            "蜿蜒庭园步道、低矮灌木和深绿树影",
            "花菖蒲或季节性花丛作为小面积点缀",
            "传统茶屋/休憩亭或木桥作为中景",
            "庭园层次清楚，适合角色站在前景",
        ],
        "mood": "幽静、柔和、私密的庭园约会场景，干净不杂乱",
        "camera": "庭园步道转角视角，前景路面开阔，中景有亭或花田",
    },
    {
        "key": "meiji_gyoen_pond",
        "title": "明治神宫｜御苑池塘背景图",
        "ref_key": "meiji_style",
        "subject": "明治神宫御苑池塘",
        "must_include": [
            "宁静池塘、水面反光和少量锦鲤/落叶点缀",
            "岸边岩石、灌木、矮桥或木栈道",
            "深绿森林包围，远处可有小亭或石灯笼",
            "水边前景留出人物立绘站位",
        ],
        "mood": "安静、清澈、温暖的水边约会背景，不要阴暗",
        "camera": "池边近景视角，水面占中景，树木形成柔和背景",
    },
]


def now_ms():
    return int(time.time() * 1000)


def http_json(method, path, payload=None, timeout=120, extra_headers=None):
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


def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def connect(connections, from_id, to_id):
    if not any(c.get("from") == from_id and c.get("to") == to_id for c in connections):
        connections.append({"id": f"conn_{from_id}_{to_id}", "from": from_id, "to": to_id})


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


def background_prompt(scene):
    includes = "；".join(scene["must_include"])
    return (
        f"任务：生成《{scene['title']}》，这是 Aiko Tokyo v2 项目里的 galgame 约会地点背景图，不是子地图。\n"
        f"主体地点：{scene['subject']}。\n"
        f"必须包含：{includes}。\n"
        f"镜头与构图：{scene['camera']}。竖版 9:16 手机背景，前景下方保持干净开阔，方便人物立绘站在前面；中景放主要地标；远景有自然空间层次。\n"
        f"情绪：{scene['mood']}。\n"
        "画风：参考组内图片的 Aiko Tokyo v2 柔和小插画感、清晰线稿、干净块面、温暖但克制的色彩、低噪点、高清完成度；只学习画风和东京项目色彩，不要照抄参考图的俯视地图构图。\n"
        "光线：明亮、柔和、可读；可以是清爽白天或温和下午，歌舞伎町允许少量柔和灯牌氛围但整体不要黑。\n"
        "质量要求：背景能直接放到游戏对话界面里，建筑/水面/树林层次清楚，边缘干净，空间透视稳定。\n"
        "禁止：不要做成俯视地图/等距子地图，不要 UI 标记，不要人物角色，不要人物特写，不要真实品牌文字，不要可读招牌字，不要 logo，不要水印，不要乱码，不要樱花泛滥，不要太黄，不要太暗，不要偏紫，不要赛博朋克强霓虹，不要写实照片，不要杂乱小窗。"
    )


def node_map(canvas):
    return {n.get("id"): n for n in canvas.get("nodes") or [] if n.get("id")}


def canvas_success_count(canvas, output_id):
    out = node_map(canvas).get(output_id) or {}
    return len([item for item in out.get("images") or [] if output_url_value(item)])


def create_board(canvas, imported_refs):
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    xs = [float(n.get("x") or 0) for n in nodes]
    ys = [float(n.get("y") or 0) for n in nodes]
    origin_x = (max(xs) if xs else 0) + 700
    origin_y = min(80, min(ys) if ys else 80)

    created = {"groups": [], "outputs": [], "generators": [], "images": [], "prompts": []}
    run_plan = []
    row_h = 820
    group_w = 1120
    group_h = 540
    gen_x = origin_x + group_w + 80
    out_x = gen_x + 520

    summary_text = (
        "生成简报：目标画布=背景图；7 个独立背景图需求；每个需求 5 张 accepted images，总目标 35 张。"
        "参考图只作为 Aiko Tokyo v2 项目画风和地点结构线索；输出是竖版 galgame 背景图，不是子地图。"
        "通用验收：9:16、无人物、无可读文字/logo/水印、前景可站角色、地点地标明确、线稿干净、不过暗不过黄不过紫。"
    )
    summary = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 250,
        "text": summary_text,
        "name": "新宿/上野/明治神宫背景图｜生成简报",
        "w": 1180,
        "h": 180,
    }
    nodes.append(summary)
    created["prompts"].append(summary["id"])

    refs_by_key = {item["key"]: item for item in imported_refs}
    for row, scene in enumerate(SCENES):
        y = origin_y + row * row_h
        ref = refs_by_key[scene["ref_key"]]
        img = {
            "id": uid("img"),
            "type": "image",
            "x": origin_x + 36,
            "y": y + 88,
            "url": ref["url"],
            "name": ref["name"],
            "role": ref["role"],
            "w": 330,
            "h": 250,
        }
        prompt_text = background_prompt(scene)
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
        created["images"].append(img["id"])
        created["prompts"].append(prompt["id"])
        created["groups"].append(group["id"])
        created["outputs"].append(output["id"])

        refs = [{"url": img["url"], "name": img["name"], "role": img["role"]}]
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
            created["generators"].append(gen["id"])
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
            })
    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_background_scenes_plan_{now_ms()}",
        "createdAt": now_ms(),
        "status": "info",
        "nodeType": "canvas-agent",
        "model": "codex_background_scenes",
        "prompt": "新宿歌舞伎町/东京都厅、上野不忍池/东京国立博物馆、明治神宫大鸟居/御苑/御苑池塘背景图；每个5张；稳定API池共享输出。",
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
            "source": "codex_background_scenes",
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
        "id": f"codex_bg_scene_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
    saved = save_canvas(latest, "codex-background-scenes-append")
    progress["appended"] += added
    progress["canvas_updated_at"] = saved.get("updated_at")
    return added


def run_round(plans, round_no, progress, max_workers=12):
    submissions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(submit_task, plan): plan for plan in plans}
        for future in concurrent.futures.as_completed(future_map):
            plan = future_map[future]
            key = f"{plan['scene_key']}::{plan['provider_name']}::r{round_no}::{uuid.uuid4().hex[:6]}"
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
                    "round": round_no,
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


def refill_plans(base_plan_by_scene, round_no):
    canvas = load_canvas()
    plans = []
    for scene in SCENES:
        base = base_plan_by_scene[scene["key"]]
        current = canvas_success_count(canvas, base["output_id"])
        remaining = max(0, TARGET_COUNT - current)
        for index in range(remaining):
            provider_id, provider_name, model = REFILL_PROVIDERS[(round_no + index) % len(REFILL_PROVIDERS)]
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
        "target_canvas_title": "背景图",
        "target_count_per_scene": TARGET_COUNT,
        "submitted": 0,
        "succeeded": 0,
        "failed": 0,
        "appended": 0,
        "scenes": {},
        "tasks": {},
    }
    write_progress(progress)

    imported_refs = []
    for ref in ATTACHED_REFS:
        if not Path(ref["path"]).exists():
            raise FileNotFoundError(ref["path"])
        imported = import_local_image(ref["path"])
        imported_refs.append({
            **ref,
            "url": imported.get("url"),
            "name": imported.get("name") or ref["name"],
        })
    progress["imported_refs"] = imported_refs
    write_progress(progress)

    canvas_file = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-background-scenes-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(canvas_file, backup_path)
    progress["backup"] = str(backup_path)

    canvas = load_canvas()
    created, run_plan = create_board(canvas, imported_refs)
    canvas = save_canvas(canvas, "codex-background-scenes-board")
    progress["created"] = created
    progress["canvas_updated_at"] = canvas.get("updated_at")
    for scene in SCENES:
        progress["scenes"][scene["key"]] = {
            "title": scene["title"],
            "target": TARGET_COUNT,
            "subject": scene["subject"],
            "ref_key": scene["ref_key"],
            "must_include": scene["must_include"],
        }
    write_progress(progress)

    base_plan_by_scene = {}
    for plan in run_plan:
        base_plan_by_scene.setdefault(plan["scene_key"], plan)

    run_round(run_plan, 1, progress, max_workers=12)
    for round_no in range(2, MAX_ROUNDS + 1):
        plans = refill_plans(base_plan_by_scene, round_no)
        if not plans:
            break
        run_round(plans, round_no, progress, max_workers=9)

    final = load_canvas()
    by = node_map(final)
    for scene_key, item in progress["scenes"].items():
        out_id = base_plan_by_scene[scene_key]["output_id"]
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
        "scenes": progress["scenes"],
        "progress": str(PROGRESS_PATH),
        "backup": str(backup_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
