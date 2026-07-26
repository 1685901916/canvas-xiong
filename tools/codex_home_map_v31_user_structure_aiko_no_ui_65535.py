#!/usr/bin/env python3
"""Generate Aiko home map candidates from the user's latest structure reference."""

from __future__ import annotations

import math
import shutil
import time
from pathlib import Path
from typing import Any

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


USER_REF_URL = "/assets/input/home_map_v31_user_structure_reference_with_ui_to_remove.png"
STRUCTURE_GUIDE_URL = "/assets/input/home_map_v31_structure_guide_from_user_ref.png"
USER_REF_SOURCE = Path(r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-04372d5b-c307-4678-bd8d-38db5e89f921.png")
USER_REF_PATH = base.INPUT_DIR / "home_map_v31_user_structure_reference_with_ui_to_remove.png"
GUIDE_PATH = base.INPUT_DIR / "home_map_v31_structure_guide_from_user_ref.png"

runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v31_user_structure_aiko_no_ui_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v31_user_structure_aiko_no_ui_contact_sheet.jpg"


def ensure_reference_files() -> None:
    if USER_REF_SOURCE.exists():
        USER_REF_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(USER_REF_SOURCE, USER_REF_PATH)
    if not USER_REF_PATH.exists():
        raise FileNotFoundError(f"missing user reference image: {USER_REF_PATH}")
    if not GUIDE_PATH.exists():
        raise FileNotFoundError(f"missing no-UI structure guide: {GUIDE_PATH}")


def prompt_for(_: str) -> tuple[str, str]:
    prompt = (
        "Reference roles:\n"
        "- The Aiko home style board controls only the final project art style: soft anime watercolor, cozy Tokyo mobile-game home feeling, warm wood, cream walls, mint/lavender/peach accents, clean thin linework, gentle afternoon domestic light.\n"
        "- The user's reference image controls only the spatial structure and room adjacency. Preserve the logic: bathroom upper-left, bedroom upper-right, wardrobe/closet in the upper center, kitchen and dining lower-left, living room lower-right, genkan entry near the bottom, balcony/laundry corner bottom-right. The glowing white circles in the user reference are UI markers that must be removed, not design elements.\n"
        "- The simplified structure guide controls the same no-UI room partition logic. Use it to avoid copying any glowing circles, pins, labels, or hotspot marks. Do not copy its flat schematic style.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for a mobile game. This is a map image used for tapping home locations, not a dialogue background and not a real-estate floor plan.\n\n"
        "Core composition: one continuous, normal, tidy single-floor apartment cutaway filling the phone frame. Use an elevated 2.5D bird's-eye/isometric camera like the user's reference. Keep the room order clear and connected, with believable interior walls and open doorways. The map should feel like a warm Japanese apartment hub: bedroom, bathroom, wardrobe/closet, kitchen, dining table, living sofa/TV, genkan cabinet, balcony with plants/laundry.\n\n"
        "Clickable readability: each location should be a large natural touch zone suggested by furniture, rugs, floor material changes, plants, lighting, and room boundaries. Keep the zones readable at phone size, but do not draw visible UI.\n\n"
        "Style: match Aiko project style, not the reference's polished generic isometric look. Softer anime watercolor, lighter pastel palette, hand-painted warmth, clean but organic lines, domestic details, cozy Tokyo romance-game mood, no harsh 3D plastic.\n\n"
        "Hard excludes: no glowing rings, no white circles, no hotspot circles, no UI markers, no target icons, no pins, no route lines, no arrows, no labels, no text, no A/B/C markers, no numbers, no characters, no roof, no exterior facade, no sky as main subject, no two-floor structure, no stairs, no loft, no strange split level, no chaotic angled shards, no disconnected rooms, no maze corridors, no blueprint, no photorealism, no plastic 3D render, no watermark."
    )
    return "v31 用户结构转 Aiko 家庭点击子地图-无UI", prompt


def backup_canvas() -> str:
    base.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = base.BACKUP_DIR / f"{base.CANVAS_ID}.home-map-v31-user-structure-no-ui-before-{time.strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(base.CANVAS_PATH, dst)
    return str(dst)


def append_board() -> list[dict[str, Any]]:
    ensure_reference_files()
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y = math.ceil(max_bottom / 40) * 40 + 160
    title, prompt = prompt_for("user_structure")
    style_id, user_ref_id, guide_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("img"), base.sid("prompt")
    group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")

    nodes.extend(
        [
            {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
            {"id": user_ref_id, "type": "image", "x": 386, "y": y + 92, "url": USER_REF_URL, "name": "user structure reference, UI circles to remove", "role": "structure reference only"},
            {"id": guide_id, "type": "image", "x": 616, "y": y + 92, "url": STRUCTURE_GUIDE_URL, "name": "no-UI structure guide", "role": "room partition guide"},
            {"id": prompt_id, "type": "prompt", "x": 846, "y": y + 92, "text": prompt, "w": 430, "h": 430, "name": title},
            {"id": group_id, "type": "group", "x": 120, "y": y, "w": 1195, "h": 560, "items": [style_id, user_ref_id, guide_id, prompt_id], "name": f"{title} 输入"},
            {
                "id": gen_id,
                "type": "generator",
                "x": 1395,
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
                "inputs": [f"{group_id}:{style_id}", f"{group_id}:{user_ref_id}", f"{group_id}:{guide_id}", f"{group_id}:prompts"],
                "count": 4,
                "apiDefaultsVersion": 2,
                "name": f"{title} / 65535",
                "w": 380,
                "h": 0,
                "generatedOutputs": [],
            },
            {"id": out_id, "type": "output", "x": 1855, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
        ]
    )
    conns.append({"id": base.sid("c"), "from": group_id, "to": gen_id})
    conns.append({"id": base.sid("c"), "from": gen_id, "to": out_id})
    logs = canvas.get("logs") or []
    logs.insert(
        0,
        {
            "id": base.sid("log"),
            "createdAt": base.now_ms(),
            "status": "done",
            "nodeType": "agent",
            "platform": "codex-v31",
            "prompt": "Append v31 user-structure Aiko home sub-map. Goal: transform latest reference into Aiko project style and remove all UI markers.",
            "outputs": [],
            "runMs": 0,
        },
    )
    payload = {
        "title": canvas.get("title") or "Aiko Home Space Map Iteration",
        "icon": canvas.get("icon") or "layers",
        "nodes": nodes,
        "connections": conns,
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": logs[:500],
        "settings": canvas.get("settings") or {},
        "client_id": "codex-home-map-v31",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return [
        {
            "key": "user_structure_aiko_no_ui",
            "title": title,
            "prompt": prompt,
            "group_id": group_id,
            "generator_id": gen_id,
            "output_id": out_id,
            "reference_images": [
                {"url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"url": USER_REF_URL, "name": "user structure reference", "role": "structure reference only, remove UI circles"},
                {"url": STRUCTURE_GUIDE_URL, "name": "no-UI structure guide", "role": "room partition guide"},
            ],
        }
    ]


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
            items.append(
                {
                    "url": url,
                    "kind": "image",
                    "source": "codex-v31",
                    "provider_id": base.PRIMARY_PROVIDER["id"],
                    "provider_name": base.PRIMARY_PROVIDER["name"],
                    "model": base.PRIMARY_PROVIDER["model"],
                    "task_id": r.get("task_id") or "",
                    "runMs": r.get("run_ms") or 0,
                    "createdAt": base.now_ms(),
                    "reviewStatus": "pending-user-structure-aiko-no-ui-review-v31",
                    "v31Variant": plan.get("key") or "",
                    "size": base.SIZE,
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
        logs.insert(
            0,
            {
                "id": base.sid("log"),
                "createdAt": base.now_ms(),
                "status": "done" if r.get("ok") else "failed",
                "nodeType": "generator",
                "model": base.PRIMARY_PROVIDER["model"],
                "prompt": plan.get("prompt") or "",
                "outputs": [i["url"] for i in items],
                "error": "" if r.get("ok") else str(r.get("error") or r.get("status"))[:1000],
                "platform": base.PRIMARY_PROVIDER["name"],
                "runMs": r.get("run_ms") or 0,
                "task_id": r.get("task_id") or "",
                "request": {
                    "provider_id": base.PRIMARY_PROVIDER["id"],
                    "model": base.PRIMARY_PROVIDER["model"],
                    "size": base.SIZE,
                    "quality": "auto",
                    "reference_count": 3,
                    "v31_variant": plan.get("key") or "",
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
        "client_id": "codex-home-map-v31",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)


runner.append_board = append_board
runner.prompt_for = prompt_for
runner.backup_canvas = backup_canvas
runner.append_results = append_results


if __name__ == "__main__":
    raise SystemExit(runner.main())
