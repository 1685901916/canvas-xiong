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
PROGRESS_PATH = ROOT / "output" / "codex_other_backgrounds_indoor_progress.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"

PROVIDERS = [
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
    ("custom-api-3", "nexus", "gpt-image-2"),
    ("custom-api-6", "mikoto", "gpt-image-2"),
]

INDOOR_SCENES = {
    "shinjuku_kabukicho": {
        "title": "新宿｜歌舞伎町室内娱乐街背景图",
        "indoor_place": "歌舞伎町大型室内娱乐楼/游戏厅与卡拉 OK 大厅，不是街道外景",
        "must": [
            "室内娱乐楼大厅或游戏中心入口区",
            "抓娃娃机、街机、卡拉 OK 前台或走廊等娱乐元素",
            "柔和霓虹灯牌只作为抽象色块，不出现可读真实文字",
            "干净地面和前景人物站位，能作为 galgame 约会背景",
        ],
        "mood": "热闹但不脏乱，都市夜生活的室内约会感，明亮可读，不要夜店化。",
        "avoid_extra": "不要酒吧陪酒场景，不要成人店，不要外部街景，不要红色拱门外景。",
    },
    "ueno_shinobazu_pond": {
        "title": "上野公园｜不忍池弁天堂内部背景图",
        "indoor_place": "不忍池弁天堂/池畔寺院内部或檐下室内空间，窗外能看到池水与莲叶",
        "must": [
            "小型寺院内部、木质地板、梁柱、格子窗或开口",
            "窗外或门外可见不忍池水面、莲叶和柔和绿意",
            "少量香炉、护符架或祭坛元素，但不要正面宗教特写",
            "前景留出人物站位，室内光线温暖干净",
        ],
        "mood": "安静、清雅、池畔约会后的休憩感，不阴暗。",
        "avoid_extra": "不要纯池边外景，不要大面积室外湖面，不要佛像神像特写。",
    },
    "ueno_tokyo_national_museum": {
        "title": "上野公园｜东京国立博物馆本馆室内展厅背景图",
        "indoor_place": "东京国立博物馆本馆室内展厅/日本美术展览空间",
        "must": [
            "高挑展厅、展柜、暖色木质或石质地面",
            "日本美术展品以抽象器物、屏风、陶瓷或刀剑展示为主",
            "远处有拱门、柱子、楼梯或展厅过渡空间",
            "安静文化约会地点氛围，前景干净可站人物",
        ],
        "mood": "庄重、温暖、博物馆室内感强，明亮但不商业。",
        "avoid_extra": "不要博物馆外立面，不要入口广场，不要可读展签文字。",
    },
    "meiji_otorii": {
        "title": "明治神宫｜神楽殿祈祷殿内部背景图",
        "indoor_place": "明治神宫神楽殿/祈祷殿或参拜接待建筑内部，不是大鸟居外景",
        "must": [
            "传统神社室内木结构、梁柱、格子窗、榻榻米或木地板",
            "纸灯笼、御札架、低矮案几或祈祷等待区元素",
            "门外可隐约看到神宫森林或回廊",
            "空间尊重、安静，前景留人物站位",
        ],
        "mood": "肃静、温暖、神社室内约会等待场景，不压迫。",
        "avoid_extra": "不要大鸟居外景，不要森林参道全景，不要神职人员或游客人群。",
    },
    "meiji_inner_garden": {
        "title": "明治神宫｜御苑茶屋室内背景图",
        "indoor_place": "明治神宫御苑里的传统茶屋/休憩亭室内，向外看见庭园绿意",
        "must": [
            "木质茶屋室内、榻榻米或木地板、低桌、纸拉门",
            "拉门或窗外可见御苑庭园步道、灌木和季节花丛",
            "柔和自然光从侧面进入，室内色彩温暖克制",
            "前景下方留出人物立绘站位",
        ],
        "mood": "安静、温柔、庭园休憩的室内约会感。",
        "avoid_extra": "不要纯室外庭园，不要大面积开放草地，不要现代咖啡店。",
    },
    "meiji_gyoen_pond": {
        "title": "明治神宫｜御苑池塘茶亭室内背景图",
        "indoor_place": "御苑池塘旁茶亭/水边休憩亭内部，从室内望向池塘",
        "must": [
            "茶亭或水边亭子内部、木地板、低桌、栏杆或开口",
            "打开的拉门外能看到池塘、水面反光、树影和岸边岩石",
            "室内干净，空间层次从前景室内到远景池塘自然过渡",
            "明亮柔和，不潮湿阴暗，适合 galgame 背景",
        ],
        "mood": "宁静、清澈、室内避暑休憩感，窗外有水景。",
        "avoid_extra": "不要只画室外池边，不要阴暗木屋，不要人物和可读文字。",
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


def scene_prompt(scene):
    must = "；".join(scene["must"])
    return (
        f"任务：生成《{scene['title']}》。这是 Aiko Tokyo v2 项目里的 galgame 室内背景图，不是子地图，不是室外地标照。\n"
        f"地点定位：{scene['indoor_place']}。\n"
        f"必须包含：{must}。\n"
        "镜头与构图：竖版 9:16 手机背景；镜头在室内，平视或略高于人眼；前景下方保持干净开阔，方便人物立绘站在前面；中景放室内主体元素；远景通过门窗或空间纵深展示地点特征。\n"
        "画风：沿用项目参考图的 Aiko Tokyo v2 柔和小插画感、清晰线稿、干净块面、温暖但克制的色彩、低噪点、高清完成度。参考图只用于项目画风和地点色彩，不要照抄外景构图。\n"
        "光线：明亮、柔和、室内自然采光或温和灯光；整体不暗、不黄、不偏紫，阴影轻。\n"
        f"空间氛围：{scene['mood']}\n"
        "质量要求：能直接放到游戏对话界面里，室内空间透视稳定，边缘干净，前景可读，背景细节丰富但不杂乱。\n"
        f"禁止：{scene['avoid_extra']} 不要俯视地图，不要 UI 标记，不要人物角色，不要人物特写，不要真实品牌文字，不要可读招牌字，不要 logo，不要水印，不要乱码，不要樱花泛滥，不要赛博朋克，不要写实照片。"
    )


def locate_ids(source, scene_key):
    scene_keys = list(source["scenes"].keys())
    index = scene_keys.index(scene_key)
    return {
        "group_id": source["created"]["groups"][index],
        "output_id": source["created"]["outputs"][index],
        "prompt_id": source["created"]["prompts"][index + 1],
        "generator_ids": source["created"]["generators"][index * 5:(index + 1) * 5],
        "scene_index": index,
    }


def prepare_workflows(progress):
    source = json.loads(SOURCE_PROGRESS.read_text(encoding="utf-8"))
    canvas_file = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-other-backgrounds-indoor-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(canvas_file, backup_path)

    canvas = load_canvas()
    by = node_map(canvas)
    plans = []
    progress["backup"] = str(backup_path)
    progress["workflows"] = {}

    for scene_key, indoor in INDOOR_SCENES.items():
        ids = locate_ids(source, scene_key)
        ref_key = source["scenes"][scene_key]["ref_key"]
        ref = next(item for item in source["imported_refs"] if item["key"] == ref_key)
        group = by[ids["group_id"]]
        prompt = by[ids["prompt_id"]]
        output = by[ids["output_id"]]
        old_images = output.get("images") or []
        existing_rejected = output.get("rejectedImages") or []
        prompt_text = scene_prompt(indoor)

        group["name"] = f"{indoor['title']} 输入｜目标5张"
        prompt["name"] = f"{indoor['title']} 提示词"
        prompt["text"] = prompt_text
        output["name"] = f"{indoor['title']} 输出｜目标5张"
        output["images"] = []
        output["rejectedImages"] = existing_rejected + old_images
        output["rejectionReason"] = "用户修正：其他背景也要室内图，旧外景/室外结果移入 rejectedImages。"

        group_x = float(group.get("x") or 0)
        group_y = float(group.get("y") or 0)
        group_w = float(group.get("w") or 1120)
        output["x"] = group_x + group_w + 600
        output["y"] = group_y + 18
        output["w"] = 760
        output["h"] = 680

        provider_plans = []
        gen_base_x = group_x + group_w + 80
        gen_base_y = group_y + 35
        for idx, gen_id in enumerate(ids["generator_ids"][:1]):
            provider_id, provider_name, model = PROVIDERS[idx]
            gen = by[gen_id]
            gen["x"] = gen_base_x + (idx % 2) * 235
            gen["y"] = gen_base_y + (idx // 2) * 118
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
            gen["name"] = f"{indoor['title']} / {provider_name}"
            gen["targetOutputId"] = ids["output_id"]
            gen["poolTargetCount"] = TARGET_COUNT
            gen["inputs"] = [
                f"{ids['group_id']}:{group.get('items', [''])[0]}",
                f"{ids['group_id']}:prompts",
            ]
            plan = {
                "scene_key": scene_key,
                "target_title": indoor["title"],
                "prompt": prompt_text,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "size": SIZE,
                "quality": QUALITY,
                "reference_images": [{
                    "url": ref["url"],
                    "name": ref["name"],
                    "role": ref["role"],
                }],
                "reference_count": 1,
                "generator_id": gen_id,
                "output_id": ids["output_id"],
                "round": 1,
            }
            provider_plans.append(plan)
            plans.append(plan)

        progress["workflows"][scene_key] = {
            **ids,
            "title": indoor["title"],
            "old_images_moved_to_rejected": len(old_images),
            "rejected_total_after_prepare": len(output.get("rejectedImages") or []),
            "target_count": TARGET_COUNT,
        }

    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_other_backgrounds_indoor_plan_{now_ms()}",
        "createdAt": now_ms(),
        "status": "info",
        "nodeType": "canvas-agent",
        "model": "codex_other_backgrounds_indoor",
        "prompt": "按用户截图修正结构：Group(参考图+提示词) -> 中间 API 池 -> 固定 Output；将其他6个背景改成室内图，每个目标5张。",
        "outputs": [],
        "error": "",
        "platform": "codex",
    })
    canvas["logs"] = canvas["logs"][:500]
    saved = save_canvas(canvas, "codex-other-backgrounds-indoor-prepare")
    progress["canvas_updated_at"] = saved.get("updated_at")
    return plans


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


def append_unique_output(output, additions):
    images = output.setdefault("images", [])
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


def append_result_to_canvas(plan, task, progress):
    canvas = load_canvas()
    by = node_map(canvas)
    output = by.get(plan["output_id"])
    gen = by.get(plan["generator_id"])
    status = str(task.get("status") or "").lower()
    result = task.get("result") or {}
    urls = result.get("images") or []
    added = 0
    if output is not None and status == "succeeded" and urls:
        additions = [{
            "url": url,
            "viewed": False,
            "source": "codex_other_backgrounds_indoor",
            "provider_id": plan["provider_id"],
            "provider_name": plan["provider_name"],
            "model": plan["model"],
            "task_id": task.get("id") or task.get("task_id") or "",
            "scene_key": plan["scene_key"],
            "createdAt": now_ms(),
            "runMs": task.get("run_ms") or task.get("total_ms") or 0,
        } for url in urls]
        added = append_unique_output(output, additions)
    if gen is not None:
        gen["runStatus"] = "done" if added else "failed"
        gen["runError"] = "" if added else str(task.get("error") or task.get("status") or "任务失败")[:500]
        if added:
            generated = gen.setdefault("generatedOutputs", [])
            for url in urls:
                if url not in generated:
                    generated.append(url)
    canvas.setdefault("logs", []).insert(0, {
        "id": f"codex_other_indoor_{uuid.uuid4().hex[:10]}_{now_ms()}",
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
    saved = save_canvas(canvas, "codex-other-backgrounds-indoor-append")
    progress["appended"] += added
    progress["canvas_updated_at"] = saved.get("updated_at")
    return added


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
                progress["tasks"][key] = {
                    "scene_key": plan["scene_key"],
                    "target_title": plan["target_title"],
                    "provider_name": plan["provider_name"],
                    "provider_id": plan["provider_id"],
                    "model": plan["model"],
                    "round": round_index,
                    "status": "submit_failed",
                    "error": str(exc),
                }
            write_progress(progress)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(submissions))) as pool:
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


def build_refill_plans(progress, round_index):
    source = json.loads(SOURCE_PROGRESS.read_text(encoding="utf-8"))
    plans = []
    for scene_key, workflow in progress["workflows"].items():
        current = accepted_count(workflow["output_id"])
        progress["scenes"][scene_key]["accepted_success_count"] = current
        missing = TARGET_COUNT - current
        if missing <= 0:
            continue
        ref_key = source["scenes"][scene_key]["ref_key"]
        ref = next(item for item in source["imported_refs"] if item["key"] == ref_key)
        canvas = load_canvas()
        prompt_text = node_map(canvas)[workflow["prompt_id"]]["text"]
        for i in range(missing):
            provider_id, provider_name, model = PROVIDERS[(round_index + i) % len(PROVIDERS)]
            plans.append({
                "scene_key": scene_key,
                "target_title": workflow["title"],
                "prompt": prompt_text,
                "provider_id": provider_id,
                "provider_name": provider_name,
                "model": model,
                "size": SIZE,
                "quality": QUALITY,
                "reference_images": [{
                    "url": ref["url"],
                    "name": ref["name"],
                    "role": ref["role"],
                }],
                "reference_count": 1,
                "generator_id": workflow["generator_ids"][i % len(workflow["generator_ids"])],
                "output_id": workflow["output_id"],
                "round": round_index,
            })
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
        "scenes": {key: {"title": value["title"], "target": TARGET_COUNT, "accepted_success_count": 0} for key, value in INDOOR_SCENES.items()},
        "diagnosis": "用户指出结构应为截图中的 Group -> API生成 -> Output，并要求其他背景也改成室内图。本轮复用旧6组，把外景输出移入 rejectedImages 后重新生成室内版本。",
    }
    write_progress(progress)
    initial_plans = prepare_workflows(progress)
    write_progress(progress)
    run_plans(initial_plans, progress, 1)

    for round_index in range(2, 5):
        refill = build_refill_plans(progress, round_index)
        if not refill:
            break
        progress.setdefault("refill_rounds", []).append({
            "round": round_index,
            "submitted_planned": len(refill),
        })
        write_progress(progress)
        run_plans(refill, progress, round_index)

    for scene_key, workflow in progress["workflows"].items():
        progress["scenes"][scene_key]["accepted_success_count"] = accepted_count(workflow["output_id"])
    progress["finished_at"] = now_ms()
    progress["canvas_url"] = f"{BASE}/static/canvas.html?canvas={CANVAS_ID}"
    write_progress(progress)
    print(json.dumps(progress, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
