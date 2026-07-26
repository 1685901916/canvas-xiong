#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
ROOT = Path(__file__).resolve().parents[1]
CANVAS_PATH = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
PROGRESS_PATH = ROOT / "output" / "codex_home_room_diffs_workflow_v1_20260621" / "progress.json"
SOURCE_TAG = "codex_home_room_diffs_workflow_v1"
OLD_STATIC_SOURCE_TAG = "codex_home_room_night_regen_v2"
TARGET_COUNT = 5
SIZE = "864x1536"
QUALITY = "auto"
TASK_DEADLINE_SECONDS = 1800
POLL_INTERVAL_SECONDS = 2.5

PROVIDER_POOL = [
    {"id": "custom-api-4", "name": "API", "model": "gpt-image-2-vip"},
    {"id": "custom-api-4", "name": "API", "model": "gpt-image-2-all"},
    {"id": "custom-api-2", "name": "65535", "model": "gpt-image-2"},
    {"id": "custom-api-8", "name": "krill", "model": "gpt-image-2"},
    {"id": "custom-api-3", "name": "nexus", "model": "gpt-image-2"},
]

ROOMS = [
    ("entryway", "01 玄关", "家地图玄关背景图", "assets/input/ai_ref_5841485f5218.png"),
    ("kitchen", "02 厨房", "家地图厨房背景图", "assets/input/ai_ref_61d9c9d5b2d2.png"),
    ("bathroom", "03 浴室", "家地图浴室背景图", "assets/input/ai_ref_eaaa113a6ee2.png"),
    ("bedroom", "04 卧室", "家地图卧室背景图", "assets/input/ai_ref_d3f7f4d68b3a.png"),
    ("living", "05 客厅", "家地图客厅背景图", "assets/input/ai_ref_b28317689c0b.png"),
    ("balcony", "06 阳台", "家地图阳台背景图", "assets/input/ai_ref_bbf7124625e3.png"),
]

VARIANTS = [
    ("afternoon", "下午差分"),
    ("night", "晚上差分"),
]


def now_ms() -> int:
    return int(time.time() * 1000)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def http_json(method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
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
        raise RuntimeError(f"{method} {path} HTTP {exc.code}: {detail[:1200]}") from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def load_canvas() -> dict[str, Any]:
    return http_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]


def save_canvas(canvas: dict[str, Any], client_id: str) -> dict[str, Any]:
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


def backup_canvas_file(label: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"{CANVAS_ID}.{label}-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    if CANVAS_PATH.exists():
        shutil.copy2(CANVAS_PATH, backup)
    return backup


def write_progress(progress: dict[str, Any]) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def read_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {}
    return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))


def asset_url(rel_path: str) -> str:
    return "/" + rel_path.replace("\\", "/")


def local_path_from_url(url: str) -> Path | None:
    if not url.startswith("/assets/"):
        return None
    return ROOT / url.lstrip("/").replace("/", os.sep)


def import_local_asset(path: Path, key: str, source: str) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    digest = hashlib.sha1((str(path.resolve()) + "|" + str(path.stat().st_mtime_ns)).encode("utf-8", errors="ignore")).hexdigest()[:10]
    dest = ROOT / "assets" / "output" / f"codex_home_{key}_{source}_{digest}{path.suffix.lower() or '.png'}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(path, dest)
    return asset_url(str(dest.relative_to(ROOT)))


def room_keep_clause(room_key: str) -> str:
    details = {
        "entryway": "entry door, wall lamps, shoe cabinet, shoe rack, pink floor mat, plant, framed wall art, tiled floor",
        "kitchen": "refrigerator, cabinets, range hood, stove, oven, sink, microwave, countertop objects, table edge, plant, pink floor mat",
        "bathroom": "bathtub, shower fixture, sink cabinet, mirror, wall lamp, towel, pink bath mat, toilet edge, window, framed art",
        "bedroom": "bed, pillows, blanket, bedside table, lamp, curtains, window, wall art, pink textiles, floor layout",
        "living": "sofa, coffee table, rug, plant, doorway, cabinet, wall art, curtains, window, visible adjoining room",
        "balcony": "balcony railing, tile floor, small round table, chair, cup, potted plants, curtains, window frame, trees and city outside",
    }
    return (
        "preserve exact source-image structure: vertical 9:16 composition, camera angle, perspective, room identity, "
        "furniture layout, object positions, wall/floor/window/door placement, line-art weight, soft anime visual-novel home-map background style, "
        f"and room anchors: {details[room_key]}"
    )


def build_prompt(room_key: str, title: str, variant: str) -> str:
    keep = room_keep_clause(room_key)
    if variant == "afternoon":
        return (
            f"Edit Image 1 into an afternoon time-difference candidate for {title}.\n"
            "Use case: lighting-weather edit for a cozy mobile game home map room background.\n"
            "Primary request: 下午差分。温暖的感觉，但不要偏白、不要发白、不要过曝、不要太黄、不要太暗，画面整体不要变换，只是下午差分。\n"
            f"Keep unchanged: {keep}.\n"
            "Change only: make a restrained warm afternoon version by adding mild directional domestic sunlight and shallow soft shadow shapes from the original light direction. "
            "Keep the source color base: cream walls stay warm cream instead of white, pale pink textiles stay pink, wood stays natural tan, plants and floor colors keep their saturation. "
            "Do not raise the global exposure above the source; the afternoon feeling should come from light direction and soft shadows, not from whitening or bleaching the room.\n"
            "Avoid: washed-out white cast, overexposure, foggy white haze, bleached walls, lowered saturation, losing wood color, losing pink textiles, sunset, golden hour, strong yellow cast, "
            "orange cast, overall darkening, heavy shadows, high contrast, muddy gray, new furniture, removed furniture, moved objects, different room, characters, pets, UI, map pins, text, logo, "
            "watermark, photorealism, 3D render, top-down map view, isometric view.\n"
            "Output: a newly rendered polished candidate, not a simple filter or color grade."
        )
    if variant == "night":
        return (
            f"Edit Image 1 into a night/evening time-difference candidate for {title}.\n"
            "Use case: lighting-weather edit for a cozy mobile game home map room background.\n"
            "Primary request: 夜晚也要温暖干净，亮度不要太暗，参考原图亮度，不要偏蓝、不要偏黄、不要偏紫、不要太黑，亮灯不要明显。\n"
            f"Keep unchanged: {keep}.\n"
            "Change only: make a bright readable neutral evening/night version, not a lamp-warmed afternoon. Keep the room interior close to the source palette: cream walls, natural wood, pale pink textiles, plants, "
            "floor colors, and small objects must remain clearly visible without turning cold or golden. The night cue should come from slightly lower ambient brightness, softer contrast, and a neutral dim exterior "
            "beyond windows or balcony, plus tiny soft ivory indoor lamp accents only where the source already supports them. Lamps must not recolor the whole room yellow. Shadows should stay open neutral gray-brown midtones, not blue and not black.\n"
            "Avoid: blue cast, blue filter, cyan/teal cast, deep-blue wash, dark navy wash, blue-gray room shadows, purple cast, too black, too dark, cyberpunk neon, overall yellow cast, golden cast, strong yellow/orange/amber/sepia cast, "
            "harsh glow, obvious lamp bloom, horror/cinematic mood, high contrast, muddy gray, simple filter/color grading look, new furniture, removed furniture, moved objects, different room, characters, "
            "pets, UI, map pins, text, logo, watermark, photorealism, 3D render.\n"
            "Output: a newly rendered polished candidate, not a simple filter or color grade."
        )
    raise ValueError(variant)


def summary_prompt_text() -> str:
    return (
        "目标：6 个家地图房间，每个房间下午/晚上两个差分，共 12 条 workflow。"
        f"每个 Output 目标 {TARGET_COUNT} 张候选；结构为 Group(源图+提示词) -> API生成 -> Output。"
        "色调修正：下午用轻微方向光和浅阴影表现，不要偏白/发白/过曝/雾白，也不要太黄或变夕阳；"
        "晚上保持明亮可读和温暖干净，室内保留奶油墙、木色、粉色，不要偏蓝/蓝色滤镜/青蓝/深蓝，也不要偏黄/金黄灯光/偏紫/太黑。"
        "只改时间光照，保持房间结构和物件位置。"
    )


def build_requirements() -> list[dict[str, Any]]:
    reqs = []
    for room_key, room_label, title, source in ROOMS:
        for variant, variant_label in VARIANTS:
            key = f"{room_key}_{variant}"
            reqs.append(
                {
                    "key": key,
                    "room_key": room_key,
                    "room_label": room_label,
                    "variant": variant,
                    "variant_label": variant_label,
                    "title": f"{room_label} {variant_label}",
                    "source": source,
                    "source_url": asset_url(source),
                    "prompt": build_prompt(room_key, title, variant),
                    "target": TARGET_COUNT,
                }
            )
    return reqs


def output_url_value(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        value = item.get("url")
        return value if isinstance(value, str) else ""
    return ""


def visible_real_images(output_node: dict[str, Any]) -> list[Any]:
    images = []
    for item in output_node.get("images") or []:
        url = output_url_value(item)
        if url and not url.startswith("failed://") and not url.startswith("pending://"):
            images.append(item)
    return images


def collect_seed_images() -> dict[str, list[dict[str, Any]]]:
    seeds: dict[str, list[dict[str, Any]]] = {req["key"]: [] for req in build_requirements()}
    old_progress_path = ROOT / "output" / "codex_home_room_time_diffs_20260621" / "progress.json"
    if old_progress_path.exists():
        old_progress = json.loads(old_progress_path.read_text(encoding="utf-8"))
        for key, result in (old_progress.get("results") or {}).items():
            if key not in seeds:
                continue
            status = result.get("status")
            if status == "local_fallback":
                continue
            url = result.get("asset_url") or result.get("copied_from_url")
            if not url and result.get("final_path"):
                try:
                    url = import_local_asset(Path(result["final_path"]), key, "historical")
                except FileNotFoundError:
                    url = ""
            if url:
                seeds[key].append(
                    {
                        "url": url,
                        "kind": "image",
                        "source": SOURCE_TAG,
                        "importSource": "historical_time_diff",
                        "reviewStatus": "candidate",
                        "createdAt": now_ms(),
                    }
                )
    night_v2_path = ROOT / "output" / "codex_home_room_night_regen_v2_20260621" / "progress.json"
    if night_v2_path.exists():
        night_v2 = json.loads(night_v2_path.read_text(encoding="utf-8"))
        for key, result in (night_v2.get("results") or {}).items():
            room_key = key.replace("_night_regen", "")
            target_key = f"{room_key}_night"
            if target_key not in seeds:
                continue
            url = result.get("asset_url")
            if url:
                seeds[target_key].append(
                    {
                        "url": url,
                        "kind": "image",
                        "source": SOURCE_TAG,
                        "importSource": "night_v2_generated",
                        "provider_id": result.get("provider_id") or "",
                        "provider_name": result.get("provider_name") or "",
                        "model": result.get("model") or "",
                        "task_id": result.get("task_id") or "",
                        "reviewStatus": "candidate",
                        "createdAt": now_ms(),
                    }
                )
    for key, items in seeds.items():
        seen = set()
        unique = []
        for item in items:
            url = item["url"]
            if url in seen:
                continue
            seen.add(url)
            unique.append(item)
        seeds[key] = unique
    return seeds


def connect(connections: list[dict[str, Any]], source_id: str, target_id: str) -> None:
    connections.append({"id": f"conn_{source_id}_{target_id}", "from": source_id, "to": target_id})


def remove_old_nodes(canvas: dict[str, Any]) -> dict[str, int]:
    nodes = canvas.get("nodes") or []
    remove_ids = {
        node.get("id")
        for node in nodes
        if node.get("source") in {SOURCE_TAG, OLD_STATIC_SOURCE_TAG}
    }
    remove_ids.discard(None)
    canvas["nodes"] = [node for node in nodes if node.get("id") not in remove_ids]
    old_connections = canvas.get("connections") or []
    canvas["connections"] = [
        conn
        for conn in old_connections
        if conn.get("from") not in remove_ids and conn.get("to") not in remove_ids
    ]
    return {"removed_nodes": len(remove_ids), "removed_connections": len(old_connections) - len(canvas["connections"])}


def create_workflows(canvas: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    reqs = build_requirements()
    seeds = collect_seed_images()

    origin_x = 0
    origin_y = 240
    row_h = 760
    group_w = 960
    group_h = 560
    gen_w = 380
    output_w = 780
    output_h = 680

    summary = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 250,
        "w": 1900,
        "h": 180,
        "name": "家地图下午/晚上差分｜结构+色调修正版",
        "text": summary_prompt_text(),
        "source": SOURCE_TAG,
    }
    nodes.append(summary)

    run_plan = []
    created = {"groups": [], "images": [], "prompts": [summary["id"]], "generators": [], "outputs": []}
    for index, req in enumerate(reqs):
        x0 = origin_x
        y0 = origin_y + index * row_h
        source_path = ROOT / req["source"]
        if not source_path.exists():
            raise FileNotFoundError(source_path)

        img = {
            "id": uid("img"),
            "type": "image",
            "x": x0 + 34,
            "y": y0 + 92,
            "url": req["source_url"],
            "name": f"{req['room_label']} 源图",
            "role": "结构参考/精确保留对象：只允许改变时间光照",
            "w": 300,
            "h": 534,
            "source": SOURCE_TAG,
        }
        prompt = {
            "id": uid("prompt"),
            "type": "prompt",
            "x": x0 + 370,
            "y": y0 + 92,
            "text": req["prompt"],
            "name": f"{req['title']} 提示词",
            "w": 560,
            "h": 430,
            "source": SOURCE_TAG,
        }
        group = {
            "id": uid("grp"),
            "type": "group",
            "x": x0,
            "y": y0,
            "w": group_w,
            "h": group_h,
            "items": [img["id"], prompt["id"]],
            "name": f"{req['title']} 输入｜目标{TARGET_COUNT}张",
            "source": SOURCE_TAG,
        }
        gen = {
            "id": uid("gen"),
            "type": "generator",
            "x": x0 + group_w + 80,
            "y": y0 + 42,
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
            "name": f"{req['title']} / 单API可调",
            "targetOutputId": "",
            "poolTargetCount": TARGET_COUNT,
            "canvasProviderMode": "single-visible-api-node",
            "providerPoolCandidates": [
                {"apiProvider": p["id"], "providerName": p["name"], "model": p["model"]}
                for p in PROVIDER_POOL
            ],
            "source": SOURCE_TAG,
        }
        out = {
            "id": uid("out"),
            "type": "output",
            "x": gen["x"] + gen_w + 80,
            "y": y0 + 20,
            "w": output_w,
            "h": output_h,
            "images": seeds.get(req["key"], []),
            "name": f"{req['title']} 输出｜目标{TARGET_COUNT}张",
            "source": SOURCE_TAG,
            "requirement_key": req["key"],
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
                **req,
                "generator_id": gen["id"],
                "output_id": out["id"],
                "group_id": group["id"],
                "source_image_id": img["id"],
                "prompt_id": prompt["id"],
                "existing_seed_count": len(out["images"]),
                "size": SIZE,
                "quality": QUALITY,
            }
        )

    canvas["viewport"] = {"x": 0, "y": 0, "scale": 1}
    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_home_room_diffs_workflow_{now_ms()}",
            "createdAt": now_ms(),
            "status": "done",
            "nodeType": "canvas-agent",
            "model": "codex_home_room_diffs_workflow_v1",
            "prompt": summary["text"],
            "outputs": [],
            "error": "",
            "platform": "codex",
        },
    )
    canvas["logs"] = canvas["logs"][:500]
    return run_plan, created


def setup_canvas() -> dict[str, Any]:
    canvas = load_canvas()
    if canvas.get("id") != CANVAS_ID or canvas.get("title") != "背景图":
        raise RuntimeError(f"unexpected canvas: {canvas.get('title')} {canvas.get('id')}")
    backup = backup_canvas_file("before-home-room-diffs-workflow-v1")
    removed = remove_old_nodes(canvas)
    run_plan, created = create_workflows(canvas)
    saved = save_canvas(canvas, "codex-home-room-diffs-workflow-v1-setup")
    progress = {
        "started_at": now_ms(),
        "base": BASE,
        "canvas_id": CANVAS_ID,
        "canvas_title": saved.get("title"),
        "canvas_updated_at": saved.get("updated_at"),
        "backup": str(backup),
        "source_tag": SOURCE_TAG,
        "target_count": TARGET_COUNT,
        "size": SIZE,
        "quality": QUALITY,
        "provider_pool": PROVIDER_POOL,
        "removed": removed,
        "created": created,
        "run_plan": run_plan,
        "results": {},
    }
    write_progress(progress)
    return progress


def update_existing_prompts() -> dict[str, Any]:
    canvas = load_canvas()
    if canvas.get("id") != CANVAS_ID or canvas.get("title") != "背景图":
        raise RuntimeError(f"unexpected canvas: {canvas.get('title')} {canvas.get('id')}")
    backup = backup_canvas_file("before-home-room-tone-prompts-v2")
    progress = read_progress()
    reqs = {req["key"]: req for req in build_requirements()}
    reqs_by_prompt_name = {f"{req['title']} 提示词": req for req in reqs.values()}
    nodes = canvas.get("nodes") or []
    by_id = {node.get("id"): node for node in nodes if node.get("id")}
    updated_prompt_nodes = []
    updated_plan_keys = []

    for plan in progress.get("run_plan") or []:
        req = reqs.get(plan.get("key"))
        if not req:
            continue
        if plan.get("prompt") != req["prompt"]:
            plan["prompt"] = req["prompt"]
            updated_plan_keys.append(plan["key"])
        plan["target"] = TARGET_COUNT
        prompt_node = by_id.get(plan.get("prompt_id"))
        if prompt_node and prompt_node.get("type") == "prompt":
            if prompt_node.get("text") != req["prompt"]:
                prompt_node["text"] = req["prompt"]
                updated_prompt_nodes.append(prompt_node.get("id"))
            prompt_node["name"] = f"{req['title']} 提示词"
            prompt_node["tonePromptVersion"] = "home-room-tone-v2"

    for node in nodes:
        if node.get("source") != SOURCE_TAG or node.get("type") != "prompt":
            continue
        req = reqs_by_prompt_name.get(str(node.get("name") or ""))
        if req and node.get("text") != req["prompt"]:
            node["text"] = req["prompt"]
            node["tonePromptVersion"] = "home-room-tone-v2"
            updated_prompt_nodes.append(node.get("id"))
        if "家地图下午/晚上差分" in str(node.get("name") or ""):
            node["name"] = "家地图下午/晚上差分｜结构+色调修正版"
            node["text"] = summary_prompt_text()
            node["tonePromptVersion"] = "home-room-tone-v2"

    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_home_room_tone_prompt_v2_{now_ms()}",
            "createdAt": now_ms(),
            "status": "done",
            "nodeType": "canvas-agent",
            "model": "codex_home_room_diffs_workflow_v1",
            "prompt": (
                "色调修正 v2：下午禁止偏白/发白/过曝/雾白，夜晚禁止偏蓝/蓝色滤镜/青蓝/深蓝；"
                "保留奶油墙、木色、粉色和房间结构，只改时间光照。"
            ),
            "outputs": [],
            "error": "",
            "platform": "codex",
        },
    )
    canvas["logs"] = canvas["logs"][:500]
    saved = save_canvas(canvas, "codex-home-room-tone-prompts-v2")
    if progress:
        progress["updated_at"] = now_ms()
        progress["tone_prompt_version"] = "home-room-tone-v2"
        progress["tone_prompt_update"] = {
            "at": progress["updated_at"],
            "backup": str(backup),
            "updated_prompt_nodes": len(set(filter(None, updated_prompt_nodes))),
            "updated_plan_keys": updated_plan_keys,
            "canvas_updated_at": saved.get("updated_at"),
        }
        write_progress(progress)
    return {
        "canvas_title": saved.get("title"),
        "canvas_id": saved.get("id"),
        "backup": str(backup),
        "updated_prompt_nodes": len(set(filter(None, updated_prompt_nodes))),
        "updated_plan_keys": updated_plan_keys,
        "canvas_updated_at": saved.get("updated_at"),
        "canvas_url": f"{BASE}/static/canvas.html?canvas={CANVAS_ID}",
    }


def submit_task(plan: dict[str, Any], provider: dict[str, str]) -> dict[str, Any]:
    payload = {
        "prompt": plan["prompt"],
        "provider_id": provider["id"],
        "model": provider["model"],
        "size": plan.get("size") or SIZE,
        "quality": plan.get("quality") or QUALITY,
        "n": 1,
        "reference_images": [
            {
                "url": plan["source_url"],
                "name": Path(plan["source"]).name,
                "role": "Image 1: exact edit target. Preserve room structure; change only time-of-day lighting.",
            }
        ],
    }
    created = http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
    if not created.get("task_id"):
        raise RuntimeError(f"missing task_id: {created}")
    return created


def poll_task(task_id: str) -> dict[str, Any]:
    deadline = time.time() + TASK_DEADLINE_SECONDS
    while True:
        state = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=60)
        status = str(state.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return state
        if time.time() >= deadline:
            state = dict(state)
            state["status"] = "still_pending_after_deadline"
            state["error"] = f"waited more than {TASK_DEADLINE_SECONDS} seconds"
            return state
        time.sleep(POLL_INTERVAL_SECONDS)


def run_generation_attempt(plan: dict[str, Any], attempt_index: int) -> dict[str, Any]:
    attempts = []
    start = now_ms()
    providers = PROVIDER_POOL[attempt_index % len(PROVIDER_POOL) :] + PROVIDER_POOL[: attempt_index % len(PROVIDER_POOL)]
    for provider in providers:
        attempt = {"provider_id": provider["id"], "provider_name": provider["name"], "model": provider["model"], "submitted_at": now_ms()}
        try:
            created = submit_task(plan, provider)
            attempt["task_id"] = created.get("task_id")
            state = poll_task(created["task_id"])
            attempt["result_state"] = state
            status = str(state.get("status") or "").lower()
            urls = (state.get("result") or {}).get("images") or []
            if status == "succeeded" and urls:
                attempt["urls"] = urls
                attempts.append(attempt)
                return {
                    "ok": True,
                    "requirement_key": plan["key"],
                    "output_id": plan["output_id"],
                    "generator_id": plan["generator_id"],
                    "provider_id": provider["id"],
                    "provider_name": provider["name"],
                    "model": provider["model"],
                    "task_id": created.get("task_id"),
                    "images": urls,
                    "attempts": attempts,
                    "runMs": now_ms() - start,
                }
            attempt["error"] = state.get("error") or status or "no image returned"
        except Exception as exc:
            attempt["error"] = str(exc)
        attempts.append(attempt)
    return {
        "ok": False,
        "requirement_key": plan["key"],
        "output_id": plan["output_id"],
        "generator_id": plan["generator_id"],
        "attempts": attempts,
        "error": attempts[-1].get("error") if attempts else "no attempt",
        "runMs": now_ms() - start,
    }


def append_results_to_canvas(results: list[dict[str, Any]]) -> dict[str, Any]:
    canvas = load_canvas()
    by_id = {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}
    added_by_output: dict[str, int] = {}
    for result in results:
        out = by_id.get(result.get("output_id"))
        gen = by_id.get(result.get("generator_id"))
        if out is None:
            continue
        images = out.setdefault("images", [])
        seen = {output_url_value(item) for item in images if output_url_value(item)}
        added = 0
        for url in result.get("images") or []:
            if not url or url in seen:
                continue
            images.append(
                {
                    "url": url,
                    "kind": "image",
                    "source": SOURCE_TAG,
                    "provider_id": result.get("provider_id") or "",
                    "provider_name": result.get("provider_name") or "",
                    "model": result.get("model") or "",
                    "task_id": result.get("task_id") or "",
                    "variant": result.get("requirement_key", "").split("_")[-1],
                    "createdAt": now_ms(),
                    "runMs": result.get("runMs") or 0,
                    "reviewStatus": "candidate",
                    "viewed": False,
                }
            )
            seen.add(url)
            added += 1
        added_by_output[out["id"]] = added_by_output.get(out["id"], 0) + added
        if gen is not None:
            if result.get("ok"):
                gen["runStatus"] = "done"
                gen["runError"] = ""
                gen.setdefault("generatedOutputs", [])
                for url in result.get("images") or []:
                    if url not in gen["generatedOutputs"]:
                        gen["generatedOutputs"].append(url)
            else:
                gen["runStatus"] = "failed"
                gen["runError"] = str(result.get("error") or "failed")[:500]
        canvas.setdefault("logs", []).insert(
            0,
            {
                "id": f"codex_home_room_diff_{uuid.uuid4().hex[:10]}_{now_ms()}",
                "createdAt": now_ms(),
                "status": "done" if result.get("ok") else "failed",
                "nodeType": "generator",
                "model": result.get("model") or "",
                "prompt": result.get("requirement_key") or "",
                "outputs": result.get("images") or [],
                "error": "" if result.get("ok") else str(result.get("error") or "failed")[:1000],
                "platform": result.get("provider_name") or "",
                "runMs": result.get("runMs") or 0,
                "task_id": result.get("task_id") or "",
                "request": {
                    "requirement_key": result.get("requirement_key") or "",
                    "provider_id": result.get("provider_id") or "",
                    "model": result.get("model") or "",
                    "size": SIZE,
                    "quality": QUALITY,
                },
            },
        )
    canvas["logs"] = canvas["logs"][:500]
    saved = save_canvas(canvas, "codex-home-room-diffs-workflow-v1-append")
    return {"canvas_updated_at": saved.get("updated_at"), "added_by_output": added_by_output}


def output_counts() -> dict[str, int]:
    canvas = load_canvas()
    by_id = {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}
    progress = read_progress()
    counts = {}
    for plan in progress.get("run_plan") or []:
        out = by_id.get(plan.get("output_id")) or {}
        counts[plan["key"]] = len(visible_real_images(out))
    return counts


def fill_outputs(max_workers: int, per_output_limit: int | None = None) -> dict[str, Any]:
    progress = read_progress()
    if not progress.get("run_plan"):
        raise RuntimeError("run setup first")
    counts = output_counts()
    jobs: list[tuple[dict[str, Any], int]] = []
    for plan in progress["run_plan"]:
        missing = max(0, int(plan.get("target") or TARGET_COUNT) - counts.get(plan["key"], 0))
        if per_output_limit is not None:
            missing = min(missing, max(0, int(per_output_limit)))
        for i in range(missing):
            jobs.append((plan, counts.get(plan["key"], 0) + i))
    if not jobs:
        return {"status": "already_full", "counts": counts, "results": []}

    results = []
    workers = max(1, min(max_workers, len(jobs)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(run_generation_attempt, plan, attempt_index): (plan, attempt_index) for plan, attempt_index in jobs}
        batch = []
        for future in concurrent.futures.as_completed(future_map):
            plan, _attempt_index = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"ok": False, "requirement_key": plan["key"], "output_id": plan["output_id"], "generator_id": plan["generator_id"], "error": str(exc), "images": []}
            results.append(result)
            batch.append(result)
            if len(batch) >= 3:
                append_results_to_canvas(batch)
                batch.clear()
            print(json.dumps({"key": plan["key"], "ok": result.get("ok"), "images": result.get("images") or [], "error": result.get("error")}, ensure_ascii=False), flush=True)
        if batch:
            append_results_to_canvas(batch)
    progress.setdefault("fill_runs", []).append({"at": now_ms(), "job_count": len(jobs), "results": results})
    progress["updated_at"] = now_ms()
    progress["counts_after"] = output_counts()
    write_progress(progress)
    return {"status": "filled", "jobs": len(jobs), "counts_before": counts, "counts_after": progress["counts_after"], "results": results}


def verify_structure() -> dict[str, Any]:
    canvas = load_canvas()
    nodes = canvas.get("nodes") or []
    connections = canvas.get("connections") or []
    by_id = {node.get("id"): node for node in nodes if node.get("id")}
    progress = read_progress()
    run_plan = progress.get("run_plan") or []
    issues = []
    counts = {}
    for plan in run_plan:
        group = by_id.get(plan.get("group_id"))
        gen = by_id.get(plan.get("generator_id"))
        out = by_id.get(plan.get("output_id"))
        prompt = by_id.get(plan.get("prompt_id"))
        img = by_id.get(plan.get("source_image_id"))
        if not group or group.get("type") != "group":
            issues.append(f"{plan['key']}: missing group")
        if not prompt or prompt.get("type") != "prompt" or prompt.get("id") not in (group or {}).get("items", []):
            issues.append(f"{plan['key']}: prompt not inside group")
        if not img or img.get("type") != "image" or img.get("id") not in (group or {}).get("items", []):
            issues.append(f"{plan['key']}: source image not inside group")
        if not gen or gen.get("type") != "generator":
            issues.append(f"{plan['key']}: missing generator")
        if not out or out.get("type") != "output":
            issues.append(f"{plan['key']}: missing output")
        if gen and out and gen.get("targetOutputId") != out.get("id"):
            issues.append(f"{plan['key']}: generator targetOutputId mismatch")
        if gen and group and not any(conn.get("from") == group.get("id") and conn.get("to") == gen.get("id") for conn in connections):
            issues.append(f"{plan['key']}: missing group->generator connection")
        if gen and out and not any(conn.get("from") == gen.get("id") and conn.get("to") == out.get("id") for conn in connections):
            issues.append(f"{plan['key']}: missing generator->output connection")
        if out:
            if not out.get("w") or not out.get("h"):
                issues.append(f"{plan['key']}: output is not fixed-size")
            counts[plan["key"]] = len(visible_real_images(out))
    return {
        "canvas_title": canvas.get("title"),
        "canvas_id": canvas.get("id"),
        "run_plan_count": len(run_plan),
        "groups": len([node for node in nodes if node.get("source") == SOURCE_TAG and node.get("type") == "group"]),
        "prompts": len([node for node in nodes if node.get("source") == SOURCE_TAG and node.get("type") == "prompt"]),
        "generators": len([node for node in nodes if node.get("source") == SOURCE_TAG and node.get("type") == "generator"]),
        "outputs": len([node for node in nodes if node.get("source") == SOURCE_TAG and node.get("type") == "output"]),
        "counts": counts,
        "issues": issues,
        "canvas_url": f"{BASE}/static/canvas.html?canvas={CANVAS_ID}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    sub.add_parser("update-prompts")
    fill = sub.add_parser("fill")
    fill.add_argument("--max-workers", type=int, default=4)
    fill.add_argument("--per-output-limit", type=int, default=None)
    sub.add_parser("verify")
    all_cmd = sub.add_parser("all")
    all_cmd.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()

    if args.cmd == "setup":
        print(json.dumps(setup_canvas(), ensure_ascii=False, indent=2))
    elif args.cmd == "update-prompts":
        print(json.dumps(update_existing_prompts(), ensure_ascii=False, indent=2))
    elif args.cmd == "fill":
        print(json.dumps(fill_outputs(args.max_workers, args.per_output_limit), ensure_ascii=False, indent=2))
    elif args.cmd == "verify":
        print(json.dumps(verify_structure(), ensure_ascii=False, indent=2))
    elif args.cmd == "all":
        setup_canvas()
        print(json.dumps(fill_outputs(args.max_workers), ensure_ascii=False, indent=2))
        print(json.dumps(verify_structure(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
