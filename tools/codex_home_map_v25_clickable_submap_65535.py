#!/usr/bin/env python3
"""Generate Aiko home clickable sub-map candidates, not background scenes."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


GUIDES = {
    "normal_1ldk_submap": {
        "url": "/assets/input/home_map_v25_clickable_1ldk_guide.png",
        "path": base.INPUT_DIR / "home_map_v25_clickable_1ldk_guide.png",
    },
    "six_hotspots_submap": {
        "url": "/assets/input/home_map_v25_clickable_6spots_guide.png",
        "path": base.INPUT_DIR / "home_map_v25_clickable_6spots_guide.png",
    },
}

runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v25_clickable_submap_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v25_clickable_submap_contact_sheet.jpg"
runner.REFS = {key: data["url"] for key, data in GUIDES.items()}


def draw_clickable_guide(path: Path, variant: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 1400), (244, 239, 226))
    d = ImageDraw.Draw(img)
    wall = (98, 87, 72)
    line = (133, 116, 91)
    floor = (226, 196, 150)
    path_col = (240, 224, 189)
    living = (142, 196, 172)
    sleep = (218, 204, 226)
    kitchen = (194, 224, 212)
    service = (210, 223, 226)
    entry = (203, 196, 183)
    balcony = (198, 222, 190)
    desk = (226, 212, 180)

    # One normal rectangular apartment footprint.
    d.rounded_rectangle((90, 95, 810, 1305), radius=22, fill=floor, outline=wall, width=8)
    d.rounded_rectangle((125, 128, 775, 1252), radius=18, fill=path_col, outline=(178, 156, 119), width=3)

    if variant == "normal_1ldk_submap":
        zones = [
            ((145, 150, 405, 405), sleep),
            ((425, 150, 755, 405), balcony),
            ((455, 445, 755, 690), kitchen),
            ((185, 455, 430, 790), living),
            ((185, 815, 515, 1050), desk),
            ((535, 760, 755, 1055), service),
            ((185, 1080, 755, 1230), entry),
        ]
    else:
        zones = [
            ((140, 150, 365, 390), sleep),
            ((390, 150, 760, 355), balcony),
            ((515, 385, 760, 650), kitchen),
            ((160, 430, 485, 725), living),
            ((160, 755, 425, 1015), desk),
            ((450, 700, 760, 1015), service),
            ((170, 1050, 760, 1230), entry),
        ]

    for box, color in zones:
        d.rounded_rectangle(box, radius=28, fill=color, outline=line, width=4)

    # Add simplified furniture symbols without text.
    d.rounded_rectangle((205, 505, 385, 635), radius=26, fill=(117, 177, 158), outline=line, width=3)
    d.ellipse((275, 650, 385, 760), fill=(238, 218, 177), outline=line, width=3)
    d.rounded_rectangle((185, 205, 335, 330), radius=18, fill=(238, 225, 222), outline=line, width=3)
    d.rounded_rectangle((500, 495, 725, 585), radius=14, fill=(232, 240, 232), outline=line, width=3)
    d.rectangle((575, 790, 705, 945), fill=(226, 238, 239), outline=line, width=3)
    d.rounded_rectangle((230, 850, 400, 960), radius=16, fill=(236, 220, 184), outline=line, width=3)
    d.rectangle((230, 1120, 730, 1190), fill=(207, 199, 184), outline=line, width=3)

    # Door/window openings as normal navigation paths.
    d.line((320, 405, 430, 405), fill=path_col, width=12)
    d.line((420, 690, 515, 690), fill=path_col, width=12)
    d.line((425, 1018, 520, 1018), fill=path_col, width=12)
    d.line((330, 1305, 560, 1305), fill=(244, 239, 226), width=12)
    img.save(path)


def ensure_guides() -> None:
    draw_clickable_guide(GUIDES["normal_1ldk_submap"]["path"], "normal_1ldk_submap")
    draw_clickable_guide(GUIDES["six_hotspots_submap"]["path"], "six_hotspots_submap")


def prompt_for(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- The Aiko home style board controls only the Tokyo project art family: soft anime watercolor, clear bright pastel colors, thin warm linework, cream wooden floors, mint green and lavender accents, cozy but readable mobile-game map rendering.\n"
        "- The simple guide controls only the clickable sub-map structure: one normal rectangular apartment footprint, large readable destination zones, natural paths between zones. Do not copy the guide colors or flat diagram look.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for mobile-game navigation. This is a map used for click-to-jump hotspots, not a character dialogue background and not a room background illustration.\n\n"
        "Map grammar: elevated bird's-eye / shallow orthographic 2.5D navigation view. The player should instantly understand the clickable home destinations. Make large readable room/furniture zones with clear empty tap areas and natural walking paths between them. Use subtle floor-material changes, rugs, furniture clusters, low wall edges, doorways and soft zone separation so the hot areas are obvious without drawing UI markers.\n\n"
        "Normal home logic: one single-floor compact Tokyo apartment. Include living room / sofa table area, bedroom or bed nook, dining-kitchen area, entry/genkan, bath-laundry utility zone, balcony/window plant zone, plus a small desk/storage nook if space allows. All zones must belong to one coherent normal apartment, not many separate fantasy rooms.\n\n"
        "Important: because this is for click jumping, make the zone silhouettes bigger and clearer than a normal background. It should feel like a usable indoor navigation map, similar to a district sub-map but inside a home. Keep top and bottom mobile UI areas usable.\n\n"
        "Hard excludes: immersive eye-level room background, first-person room view, real-estate blueprint, flat floor plan, tiny fragmented rooms, weird cutaway, dollhouse, second floor, stairs, loft, split-level, platform, roof, exterior facade, sky, open exposed bathroom, chopped-up bathroom, labels, text, UI, map pins, route arrows, A/B/C markers, characters, photorealism, plastic 3D render, watermark."
    )
    if key == "normal_1ldk_submap":
        return (
            "v25A 家子地图-正常1LDK点击图",
            common
            + "\n\nVariant direction: standard 1LDK home sub-map. Use five to six large destination zones. Central living area is the main hub, kitchen/dining and bedroom are strong secondary zones, entry and bath/laundry are compact but still clickable, balcony is a clear back/top destination.",
        )
    return (
        "v25B 家子地图-六热点导航图",
        common
        + "\n\nVariant direction: six clear hotspot zones inside one normal apartment: living hub, kitchen/dining, bedroom, desk/storage, bath/laundry, balcony/entry. Push zone readability and tap-area clarity more strongly, but keep it natural and not like a UI board.",
    )


def append_board() -> list[dict]:
    ensure_guides()
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict] = []

    for i, key in enumerate(["normal_1ldk_submap", "six_hotspots_submap"]):
        y = y0 + i * 800
        title, prompt = prompt_for(key)
        style_id, guide_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
        group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": guide_id, "type": "image", "x": 396, "y": y + 92, "url": runner.REFS[key], "name": "clickable home sub-map structure guide", "role": "sub-map structure guide only"},
                {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 390, "h": 350, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 970, "h": 490, "items": [style_id, guide_id, prompt_id], "name": f"{title} 输入"},
                {
                    "id": gen_id,
                    "type": "generator",
                    "x": 1170,
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
                    "inputs": [f"{group_id}:{style_id}", f"{group_id}:{guide_id}", f"{group_id}:prompts"],
                    "count": 3,
                    "apiDefaultsVersion": 2,
                    "name": f"{title} / 65535",
                    "w": 380,
                    "h": 0,
                    "generatedOutputs": [],
                },
                {"id": out_id, "type": "output", "x": 1630, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
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
                    {"url": runner.REFS[key], "name": "clickable home sub-map structure guide", "role": "sub-map structure guide only"},
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
            "platform": "codex-v25",
            "prompt": "Append v25 clickable home sub-map lanes. Target is click-to-jump navigation map, not background scene.",
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
        "client_id": "codex-home-map-v25",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return groups


runner.prompt_for = prompt_for
runner.append_board = append_board


if __name__ == "__main__":
    raise SystemExit(runner.main())
