#!/usr/bin/env python3
"""Refine v21 normal home candidates into more mobile-game-like maps."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base


REFS = {
    "cozy_ldk": "/assets/output/online_aaa4a65c12.png",
    "soft_lshape": "/assets/output/online_fa0fae3039.png",
}
STATE_PATH = base.OUTPUT_DIR / "home_map_v22_from_v21_task_state.json"
SHEET_PATH = base.OUTPUT_DIR / "home_map_v22_from_v21_contact_sheet.jpg"


def prompt_for(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- Use the Aiko home style board for color, lighting, softness, cozy Tokyo furniture details, and watercolor anime rendering.\n"
        "- Use the selected v21 normal home candidate only for normal same-floor structure and room scale. Keep it normal and believable, but improve the composition for a mobile game home map.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME SPACE MAP. It should feel like a phone game clickable home hub background, not a weird fantasy dollhouse and not a dry real-estate floor plan. Keep a normal single-floor Japanese apartment, shown in gentle elevated 2.5D cutaway. All zones stay on one floor.\n\n"
        "Improve over the reference: make the central living-dining-kitchen more charming and intentionally composed, with clear natural tap areas around sofa/table, dining, compact kitchen, bedroom, bath/wash/laundry, balcony plants/laundry, entry, and desk/closet. Use rugs, furniture islands, lighting, plants, doorways, and small decor clusters to make each zone readable without labels.\n\n"
        "Hard rules: no second floor, no stair, no split-level, no loft, no railing, no stacked rooms, no platform, no strange outer shell, no facade, no roof. Avoid long corridor and over-separated room boxes. Avoid text, labels, UI, pins, route lines, icons, A/B/C markers, blueprint, photorealism, plastic 3D render, watermark."
    )
    if key == "cozy_ldk":
        return (
            "v22A 正常家地图-客餐厨主中心",
            common
            + "\n\nVariant: keep the normal 1LDK feeling. The LDK should be the visual center and feel playable: sofa + round table + dining + side kitchen form one warm central hub. Bedroom and bath are secondary side/rear rooms, not dominant. Entry and balcony are compact edge zones.",
        )
    return (
        "v22B 正常家地图-L型温馨版",
        common
        + "\n\nVariant: keep the normal L-shaped apartment feeling but reduce floor-plan dryness. Make the L shape feel like a designed game hub with a soft diagonal visual flow from entry to living/dining/kitchen to balcony. Rooms should be readable but not boxed like a real estate plan.",
    )


def backup_canvas() -> str:
    base.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = base.BACKUP_DIR / f"{base.CANVAS_ID}.home-map-v22-from-v21-before-{time.strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(base.CANVAS_PATH, dst)
    return str(dst)


def append_board() -> list[dict[str, Any]]:
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict[str, Any]] = []
    for i, key in enumerate(["cozy_ldk", "soft_lshape"]):
        y = y0 + i * 760
        title, prompt = prompt_for(key)
        style_id, ref_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
        group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": ref_id, "type": "image", "x": 396, "y": y + 92, "url": REFS[key], "name": "v21 normal structure reference", "role": "normal structure reference"},
                {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 360, "h": 260, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 944, "h": 402, "items": [style_id, ref_id, prompt_id], "name": f"{title} 输入"},
                {
                    "id": gen_id,
                    "type": "generator",
                    "x": 1144,
                    "y": y + 40,
                    "apiProvider": base.PRIMARY_PROVIDER["id"],
                    "model": base.PRIMARY_PROVIDER["model"],
                    "ratio": "story",
                    "resolution": "2k",
                    "quality": "auto",
                    "customRatio": "",
                    "customSize": "",
                    "customRatioWidth": "",
                    "customRatioHeight": "",
                    "customWidth": "",
                    "customHeight": "",
                    "inputs": [f"{group_id}:{style_id}", f"{group_id}:{ref_id}", f"{group_id}:prompts"],
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
        conns.append({"id": base.sid("c"), "from": group_id, "to": gen_id})
        conns.append({"id": base.sid("c"), "from": gen_id, "to": out_id})
        groups.append(
            {
                "key": key,
                "title": title,
                "prompt": prompt,
                "group_id": group_id,
                "generator_id": gen_id,
                "output_id": out_id,
                "reference_images": [
                    {"url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                    {"url": REFS[key], "name": "v21 normal structure reference", "role": "normal structure reference"},
                ],
            }
        )
    logs = canvas.get("logs") or []
    logs.insert(0, {"id": base.sid("log"), "createdAt": base.now_ms(), "status": "done", "nodeType": "agent", "platform": "codex-v22", "prompt": "Append v22 normal home map refinements from v21 references.", "outputs": [], "runMs": 0})
    payload = {"title": canvas.get("title") or "Aiko Home Space Map Iteration", "icon": canvas.get("icon") or "layers", "nodes": nodes, "connections": conns, "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1}, "logs": logs[:500], "settings": canvas.get("settings") or {}, "client_id": "codex-home-map-v22", "base_updated_at": canvas.get("updated_at") or 0}
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return groups


def create_task(plan: dict[str, Any], index: int) -> dict[str, Any]:
    start = base.now_ms()
    payload = {"prompt": plan["prompt"], "provider_id": base.PRIMARY_PROVIDER["id"], "model": base.PRIMARY_PROVIDER["model"], "size": base.SIZE, "quality": "auto", "n": 1, "reference_images": plan["reference_images"]}
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


def run(groups: list[dict[str, Any]], count: int, concurrency: int) -> list[dict[str, Any]]:
    jobs = [(g, i + 1) for g in groups for i in range(count)]
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(create_task, g, i) for g, i in jobs]
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results.append(r)
            print(f"[{'OK' if r.get('ok') else 'FAIL'}] 65535 {base.SIZE} {r.get('plan',{}).get('title')} #{r.get('index')} task={r.get('task_id') or '-'} error={str(r.get('error') or '')[:160]}", flush=True)
    return results


def append_results(results: list[dict[str, Any]]) -> None:
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
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
            items.append({"url": url, "kind": "image", "source": "codex-v22", "provider_id": base.PRIMARY_PROVIDER["id"], "provider_name": base.PRIMARY_PROVIDER["name"], "model": base.PRIMARY_PROVIDER["model"], "task_id": r.get("task_id") or "", "runMs": r.get("run_ms") or 0, "createdAt": base.now_ms(), "reviewStatus": "pending-game-map-review-v22", "v22Variant": plan.get("key") or "", "size": base.SIZE})
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
        logs.insert(0, {"id": base.sid("log"), "createdAt": base.now_ms(), "status": "done" if r.get("ok") else "failed", "nodeType": "generator", "model": base.PRIMARY_PROVIDER["model"], "prompt": plan.get("prompt") or "", "outputs": [i["url"] for i in items], "error": "" if r.get("ok") else str(r.get("error") or r.get("status"))[:1000], "platform": base.PRIMARY_PROVIDER["name"], "runMs": r.get("run_ms") or 0, "task_id": r.get("task_id") or "", "request": {"provider_id": base.PRIMARY_PROVIDER["id"], "model": base.PRIMARY_PROVIDER["model"], "size": base.SIZE, "quality": "auto", "reference_count": 2, "v22_variant": plan.get("key") or ""}})
    payload = {"title": canvas.get("title") or "Aiko Home Space Map Iteration", "icon": canvas.get("icon") or "layers", "nodes": nodes, "connections": canvas.get("connections") or [], "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1}, "logs": logs[:500], "settings": canvas.get("settings") or {}, "client_id": "codex-home-map-v22", "base_updated_at": canvas.get("updated_at") or 0}
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)


def contact(results: list[dict[str, Any]]) -> str:
    items = [(r, url) for r in results if r.get("ok") for url in (r.get("images") or [])]
    cols, cw, ch, lh = 2, 430, 764, 50
    rows = max(1, math.ceil(max(1, len(items)) / cols))
    sheet = Image.new("RGB", (cols * cw, rows * (ch + lh)), (242, 238, 229))
    d = ImageDraw.Draw(sheet)
    for i, (r, url) in enumerate(items):
        x, y = (i % cols) * cw, (i // cols) * (ch + lh)
        img = base.load_image(url)
        if img:
            img.thumbnail((cw, ch), Image.Resampling.LANCZOS)
            sheet.paste(img, (x + (cw - img.width) // 2, y + (ch - img.height) // 2))
        label = f"{r.get('plan',{}).get('title','v22')} | 65535"
        d.rectangle((x, y + ch, x + cw, y + ch + lh), fill=(250, 247, 240))
        d.text((x + 10, y + ch + 10), label[:56], fill=(55, 48, 40))
    sheet.save(SHEET_PATH, quality=92)
    base.AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SHEET_PATH, base.AIKO_TMP_DIR / SHEET_PATH.name)
    return str(SHEET_PATH)


def write_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    base.AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(STATE_PATH, base.AIKO_TMP_DIR / STATE_PATH.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    backup = ""
    if args.run_only:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        groups = state["groups"]
    else:
        backup = backup_canvas()
        groups = append_board()
        write_state({"canvas_id": base.CANVAS_ID, "canvas_url": base.CANVAS_URL, "backup": backup, "groups": groups, "runs": [], "created_at": base.now_ms()})
        print(f"prepared v22 canvas={base.CANVAS_ID} backup={backup}", flush=True)
    if args.prepare_only:
        return 0
    results = run(groups, args.count, args.concurrency)
    append_results(results)
    sheet = contact(results)
    write_state({"canvas_id": base.CANVAS_ID, "canvas_url": base.CANVAS_URL, "backup": backup, "groups": groups, "runs": results, "contact_sheet": sheet, "aiko_tmp_contact_sheet": str(base.AIKO_TMP_DIR / SHEET_PATH.name), "completed_at": base.now_ms()})
    print(json.dumps({"ok": True, "contact_sheet": sheet, "success": sum(1 for r in results if r.get("ok")), "total": len(results)}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
