from __future__ import annotations

import json
import math
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AIKO_ROOT = Path(r"F:/cursor/Aiko")
CANVAS_ROOT = Path(r"F:/cursor/project29 画布工具/Infinite-Canvas-main")
CANVAS_ID = "76a36ce2c28e47fd9a6ccc34ab67d47f"
HOME_MAP = AIKO_ROOT / "assets/worlds/tokyo_v2/maps/kichijoji_home_interior/world_map.png"
OUT_DIR = AIKO_ROOT / "tmp" / "home_ui_overlay_style_previews_v2"

LOCATIONS = {
    "bathroom": (0.285, 0.22249, "drop"),
    "bedroom": (0.735, 0.18541, "moon"),
    "kitchen": (0.285, 0.65072, "utensils"),
    "living_room": (0.76, 0.60048, "spark"),
    "entryway": (0.485, 0.86962, "door"),
    "balcony": (0.78, 0.89, "leaf"),
}

STYLES = [
    ("01_soft_round", 178),
    ("02_open_ring", 176),
    ("03_round_diamond", 176),
    ("04_horizontal_pill", 196),
    ("05_house_tag", 184),
    ("06_pin_bubble", 186),
    ("07_floor_glow", 198),
    ("08_minimal_tile", 170),
]


def color(hex_value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_value = hex_value.strip("#")
    return (
        int(hex_value[0:2], 16),
        int(hex_value[2:4], 16),
        int(hex_value[4:6], 16),
        alpha,
    )


def font(size: int) -> ImageFont.ImageFont:
    for path in [r"C:/Windows/Fonts/segoeui.ttf", r"C:/Windows/Fonts/arial.ttf"]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def line(draw: ImageDraw.ImageDraw, points, fill, width):
    draw.line(points, fill=fill, width=width, joint="curve")
    radius = max(1, width // 2)
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def star_points(cx: int, cy: int, r1: int, r2: int, count: int = 8):
    pts = []
    for i in range(count * 2):
        angle = -math.pi / 2 + i * math.pi / count
        r = r1 if i % 2 == 0 else r2
        pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    return pts


def icon(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, s: int, fill, cut=None, stroke=None):
    stroke = stroke or fill
    w = max(4, s // 15)
    if kind == "drop":
        pts = [
            (cx, cy - int(s * 0.36)),
            (cx - int(s * 0.24), cy + int(s * 0.02)),
            (cx - int(s * 0.15), cy + int(s * 0.27)),
            (cx, cy + int(s * 0.36)),
            (cx + int(s * 0.15), cy + int(s * 0.27)),
            (cx + int(s * 0.24), cy + int(s * 0.02)),
        ]
        draw.polygon(pts, fill=fill)
    elif kind == "moon":
        r = int(s * 0.30)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
        if cut:
            draw.ellipse((cx - int(r * 0.15), cy - r, cx + int(r * 1.15), cy + int(r * 0.88)), fill=cut)
        draw.polygon(star_points(cx + int(s * 0.27), cy - int(s * 0.18), int(s * 0.12), int(s * 0.04)), fill=fill)
    elif kind == "utensils":
        x1 = cx - int(s * 0.14)
        x2 = cx + int(s * 0.14)
        line(draw, [(x1, cy - int(s * 0.12)), (x1, cy + int(s * 0.31))], fill, w)
        for dx in [-int(s * 0.065), 0, int(s * 0.065)]:
            line(draw, [(x1 + dx, cy - int(s * 0.34)), (x1 + dx, cy - int(s * 0.12))], fill, max(2, s // 30))
        draw.ellipse((x2 - int(s * 0.12), cy - int(s * 0.35), x2 + int(s * 0.12), cy - int(s * 0.09)), fill=fill)
        line(draw, [(x2, cy - int(s * 0.06)), (x2, cy + int(s * 0.31))], fill, w)
    elif kind == "spark":
        draw.polygon(star_points(cx, cy, int(s * 0.38), int(s * 0.12)), fill=fill)
    elif kind == "door":
        ww = int(s * 0.40)
        hh = int(s * 0.58)
        x0, y0 = cx - ww // 2, cy - hh // 2
        x1, y1 = cx + ww // 2, cy + hh // 2
        draw.rounded_rectangle((x0, y0, x1, y1), radius=max(4, s // 16), outline=fill, width=w)
        line(draw, [(x1, y0 + int(hh * 0.10)), (x1 + int(ww * 0.20), y0)], fill, max(3, w - 1))
        line(draw, [(x1, y1 - int(hh * 0.10)), (x1 + int(ww * 0.20), y1)], fill, max(3, w - 1))
        draw.ellipse((cx + int(ww * 0.12), cy - 3, cx + int(ww * 0.12) + 6, cy + 3), fill=stroke)
    elif kind == "leaf":
        line(draw, [(cx, cy + int(s * 0.30)), (cx, cy - int(s * 0.20))], fill, max(3, w - 1))
        draw.ellipse((cx - int(s * 0.36), cy - int(s * 0.15), cx, cy + int(s * 0.21)), fill=fill)
        draw.ellipse((cx, cy - int(s * 0.23), cx + int(s * 0.36), cy + int(s * 0.13)), fill=fill)


def glow(size: int, fill: str, alpha_scale: float = 1.0) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    for i in range(11, 0, -1):
        r = int(size * (0.18 + i * 0.035))
        a = int(alpha_scale * 14 * i)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color(fill, min(180, a)))
    return img.filter(ImageFilter.GaussianBlur(max(8, size // 22)))


def rounded_polygon(draw: ImageDraw.ImageDraw, pts, fill, outline=None, width=1):
    draw.polygon(pts, fill=fill)
    if outline:
        draw.line(pts + [pts[0]], fill=outline, width=width, joint="curve")


def make_marker(style: str, kind: str, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2
    white = color("ffffff", 246)
    peach = color("ffb38f", 192)
    warm = color("fff1d9", 190)
    brown = color("9b5f3e", 236)
    if style == "01_soft_round":
        img.alpha_composite(glow(size, "ffb07f", 0.85))
        r = int(size * 0.32)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=peach)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=white, width=max(4, size // 34))
        d.ellipse((cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10), outline=color("ffffff", 145), width=max(2, size // 55))
        icon(d, kind, cx, cy, int(size * 0.42), white, cut=peach, stroke=color("ec8f65", 230))
    elif style == "02_open_ring":
        img.alpha_composite(glow(size, "ffc49c", 0.52))
        r = int(size * 0.33)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color("ffffff", 236), width=max(5, size // 32))
        d.ellipse((cx - r + 12, cy - r + 12, cx + r - 12, cy + r - 12), outline=color("ffbf9b", 190), width=max(3, size // 48))
        for ang in [45, 135, 225, 315]:
            x = cx + math.cos(math.radians(ang)) * (r + 4)
            y = cy + math.sin(math.radians(ang)) * (r + 4)
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color("ffffff", 210))
        icon(d, kind, cx, cy, int(size * 0.38), color("ffffff", 245), cut=color("ffb994", 0), stroke=color("ffffff", 245))
    elif style == "03_round_diamond":
        img.alpha_composite(glow(size, "ffc194", 0.72))
        rr = int(size * 0.35)
        pts = [(cx, cy - rr), (cx + rr, cy), (cx, cy + rr), (cx - rr, cy)]
        rounded_polygon(d, pts, fill=color("ffe4ca", 185), outline=color("ffffff", 230), width=max(4, size // 36))
        d.line([(cx - rr + 16, cy), (cx, cy - rr + 16), (cx + rr - 16, cy)], fill=color("ffbd98", 130), width=max(2, size // 64))
        icon(d, kind, cx, cy, int(size * 0.40), color("b66b43", 236), cut=color("ffe4ca", 185), stroke=brown)
    elif style == "04_horizontal_pill":
        img.alpha_composite(glow(size, "ffc09a", 0.60))
        pill_w = int(size * 0.70)
        pill_h = int(size * 0.42)
        box = (cx - pill_w // 2, cy - pill_h // 2, cx + pill_w // 2, cy + pill_h // 2)
        d.rounded_rectangle(box, radius=pill_h // 2, fill=color("fff0df", 202), outline=color("ffffff", 238), width=max(4, size // 38))
        d.ellipse((box[0] + 12, cy - pill_h // 4, box[0] + 12 + pill_h // 2, cy + pill_h // 4), fill=color("ffb28d", 220))
        icon(d, kind, box[0] + 12 + pill_h // 4, cy, int(size * 0.26), white, cut=color("ffb28d", 220), stroke=color("e98b62", 235))
        d.ellipse((box[2] - 30, cy - 4, box[2] - 22, cy + 4), fill=color("d49268", 180))
        d.ellipse((box[2] - 46, cy - 4, box[2] - 38, cy + 4), fill=color("d49268", 120))
    elif style == "05_house_tag":
        img.alpha_composite(glow(size, "ffc49f", 0.65))
        w = int(size * 0.54)
        h = int(size * 0.54)
        x0, y0 = cx - w // 2, cy - h // 2 + int(size * 0.04)
        pts = [
            (cx, y0 - int(h * 0.20)),
            (x0 + w, y0 + int(h * 0.08)),
            (x0 + w, y0 + h),
            (x0, y0 + h),
            (x0, y0 + int(h * 0.08)),
        ]
        rounded_polygon(d, pts, fill=color("ffd8bd", 210), outline=color("ffffff", 240), width=max(4, size // 36))
        d.ellipse((cx - 7, y0 + int(h * 0.04) - 7, cx + 7, y0 + int(h * 0.04) + 7), fill=color("ffffff", 190))
        icon(d, kind, cx, cy + int(size * 0.08), int(size * 0.36), color("ffffff", 245), cut=color("ffd8bd", 210), stroke=color("e1845b", 235))
    elif style == "06_pin_bubble":
        img.alpha_composite(glow(size, "ffb57f", 0.78))
        r = int(size * 0.30)
        d.ellipse((cx - r, cy - r - 8, cx + r, cy + r - 8), fill=color("ffb78f", 202), outline=color("ffffff", 244), width=max(4, size // 34))
        pts = [(cx - int(r * 0.45), cy + int(r * 0.55)), (cx + int(r * 0.45), cy + int(r * 0.55)), (cx, cy + int(r * 1.12))]
        d.polygon(pts, fill=color("ffb78f", 202))
        d.line([pts[0], pts[2], pts[1]], fill=color("ffffff", 230), width=max(3, size // 42), joint="curve")
        icon(d, kind, cx, cy - 8, int(size * 0.37), white, cut=color("ffb78f", 202), stroke=color("e48a62", 235))
    elif style == "07_floor_glow":
        img.alpha_composite(glow(size, "ffd0a3", 0.95))
        ew = int(size * 0.76)
        eh = int(size * 0.38)
        d.ellipse((cx - ew // 2, cy - eh // 2 + 16, cx + ew // 2, cy + eh // 2 + 16), fill=color("ffc099", 98))
        d.ellipse((cx - ew // 2 + 10, cy - eh // 2 + 22, cx + ew // 2 - 10, cy + eh // 2 + 10), outline=color("ffffff", 210), width=max(3, size // 48))
        icon(d, kind, cx, cy - int(size * 0.02), int(size * 0.42), color("ffffff", 244), cut=color("ffc099", 98), stroke=color("ffffff", 244))
    elif style == "08_minimal_tile":
        img.alpha_composite(glow(size, "ffd5b5", 0.43))
        w = int(size * 0.54)
        h = int(size * 0.54)
        x0, y0 = cx - w // 2, cy - h // 2
        d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=int(size * 0.13), fill=color("fff7ec", 170), outline=color("f2b38b", 210), width=max(3, size // 45))
        d.rounded_rectangle((x0 + 9, y0 + 9, x0 + w - 9, y0 + h - 9), radius=int(size * 0.10), outline=color("ffffff", 150), width=max(2, size // 70))
        icon(d, kind, cx, cy, int(size * 0.37), color("a76645", 235), cut=color("fff7ec", 170), stroke=brown)
    else:
        raise ValueError(style)
    return img


def make_overlay(style: str, marker_size: int) -> Path:
    base = Image.open(HOME_MAP).convert("RGBA")
    w, h = base.size
    for _, (nx, ny, kind) in LOCATIONS.items():
        marker = make_marker(style, kind, marker_size)
        x = round(nx * w - marker_size / 2)
        y = round(ny * h - marker_size / 2)
        base.alpha_composite(marker, (x, y))
    out = OUT_DIR / f"home_ui_v2_{style}_{marker_size}.png"
    base.save(out)
    return out


def make_sheet(paths: list[Path]) -> Path:
    thumbs = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        thumb_w = 328
        thumb = image.resize((thumb_w, round(thumb_w * image.height / image.width)), Image.Resampling.LANCZOS)
        label = path.stem.replace("home_ui_v2_", "")
        thumbs.append((label, thumb))
    cols = 4
    pad = 18
    label_h = 32
    cell_w = 328
    cell_h = max(thumb.height for _, thumb in thumbs) + label_h
    sheet = Image.new("RGB", (cols * cell_w + (cols + 1) * pad, 2 * cell_h + 3 * pad), (247, 235, 219))
    draw = ImageDraw.Draw(sheet)
    label_font = font(16)
    for idx, (label, thumb) in enumerate(thumbs):
        col = idx % cols
        row = idx // cols
        x = pad + col * (cell_w + pad)
        y = pad + row * (cell_h + pad)
        draw.text((x + 4, y + 5), label, fill=(87, 56, 37), font=label_font)
        sheet.paste(thumb, (x, y + label_h))
    out = OUT_DIR / "home_ui_v2_type_contact_sheet.png"
    sheet.save(out)
    return out


def import_to_canvas(paths: list[Path], contact: Path) -> None:
    canvas_path = CANVAS_ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
    backup_dir = CANVAS_ROOT / "data" / "canvases" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{CANVAS_ID}.before_home_ui_v2_{int(time.time())}.bak"
    canvas_path.write_bytes(canvas_path.read_bytes())
    backup.write_bytes(canvas_path.read_bytes())
    data = json.loads(canvas_path.read_text(encoding="utf-8"))
    nodes = data.setdefault("nodes", [])
    now = int(time.time() * 1000)
    group_id = f"grp_home_ui_v2_preview_{now}"
    x0, y0 = 2280, 12040
    item_ids: list[str] = []
    all_paths = [contact] + paths
    for idx, path in enumerate(all_paths):
        target = CANVAS_ROOT / "assets" / "input" / f"home_ui_v2_{path.name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        node_id = f"img_home_ui_v2_{idx}_{now}"
        item_ids.append(node_id)
        col = idx % 2
        row = idx // 2
        nodes.append(
            {
                "id": node_id,
                "type": "image",
                "x": x0 + 40 + col * 430,
                "y": y0 + 70 + row * 360,
                "w": 390,
                "h": 320,
                "url": f"/assets/input/{target.name}",
                "name": path.name,
                "role": "home-ui-type-preview",
            }
        )
    nodes.append(
        {
            "id": group_id,
            "type": "group",
            "x": x0,
            "y": y0,
            "w": 930,
            "h": 1880,
            "items": item_ids,
            "name": "家庭地图 UI 类型预览 v2 - 只看比例和样式",
        }
    )
    data["updated_at"] = now
    data.setdefault("logs", []).insert(
        0,
        {
            "id": f"log_home_ui_v2_{now}",
            "createdAt": now,
            "status": "done",
            "nodeType": "image",
            "prompt": "Imported deterministic home-map UI overlay type previews v2.",
            "outputs": [f"/assets/input/home_ui_v2_{p.name}" for p in all_paths],
            "platform": "codex-local",
        },
    )
    canvas_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"canvas_imported_group={group_id}")
    print(f"canvas_backup={backup}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [make_overlay(style, size) for style, size in STYLES]
    contact = make_sheet(paths)
    import_to_canvas(paths, contact)
    print(f"contact={contact}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
