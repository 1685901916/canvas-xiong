#!/usr/bin/env python3
"""Redesign Aiko home map structures from scratch, without the v31 reference layout."""

from __future__ import annotations

import math
import shutil
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner


GUIDES = {
    "central_hub": {
        "path": base.INPUT_DIR / "home_map_v32_structure_central_hub.png",
        "url": "/assets/input/home_map_v32_structure_central_hub.png",
        "title": "v32A 中央客厅枢纽一层家",
    },
    "two_floor_side_stair": {
        "path": base.INPUT_DIR / "home_map_v32_structure_two_floor_side_stair.png",
        "url": "/assets/input/home_map_v32_structure_two_floor_side_stair.png",
        "title": "v32B 正常双层小家侧楼梯",
    },
    "japanese_2ldk": {
        "path": base.INPUT_DIR / "home_map_v32_structure_japanese_2ldk.png",
        "url": "/assets/input/home_map_v32_structure_japanese_2ldk.png",
        "title": "v32C 日式2LDK家庭节点图",
    },
}

runner.STATE_PATH = base.OUTPUT_DIR / "home_map_v32_redesign_structures_task_state.json"
runner.SHEET_PATH = base.OUTPUT_DIR / "home_map_v32_redesign_structures_contact_sheet.jpg"


def _shadowed_canvas(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    w, h = size
    img = Image.new("RGB", size, (248, 242, 232))
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((92, 72, w - 78, h - 78), radius=34, fill=(0, 0, 0, 38))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    return img, ImageDraw.Draw(img)


def _floor_lines(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: tuple[int, int, int] = (215, 174, 116)) -> None:
    x1, y1, x2, y2 = box
    for y in range(y1 + 30, y2 - 20, 58):
        draw.line((x1 + 20, y, x2 - 20, y), fill=color, width=1)


def _rr(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: tuple[int, int, int], radius: int = 14, width: int = 3) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=(95, 74, 54), width=width)


def _plant(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    leaf = (129, 177, 116)
    stem = (95, 74, 54)
    draw.line((cx, cy + 12, cx, cy - 10), fill=stem, width=2)
    draw.ellipse((cx - 22, cy - 13, cx - 5, cy + 4), fill=leaf, outline=stem, width=1)
    draw.ellipse((cx + 5, cy - 13, cx + 22, cy + 4), fill=leaf, outline=stem, width=1)
    draw.ellipse((cx - 12, cy - 25, cx + 5, cy - 7), fill=leaf, outline=stem, width=1)
    draw.rectangle((cx - 9, cy + 12, cx + 9, cy + 25), fill=(185, 132, 82), outline=stem, width=1)


def draw_central_hub(path: Path) -> None:
    img, d = _shadowed_canvas((900, 1400))
    wall = (126, 96, 70)
    wood = (232, 191, 134)
    cream = (249, 232, 205)
    tile = (230, 223, 209)
    mint = (177, 212, 188)
    bath = (202, 229, 229)
    shell = (90, 80, 810, 1320)
    d.rounded_rectangle(shell, radius=24, fill=wood, outline=wall, width=8)
    _floor_lines(d, shell)

    # Four supporting rooms wrap around one large, readable central living hub.
    rooms = [
        (120, 110, 390, 395, (218, 230, 214)),  # kitchen/dining
        (420, 110, 780, 390, (249, 229, 219)),  # bedroom
        (120, 420, 360, 660, bath),  # bath/laundry
        (560, 430, 780, 670, tile),  # closet/study
        (120, 1030, 390, 1290, tile),  # entry
        (520, 1030, 780, 1290, (225, 194, 166)),  # balcony/hobby
    ]
    for x1, y1, x2, y2, fill in rooms:
        d.rounded_rectangle((x1, y1, x2, y2), radius=14, fill=fill, outline=wall, width=5)

    d.rounded_rectangle((310, 420, 610, 1030), radius=24, fill=cream, outline=wall, width=6)
    d.rectangle((355, 392, 455, 445), fill=wood)
    d.rectangle((500, 392, 585, 445), fill=wood)
    d.rectangle((360, 1000, 520, 1050), fill=wood)
    d.rectangle((590, 620, 640, 760), fill=wood)

    # Furniture symbols: large natural touch zones, not UI markers.
    _rr(d, (360, 620, 560, 735), mint, 18)
    d.ellipse((370, 760, 560, 950), fill=(243, 228, 210), outline=(95, 74, 54), width=3)
    _rr(d, (405, 815, 535, 900), (218, 164, 96), 12)
    _rr(d, (155, 185, 345, 270), cream, 10)
    _rr(d, (175, 285, 330, 360), (221, 164, 98), 12)
    _rr(d, (510, 180, 735, 315), (250, 235, 228), 20)
    _rr(d, (150, 480, 300, 605), bath, 18)
    _rr(d, (595, 490, 745, 635), (174, 126, 78), 10)
    _rr(d, (175, 1110, 330, 1225), (170, 123, 77), 10)
    _rr(d, (570, 1090, 745, 1215), (220, 176, 126), 12)
    for cx, cy in [(255, 720), (650, 760), (255, 980), (660, 980), (455, 560), (470, 1160)]:
        _plant(d, cx, cy)
    img.save(path, quality=95)


def draw_two_floor_side_stair(path: Path) -> None:
    img, d = _shadowed_canvas((900, 1400))
    wall = (126, 96, 70)
    wood = (232, 191, 134)
    cream = (249, 232, 205)
    tile = (230, 223, 209)
    mint = (177, 212, 188)
    bath = (202, 229, 229)

    top = (160, 95, 790, 495)
    bottom = (95, 650, 805, 1310)
    d.rounded_rectangle(top, radius=20, fill=(235, 202, 157), outline=wall, width=8)
    d.rounded_rectangle(bottom, radius=24, fill=wood, outline=wall, width=8)
    _floor_lines(d, top)
    _floor_lines(d, bottom)

    # Upper private floor.
    d.rounded_rectangle((190, 130, 500, 450), radius=14, fill=(250, 229, 219), outline=wall, width=5)
    d.rounded_rectangle((520, 130, 760, 300), radius=14, fill=(222, 230, 212), outline=wall, width=5)
    d.rounded_rectangle((520, 310, 760, 460), radius=14, fill=tile, outline=wall, width=5)

    # Lower public floor.
    d.rounded_rectangle((125, 690, 370, 920), radius=14, fill=tile, outline=wall, width=5)
    d.rounded_rectangle((390, 690, 775, 890), radius=14, fill=cream, outline=wall, width=5)
    d.rounded_rectangle((390, 900, 775, 1160), radius=18, fill=cream, outline=wall, width=5)
    d.rounded_rectangle((125, 940, 370, 1160), radius=14, fill=bath, outline=wall, width=5)
    d.rounded_rectangle((125, 1175, 775, 1280), radius=14, fill=(225, 194, 166), outline=wall, width=5)

    # Side stair: one believable stair core, not a center bridge.
    d.rounded_rectangle((80, 480, 215, 680), radius=16, fill=(218, 170, 108), outline=wall, width=6)
    for i in range(8):
        y = 505 + i * 20
        d.line((100, y, 195, y), fill=(245, 219, 180), width=3)
    d.line((215, 560, 330, 650), fill=wall, width=5)

    # Furniture symbols.
    _rr(d, (255, 220, 455, 350), (250, 235, 228), 20)
    _rr(d, (555, 170, 725, 245), (218, 164, 96), 10)
    _rr(d, (570, 350, 735, 430), (174, 126, 78), 10)
    _rr(d, (175, 740, 320, 850), (170, 123, 77), 10)
    _rr(d, (430, 730, 735, 850), (244, 235, 219), 10)
    _rr(d, (475, 955, 710, 1065), mint, 18)
    d.ellipse((515, 1060, 690, 1220), fill=(243, 228, 210), outline=(95, 74, 54), width=3)
    _rr(d, (155, 995, 315, 1105), bath, 18)
    _rr(d, (300, 1195, 590, 1260), (221, 164, 98), 12)
    for cx, cy in [(240, 555), (640, 540), (310, 640), (730, 975), (250, 1230)]:
        _plant(d, cx, cy)
    img.save(path, quality=95)


def draw_japanese_2ldk(path: Path) -> None:
    img, d = _shadowed_canvas((900, 1400))
    wall = (126, 96, 70)
    wood = (232, 191, 134)
    cream = (249, 232, 205)
    tile = (230, 223, 209)
    tatami = (199, 219, 170)
    bath = (202, 229, 229)
    shell = [(125, 90), (805, 90), (805, 1235), (640, 1320), (160, 1320), (95, 1130), (95, 230)]
    d.polygon(shell, fill=wood, outline=wall)
    d.line(shell + [shell[0]], fill=wall, width=8)
    _floor_lines(d, (110, 110, 790, 1290))

    # Japanese apartment arrangement: LDK is large, tatami and study are separate map nodes.
    d.rounded_rectangle((135, 120, 430, 395), radius=14, fill=cream, outline=wall, width=5)
    d.rounded_rectangle((455, 120, 775, 415), radius=14, fill=(250, 229, 219), outline=wall, width=5)
    d.rounded_rectangle((135, 425, 385, 670), radius=14, fill=bath, outline=wall, width=5)
    d.rounded_rectangle((410, 445, 775, 860), radius=18, fill=cream, outline=wall, width=5)
    d.rounded_rectangle((135, 700, 385, 1010), radius=14, fill=tatami, outline=wall, width=5)
    d.rounded_rectangle((410, 890, 775, 1120), radius=14, fill=(223, 232, 215), outline=wall, width=5)
    d.rounded_rectangle((190, 1045, 610, 1280), radius=14, fill=tile, outline=wall, width=5)
    d.rounded_rectangle((625, 1135, 785, 1280), radius=12, fill=(225, 194, 166), outline=wall, width=5)

    d.rectangle((390, 350, 460, 430), fill=wood)
    d.rectangle((380, 610, 430, 780), fill=wood)
    d.rectangle((555, 1120, 650, 1185), fill=wood)

    _rr(d, (165, 185, 380, 305), (244, 235, 219), 10)
    _rr(d, (530, 220, 735, 350), (250, 235, 228), 20)
    _rr(d, (185, 500, 325, 625), bath, 18)
    _rr(d, (470, 520, 735, 625), (177, 212, 188), 18)
    _rr(d, (505, 675, 700, 790), (218, 164, 96), 12)
    for x in [165, 245, 325]:
        d.line((x, 735, x, 970), fill=(142, 164, 119), width=4)
    d.line((150, 825, 370, 825), fill=(142, 164, 119), width=4)
    d.line((150, 915, 370, 915), fill=(142, 164, 119), width=4)
    _rr(d, (470, 945, 730, 1055), (174, 126, 78), 10)
    _rr(d, (300, 1130, 520, 1230), (170, 123, 77), 10)
    _rr(d, (650, 1185, 760, 1255), (221, 164, 98), 12)
    for cx, cy in [(410, 225), (735, 470), (470, 840), (235, 1035), (690, 1115), (725, 1300)]:
        _plant(d, cx, cy)
    img.save(path, quality=95)


def make_guides() -> None:
    base.INPUT_DIR.mkdir(parents=True, exist_ok=True)
    draw_central_hub(GUIDES["central_hub"]["path"])
    draw_two_floor_side_stair(GUIDES["two_floor_side_stair"]["path"])
    draw_japanese_2ldk(GUIDES["japanese_2ldk"]["path"])


def prompt_for(key: str) -> tuple[str, str]:
    common = (
        "Reference roles:\n"
        "- The Aiko home style board controls only the final project art style: soft anime watercolor, clear pastel Aiko Tokyo mood, warm wood, cream walls, mint/lavender/peach accents, clean thin lines, gentle domestic light.\n"
        "- The structure guide controls only this new spatial structure. Do not copy the guide's flat diagram style, thick outlines, or plain blocks.\n\n"
        "Create a vertical 9:16 Aiko Tokyo v2 HOME CLICKABLE SUB-MAP for a mobile game. This is a tappable navigation map, not a dialogue background and not a real-estate plan.\n\n"
        "Important redesign instruction: discard the previous v31 structure entirely. Do not use the old bath-upper-left / bed-upper-right / wardrobe-center / kitchen-lower-left / living-lower-right arrangement. Build a fresh home-map structure from the guide and make it feel designed for mobile clicking.\n\n"
        "Map art direction: reduce realistic dollhouse feeling. Use lower cutaway walls, bigger readable location zones, fewer micro props, cleaner cream walking paths, furniture clusters as destination nodes, and soft Aiko watercolor rendering. It should read like an Aiko project spatial map first, not a generic isometric interior illustration.\n\n"
        "Clickable zones must be visually distinct but natural: entry/genkan, living sofa hub, kitchen, dining, bedroom, bath/wash/laundry, closet/study, balcony or hobby corner. Use rugs, floor material changes, plants, shelves, light pools, sliding doors, and furniture islands. No visible UI.\n\n"
        "Hard excludes: previous v31 layout, glowing circles, white rings, hotspot circles, map pins, labels, text, arrows, route lines, target icons, A/B/C markers, characters, roof, exterior facade, sky as the subject, random weird geometry, scattered platforms, maze corridors, fake impossible stairs, overly high dollhouse walls, cluttered tiny props, blueprint, photorealism, plastic 3D render, watermark."
    )
    if key == "central_hub":
        return (
            GUIDES[key]["title"],
            common
            + "\n\nVariant structure: one-floor central hub home map. The living room is the large central playable hub, with kitchen/dining, bedroom, bath/laundry, study/closet, entry, and balcony arranged around it. Make the central living area the strongest tap zone and use short open doorways around it.",
        )
    if key == "two_floor_side_stair":
        return (
            GUIDES[key]["title"],
            common
            + "\n\nVariant structure: normal two-floor compact home. Lower floor is public and large: entry, kitchen/dining, living sofa, bath/laundry, small balcony/hobby strip. Upper floor is private and smaller: bedroom, study, closet. Use one simple side stair as a believable connector, not a dramatic bridge. Keep the two floors tidy and aligned.",
        )
    return (
        GUIDES[key]["title"],
        common
        + "\n\nVariant structure: Japanese 2LDK home map. Use a large LDK as the main social zone, plus bedroom, bath/wash, genkan, balcony, a tatami or floor-cushion room, and a small study/closet node. Use sliding doors and warm wood/tatami materials so it feels different from the previous Western dollhouse layout.",
    )


def backup_canvas() -> str:
    base.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = base.BACKUP_DIR / f"{base.CANVAS_ID}.home-map-v32-redesign-before-{time.strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(base.CANVAS_PATH, dst)
    return str(dst)


def append_board() -> list[dict[str, Any]]:
    make_guides()
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    nodes = canvas.get("nodes") or []
    conns = canvas.get("connections") or []
    max_bottom = max(float(n.get("y") or 0) + float(n.get("h") or 300) for n in nodes)
    y0 = math.ceil(max_bottom / 40) * 40 + 160
    groups: list[dict[str, Any]] = []
    for i, key in enumerate(["central_hub", "two_floor_side_stair", "japanese_2ldk"]):
        y = y0 + i * 760
        title, prompt = prompt_for(key)
        style_id, guide_id, prompt_id = base.sid("img"), base.sid("img"), base.sid("prompt")
        group_id, gen_id, out_id = base.sid("grp"), base.sid("gen"), base.sid("out")
        nodes.extend(
            [
                {"id": style_id, "type": "image", "x": 156, "y": y + 92, "url": base.STYLE_BOARD_URL, "name": "Aiko home style board", "role": "style reference only"},
                {"id": guide_id, "type": "image", "x": 426, "y": y + 92, "url": GUIDES[key]["url"], "name": f"{title} structure guide", "role": "new structure guide"},
                {"id": prompt_id, "type": "prompt", "x": 696, "y": y + 92, "text": prompt, "w": 430, "h": 430, "name": title},
                {"id": group_id, "type": "group", "x": 120, "y": y, "w": 1045, "h": 560, "items": [style_id, guide_id, prompt_id], "name": f"{title} 输入"},
                {
                    "id": gen_id,
                    "type": "generator",
                    "x": 1245,
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
                    "count": 2,
                    "apiDefaultsVersion": 2,
                    "name": f"{title} / 65535",
                    "w": 380,
                    "h": 0,
                    "generatedOutputs": [],
                },
                {"id": out_id, "type": "output", "x": 1705, "y": y + 40, "images": [], "name": "65535 输出", "w": 780, "h": 640},
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
                    {"url": GUIDES[key]["url"], "name": f"{title} structure guide", "role": "new structure guide"},
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
            "platform": "codex-v32",
            "prompt": "Append v32 home map redesign structures. Goal: discard v31 structure and test three fresh mobile clickable home-map layouts.",
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
        "client_id": "codex-home-map-v32",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)
    return groups


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
                    "source": "codex-v32",
                    "provider_id": base.PRIMARY_PROVIDER["id"],
                    "provider_name": base.PRIMARY_PROVIDER["name"],
                    "model": base.PRIMARY_PROVIDER["model"],
                    "task_id": r.get("task_id") or "",
                    "runMs": r.get("run_ms") or 0,
                    "createdAt": base.now_ms(),
                    "reviewStatus": "pending-redesign-structure-review-v32",
                    "v32Variant": plan.get("key") or "",
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
                    "reference_count": 2,
                    "v32_variant": plan.get("key") or "",
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
        "client_id": "codex-home-map-v32",
        "base_updated_at": canvas.get("updated_at") or 0,
    }
    base.req_json("PUT", f"/api/canvases/{base.CANVAS_ID}", payload, timeout=120)


runner.append_board = append_board
runner.prompt_for = prompt_for
runner.backup_canvas = backup_canvas
runner.append_results = append_results


if __name__ == "__main__":
    raise SystemExit(runner.main())
