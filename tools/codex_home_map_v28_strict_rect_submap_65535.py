#!/usr/bin/env python3
"""Generate strict rectangular normal-home sub-map candidates."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


GUIDE_PATH = base.INPUT_DIR / "home_map_v28_strict_rect_apartment_guide.png"
GUIDE_URL = "/assets/input/home_map_v28_strict_rect_apartment_guide.png"

runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v28_strict_rect_submap_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v28_strict_rect_submap_contact_sheet.jpg"


def draw_strict_rect_guide(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 1400), (246, 240, 229))
    d = ImageDraw.Draw(img)
    wall = (128, 102, 74)
    floor = (235, 203, 158)
    living = (238, 219, 184)
    bed = (224, 205, 225)
    desk = (218, 225, 205)
    kitchen = (211, 229, 214)
    bath = (207, 225, 229)
    entry = (218, 207, 190)
    balcony = (205, 224, 191)

    # One simple apartment footprint: no rounded cells, no protrusions, no puzzle contour.
    outer = (120, 90, 780, 1310)
    d.rectangle(outer, fill=floor, outline=wall, width=8)

    # Straight-wall layout. Openings are intentionally drawn as breaks later.
    # Top balcony strip.
    d.rectangle((120, 90, 780, 210), fill=balcony, outline=wall, width=5)
    # Bedroom and desk/closet.
    d.rectangle((120, 210, 430, 520), fill=bed, outline=wall, width=5)
    d.rectangle((430, 210, 780, 520), fill=desk, outline=wall, width=5)
    # Central living hub.
    d.rectangle((120, 520, 780, 880), fill=living, outline=wall, width=5)
    # Kitchen/dining and bath/laundry.
    d.rectangle((120, 880, 455, 1160), fill=kitchen, outline=wall, width=5)
    d.rectangle((455, 880, 780, 1160), fill=bath, outline=wall, width=5)
    # Entry.
    d.rectangle((120, 1160, 780, 1310), fill=entry, outline=wall, width=5)

    # Door/opening breaks so it reads as a home, not isolated cells.
    for box in [
        (385, 515, 510, 528),
        (390, 875, 510, 888),
        (395, 1155, 520, 1168),
        (425, 345, 438, 435),
        (500, 205, 615, 218),
    ]:
        d.rectangle(box, fill=floor)

    line = (122, 94, 66)
    # Furniture icons, no text.
    d.rectangle((175, 270, 350, 405), fill=(242, 229, 224), outline=line, width=3)
    d.rectangle((500, 275, 710, 340), fill=(228, 196, 144), outline=line, width=3)
    d.rectangle((545, 342, 665, 390), fill=(65, 78, 78), outline=line, width=3)
    d.rectangle((535, 410, 720, 485), fill=(220, 204, 186), outline=line, width=3)

    d.rounded_rectangle((265, 600, 560, 700), radius=18, fill=(151, 196, 171), outline=line, width=3)
    d.ellipse((350, 710, 515, 855), fill=(236, 216, 179), outline=line, width=3)
    d.rectangle((170, 940, 365, 1010), fill=(210, 226, 211), outline=line, width=3)
    d.rectangle((195, 1020, 380, 1110), fill=(232, 191, 132), outline=line, width=3)
    d.rectangle((510, 925, 610, 1075), fill=(226, 239, 240), outline=line, width=3)
    d.rectangle((630, 925, 740, 1000), fill=(237, 226, 212), outline=line, width=3)
    d.rectangle((245, 1210, 655, 1272), fill=entry, outline=line, width=3)
    d.line((200, 150, 720, 150), fill=(130, 160, 117), width=5)
    img.save(path)


def prompt_for(_: str) -> tuple[str, str]:
    prompt = (
        "Reference roles:\n"
        "- The Aiko home style board controls only the final Tokyo project art style: soft anime watercolor, warm wood floor, cream walls, mint/lavender/peach accents, clean thin lines, cozy mobile-game readability.\n"
        "- The strict rectangle guide controls the structure. Follow the simple one-rectangle apartment footprint and straight-wall room adjacency. Do not copy it as a flat schematic; render it as finished Aiko map art.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for a mobile game. It is the player's home navigation map for tapping destinations. It must be a normal home map, not a background scene.\n\n"
        "Most important structure rule: ONE SIMPLE RECTANGULAR APARTMENT FOOTPRINT. The outer edge is a single clean vertical rectangle with straight sides. No irregular outline. No protruding rooms. No puzzle-piece contour. No rounded capsule rooms. No separated island rooms. No jagged or diagonal exterior contour. Interior walls are straight horizontal/vertical separators with a few open door gaps.\n\n"
        "Normal same-floor home layout: top balcony/window strip, one bedroom, one desk/closet nook, large central living sofa hub, compact kitchen/dining area, compact bath/wash/laundry room, bottom entry/genkan. Exactly one bedroom, one bath/wash room, one kitchen/dining, one living hub, one entry, one balcony. Keep it like a believable compact Tokyo apartment.\n\n"
        "Clickable-map readability: each destination is a large clean touch zone marked naturally by furniture and rugs. Leave usable empty floor or rug space in every zone for invisible game hotspots. No labels, pins, arrows, UI outlines, or text.\n\n"
        "Camera/art: shallow elevated 2.5D bird's-eye navigation view, phone-game map art, soft watercolor anime, warm clean lighting, clear rooms, cozy domestic details, restrained decoration. Walls should be light interior separators, not heavy exterior shell.\n\n"
        "Hard excludes: weird structure, irregular outline, organic shell, room capsules, rounded boxed rooms, protruding side rooms, separated modules, dollhouse cutaway, roof, eaves, facade, exterior house shell, second floor, stairs, split-level, loft, railing, long corridor, duplicate bedroom, duplicate bath, random extra rooms, sky/street background, blueprint, flat diagram, labels, text, map pins, route arrows, colored hotspot outlines, A/B/C markers, characters, photorealism, plastic 3D render, watermark."
    )
    return "v28 正常矩形公寓点击子地图", prompt


def append_board() -> list[dict[str, Any]]:
    draw_strict_rect_guide(GUIDE_PATH)
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y = math.ceil(max_bottom / 40) * 40 + 160
    title, prompt = prompt_for("strict_rect")

    style_id, guide_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
    group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
    nodes.extend(
        [
            {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
            {"id": guide_id, "type": "image", "x": 396, "y": y + 92, "url": GUIDE_URL, "name": "strict rectangular apartment guide", "role": "structure guide only"},
            {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 430, "h": 420, "name": title},
            {"id": group_id, "type": "group", "x": 120, "y": y, "w": 1005, "h": 540, "items": [style_id, guide_id, prompt_id], "name": f"{title} 输入"},
            {
                "id": gen_id,
                "type": "generator",
                "x": 1205,
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
                "count": 4,
                "apiDefaultsVersion": 2,
                "name": f"{title} / 65535",
                "w": 380,
                "h": 0,
                "generatedOutputs": [],
            },
            {"id": out_id, "type": "output", "x": 1665, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
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
            "platform": "codex-v28",
            "prompt": "Append v28 strict rectangular normal home sub-map. Fix: no strange/irregular structure.",
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
        "client_id": "codex-home-map-v28",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return [
        {
            "key": "strict_rect",
            "title": title,
            "prompt": prompt,
            "group_id": group_id,
            "generator_id": gen_id,
            "output_id": out_id,
            "reference_images": [
                {"url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"url": GUIDE_URL, "name": "strict rectangular apartment guide", "role": "structure guide only"},
            ],
        }
    ]


runner.append_board = append_board
runner.prompt_for = prompt_for


if __name__ == "__main__":
    raise SystemExit(runner.main())
