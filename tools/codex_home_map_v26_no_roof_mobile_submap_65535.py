#!/usr/bin/env python3
"""Generate no-roof mobile home sub-map candidates for Aiko."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


GUIDES = {
    "no_roof_room_grid": {
        "url": "/assets/input/home_map_v26_no_roof_room_grid_guide.png",
        "path": base.INPUT_DIR / "home_map_v26_no_roof_room_grid_guide.png",
    },
    "mobile_home_hub": {
        "url": "/assets/input/home_map_v26_mobile_home_hub_guide.png",
        "path": base.INPUT_DIR / "home_map_v26_mobile_home_hub_guide.png",
    },
}

runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v26_no_roof_mobile_submap_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v26_no_roof_mobile_submap_contact_sheet.jpg"
runner.REFS = {key: data["url"] for key, data in GUIDES.items()}


def draw_guide(path: Path, variant: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 1400), (244, 239, 226))
    d = ImageDraw.Draw(img)
    line = (126, 106, 82)
    floor = (228, 198, 151)
    path_col = (241, 224, 188)
    bed = (220, 203, 225)
    work = (224, 213, 184)
    closet = (217, 205, 186)
    laundry = (210, 224, 224)
    living = (151, 197, 172)
    kitchen = (196, 224, 212)
    bath = (210, 222, 230)
    entry = (206, 198, 184)
    balcony = (200, 224, 190)

    # No roof, no exterior shell: just a clean phone-map board.
    d.rounded_rectangle((90, 90, 810, 1310), radius=30, fill=path_col, outline=(185, 158, 120), width=4)

    if variant == "no_roof_room_grid":
        zones = [
            ((130, 135, 365, 410), bed),
            ((385, 135, 625, 410), work),
            ((645, 135, 775, 410), closet),
            ((645, 430, 775, 650), laundry),
            ((130, 445, 510, 820), living),
            ((530, 690, 775, 1010), kitchen),
            ((530, 430, 775, 670), bath),
            ((130, 840, 510, 1110), entry),
            ((130, 1130, 775, 1270), balcony),
        ]
    else:
        zones = [
            ((135, 135, 380, 405), bed),
            ((400, 135, 765, 320), balcony),
            ((505, 345, 765, 650), kitchen),
            ((180, 420, 500, 820), living),
            ((135, 845, 390, 1065), work),
            ((415, 720, 765, 1055), bath),
            ((135, 1090, 765, 1270), entry),
        ]

    for box, color in zones:
        d.rounded_rectangle(box, radius=28, fill=color, outline=line, width=4)

    # Representative furniture icons, no text.
    d.rounded_rectangle((170, 190, 330, 330), radius=18, fill=(239, 226, 220), outline=line, width=3)
    d.rounded_rectangle((430, 190, 570, 280), radius=14, fill=(236, 220, 184), outline=line, width=3)
    d.rectangle((675, 180, 745, 360), fill=(229, 215, 195), outline=line, width=3)
    d.rounded_rectangle((220, 535, 420, 680), radius=28, fill=living, outline=line, width=3)
    d.ellipse((300, 700, 445, 845), fill=(239, 220, 180), outline=line, width=3)
    d.rounded_rectangle((560, 740, 735, 835), radius=14, fill=(232, 240, 233), outline=line, width=3)
    d.ellipse((595, 505, 710, 620), fill=(226, 239, 240), outline=line, width=3)
    d.rectangle((580, 470, 730, 510), fill=(226, 239, 240), outline=line, width=3)
    d.rectangle((205, 925, 440, 1015), fill=entry, outline=line, width=3)
    d.line((220, 1188, 720, 1188), fill=(134, 160, 119), width=5)

    # Soft openings between zones to suggest navigation paths.
    d.line((358, 410, 420, 410), fill=path_col, width=12)
    d.line((500, 650, 560, 650), fill=path_col, width=12)
    d.line((505, 1000, 560, 1000), fill=path_col, width=12)
    d.line((360, 1110, 520, 1110), fill=path_col, width=12)
    img.save(path)


def ensure_guides() -> None:
    draw_guide(GUIDES["no_roof_room_grid"]["path"], "no_roof_room_grid")
    draw_guide(GUIDES["mobile_home_hub"]["path"], "mobile_home_hub")


def prompt_for(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- The Aiko home style board controls only the Tokyo project rendering family: soft anime watercolor, clean thin linework, warm cream wood, mint green and lavender accents, clear phone-size readability.\n"
        "- The simple guide controls only the mobile clickable home-map structure. Follow its no-roof, no-exterior, room-zone layout. Do not copy the guide as a flat diagram and do not add text.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for a mobile game. This is the map used to tap and jump to home locations. It must read as a game navigation map, not as a dialogue background and not as a real house cutaway.\n\n"
        "Core visual logic: no roof at all, no eaves, no house exterior silhouette, no facade, no outer building shell. Show only an open interior map board with clean room zones. Use a shallow elevated 2.5D / bird's-eye navigation view. Make every destination large and readable for touch targets.\n\n"
        "Home destinations: bedroom/bed zone, desk or computer zone, closet/storage zone, living sofa hub, kitchen/dining zone, bath/laundry utility zone, entry/genkan, balcony/window plant zone. Use furniture and floor/rug shapes as natural visual markers. Leave clear empty tap areas in each zone so the game can overlay invisible hotspots later.\n\n"
        "Mobile composition: the top and bottom should not be wasted by roof or decoration. Fill the phone canvas with useful indoor map content. Room blocks can be neatly stacked or arranged around a central living hub, but it must feel like a coherent home in Aiko's Tokyo project.\n\n"
        "Hard excludes: roof, roof tiles, attic, eaves, exterior wall, facade, house cross-section, dollhouse shell, two-story architecture, stairs, stairwell, railing, loft, split-level, platform, heavy beams, thick building frame, sky, street, garden exterior, immersive room background, eye-level perspective, real-estate blueprint, labels, text, map pins, route arrows, colored UI hotspot outlines, A/B/C markers, characters, photorealism, plastic 3D render, watermark."
    )
    if key == "no_roof_room_grid":
        return (
            "v26A 无屋顶手机家子地图-房间分块",
            common
            + "\n\nVariant direction: borrow only the useful idea from the user's reference: rooms are clear and clickable like compartments. Remove roof, exterior, stairs, and real building logic. Arrange private zones near the upper area and living/kitchen/entry zones below, as a clean phone navigation board.",
        )
    return (
        "v26B 无屋顶手机家子地图-中心客厅Hub",
        common
        + "\n\nVariant direction: make the living sofa area the central hub, with bedroom, desk/storage, kitchen/dining, bath/laundry, entry and balcony arranged around it as large touchable destinations. Less rigid than a room grid, but still clearly a clickable sub-map.",
    )


def append_board() -> list[dict]:
    ensure_guides()
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict] = []

    for i, key in enumerate(["no_roof_room_grid", "mobile_home_hub"]):
        y = y0 + i * 820
        title, prompt = prompt_for(key)
        style_id, guide_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
        group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": guide_id, "type": "image", "x": 396, "y": y + 92, "url": runner.REFS[key], "name": "no-roof mobile home map guide", "role": "structure guide only"},
                {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 400, "h": 380, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 985, "h": 520, "items": [style_id, guide_id, prompt_id], "name": f"{title} 输入"},
                {
                    "id": gen_id,
                    "type": "generator",
                    "x": 1185,
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
                {"id": out_id, "type": "output", "x": 1645, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
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
                    {"url": runner.REFS[key], "name": "no-roof mobile home map guide", "role": "structure guide only"},
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
            "platform": "codex-v26",
            "prompt": "Append v26 no-roof mobile home sub-map lanes. Target: phone clickable home navigation map, not roofed house cutaway.",
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
        "client_id": "codex-home-map-v26",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return groups


runner.prompt_for = prompt_for
runner.append_board = append_board


if __name__ == "__main__":
    raise SystemExit(runner.main())
