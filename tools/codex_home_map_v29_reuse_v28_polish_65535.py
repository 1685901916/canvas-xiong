#!/usr/bin/env python3
"""Reuse the v28 workflow and append polished rectangular candidates."""

from __future__ import annotations

import concurrent.futures
import json
import math
import shutil
import time
from typing import Any

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


STATE_PATH = base.OUTPUT_DIR / "home_map_v29_rect_polish_task_state.json"
SHEET_PATH = base.OUTPUT_DIR / "home_map_v29_rect_polish_contact_sheet.jpg"
V28_STATE_PATH = base.OUTPUT_DIR / "home_map_v28_strict_rect_submap_task_state.json"
BEST_V28_REF = "/assets/output/online_3a23f57e8b.png"
GUIDE_URL = "/assets/input/home_map_v28_strict_rect_apartment_guide.png"


def polish_prompt() -> str:
    return (
        "Reference roles:\n"
        "- The Aiko home style board controls final rendering only: soft anime watercolor, warm cream wood, mint/lavender/peach accents, clean thin lines, cozy Tokyo mobile-game readability.\n"
        "- The strict rectangle guide controls the non-negotiable structure: one simple vertical rectangular apartment footprint, straight walls, no irregular outline.\n"
        "- The v28 successful reference controls only the approved normal-home direction: clear rectangular home sub-map, no weird structure. Improve it; do not copy every object.\n\n"
        "Create a polished vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for a mobile game. This is a tap-to-jump home navigation map, not a dialogue background.\n\n"
        "Non-negotiable structure: ONE SIMPLE RECTANGULAR APARTMENT. Keep the outside footprint a clean vertical rectangle with straight left/right/top/bottom edges. No protruding rooms, no jagged outline, no rounded capsule rooms, no puzzle-piece contour, no separated island modules, no diagonal exterior edge.\n\n"
        "Layout: top balcony/window strip, one bedroom, one desk or closet nook, large central living sofa hub, compact kitchen/dining, compact bath/wash/laundry, bottom entry/genkan. Exactly one bedroom and one bath/wash room. Use straight interior partitions with a few door openings. Keep room sizes believable and not too many.\n\n"
        "Clickable gameplay readability: each location is a large natural tap zone with furniture/rugs marking it. Leave clean empty floor/rug space in each zone for invisible hotspots. The living sofa hub should be the visual center. Kitchen, bath, entry, desk, bedroom, and balcony should be obvious at phone size without text.\n\n"
        "Polish: reduce heavy outer frame, keep walls light and neat, make the image feel like Aiko Tokyo map art rather than a real-estate plan. Warm daylight, soft shadows, tidy domestic details, enough charm but not clutter.\n\n"
        "Hard excludes: weird structure, irregular outline, protruding side rooms, rounded room capsules, organic shell, maze walls, long corridor, duplicate bedroom, duplicate bath, random extra rooms, roof, eaves, facade, exterior shell, second floor, stairs, split-level, loft, railing, sky/street background, blueprint, flat schematic, labels, text, map pins, route arrows, colored hotspot outlines, A/B/C markers, characters, photorealism, plastic 3D render, watermark."
    )


def update_v28_workflow() -> dict[str, Any]:
    v28_state = json.loads(V28_STATE_PATH.read_text(encoding="utf-8"))
    plan = v28_state["groups"][0]
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    by_id = {node.get("id"): node for node in nodes}
    group = by_id[plan["group_id"]]
    gen = by_id[plan["generator_id"]]
    prompt = polish_prompt()

    prompt_id = next(
        (item_id for item_id in group.get("items") or [] if by_id.get(item_id, {}).get("type") == "prompt"),
        "",
    )
    if prompt_id and prompt_id in by_id:
        by_id[prompt_id]["text"] = prompt
        by_id[prompt_id]["name"] = "v29 正常矩形公寓最终打磨"
        by_id[prompt_id]["h"] = 440

    ref_name = "v29 positive rectangular reference"
    existing_ref_id = next((node.get("id") for node in nodes if node.get("name") == ref_name and node.get("url") == BEST_V28_REF), "")
    if not existing_ref_id:
        existing_ref_id = base.sid("img")
        nodes.append(
            {
                "id": existing_ref_id,
                "type": "image",
                "x": float(group.get("x") or 120) + 155,
                "y": float(group.get("y") or 0) + 390,
                "url": BEST_V28_REF,
                "name": ref_name,
                "role": "approved normal rectangular structure reference",
            }
        )
    items = list(group.get("items") or [])
    if existing_ref_id not in items:
        items.append(existing_ref_id)
    group["items"] = items
    group["h"] = max(float(group.get("h") or 540), 735)
    group["name"] = "v29 正常矩形公寓最终打磨 输入"

    gen["name"] = "v29 正常矩形公寓最终打磨 / 65535"
    gen["count"] = 3
    inputs = list(gen.get("inputs") or [])
    ref_input = f"{plan['group_id']}:{existing_ref_id}"
    if ref_input not in inputs:
        insert_at = max(0, len(inputs) - 1)
        inputs.insert(insert_at, ref_input)
    gen["inputs"] = inputs
    gen["runStatus"] = "idle"
    gen["runError"] = ""

    logs = canvas.get("logs") or []
    logs.insert(
        0,
        {
            "id": base.sid("log"),
            "createdAt": base.now_ms(),
            "status": "done",
            "nodeType": "agent",
            "platform": "codex-v29",
            "prompt": "Reuse v28 workflow. Add approved rectangular reference and polish prompt; append results to existing output.",
            "outputs": [],
            "runMs": 0,
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
        "client_id": "codex-home-map-v29",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)

    return {
        "key": "rect_polish",
        "title": "v29 正常矩形公寓最终打磨",
        "prompt": prompt,
        "group_id": plan["group_id"],
        "generator_id": plan["generator_id"],
        "output_id": plan["output_id"],
        "reference_images": [
            {"url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
            {"url": GUIDE_URL, "name": "strict rectangular apartment guide", "role": "structure guide only"},
            {"url": BEST_V28_REF, "name": "v28 approved rectangular reference", "role": "approved normal structure reference"},
        ],
    }


def create_task(plan: dict[str, Any], index: int) -> dict[str, Any]:
    start = base.now_ms()
    payload = {
        "prompt": plan["prompt"],
        "provider_id": base.PRIMARY_PROVIDER["id"],
        "model": base.PRIMARY_PROVIDER["model"],
        "size": base.SIZE,
        "quality": "auto",
        "n": 1,
        "reference_images": plan["reference_images"],
    }
    try:
        task = base.req_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
        task_id = task.get("task_id")
        if not task_id:
            raise RuntimeError(f"missing task_id: {task}")
        last = task
        deadline = time.time() + 1800
        while time.time() < deadline:
            time.sleep(3)
            last = base.req_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=60)
            status = str(last.get("status") or "").lower()
            if status in {"succeeded", "success", "done", "completed", "complete", "finished"}:
                images = (last.get("result") or {}).get("images") or []
                return {"ok": bool(images), "status": status, "task_id": task_id, "images": images, "error": "" if images else "completed without images", "raw": last, "run_ms": last.get("run_ms") or last.get("total_ms") or base.now_ms() - start, "created_at": start, "plan": plan, "index": index}
            if status in {"failed", "fail", "error", "canceled", "cancelled"}:
                return {"ok": False, "status": status, "task_id": task_id, "images": [], "error": last.get("error") or "task failed", "raw": last, "run_ms": last.get("run_ms") or last.get("total_ms") or base.now_ms() - start, "created_at": start, "plan": plan, "index": index}
        return {"ok": False, "status": "timeout", "task_id": task_id, "images": [], "error": "task timeout", "raw": last, "run_ms": base.now_ms() - start, "created_at": start, "plan": plan, "index": index}
    except Exception as exc:
        return {"ok": False, "status": "error", "task_id": "", "images": [], "error": str(exc), "raw": {}, "run_ms": base.now_ms() - start, "created_at": start, "plan": plan, "index": index}


def run(plan: dict[str, Any], count: int = 3, concurrency: int = 2) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(create_task, plan, index + 1) for index in range(count)]
        for fut in concurrent.futures.as_completed(futs):
            result = fut.result()
            results.append(result)
            print(
                f"[{'OK' if result.get('ok') else 'FAIL'}] {plan['title']} #{result.get('index')} "
                f"task={result.get('task_id') or '-'} error={str(result.get('error') or '')[:180]}",
                flush=True,
            )
    return results


def make_contact_sheet(output_id: str) -> str:
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    by_id = {node.get("id"): node for node in canvas.get("nodes") or []}
    out = by_id.get(output_id, {})
    urls: list[str] = []
    for item in out.get("images") or []:
        url = item.get("url") if isinstance(item, dict) else item
        if isinstance(url, str) and url.startswith("/assets/output/"):
            urls.append(url)

    cols, cw, ch, lh = 2, 430, 764, 54
    rows = max(1, math.ceil(max(1, len(urls)) / cols))
    sheet = Image.new("RGB", (cols * cw, rows * (ch + lh)), (242, 238, 229))
    draw = ImageDraw.Draw(sheet)
    for i, url in enumerate(urls):
        x = (i % cols) * cw
        y = (i // cols) * (ch + lh)
        img = base.load_image(url)
        if img:
            img.thumbnail((cw, ch), Image.Resampling.LANCZOS)
            sheet.paste(img, (x + (cw - img.width) // 2, y + (ch - img.height) // 2))
        label = "v28/v29 strict rectangular home sub-map"
        draw.rectangle((x, y + ch, x + cw, y + ch + lh), fill=(250, 247, 240))
        draw.text((x + 10, y + ch + 8), label, fill=(55, 48, 40))

    SHEET_PATH.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(SHEET_PATH, quality=92)
    base.AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SHEET_PATH, base.AIKO_TMP_DIR / SHEET_PATH.name)
    return str(SHEET_PATH)


def main() -> int:
    plan = update_v28_workflow()
    results = run(plan, count=3, concurrency=2)
    runner.append_results(results)
    sheet = make_contact_sheet(plan["output_id"])
    state = {
        "canvas_id": base.CANVAS_ID,
        "canvas_url": base.CANVAS_URL,
        "groups": [plan],
        "runs": results,
        "contact_sheet": sheet,
        "aiko_tmp_contact_sheet": str(base.AIKO_TMP_DIR / SHEET_PATH.name),
        "completed_at": base.now_ms(),
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(STATE_PATH, base.AIKO_TMP_DIR / STATE_PATH.name)
    print(json.dumps({"ok": True, "contact_sheet": sheet, "success": sum(1 for r in results if r.get("ok")), "total": len(results)}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
