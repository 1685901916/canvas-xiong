#!/usr/bin/env python3
"""Append and run Aiko home map v20 candidates on the existing canvas."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


BASE_DIR = Path(__file__).resolve().parents[1]
CANVAS_ID = "e7e89ae428904fcb91c3351c81b59840"
BASE_URL = "http://127.0.0.1:3001"
CANVAS_URL = f"{BASE_URL}/static/canvas.html?canvas={CANVAS_ID}"
CANVAS_PATH = BASE_DIR / "data" / "canvases" / f"{CANVAS_ID}.json"
BACKUP_DIR = BASE_DIR / "data" / "canvases" / "backups"
INPUT_DIR = BASE_DIR / "assets" / "input"
OUTPUT_DIR = BASE_DIR / "assets" / "output"
AIKO_TMP_DIR = Path("F:/cursor/Aiko/tmp")

STYLE_BOARD_URL = "/assets/input/home_map_v18_aiko_home_style_refs.png"
PRIMARY_PROVIDER = {"id": "custom-api-2", "name": "65535", "model": "gpt-image-2"}
BACKUP_PROVIDER = {"id": "custom-api-8", "name": "krill", "model": "gpt-image-2"}
STORY_2K_SIZE = "1152x2048"
STORY_1K_SIZE = "720x1280"


def now_ms() -> int:
    return int(time.time() * 1000)


def short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def request_json(method: str, path: str, payload: Any | None = None, timeout: float = 120) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} HTTP {exc.code}: {detail[:1000]}") from exc
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def backup_canvas() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"{CANVAS_ID}.home-map-v20-before-{stamp}.json"
    shutil.copy2(CANVAS_PATH, dst)
    return dst


def rounded_poly(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str, outline: str, width: int = 5) -> None:
    draw.polygon(points, fill=fill, outline=outline)
    for x, y in points:
        r = 10
        draw.ellipse((x - r, y - r, x + r, y + r), fill=outline)


def draw_floor_lines(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    for y in range(140, h - 120, 44):
        draw.line((82, y, w - 82, y + 18), fill=(214, 184, 139), width=1)
    for x in range(100, w - 80, 58):
        draw.line((x, 126, x + 32, h - 116), fill=(224, 196, 154), width=1)


def draw_outer_shell(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    shell = [(112, 164), (594, 122), (682, 320), (642, 1188), (376, 1282), (102, 1126), (76, 330)]
    draw.polygon(shell, fill=(246, 230, 203), outline=(117, 92, 64))
    draw.line(shell + [shell[0]], fill=(117, 92, 64), width=8, joint="curve")
    inner = [(136, 190), (570, 156), (650, 332), (612, 1164), (378, 1248), (130, 1100), (104, 346)]
    draw.polygon(inner, fill=(236, 197, 136), outline=(196, 154, 100))
    draw_floor_lines(draw, w, h)


def add_soft_zone(
    layer: Image.Image,
    points: list[tuple[float, float]],
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
    blur: int = 0,
) -> None:
    z = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(z)
    d.polygon(points, fill=fill, outline=outline)
    d.line(points + [points[0]], fill=outline, width=8, joint="curve")
    if blur:
        z = z.filter(ImageFilter.GaussianBlur(blur))
    layer.alpha_composite(z)


def draw_furniture(draw: ImageDraw.ImageDraw, variant: str) -> None:
    wood = (133, 92, 50)
    mint = (130, 177, 148)
    peach = (229, 156, 128)
    cream = (242, 222, 183)
    lavender = (176, 150, 202)
    aqua = (122, 185, 184)
    if variant == "ldk":
        draw.rounded_rectangle((300, 626, 505, 702), radius=18, fill=mint, outline=wood, width=4)
        draw.ellipse((352, 548, 470, 666), fill=cream, outline=wood, width=4)
        draw.rounded_rectangle((210, 760, 515, 826), radius=10, fill=(196, 143, 83), outline=wood, width=4)
        draw.rounded_rectangle((178, 798, 548, 872), radius=10, fill=(222, 188, 129), outline=wood, width=4)
        draw.rounded_rectangle((164, 474, 274, 860), radius=18, fill=(157, 194, 164), outline=wood, width=4)
        draw.rounded_rectangle((186, 514, 246, 636), radius=10, fill=(248, 239, 213), outline=wood, width=3)
    elif variant == "u":
        draw.rounded_rectangle((248, 590, 516, 708), radius=24, fill=mint, outline=wood, width=4)
        draw.rounded_rectangle((210, 690, 284, 884), radius=20, fill=mint, outline=wood, width=4)
        draw.rounded_rectangle((472, 680, 548, 876), radius=20, fill=mint, outline=wood, width=4)
        draw.ellipse((326, 706, 450, 830), fill=cream, outline=wood, width=4)
        draw.rounded_rectangle((160, 472, 250, 892), radius=16, fill=(157, 194, 164), outline=wood, width=4)
        draw.rounded_rectangle((508, 452, 604, 842), radius=16, fill=(226, 177, 114), outline=wood, width=4)
    else:
        draw.rounded_rectangle((248, 658, 510, 746), radius=22, fill=mint, outline=wood, width=4)
        draw.ellipse((330, 566, 456, 692), fill=cream, outline=wood, width=4)
        draw.rounded_rectangle((172, 780, 490, 850), radius=14, fill=(222, 188, 129), outline=wood, width=4)
        draw.rounded_rectangle((454, 424, 568, 808), radius=16, fill=(157, 194, 164), outline=wood, width=4)
    draw.rounded_rectangle((118, 1010, 242, 1124), radius=14, fill=(90, 125, 122), outline=wood, width=4)
    draw.rounded_rectangle((466, 220, 608, 360), radius=18, fill=(201, 184, 222), outline=wood, width=4)
    draw.rounded_rectangle((126, 248, 268, 388), radius=18, fill=(146, 203, 204), outline=wood, width=4)
    draw.rounded_rectangle((512, 946, 626, 1100), radius=14, fill=(163, 201, 142), outline=wood, width=4)
    for x, y, color in [(558, 590, peach), (168, 562, lavender), (596, 810, aqua), (238, 930, peach)]:
        draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=color, outline=wood, width=3)


def make_structure_guides() -> dict[str, str]:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = {
        "ldk": "home_map_v20_structure_ldk_center.png",
        "u": "home_map_v20_structure_u_surround.png",
        "diagonal": "home_map_v20_structure_diagonal_cozy.png",
    }
    for key, filename in specs.items():
        w, h = 768, 1365
        img = Image.new("RGBA", (w, h), (250, 244, 232, 255))
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.polygon([(128, 186), (596, 144), (696, 330), (654, 1192), (378, 1300), (92, 1142), (68, 338)], fill=(0, 0, 0, 45))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        img.alpha_composite(shadow, (10, 18))
        draw = ImageDraw.Draw(img)
        draw_outer_shell(draw, w, h)
        zones = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if key == "ldk":
            add_soft_zone(zones, [(160, 438), (560, 398), (624, 908), (372, 1050), (146, 924)], (226, 210, 157, 160), (135, 112, 71, 210))
            add_soft_zone(zones, [(134, 928), (306, 952), (276, 1132), (128, 1108)], (161, 190, 205, 155), (92, 118, 130, 210))
            add_soft_zone(zones, [(452, 196), (620, 234), (594, 396), (466, 392)], (191, 174, 215, 150), (116, 92, 140, 210))
            add_soft_zone(zones, [(112, 222), (302, 206), (292, 410), (112, 390)], (151, 204, 205, 140), (75, 137, 139, 210))
            add_soft_zone(zones, [(514, 900), (638, 930), (604, 1120), (490, 1122)], (156, 204, 152, 150), (92, 135, 88, 210))
        elif key == "u":
            add_soft_zone(zones, [(188, 454), (602, 420), (628, 950), (496, 1126), (156, 1060), (110, 792)], (224, 210, 158, 145), (135, 112, 71, 210))
            add_soft_zone(zones, [(118, 420), (258, 386), (248, 990), (114, 1040)], (151, 204, 205, 150), (75, 137, 139, 210))
            add_soft_zone(zones, [(500, 380), (636, 424), (612, 890), (510, 940)], (204, 178, 217, 140), (116, 92, 140, 210))
            add_soft_zone(zones, [(112, 1014), (300, 1040), (280, 1160), (122, 1110)], (161, 190, 205, 145), (92, 118, 130, 210))
            add_soft_zone(zones, [(474, 930), (638, 924), (604, 1132), (456, 1160)], (156, 204, 152, 140), (92, 135, 88, 210))
        else:
            add_soft_zone(zones, [(180, 520), (568, 420), (640, 810), (362, 1050), (128, 930)], (226, 210, 157, 150), (135, 112, 71, 210))
            add_soft_zone(zones, [(438, 204), (622, 236), (590, 410), (454, 430)], (204, 178, 217, 145), (116, 92, 140, 210))
            add_soft_zone(zones, [(110, 258), (294, 230), (292, 430), (120, 438)], (151, 204, 205, 135), (75, 137, 139, 210))
            add_soft_zone(zones, [(118, 944), (322, 1000), (258, 1160), (116, 1094)], (161, 190, 205, 145), (92, 118, 130, 210))
            add_soft_zone(zones, [(478, 832), (650, 882), (610, 1130), (456, 1136)], (156, 204, 152, 145), (92, 135, 88, 210))
        img.alpha_composite(zones)
        draw = ImageDraw.Draw(img)
        draw_furniture(draw, key)
        img = img.convert("RGB")
        img.save(INPUT_DIR / filename, quality=95)
    return {key: f"/assets/input/{filename}" for key, filename in specs.items()}


def prompt_for_variant(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- Use the Aiko home style board only for the finished art family: soft anime watercolor, warm wood, cream walls, mint/peach/aqua accents, thin clean outlines, cozy Tokyo home details.\n"
        "- Use the structure guide only for spatial massing and adjacency. Do not copy its diagram colors, flat schematic look, marker-like shapes, or absence of detail.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME SPACE MAP for a mobile game. It is a playable clickable home hub background, not a realistic floor plan and not a single-room local background. Show one complete cozy two-level house interior as an elevated 2.5D cutaway with warm believable depth. No characters.\n\n"
        "Main correction from the rejected version: the central living-dining-kitchen activity area must be the largest and most attractive visual center of the whole image. Entry, bedroom, bathroom, laundry, balcony, study/storage are smaller tappable corners around it. Divide places with furniture clusters, rugs, half-height walls, open thresholds, shelves, plants, lighting, and floor material changes instead of hard boxed rooms.\n\n"
        "Two-level logic: suggest a compact second level through a rear loft/raised band, balcony edge, landing door, or layered cutaway depth. Do not draw a large staircase. If a connector is needed, make it tiny, believable, and visually secondary, like a closed stairwell nook or short hidden landing, not a central feature.\n\n"
        "Hard avoid: long corridor, six separate rectangular boxes, dominant bedroom, dominant entryway, giant bathroom, fake/oversized staircase, visible route lines, colored pins, target icons, labels, UI, text, A/B/C markers, blueprint, flat top-down plan, exterior facade, roof, sky, postcard exterior view, photorealism, plastic 3D render, watermark."
    )
    if key == "ldk":
        title = "v20A LDK中心活动岛"
        direction = (
            "Variant direction: make an open LDK center island. The lower-middle of the frame contains one continuous cozy hub with sofa, round table, dining table, compact kitchen counter, plants, lamps, and rugs. The player should immediately understand this is the main home hub. Put a tiny genkan entry nook in the foreground, a compact bedroom/study corner on the rear raised level, bath/wash/laundry on one side, and balcony/plant laundry corner as a small edge zone."
        )
    elif key == "u":
        title = "v20B U型围合生活核心"
        direction = (
            "Variant direction: use a U-shaped surrounding composition. The living rug and table sit in the open center, with kitchen, dining, desk, laundry, bath, bedroom nook, and balcony wrapping around it like a cozy house hub. The center stays open and readable for tapping. Keep the home continuous, with short open thresholds instead of corridors."
        )
    else:
        title = "v20C 斜向温馨切面"
        direction = (
            "Variant direction: use a diagonal cozy cutaway. A warm wooden floor flow runs diagonally from tiny foreground entry to central living-dining-kitchen, then toward a softer rear raised bedroom/study corner. Bath, laundry, balcony garden, closet/storage, and a small hobby nook sit on the sides. The diagonal layout should feel more like a designed game home hub than a rectangular apartment plan."
        )
    return title, f"{common}\n\n{direction}"


def append_v20_nodes(guide_urls: dict[str, str]) -> dict[str, Any]:
    data = request_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)
    canvas = data["canvas"]
    nodes = canvas.get("nodes") or []
    connections = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict[str, Any]] = []
    for i, key in enumerate(["ldk", "u", "diagonal"]):
        y = y0 + i * 760
        title, prompt = prompt_for_variant(key)
        style_id = short_id("img")
        guide_id = short_id("img")
        prompt_id = short_id("prompt")
        group_id = short_id("grp")
        gen_id = short_id("gen")
        out_id = short_id("out")
        style_node = {
            "id": style_id,
            "type": "image",
            "x": 156,
            "y": y + 92,
            "url": STYLE_BOARD_URL,
            "name": "Aiko home style board",
            "role": "style reference only",
        }
        guide_node = {
            "id": guide_id,
            "type": "image",
            "x": 396,
            "y": y + 92,
            "url": guide_urls[key],
            "name": "v20 structure guide",
            "role": "spatial adjacency only",
        }
        prompt_node = {
            "id": prompt_id,
            "type": "prompt",
            "x": 668,
            "y": y + 92,
            "text": prompt,
            "w": 360,
            "h": 260,
            "name": title,
        }
        group_node = {
            "id": group_id,
            "type": "group",
            "x": 120,
            "y": y,
            "w": 944,
            "h": 402,
            "items": [style_id, guide_id, prompt_id],
            "name": f"{title} 输入",
        }
        gen_node = {
            "id": gen_id,
            "type": "generator",
            "x": 1144,
            "y": y + 40,
            "apiProvider": PRIMARY_PROVIDER["id"],
            "model": PRIMARY_PROVIDER["model"],
            "ratio": "story",
            "resolution": "2k",
            "quality": "auto",
            "customRatio": "",
            "customSize": "",
            "customRatioWidth": "",
            "customRatioHeight": "",
            "customWidth": "",
            "customHeight": "",
            "inputs": [f"{group_id}:{style_id}", f"{group_id}:{guide_id}", f"{group_id}:prompts"],
            "count": 2,
            "apiDefaultsVersion": 2,
            "name": f"{title} / 65535",
            "w": 380,
            "h": 0,
            "generatedOutputs": [],
        }
        out_node = {
            "id": out_id,
            "type": "output",
            "x": 1604,
            "y": y + 40,
            "images": [],
            "name": "65535 输出",
            "w": 780,
            "h": 640,
        }
        nodes.extend([style_node, guide_node, prompt_node, group_node, gen_node, out_node])
        connections.append({"id": short_id("c"), "from": group_id, "to": gen_id})
        connections.append({"id": short_id("c"), "from": gen_id, "to": out_id})
        groups.append(
            {
                "key": key,
                "title": title,
                "prompt": prompt,
                "generator_id": gen_id,
                "output_id": out_id,
                "group_id": group_id,
                "reference_images": [
                    {"url": STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                    {"url": guide_urls[key], "name": "v20 structure guide", "role": "spatial adjacency only"},
                ],
            }
        )
    canvas["nodes"] = nodes
    canvas["connections"] = connections
    logs = canvas.get("logs") or []
    logs.insert(
        0,
        {
            "id": short_id("log"),
            "createdAt": now_ms(),
            "status": "done",
            "nodeType": "agent",
            "platform": "codex-v20",
            "prompt": "Appended v20 home map candidate groups. Primary provider custom-api-2 / 65535.",
            "outputs": [],
            "runMs": 0,
        },
    )
    payload = {
        "title": canvas.get("title") or "Aiko Home Space Map Iteration",
        "icon": canvas.get("icon") or "layers",
        "nodes": nodes,
        "connections": connections,
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": logs[:500],
        "settings": canvas.get("settings") or {},
        "client_id": "codex-home-map-v20",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    saved = request_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)
    return {"groups": groups, "saved_updated_at": saved.get("canvas", {}).get("updated_at"), "y0": y0}


def create_task(plan: dict[str, Any], provider: dict[str, str], size: str, attempt_label: str, index: int) -> dict[str, Any]:
    payload = {
        "prompt": plan["prompt"],
        "provider_id": provider["id"],
        "model": provider["model"],
        "size": size,
        "quality": "auto",
        "n": 1,
        "reference_images": plan["reference_images"],
    }
    started = now_ms()
    try:
        created = request_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
        task_id = created.get("task_id")
        if not task_id:
            raise RuntimeError(f"missing task_id in response: {created}")
        deadline = time.time() + 1800
        last = created
        while time.time() < deadline:
            time.sleep(3)
            last = request_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=60)
            status = str(last.get("status") or "").lower()
            if status in {"succeeded", "success", "done", "completed", "complete", "finished"}:
                result = last.get("result") or {}
                images = result.get("images") or []
                return {
                    "ok": bool(images),
                    "status": status,
                    "task_id": task_id,
                    "images": images,
                    "error": "" if images else "completed without images",
                    "raw": last,
                    "run_ms": last.get("run_ms") or last.get("total_ms") or now_ms() - started,
                    "created_at": started,
                    "plan": plan,
                    "provider": provider,
                    "size": size,
                    "attempt": attempt_label,
                    "index": index,
                }
            if status in {"failed", "fail", "error", "canceled", "cancelled"}:
                return {
                    "ok": False,
                    "status": status,
                    "task_id": task_id,
                    "images": [],
                    "error": last.get("error") or "task failed",
                    "raw": last,
                    "run_ms": last.get("run_ms") or last.get("total_ms") or now_ms() - started,
                    "created_at": started,
                    "plan": plan,
                    "provider": provider,
                    "size": size,
                    "attempt": attempt_label,
                    "index": index,
                }
        return {
            "ok": False,
            "status": "timeout",
            "task_id": task_id,
            "images": [],
            "error": "task timeout",
            "raw": last,
            "run_ms": now_ms() - started,
            "created_at": started,
            "plan": plan,
            "provider": provider,
            "size": size,
            "attempt": attempt_label,
            "index": index,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "task_id": "",
            "images": [],
            "error": str(exc),
            "raw": {},
            "run_ms": now_ms() - started,
            "created_at": started,
            "plan": plan,
            "provider": provider,
            "size": size,
            "attempt": attempt_label,
            "index": index,
        }


def run_batch(plans: list[dict[str, Any]], provider: dict[str, str], size: str, target_each: int, attempt_label: str, concurrency: int) -> list[dict[str, Any]]:
    jobs: list[tuple[dict[str, Any], int]] = []
    for plan in plans:
        for i in range(target_each):
            jobs.append((plan, i + 1))
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(create_task, plan, provider, size, attempt_label, index) for plan, index in jobs]
        for fut in concurrent.futures.as_completed(futs):
            result = fut.result()
            results.append(result)
            title = result.get("plan", {}).get("title", "")
            provider_name = result.get("provider", {}).get("name", "")
            state = "OK" if result.get("ok") else "FAIL"
            print(f"[{state}] {attempt_label} {provider_name} {size} {title} #{result.get('index')} task={result.get('task_id') or '-'} error={str(result.get('error') or '')[:180]}", flush=True)
    return results


def append_results_to_canvas(results: list[dict[str, Any]]) -> None:
    data = request_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)
    canvas = data["canvas"]
    nodes = canvas.get("nodes") or []
    by_id = {n.get("id"): n for n in nodes}
    logs = canvas.get("logs") or []
    gen_success: dict[str, bool] = {}
    for result in results:
        plan = result.get("plan") or {}
        provider = result.get("provider") or {}
        gen = by_id.get(plan.get("generator_id"))
        out = by_id.get(plan.get("output_id"))
        items = []
        for url in result.get("images") or []:
            if not url:
                continue
            item = {
                "url": url,
                "kind": "image",
                "source": "codex-v20",
                "provider_id": provider.get("id") or "",
                "provider_name": provider.get("name") or "",
                "model": provider.get("model") or "",
                "task_id": result.get("task_id") or "",
                "runMs": result.get("run_ms") or 0,
                "createdAt": now_ms(),
                "reviewStatus": "pending-structure-review-v20",
                "v20StructureVariant": plan.get("key") or "",
                "attempt": result.get("attempt") or "",
                "size": result.get("size") or "",
            }
            items.append(item)
        if out is not None and items:
            out.setdefault("images", []).extend(items)
        if gen is not None:
            if items:
                gen.setdefault("generatedOutputs", []).extend(items)
                gen["runStatus"] = "done"
                gen["runError"] = ""
                gen_success[gen.get("id")] = True
            elif not gen_success.get(gen.get("id")):
                gen["runStatus"] = "failed"
                gen["runError"] = str(result.get("error") or result.get("status") or "task failed")[:500]
        logs.insert(
            0,
            {
                "id": short_id("log"),
                "createdAt": now_ms(),
                "status": "done" if result.get("ok") else "failed",
                "nodeType": "generator",
                "model": provider.get("model") or "",
                "prompt": plan.get("prompt") or "",
                "outputs": [item["url"] for item in items],
                "error": "" if result.get("ok") else str(result.get("error") or result.get("status") or "task failed")[:1000],
                "platform": provider.get("name") or provider.get("id") or "",
                "runMs": result.get("run_ms") or 0,
                "task_id": result.get("task_id") or "",
                "request": {
                    "provider_id": provider.get("id") or "",
                    "model": provider.get("model") or "",
                    "size": result.get("size") or "",
                    "quality": "auto",
                    "reference_count": len(plan.get("reference_images") or []),
                    "attempt": result.get("attempt") or "",
                    "v20_variant": plan.get("key") or "",
                },
            },
        )
    payload = {
        "title": canvas.get("title") or "Aiko Home Space Map Iteration",
        "icon": canvas.get("icon") or "layers",
        "nodes": nodes,
        "connections": canvas.get("connections") or [],
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": logs[:500],
        "settings": canvas.get("settings") or {},
        "client_id": "codex-home-map-v20",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    request_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)


def url_to_local_path(url: str) -> Path | None:
    text = str(url or "").strip()
    if text.startswith("/assets/") or text.startswith("/output/"):
        return BASE_DIR / text.lstrip("/").replace("/", os.sep)
    return None


def load_result_image(url: str) -> Image.Image | None:
    local = url_to_local_path(url)
    try:
        if local and local.exists():
            return Image.open(local).convert("RGB")
        if url.startswith("http://") or url.startswith("https://"):
            with urllib.request.urlopen(url, timeout=90) as resp:
                data = resp.read()
            from io import BytesIO

            return Image.open(BytesIO(data)).convert("RGB")
    except Exception:
        return None
    return None


def make_contact_sheet(results: list[dict[str, Any]]) -> Path:
    success_items = []
    failures = []
    for result in results:
        if result.get("ok"):
            for url in result.get("images") or []:
                success_items.append((result, url))
        else:
            failures.append(result)
    cell_w, cell_h = 360, 640
    label_h = 52
    cols = 3
    rows = max(1, math.ceil(max(1, len(success_items)) / cols))
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + label_h)), (242, 238, 229))
    draw = ImageDraw.Draw(sheet)
    for idx, (result, url) in enumerate(success_items):
        img = load_result_image(url)
        x = (idx % cols) * cell_w
        y = (idx // cols) * (cell_h + label_h)
        if img:
            img.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
            px = x + (cell_w - img.width) // 2
            py = y + (cell_h - img.height) // 2
            sheet.paste(img, (px, py))
        plan = result.get("plan") or {}
        provider = result.get("provider") or {}
        label = f"{plan.get('title','v20')} | {provider.get('name','')} | {result.get('size','')}"
        draw.rectangle((x, y + cell_h, x + cell_w, y + cell_h + label_h), fill=(250, 247, 240))
        draw.text((x + 10, y + cell_h + 10), label[:54], fill=(55, 48, 40))
    if not success_items:
        msg = "No successful v20 images yet. Failures: " + "; ".join(str(f.get("error") or f.get("status"))[:120] for f in failures[:6])
        draw.multiline_text((24, 24), msg, fill=(70, 52, 44), spacing=8)
    out_path = OUTPUT_DIR / "home_map_v20_contact_sheet.jpg"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)
    AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_path, AIKO_TMP_DIR / out_path.name)
    return out_path


def write_state(state: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "home_map_v20_task_state.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, AIKO_TMP_DIR / path.name)
    return path


def verify_canvas() -> dict[str, Any]:
    data = request_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)
    canvas = data["canvas"]
    nodes = canvas.get("nodes") or []
    groups = [n for n in nodes if str(n.get("name") or "").startswith("v20")]
    gens = [n for n in nodes if n.get("type") == "generator" and str(n.get("name") or "").startswith("v20")]
    outs = [n for n in nodes if n.get("type") == "output" and n.get("x") == 1604 and n.get("y", 0) >= 9000]
    return {
        "canvas_id": CANVAS_ID,
        "canvas_title": canvas.get("title"),
        "canvas_url": CANVAS_URL,
        "v20_named_nodes": len(groups),
        "v20_generators": len(gens),
        "v20_generator_providers": sorted({g.get("apiProvider") for g in gens}),
        "v20_output_image_count": sum(len(o.get("images") or []) for o in outs),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument("--target-each", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()

    state_path = OUTPUT_DIR / "home_map_v20_task_state.json"
    backup = None
    plans: list[dict[str, Any]]
    if args.run_only and state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        plans = state.get("groups") or []
    else:
        backup = backup_canvas()
        guide_urls = make_structure_guides()
        append_info = append_v20_nodes(guide_urls)
        plans = append_info["groups"]
        state = {
            "canvas_id": CANVAS_ID,
            "canvas_url": CANVAS_URL,
            "backup": str(backup) if backup else "",
            "groups": plans,
            "created_at": now_ms(),
            "runs": [],
            "contact_sheet": "",
            "verification": {},
        }
        write_state(state)
        print(f"prepared canvas={CANVAS_ID} backup={backup}", flush=True)
    if args.prepare_only:
        return 0

    all_results: list[dict[str, Any]] = []
    first = run_batch(plans, PRIMARY_PROVIDER, STORY_2K_SIZE, args.target_each, "primary-story-2k", args.concurrency)
    all_results.extend(first)
    by_key_success: dict[str, int] = {}
    for r in first:
        if r.get("ok"):
            by_key_success[r.get("plan", {}).get("key", "")] = by_key_success.get(r.get("plan", {}).get("key", ""), 0) + len(r.get("images") or [])
    retry_plans = [p for p in plans if by_key_success.get(p.get("key", ""), 0) < args.target_each]
    if retry_plans:
        retry_target_each = 1
        retry = run_batch(retry_plans, PRIMARY_PROVIDER, STORY_1K_SIZE, retry_target_each, "primary-story-1k-retry", min(args.concurrency, len(retry_plans)))
        all_results.extend(retry)
    by_key_success = {}
    for r in all_results:
        if r.get("ok"):
            by_key_success[r.get("plan", {}).get("key", "")] = by_key_success.get(r.get("plan", {}).get("key", ""), 0) + len(r.get("images") or [])
    backup_plans = [p for p in plans if by_key_success.get(p.get("key", ""), 0) == 0]
    if backup_plans:
        backup_results = run_batch(backup_plans, BACKUP_PROVIDER, STORY_2K_SIZE, 1, "backup-krill-if-65535-empty", min(3, len(backup_plans)))
        all_results.extend(backup_results)
    append_results_to_canvas(all_results)
    contact_sheet = make_contact_sheet(all_results)
    verification = verify_canvas()
    state = {
        "canvas_id": CANVAS_ID,
        "canvas_url": CANVAS_URL,
        "backup": str(backup) if backup else "",
        "groups": plans,
        "runs": all_results,
        "contact_sheet": str(contact_sheet),
        "aiko_tmp_contact_sheet": str(AIKO_TMP_DIR / contact_sheet.name),
        "verification": verification,
        "completed_at": now_ms(),
    }
    write_state(state)
    print(json.dumps({"ok": True, "contact_sheet": str(contact_sheet), "verification": verification}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
