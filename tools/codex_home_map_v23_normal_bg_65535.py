#!/usr/bin/env python3
"""v23 normal home background-map refinements using the best v22 structures."""

from __future__ import annotations

import math

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


runner.REFS = {
    "open_ldk": "/assets/output/online_9838607ec5.png",
    "low_cutaway": "/assets/output/online_7439e63bcb.png",
    "normal_hub": "/assets/output/online_9838607ec5.png",
}
runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v23_normal_bg_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v23_normal_bg_contact_sheet.jpg"


def prompt_for(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- Use the Aiko home style board for the Tokyo project art family: soft anime watercolor, thin warm linework, pastel cream wood, mint green, soft coral and lavender accents, cozy daylight, phone-size readable details.\n"
        "- Use the selected v22 image only as a sanity reference for normal single-floor room scale and believable apartment furniture. Do not copy its thick outer walls, real-estate floor-plan feeling, or dollhouse enclosure.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME BACKGROUND MAP for a mobile game. This is a normal lived-in Japanese apartment shown as an elevated 2.5D interior background, not a sub-map, not a blueprint, not a house exterior, and not a fantasy cutaway. The player should feel they are looking at one coherent home space where furniture clusters naturally become tap areas.\n\n"
        "Composition rules: keep everything on one single floor. Use a continuous warm wood floor and soft partial walls/doorways only where needed. Prefer an open connected living-dining-kitchen center, with bedroom, compact kitchen, bath/wash/laundry, genkan entry, balcony plants/laundry, desk/closet and small storage/hobby corners arranged around it. Make zones readable through rugs, lighting, furniture islands, plants, shelves, door openings and floor material changes, without labels or UI pins.\n\n"
        "Make it feel like a polished game background: charming, calm, normal, usable, with clear foreground/midground/background layering and enough empty floor for mobile UI and character overlays. Avoid dry apartment listing top-down view.\n\n"
        "Hard excludes: no second floor, no stairs, no split-level, no loft, no platform, no railing, no stacked rooms, no thick grey outer shell, no roof, no facade, no sky, no floating rooms, no long corridor maze, no blueprint, no text, no labels, no map pins, no route arrows, no A/B/C markers, no characters, no photorealism, no plastic 3D render, no watermark."
    )
    if key == "open_ldk":
        return (
            "v23A 正常家背景地图-开放1LDK",
            common
            + "\n\nVariant direction: a very normal open 1LDK. The living sofa, low table, dining table and compact kitchen form one continuous warm center. Bedroom is a soft side niche behind a partial wall, not a separate boxed cell. Bathroom and genkan stay compact at the lower edge. Balcony is a cozy window-side extension with plants and laundry.",
        )
    if key == "low_cutaway":
        return (
            "v23B 正常家背景地图-低切面温馨版",
            common
            + "\n\nVariant direction: use a lower, softer 2.5D camera than a floor plan. Front wall is removed, side walls are subtle and low, furniture defines the map more than architecture. Keep the apartment believable and normal, with no dramatic dollhouse cross-section.",
        )
    return (
        "v23C 正常家背景地图-多地点但不复杂",
        common
        + "\n\nVariant direction: include a few more usable home spots while staying normal: sofa/tv area, dining/kitchen, bed corner, desk/work corner, bath/laundry, entry shoe area, balcony plant area and closet/storage. Arrange them as one coherent compact apartment, not many separated rooms.",
    )


runner.prompt_for = prompt_for


def append_board() -> list[dict]:
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict] = []

    for i, key in enumerate(runner.REFS.keys()):
        y = y0 + i * 760
        title, prompt = prompt_for(key)
        style_id, ref_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
        group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": ref_id, "type": "image", "x": 396, "y": y + 92, "url": runner.REFS[key], "name": "v22 sane home reference", "role": "normal scale reference only"},
                {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 360, "h": 300, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 944, "h": 442, "items": [style_id, ref_id, prompt_id], "name": f"{title} 输入"},
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
                    {"url": runner.REFS[key], "name": "v22 sane home reference", "role": "normal scale reference only"},
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
            "platform": "codex-v23",
            "prompt": "Append v23 normal home background-map refinements: reduce thick walls, floor-plan dryness, and dollhouse structure.",
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
        "client_id": "codex-home-map-v23",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return groups


runner.append_board = append_board


if __name__ == "__main__":
    raise SystemExit(runner.main())
