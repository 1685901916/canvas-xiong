#!/usr/bin/env python3
"""Generate orderly two-floor Aiko home sub-map candidates."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


USER_REF_URL = "/assets/input/home_map_v30_user_two_floor_reference.png"
GUIDE_PATH = base.INPUT_DIR / "home_map_v30_orderly_two_floor_guide.png"
GUIDE_URL = "/assets/input/home_map_v30_orderly_two_floor_guide.png"

runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v30_orderly_two_floor_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v30_orderly_two_floor_contact_sheet.jpg"


def draw_two_floor_guide(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 1400), (247, 241, 231))
    d = ImageDraw.Draw(img)
    wall = (126, 98, 70)
    wood = (236, 201, 153)
    top_floor = (230, 205, 169)
    bottom_floor = (232, 199, 151)
    service = (210, 226, 228)
    kitchen = (211, 228, 212)
    entry = (214, 204, 188)
    rug = (190, 215, 181)
    bed = (230, 211, 222)
    desk = (218, 226, 206)

    # Fill the phone canvas with two simple, aligned floor plates.
    top = (150, 70, 770, 465)
    bottom = (95, 620, 805, 1310)
    d.rectangle(top, fill=top_floor, outline=wall, width=6)
    d.rectangle(bottom, fill=bottom_floor, outline=wall, width=6)

    # Top floor zones: bedroom + desk/closet + small utility.
    d.rectangle((180, 115, 455, 410), fill=bed, outline=wall, width=4)
    d.rectangle((455, 115, 705, 315), fill=desk, outline=wall, width=4)
    d.rectangle((615, 315, 740, 430), fill=service, outline=wall, width=4)

    # Lower floor zones: entry, living, kitchen/dining, bath.
    d.rectangle((125, 1110, 345, 1280), fill=entry, outline=wall, width=4)
    d.rectangle((345, 760, 770, 1110), fill=(234, 215, 182), outline=wall, width=4)
    d.rectangle((390, 660, 770, 760), fill=kitchen, outline=wall, width=4)
    d.rectangle((125, 650, 345, 860), fill=service, outline=wall, width=4)

    # Central stair core, neat and readable, not a zigzag bridge.
    stair_outer = [(310, 465), (430, 465), (505, 620), (385, 620)]
    d.polygon(stair_outer, fill=wood, outline=wall)
    d.line(stair_outer + [stair_outer[0]], fill=wall, width=5)
    for i in range(8):
        y = 480 + i * 16
        d.line((325 + i * 8, y, 410 + i * 8, y), fill=(150, 111, 73), width=2)
    d.rectangle((345, 540, 560, 610), fill=(214, 194, 166), outline=wall, width=4)

    # Furniture icons: enough to teach zones, no text.
    line = (110, 83, 58)
    d.rectangle((215, 210, 390, 315), fill=(244, 232, 224), outline=line, width=3)
    d.ellipse((215, 335, 350, 420), fill=rug, outline=line, width=3)
    d.rectangle((500, 165, 650, 220), fill=(226, 190, 135), outline=line, width=3)
    d.rectangle((520, 225, 625, 265), fill=(70, 83, 80), outline=line, width=3)
    d.rectangle((635, 335, 720, 395), fill=(225, 236, 237), outline=line, width=3)
    d.rounded_rectangle((430, 900, 690, 1015), radius=16, fill=(151, 196, 171), outline=line, width=3)
    d.rectangle((455, 780, 705, 855), fill=(228, 190, 130), outline=line, width=3)
    d.rectangle((440, 680, 700, 735), fill=(210, 226, 211), outline=line, width=3)
    d.rectangle((175, 700, 300, 815), fill=(226, 239, 240), outline=line, width=3)
    d.rectangle((165, 1170, 300, 1245), fill=entry, outline=line, width=3)
    img.save(path)


def prompt_for(_: str) -> tuple[str, str]:
    prompt = (
        "Reference roles:\n"
        "- The Aiko home style board controls only the final game art style: soft anime watercolor, warm wood, cream walls, mint/lavender/peach accents, clean thin linework, cozy Tokyo mobile-game readability.\n"
        "- The user's reference image controls the desired two-floor logic: upper private floor, lower living floor, central stairs connecting them, open cutaway interior, no roof, phone-map perspective.\n"
        "- The simplified guide controls the structure discipline: fill the vertical phone frame, two clean floor plates, centered stair core, straight tidy zones. Do not copy it as a flat diagram.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for a mobile game. This is the player's home map for tapping and jumping to home locations.\n\n"
        "Use a TWO-FLOOR structure like the user reference, but make it orderly and readable. The upper floor should sit near the top and contain bedroom, desk/study, closet/storage, and a small laundry or utility nook. The lower floor should fill the lower half and contain entry/genkan, living sofa area, dining table, compact kitchen, bath/wash area, and TV/plant corner. A single normal indoor stairway connects the two floors near the center-left or center, with simple straight railings.\n\n"
        "Composition: fill the entire phone canvas with useful home map content. Very little empty background around the house. Top floor uses about 35-40 percent of the image height, lower floor uses about 50-55 percent, and the stair/core connection occupies the middle. Keep the two floor plates aligned and tidy, with clean rectangular or gently angled edges, not scattered pieces.\n\n"
        "Clickable readability: each location is a large natural touch target marked by furniture, rugs, floor material, plants, and door openings. Keep clear empty floor/rug space in each zone for invisible hotspots. No labels, pins, arrows, UI outlines, text, or character sprites.\n\n"
        "Style and camera: elevated 2.5D bird's-eye navigation map, soft anime watercolor, warm domestic lighting, clean thin lines, same Aiko Tokyo home-map feeling, readable at phone size.\n\n"
        "Hard excludes: chaotic structure, messy zigzag layout, tiny scattered rooms, many disconnected platforms, strange bridges, maze corridors, random diagonal shards, roof, roof tiles, facade, exterior house shell, sky/street as the main subject, third floor, fake impossible stairs, spiral stairs, excessive railings, duplicate bedrooms, duplicate bathrooms, cluttered props everywhere, real-estate blueprint, labels, text, map pins, route arrows, A/B/C markers, colored hotspot outlines, characters, photorealism, plastic 3D render, watermark."
    )
    return "v30 双层整齐填满家庭点击子地图", prompt


def append_board() -> list[dict[str, Any]]:
    draw_two_floor_guide(GUIDE_PATH)
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y = math.ceil(max_bottom / 40) * 40 + 160
    title, prompt = prompt_for("two_floor")
    style_id, user_ref_id, guide_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("img"), base.sid("prompt")
    group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")

    nodes.extend(
        [
            {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
            {"id": user_ref_id, "type": "image", "x": 386, "y": y + 92, "url": USER_REF_URL, "name": "user two-floor structure reference", "role": "two-floor structure reference"},
            {"id": guide_id, "type": "image", "x": 616, "y": y + 92, "url": GUIDE_URL, "name": "orderly two-floor guide", "role": "structure discipline guide"},
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
            "platform": "codex-v30",
            "prompt": "Append v30 orderly two-floor home sub-map based on user's reference. Goal: fill frame, tidy two floors, no chaotic structure.",
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
        "client_id": "codex-home-map-v30",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return [
        {
            "key": "two_floor_orderly",
            "title": title,
            "prompt": prompt,
            "group_id": group_id,
            "generator_id": gen_id,
            "output_id": out_id,
            "reference_images": [
                {"url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"url": USER_REF_URL, "name": "user two-floor structure reference", "role": "two-floor structure reference"},
                {"url": GUIDE_URL, "name": "orderly two-floor guide", "role": "structure discipline guide"},
            ],
        }
    ]


runner.append_board = append_board
runner.prompt_for = prompt_for


if __name__ == "__main__":
    raise SystemExit(runner.main())
