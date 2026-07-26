from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

AIKO_ROOT = Path(r"F:/cursor/Aiko")
HOME_MAP = AIKO_ROOT / "assets/worlds/tokyo_v2/maps/kichijoji_home_interior/world_map.png"
OUT_DIR = AIKO_ROOT / "tmp" / "home_ui_overlay_style_previews"

LOCATIONS = {
    "bathroom": (0.285, 0.22249, "drop"),
    "bedroom": (0.735, 0.18541, "moon"),
    "kitchen": (0.285, 0.65072, "fork_spoon"),
    "living_room": (0.76, 0.60048, "spark"),
    "entryway": (0.485, 0.86962, "door"),
    "balcony_laundry": (0.78, 0.89, "leaf"),
}


def rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    hex_color = hex_color.strip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
        alpha,
    )


def rounded_line(draw: ImageDraw.ImageDraw, points, fill, width):
    draw.line(points, fill=fill, width=width, joint="curve")
    r = width // 2
    for x, y in points:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def icon_drop(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill):
    pts = [
        (cx, cy - int(s * 0.36)),
        (cx - int(s * 0.26), cy + int(s * 0.04)),
        (cx - int(s * 0.15), cy + int(s * 0.30)),
        (cx, cy + int(s * 0.38)),
        (cx + int(s * 0.15), cy + int(s * 0.30)),
        (cx + int(s * 0.26), cy + int(s * 0.04)),
    ]
    draw.polygon(pts, fill=fill)


def icon_moon(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill, bg):
    r = int(s * 0.31)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
    draw.ellipse((cx - int(r * 0.20), cy - r, cx + int(r * 1.10), cy + int(r * 0.85)), fill=bg)
    icon_spark(draw, cx + int(s * 0.26), cy - int(s * 0.18), int(s * 0.34), fill)


def icon_spark(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill):
    r1 = int(s * 0.38)
    r2 = int(s * 0.12)
    pts = [
        (cx, cy - r1),
        (cx + r2, cy - r2),
        (cx + r1, cy),
        (cx + r2, cy + r2),
        (cx, cy + r1),
        (cx - r2, cy + r2),
        (cx - r1, cy),
        (cx - r2, cy - r2),
    ]
    draw.polygon(pts, fill=fill)


def icon_door(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill, line):
    w = int(s * 0.42)
    h = int(s * 0.56)
    x0, y0 = cx - w // 2, cy - h // 2
    x1, y1 = cx + w // 2, cy + h // 2
    draw.rounded_rectangle((x0, y0, x1, y1), radius=max(2, s // 20), outline=fill, width=max(3, s // 14))
    draw.line((x1, y0 + int(h * 0.12), x1 + int(w * 0.18), y0), fill=fill, width=max(3, s // 15))
    draw.line((x1, y1 - int(h * 0.12), x1 + int(w * 0.18), y1), fill=fill, width=max(3, s // 15))
    draw.ellipse((cx + int(w * 0.16), cy - 2, cx + int(w * 0.16) + 5, cy + 3), fill=line)


def icon_leaf(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill):
    stem_w = max(3, s // 18)
    rounded_line(draw, [(cx, cy + int(s * 0.28)), (cx, cy - int(s * 0.22))], fill, stem_w)
    r = int(s * 0.20)
    draw.ellipse((cx - int(s * 0.36), cy - int(s * 0.16), cx, cy + int(s * 0.20)), fill=fill)
    draw.ellipse((cx, cy - int(s * 0.22), cx + int(s * 0.36), cy + int(s * 0.14)), fill=fill)


def icon_fork_spoon(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, fill):
    width = max(4, s // 17)
    x1 = cx - int(s * 0.14)
    x2 = cx + int(s * 0.15)
    rounded_line(draw, [(x1, cy - int(s * 0.18)), (x1, cy + int(s * 0.30))], fill, width)
    for dx in [-int(s * 0.06), 0, int(s * 0.06)]:
        rounded_line(draw, [(x1 + dx, cy - int(s * 0.34)), (x1 + dx, cy - int(s * 0.12))], fill, max(2, s // 28))
    draw.ellipse((x2 - int(s * 0.12), cy - int(s * 0.34), x2 + int(s * 0.12), cy - int(s * 0.08)), fill=fill)
    rounded_line(draw, [(x2, cy - int(s * 0.06)), (x2, cy + int(s * 0.30))], fill, width)


def draw_icon(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, s: int, fill, bg, line):
    if kind == "drop":
        icon_drop(draw, cx, cy, s, fill)
    elif kind == "moon":
        icon_moon(draw, cx, cy, s, fill, bg)
    elif kind == "fork_spoon":
        icon_fork_spoon(draw, cx, cy, s, fill)
    elif kind == "spark":
        icon_spark(draw, cx, cy, s, fill)
    elif kind == "door":
        icon_door(draw, cx, cy, s, fill, line)
    elif kind == "leaf":
        icon_leaf(draw, cx, cy, s, fill)


def glow_circle(size: int, color: str, strength: float) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx = cy = size // 2
    for i in range(9, 0, -1):
        r = int(size * (0.24 + i * 0.038))
        a = int(20 * strength * (i / 9))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba(color, a))
    return layer.filter(ImageFilter.GaussianBlur(int(size * 0.045)))


def marker(style: str, kind: str, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size // 2
    line = rgba("ffffff", 245)
    if style == "01_peach_double_ring":
        img.alpha_composite(glow_circle(size, "ffb27d", 1.25))
        d = ImageDraw.Draw(img)
        r = int(size * 0.33)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba("ffb18b", 188))
        for off, width, alpha in [(0, 5, 245), (10, 3, 170), (-9, 2, 150)]:
            rr = r + off
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=rgba("ffffff", alpha), width=width)
        draw_icon(d, kind, cx, cy, int(size * 0.44), line, rgba("ffb18b", 188), rgba("f58d62", 235))
    elif style == "02_thin_clean_ring":
        img.alpha_composite(glow_circle(size, "ffc39d", 0.75))
        d = ImageDraw.Draw(img)
        r = int(size * 0.31)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba("ffcab2", 112))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=rgba("ffffff", 230), width=3)
        d.ellipse((cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), outline=rgba("ffffff", 130), width=2)
        draw_icon(d, kind, cx, cy, int(size * 0.38), line, rgba("ffcab2", 112), rgba("ed9a75", 220))
    elif style == "03_cream_glass_home":
        img.alpha_composite(glow_circle(size, "ffcc9a", 0.85))
        d = ImageDraw.Draw(img)
        r = int(size * 0.31)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba("fff0d8", 138))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=rgba("ffe0bf", 240), width=6)
        d.ellipse((cx - r + 12, cy - r + 12, cx + r - 12, cy + r - 12), outline=rgba("ffffff", 145), width=2)
        draw_icon(d, kind, cx, cy, int(size * 0.39), rgba("9f603b", 235), rgba("fff0d8", 138), rgba("9f603b", 235))
    elif style == "04_small_dot_corner":
        img.alpha_composite(glow_circle(size, "ffbd90", 0.58))
        d = ImageDraw.Draw(img)
        r = int(size * 0.24)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba("ffb996", 180))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=rgba("ffffff", 235), width=4)
        d.arc((cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), start=210, end=330, fill=rgba("ffffff", 170), width=3)
        d.arc((cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), start=30, end=150, fill=rgba("ffffff", 170), width=3)
        draw_icon(d, kind, cx, cy, int(size * 0.32), line, rgba("ffb996", 180), rgba("e68b62", 230))
    else:
        raise ValueError(style)
    return img


def overlay(style: str, marker_size: int) -> Path:
    base = Image.open(HOME_MAP).convert("RGBA")
    w, h = base.size
    for _, (nx, ny, kind) in LOCATIONS.items():
        m = marker(style, kind, marker_size)
        x = round(nx * w - marker_size / 2)
        y = round(ny * h - marker_size / 2)
        base.alpha_composite(m, (x, y))
    out = OUT_DIR / f"home_ui_{style}_{marker_size}.png"
    base.save(out)
    return out


def make_contact(paths: list[Path]) -> Path:
    thumbs = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        thumb = img.resize((360, round(360 * img.height / img.width)), Image.Resampling.LANCZOS)
        thumbs.append((path.stem, thumb))
    pad = 18
    label_h = 34
    cell_w = 360
    cell_h = max(t.height for _, t in thumbs) + label_h
    sheet = Image.new("RGB", (2 * cell_w + 3 * pad, 2 * cell_h + 3 * pad), (246, 233, 215))
    draw = ImageDraw.Draw(sheet)
    for i, (label, thumb) in enumerate(thumbs):
        col = i % 2
        row = i // 2
        x = pad + col * (cell_w + pad)
        y = pad + row * (cell_h + pad)
        sheet.paste(thumb, (x, y + label_h))
        draw.text((x + 6, y + 6), label.replace("home_ui_", ""), fill=(96, 65, 45))
    out = OUT_DIR / "home_ui_overlay_type_contact_sheet.png"
    sheet.save(out)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    styles = [
        ("01_peach_double_ring", 168),
        ("02_thin_clean_ring", 156),
        ("03_cream_glass_home", 156),
        ("04_small_dot_corner", 144),
    ]
    paths = [overlay(style, size) for style, size in styles]
    contact = make_contact(paths)
    print("contact:", contact)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
