#!/usr/bin/env python3
"""Generate plain normal home-map backgrounds with simple apartment guides."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


GUIDES = {
    "plain_1ldk": {
        "url": "/assets/input/home_map_v24_plain_1ldk_guide.png",
        "path": base.INPUT_DIR / "home_map_v24_plain_1ldk_guide.png",
    },
    "plain_studio": {
        "url": "/assets/input/home_map_v24_plain_studio_guide.png",
        "path": base.INPUT_DIR / "home_map_v24_plain_studio_guide.png",
    },
}

runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v24_plain_normal_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v24_plain_normal_contact_sheet.jpg"
runner.REFS = {key: data["url"] for key, data in GUIDES.items()}


def draw_plain_guide(path: Path, variant: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 1400), (245, 239, 226))
    d = ImageDraw.Draw(img)
    wall = (92, 82, 70)
    floor = (229, 198, 150)
    service = (218, 226, 223)
    balcony = (202, 222, 190)
    sleep = (218, 202, 222)
    kitchen = (205, 228, 218)
    entry = (200, 196, 186)
    line = (118, 104, 86)

    d.rounded_rectangle((95, 95, 805, 1305), radius=18, fill=floor, outline=wall, width=8)
    d.rectangle((135, 100, 765, 215), fill=balcony, outline=line, width=4)
    d.line((135, 225, 765, 225), fill=line, width=4)

    if variant == "plain_1ldk":
        d.rectangle((135, 245, 362, 515), fill=sleep, outline=line, width=4)
        d.rounded_rectangle((170, 290, 330, 445), radius=18, fill=(238, 226, 222), outline=line, width=3)
        d.rectangle((390, 255, 750, 430), fill=kitchen, outline=line, width=4)
        d.rounded_rectangle((420, 292, 720, 390), radius=14, fill=(235, 242, 235), outline=line, width=3)
        d.rounded_rectangle((250, 560, 650, 955), radius=24, fill=(235, 215, 172), outline=(180, 148, 110), width=3)
        d.rounded_rectangle((285, 650, 550, 780), radius=26, fill=(139, 194, 172), outline=line, width=3)
        d.ellipse((380, 805, 535, 960), fill=(236, 218, 178), outline=line, width=3)
        d.rectangle((135, 980, 350, 1190), fill=service, outline=line, width=4)
        d.rectangle((135, 1195, 360, 1268), fill=entry, outline=line, width=4)
        d.rectangle((395, 1120, 765, 1268), fill=entry, outline=line, width=4)
    else:
        d.rectangle((135, 245, 340, 520), fill=sleep, outline=line, width=4)
        d.rounded_rectangle((165, 295, 310, 455), radius=16, fill=(238, 226, 222), outline=line, width=3)
        d.rectangle((585, 245, 765, 650), fill=kitchen, outline=line, width=4)
        d.rounded_rectangle((615, 300, 735, 600), radius=14, fill=(235, 242, 235), outline=line, width=3)
        d.rectangle((135, 560, 330, 800), fill=(226, 219, 195), outline=line, width=4)
        d.rounded_rectangle((400, 570, 590, 740), radius=24, fill=(236, 218, 178), outline=line, width=3)
        d.rounded_rectangle((270, 780, 585, 980), radius=26, fill=(139, 194, 172), outline=line, width=3)
        d.ellipse((405, 955, 550, 1100), fill=(236, 218, 178), outline=line, width=3)
        d.rectangle((135, 915, 350, 1160), fill=service, outline=line, width=4)
        d.rectangle((135, 1175, 365, 1268), fill=entry, outline=line, width=4)
        d.rectangle((405, 1165, 765, 1268), fill=entry, outline=line, width=4)

    # Simple openings/windows, no text.
    d.line((260, 224, 360, 224), fill=(245, 239, 226), width=9)
    d.line((470, 224, 620, 224), fill=(245, 239, 226), width=9)
    d.line((94, 540, 94, 710), fill=(245, 239, 226), width=10)
    d.line((806, 720, 806, 900), fill=(245, 239, 226), width=10)
    img.save(path)


def ensure_guides() -> None:
    draw_plain_guide(GUIDES["plain_1ldk"]["path"], "plain_1ldk")
    draw_plain_guide(GUIDES["plain_studio"]["path"], "plain_studio")


def prompt_for(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- The Aiko home style board controls art style only: soft Tokyo anime watercolor, warm cream wood, mint green, coral and lavender accents, clean thin linework, cozy daylight, gentle mobile-game polish.\n"
        "- The simple structure guide controls apartment logic only. Follow its plain rectangular single-floor room relationship. Do not copy the guide as a flat diagram, do not draw its colors, and do not add any text.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME BACKGROUND MAP for a mobile game. The structure must be a normal believable Japanese apartment, not a weird cutaway. Keep one clean rectangular apartment footprint, one floor only, straight walls, simple doors, normal windows and balcony. The camera is a gentle elevated 2.5D interior view with the front wall removed, like a clean game background set, not a top-down floor plan.\n\n"
        "Use normal home logic: central living room and dining table, compact kitchen along one wall, bedroom or sleeping nook near the back/side, genkan entry near the bottom, bathroom/laundry as closed doors or a small normal utility corner, balcony/window area at the back. The clickable points should be natural furniture clusters: sofa/table, kitchen, bed, desk/storage, entry, balcony. Keep enough empty floor for mobile UI and character overlay.\n\n"
        "Important corrections from previous attempts: no exposed open bathtub room, no chopped-up private bathroom, no maze of small rooms, no diagonal/floating walls, no thick grey outer shell, no stacked-room dollhouse, no real-estate blueprint. The home should look like a normal compact Tokyo apartment first, then a game background second.\n\n"
        "Hard excludes: no second floor, no stairs, no split-level, no loft, no platform, no railing, no roof, no exterior facade, no sky scene, no long corridor maze, no many tiny compartments, no random alcoves, no floating room islands, no blueprint/top-down plan, no text, no labels, no map pins, no arrows, no A/B/C markers, no characters, no photorealism, no plastic 3D render, no watermark."
    )
    if key == "plain_1ldk":
        return (
            "v24A 正常结构-标准1LDK",
            common
            + "\n\nVariant direction: standard 1LDK. A single open living-dining-kitchen occupies the center. Bedroom is one calm side/back room or sleep area. Kitchen is a normal side-wall counter. Bathroom/laundry is represented by normal doors and a tidy utility corner, not by an exposed bath scene.",
        )
    return (
        "v24B 正常结构-开放单间",
        common
        + "\n\nVariant direction: normal open studio / 1R apartment. One main open room with a bed alcove, sofa area, small dining table, kitchen counter, desk corner, entry and balcony. Very simple structure, fewer walls, no complex cutaway.",
    )


def append_board() -> list[dict]:
    ensure_guides()
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict] = []

    for i, key in enumerate(["plain_1ldk", "plain_studio"]):
        y = y0 + i * 780
        title, prompt = prompt_for(key)
        style_id, guide_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
        group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": guide_id, "type": "image", "x": 396, "y": y + 92, "url": runner.REFS[key], "name": "plain normal apartment structure guide", "role": "structure guide only"},
                {"id": prompt_id, "type": "prompt", "x": 668, "y": y + 92, "text": prompt, "w": 380, "h": 330, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 965, "h": 468, "items": [style_id, guide_id, prompt_id], "name": f"{title} 输入"},
                {
                    "id": gen_id,
                    "type": "generator",
                    "x": 1165,
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
                {"id": out_id, "type": "output", "x": 1625, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
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
                    {"url": runner.REFS[key], "name": "plain normal apartment structure guide", "role": "structure guide only"},
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
            "platform": "codex-v24",
            "prompt": "Append v24 plain normal apartment structure lanes. Structure guide controls a simple rectangular single-floor home; prompt excludes weird cutaway and exposed bath rooms.",
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
        "client_id": "codex-home-map-v24",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return groups


runner.prompt_for = prompt_for
runner.append_board = append_board


if __name__ == "__main__":
    raise SystemExit(runner.main())
