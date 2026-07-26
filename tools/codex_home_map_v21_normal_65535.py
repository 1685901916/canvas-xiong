#!/usr/bin/env python3
"""Generate normal one-floor Aiko home map v21 candidates."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import time
import urllib.error
import urllib.request
import uuid
from io import BytesIO
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
SIZE = "1152x2048"


def now_ms() -> int:
    return int(time.time() * 1000)


def sid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


def req_json(method: str, path: str, payload: Any | None = None, timeout: float = 120) -> Any:
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
    return json.loads(raw.decode("utf-8")) if raw else {}


def backup_canvas() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"{CANVAS_ID}.home-map-v21-normal-before-{stamp}.json"
    shutil.copy2(CANVAS_PATH, dst)
    return dst


def draw_wall(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], width: int = 8) -> None:
    draw.rounded_rectangle(xy, radius=8, outline=(115, 88, 58), width=width, fill=(244, 228, 199))


def draw_floor(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: tuple[int, int, int]) -> None:
    draw.rounded_rectangle(xy, radius=12, fill=fill, outline=(166, 126, 78), width=4)
    x1, y1, x2, y2 = xy
    for y in range(y1 + 18, y2 - 10, 34):
        draw.line((x1 + 8, y, x2 - 8, y + 8), fill=(214, 180, 128), width=1)


def draw_room_icon(draw: ImageDraw.ImageDraw, variant: str) -> None:
    wood = (128, 87, 49)
    mint = (128, 178, 148)
    peach = (230, 155, 126)
    cream = (242, 224, 190)
    aqua = (140, 203, 204)
    lavender = (184, 156, 205)
    # Main LDK furniture.
    draw.ellipse((276, 576, 492, 792), fill=cream, outline=wood, width=4)
    draw.rounded_rectangle((236, 504, 530, 594), radius=24, fill=mint, outline=wood, width=4)
    draw.rounded_rectangle((332, 792, 528, 888), radius=14, fill=(215, 166, 96), outline=wood, width=4)
    draw.rounded_rectangle((142, 472, 238, 884), radius=12, fill=(166, 204, 168), outline=wood, width=4)
    draw.rounded_rectangle((172, 510, 222, 828), radius=8, fill=(246, 236, 210), outline=wood, width=2)
    # Entry, bath, bedroom, balcony, desk/storage.
    draw.rounded_rectangle((110, 1042, 246, 1168), radius=12, fill=(82, 122, 122), outline=wood, width=4)
    draw.rounded_rectangle((108, 240, 292, 398), radius=12, fill=lavender, outline=wood, width=4)
    draw.rounded_rectangle((482, 236, 636, 416), radius=12, fill=aqua, outline=wood, width=4)
    draw.rounded_rectangle((480, 914, 638, 1110), radius=12, fill=(166, 205, 150), outline=wood, width=4)
    draw.rounded_rectangle((508, 512, 626, 724), radius=12, fill=(218, 182, 124), outline=wood, width=4)
    if variant == "2ldk":
        draw.rounded_rectangle((304, 226, 452, 390), radius=12, fill=(205, 190, 222), outline=wood, width=4)
    if variant == "lshape":
        draw.rounded_rectangle((330, 914, 452, 1110), radius=12, fill=(224, 184, 132), outline=wood, width=4)
    for x, y, c in [(565, 840, peach), (595, 610, lavender), (218, 950, peach), (612, 1070, mint)]:
        draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=c, outline=wood, width=3)


def make_normal_guides() -> dict[str, str]:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    variants = {
        "ldk": "home_map_v21_normal_1ldk_guide.png",
        "2ldk": "home_map_v21_normal_2ldk_guide.png",
        "lshape": "home_map_v21_normal_lshape_guide.png",
    }
    for key, name in variants.items():
        w, h = 768, 1365
        img = Image.new("RGBA", (w, h), (250, 244, 233, 255))
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((82, 154, 686, 1244), radius=42, fill=(0, 0, 0, 44))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        img.alpha_composite(shadow, (12, 20))
        d = ImageDraw.Draw(img)
        if key == "lshape":
            shell = [(96, 184), (666, 184), (666, 1010), (486, 1010), (486, 1222), (96, 1222)]
            d.polygon(shell, fill=(244, 228, 199), outline=(115, 88, 58))
            d.line(shell + [shell[0]], fill=(115, 88, 58), width=8, joint="curve")
            draw_floor(d, (126, 214, 636, 982), (232, 190, 126))
            draw_floor(d, (126, 982, 456, 1190), (230, 188, 126))
        else:
            draw_wall(d, (90, 170, 678, 1232))
            draw_floor(d, (124, 204, 644, 1196), (232, 190, 126))
        # Subtle same-level room outlines: no stairs, no raised platforms.
        for xy in [(108, 220, 312, 430), (462, 220, 650, 444), (100, 1018, 268, 1188), (462, 900, 648, 1134)]:
            d.rounded_rectangle(xy, radius=14, outline=(150, 114, 74), width=4)
        if key == "2ldk":
            d.rounded_rectangle((292, 220, 468, 420), radius=14, outline=(150, 114, 74), width=4)
        d.rounded_rectangle((136, 452, 630, 914), radius=28, outline=(129, 96, 60), width=5)
        draw_room_icon(d, key)
        img.convert("RGB").save(INPUT_DIR / name, quality=95)
    return {k: f"/assets/input/{v}" for k, v in variants.items()}


def prompt_for(key: str) -> tuple[str, str]:
    base = (
        "Reference roles:\n"
        "- Use the Aiko home style board only for finished art style: soft anime watercolor, warm wood floors, cream walls, mint sofa, peach/lavender accents, clean thin outlines, cozy Tokyo apartment details.\n"
        "- Use the normal layout guide only for same-level room adjacency and relative scale. Do not copy guide colors, flat diagram shapes, or schematic look.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME SPACE MAP for a mobile game. This is a normal home space map background with clickable areas, not an architectural fantasy and not a plain first-person room background. Use an elevated 2.5D cutaway camera, but keep the home normal, believable, compact, and easy to understand on a phone.\n\n"
        "Critical structure rules: single-floor apartment only. No second floor, no split level, no loft, no staircase, no stairwell, no platform, no railing, no stacked rooms, no exterior roof, no facade. All rooms and zones are on the same floor plane. Make it feel like a normal Japanese 1LDK/2LDK home seen from a gentle overhead angle.\n\n"
        "Clickable zones should be clear but natural: genkan entry, living area, dining table, kitchen counter, bedroom, bath/wash/laundry, balcony plant/laundry corner, study/desk or closet. The central living-dining-kitchen should be the main readable hub. Use open doorways, sliding doors, furniture, rugs, plants, shelves, and floor material changes for separation, not boxed maze walls.\n\n"
        "Avoid: weird house structure, dollhouse stacked floors, separated boxes, long corridor, large bedroom dominance, giant entry dominance, over-complicated walls, route lines, pins, labels, UI, text, A/B/C markers, blueprint, flat top-down floor plan, photorealism, plastic 3D render, watermark."
    )
    if key == "ldk":
        return "v21A 正常1LDK开放客餐厨", base + "\n\nVariant: normal 1LDK. One open LDK occupies the center and lower-middle: mint sofa, round table, small dining table, compact side kitchen. Bedroom is one quiet rear room with sliding doorway. Bath/wash/laundry sits as a compact side room. Entry is a small foreground nook; balcony is a small rear or side edge."
    if key == "2ldk":
        return "v21B 正常2LDK小家庭", base + "\n\nVariant: normal 2LDK. Keep a rectangular same-floor apartment with a large central LDK, one bedroom, one small study/closet room, compact bath/wash area, small genkan, and balcony. Make the rooms connected by short doorways around the central living area, not by a long corridor."
    return "v21C 正常L型公寓", base + "\n\nVariant: normal L-shaped apartment. Use a slightly L-shaped single-floor layout so it feels less boxy but still normal. The LDK is central; bedroom and bath are tucked naturally on the upper/side edges, balcony and desk nook are small side destinations. No fantasy architecture."


def append_board(guide_urls: dict[str, str]) -> list[dict[str, Any]]:
    canvas = req_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict[str, Any]] = []
    for i, key in enumerate(["ldk", "2ldk", "lshape"]):
        y = y0 + i * 760
        title, prompt = prompt_for(key)
        style_id, guide_id, prompt_id = sid("img"), sid("img"), sid("prompt")
        group_id, gen_id, out_id = sid("grp"), sid("gen"), sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": guide_id, "type": "image", "x": 396, "y": y + 92, "url": guide_urls[key], "name": "v21 normal layout guide", "role": "same-floor layout only"},
                {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 360, "h": 260, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 944, "h": 402, "items": [style_id, guide_id, prompt_id], "name": f"{title} 输入"},
                {
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
                },
                {"id": out_id, "type": "output", "x": 1604, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
            ]
        )
        conns.append({"id": sid("c"), "from": group_id, "to": gen_id})
        conns.append({"id": sid("c"), "from": gen_id, "to": out_id})
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
                    {"url": guide_urls[key], "name": "v21 normal layout guide", "role": "same-floor layout only"},
                ],
            }
        )
    logs = canvas.get("logs") or []
    logs.insert(0, {"id": sid("log"), "createdAt": now_ms(), "status": "done", "nodeType": "agent", "platform": "codex-v21", "prompt": "Append v21 normal same-floor home map candidates.", "outputs": [], "runMs": 0})
    payload = {
        "title": canvas.get("title") or "Aiko Home Space Map Iteration",
        "icon": canvas.get("icon") or "layers",
        "nodes": nodes,
        "connections": conns,
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": logs[:500],
        "settings": canvas.get("settings") or {},
        "client_id": "codex-home-map-v21",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    req_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)
    return groups


def create_task(plan: dict[str, Any], index: int) -> dict[str, Any]:
    start = now_ms()
    payload = {
        "prompt": plan["prompt"],
        "provider_id": PRIMARY_PROVIDER["id"],
        "model": PRIMARY_PROVIDER["model"],
        "size": SIZE,
        "quality": "auto",
        "n": 1,
        "reference_images": plan["reference_images"],
    }
    try:
        task = req_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
        task_id = task.get("task_id")
        if not task_id:
            raise RuntimeError(f"missing task_id: {task}")
        last = task
        deadline = time.time() + 1800
        while time.time() < deadline:
            time.sleep(3)
            last = req_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=60)
            status = str(last.get("status") or "").lower()
            if status in {"succeeded", "success", "done", "completed", "complete", "finished"}:
                images = (last.get("result") or {}).get("images") or []
                return {"ok": bool(images), "status": status, "task_id": task_id, "images": images, "error": "" if images else "completed without images", "raw": last, "run_ms": last.get("run_ms") or last.get("total_ms") or now_ms() - start, "created_at": start, "plan": plan, "index": index}
            if status in {"failed", "fail", "error", "canceled", "cancelled"}:
                return {"ok": False, "status": status, "task_id": task_id, "images": [], "error": last.get("error") or "task failed", "raw": last, "run_ms": last.get("run_ms") or last.get("total_ms") or now_ms() - start, "created_at": start, "plan": plan, "index": index}
        return {"ok": False, "status": "timeout", "task_id": task_id, "images": [], "error": "task timeout", "raw": last, "run_ms": now_ms() - start, "created_at": start, "plan": plan, "index": index}
    except Exception as exc:
        return {"ok": False, "status": "error", "task_id": "", "images": [], "error": str(exc), "raw": {}, "run_ms": now_ms() - start, "created_at": start, "plan": plan, "index": index}


def run_tasks(groups: list[dict[str, Any]], count: int, concurrency: int) -> list[dict[str, Any]]:
    jobs = [(g, i + 1) for g in groups for i in range(count)]
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(create_task, g, idx) for g, idx in jobs]
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results.append(r)
            print(f"[{'OK' if r.get('ok') else 'FAIL'}] 65535 {SIZE} {r.get('plan',{}).get('title')} #{r.get('index')} task={r.get('task_id') or '-'} error={str(r.get('error') or '')[:180]}", flush=True)
    return results


def append_results(results: list[dict[str, Any]]) -> None:
    canvas = req_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    by_id = {n.get("id"): n for n in nodes}
    logs = canvas.get("logs") or []
    success_by_gen: dict[str, bool] = {}
    for r in results:
        plan = r.get("plan") or {}
        gen = by_id.get(plan.get("generator_id"))
        out = by_id.get(plan.get("output_id"))
        items = []
        for url in r.get("images") or []:
            items.append(
                {
                    "url": url,
                    "kind": "image",
                    "source": "codex-v21",
                    "provider_id": PRIMARY_PROVIDER["id"],
                    "provider_name": PRIMARY_PROVIDER["name"],
                    "model": PRIMARY_PROVIDER["model"],
                    "task_id": r.get("task_id") or "",
                    "runMs": r.get("run_ms") or 0,
                    "createdAt": now_ms(),
                    "reviewStatus": "pending-normal-structure-review-v21",
                    "v21StructureVariant": plan.get("key") or "",
                    "size": SIZE,
                }
            )
        if out is not None and items:
            out.setdefault("images", []).extend(items)
        if gen is not None:
            if items:
                gen.setdefault("generatedOutputs", []).extend(items)
                gen["runStatus"] = "done"
                gen["runError"] = ""
                success_by_gen[gen.get("id")] = True
            elif not success_by_gen.get(gen.get("id")):
                gen["runStatus"] = "failed"
                gen["runError"] = str(r.get("error") or r.get("status") or "task failed")[:500]
        logs.insert(0, {"id": sid("log"), "createdAt": now_ms(), "status": "done" if r.get("ok") else "failed", "nodeType": "generator", "model": PRIMARY_PROVIDER["model"], "prompt": plan.get("prompt") or "", "outputs": [i["url"] for i in items], "error": "" if r.get("ok") else str(r.get("error") or r.get("status"))[:1000], "platform": PRIMARY_PROVIDER["name"], "runMs": r.get("run_ms") or 0, "task_id": r.get("task_id") or "", "request": {"provider_id": PRIMARY_PROVIDER["id"], "model": PRIMARY_PROVIDER["model"], "size": SIZE, "quality": "auto", "reference_count": 2, "v21_variant": plan.get("key") or ""}})
    payload = {"title": canvas.get("title") or "Aiko Home Space Map Iteration", "icon": canvas.get("icon") or "layers", "nodes": nodes, "connections": canvas.get("connections") or [], "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1}, "logs": logs[:500], "settings": canvas.get("settings") or {}, "client_id": "codex-home-map-v21", "base_updated_at": canvas.get("updated_at") or 0}
    req_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)


def load_image(url: str) -> Image.Image | None:
    try:
        if url.startswith("/assets/") or url.startswith("/output/"):
            path = BASE_DIR / url.lstrip("/").replace("/", os.sep)
            return Image.open(path).convert("RGB") if path.exists() else None
        with urllib.request.urlopen(url, timeout=90) as resp:
            return Image.open(BytesIO(resp.read())).convert("RGB")
    except Exception:
        return None


def contact_sheet(results: list[dict[str, Any]]) -> Path:
    items = [(r, url) for r in results if r.get("ok") for url in (r.get("images") or [])]
    cols, cell_w, cell_h, label_h = 3, 360, 640, 52
    rows = max(1, math.ceil(max(1, len(items)) / cols))
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + label_h)), (242, 238, 229))
    d = ImageDraw.Draw(sheet)
    for i, (r, url) in enumerate(items):
        x, y = (i % cols) * cell_w, (i // cols) * (cell_h + label_h)
        img = load_image(url)
        if img:
            img.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
            sheet.paste(img, (x + (cell_w - img.width) // 2, y + (cell_h - img.height) // 2))
        label = f"{r.get('plan',{}).get('title','v21')} | 65535 | {SIZE}"
        d.rectangle((x, y + cell_h, x + cell_w, y + cell_h + label_h), fill=(250, 247, 240))
        d.text((x + 10, y + cell_h + 10), label[:54], fill=(55, 48, 40))
    out = OUTPUT_DIR / "home_map_v21_normal_contact_sheet.jpg"
    sheet.save(out, quality=92)
    AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, AIKO_TMP_DIR / out.name)
    return out


def write_state(state: dict[str, Any]) -> Path:
    out = OUTPUT_DIR / "home_map_v21_normal_task_state.json"
    out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, AIKO_TMP_DIR / out.name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()
    state_path = OUTPUT_DIR / "home_map_v21_normal_task_state.json"
    backup = ""
    if args.run_only:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        groups = state["groups"]
    else:
        backup = str(backup_canvas())
        guides = make_normal_guides()
        groups = append_board(guides)
        state = {"canvas_id": CANVAS_ID, "canvas_url": CANVAS_URL, "backup": backup, "groups": groups, "runs": [], "contact_sheet": "", "created_at": now_ms()}
        write_state(state)
        print(f"prepared v21 normal canvas={CANVAS_ID} backup={backup}", flush=True)
    if args.prepare_only:
        return 0
    results = run_tasks(groups, args.count, args.concurrency)
    append_results(results)
    sheet = contact_sheet(results)
    state = {"canvas_id": CANVAS_ID, "canvas_url": CANVAS_URL, "backup": backup, "groups": groups, "runs": results, "contact_sheet": str(sheet), "aiko_tmp_contact_sheet": str(AIKO_TMP_DIR / sheet.name), "completed_at": now_ms()}
    write_state(state)
    print(json.dumps({"ok": True, "contact_sheet": str(sheet), "success": sum(1 for r in results if r.get("ok")), "total": len(results)}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
