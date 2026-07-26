#!/usr/bin/env python3
"""Generate cleaner normal-home v27 candidates from accepted v26 directions."""

from __future__ import annotations

import math
from typing import Any

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v27_normalized_submap_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v27_normalized_submap_contact_sheet.jpg"

REFS = {
    "clean_1ldk": "/assets/output/online_8a7af0c36e.png",
    "soft_hub": "/assets/output/online_fd0957c448.png",
}


def prompt_for(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- The Aiko home style board controls only the final art family: soft anime watercolor, clean warm wood, cream walls, mint green sofa, lavender and peach accents, phone-size readability.\n"
        "- The v26 positive reference controls only the successful direction: no roof, no exterior shell, elevated mobile-game clickable home map, clear home destinations. Improve the structure; do not copy the exact room placement.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for a mobile game. This is a tap-to-jump home navigation map, not a dialogue background and not a real estate blueprint.\n\n"
        "Structure target: a normal same-floor Tokyo apartment. Keep one coherent apartment board with believable room adjacency. Use a clean rectangular or very gentle L-shaped plan. Avoid jagged puzzle-piece contours, separated island rooms, maze-like walls, oversized exterior border, or fantasy dollhouse structure.\n\n"
        "Home destinations should be few, clear, and useful for gameplay: entry/genkan, central living sofa zone, dining table, compact kitchen counter, one bedroom, desk/PC or closet/storage nook, bath/wash/laundry utility room, balcony/window plants/laundry corner. Use furniture, rugs, floor materials, door openings, curtains, shelves, and plants as natural clickable landmarks. Leave clean empty floor/rug areas for invisible tap hotspots.\n\n"
        "Art and camera: shallow elevated 2.5D / bird's-eye navigation view, soft watercolor anime mobile-map rendering, normal household scale, clear readable zones, cozy but not cluttered. Walls should be light separators, not thick roof/exterior framing.\n\n"
        "Hard excludes: roof, roof tiles, attic, eaves, facade, exterior house silhouette, outer building shell, sky/street scene as the main subject, second floor, stairs, stairwell, railing, split-level, loft, platform, heavy beams, repeated bedrooms, duplicate bath rooms, random extra rooms, long corridor, tiny unusable rooms, labels, text, map pins, route arrows, colored hotspot outlines, A/B/C markers, characters, photorealism, plastic 3D render, watermark."
    )
    if key == "clean_1ldk":
        return (
            "v27A 正常1LDK手机点击子地图",
            common
            + "\n\nVariant direction: clean normal 1LDK. Central living sofa and round table are the main hub. Kitchen/dining connect naturally to the lower or side area. One bedroom and one desk/closet nook sit near the upper area. Bath/laundry, entry, and balcony are compact edge zones. This should be the most normal and usable game home map.",
        )
    return (
        "v27B 正常家庭Hub轻L型",
        common
        + "\n\nVariant direction: slightly softer L-shaped same-floor home hub. Keep the central living zone readable, with bedroom, kitchen/dining, bath/laundry, entry, and balcony arranged around it. The plan may feel organic, but must still look like a normal apartment, not a strange structure.",
    )


def append_board() -> list[dict[str, Any]]:
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict[str, Any]] = []

    for i, key in enumerate(["clean_1ldk", "soft_hub"]):
        y = y0 + i * 760
        title, prompt = prompt_for(key)
        style_id, ref_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
        group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": ref_id, "type": "image", "x": 396, "y": y + 92, "url": REFS[key], "name": "v26 positive home sub-map reference", "role": "positive structure direction only"},
                {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 410, "h": 390, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 990, "h": 520, "items": [style_id, ref_id, prompt_id], "name": f"{title} 输入"},
                {
                    "id": gen_id,
                    "type": "generator",
                    "x": 1190,
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
                {"id": out_id, "type": "output", "x": 1650, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
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
                    {"url": REFS[key], "name": "v26 positive home sub-map reference", "role": "positive structure direction only"},
                ],
            }
        )

    logs = canvas.get("logs") or []
    logs.insert(
        0,
        {
            "id": base.sid("log"),
            "createdAt": base.now_ms(),
            "status": "done",
            "nodeType": "agent",
            "platform": "codex-v27",
            "prompt": "Append v27 normalized no-roof home sub-map lanes from best v26 positive references.",
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
        "client_id": "codex-home-map-v27",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return groups


runner.append_board = append_board
runner.prompt_for = prompt_for


if __name__ == "__main__":
    raise SystemExit(runner.main())
