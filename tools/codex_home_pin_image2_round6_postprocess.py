from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS_ROOT = Path(r"F:/cursor/project29 画布工具/Infinite-Canvas-main")
AIKO_ROOT = Path(r"F:/cursor/Aiko")
OUT_DIR = AIKO_ROOT / "tmp" / "home_pin_image2_round6_home_hotspot_glow"
CHROMA_HELPER = Path(r"C:/Users/Arthur/.codex/skills/.system/imagegen/scripts/remove_chroma_key.py")
HOME_MAP = AIKO_ROOT / "assets/worlds/tokyo_v2/maps/kichijoji_home_interior/world_map.png"

TARGETS = [
    ("entryway", "out_674c749f2d78_1781676695595"),
    ("living_room", "out_4651779d8b12_1781676695620"),
    ("kitchen", "out_917533c68c41_1781676695646"),
    ("bedroom", "out_c788f695418c_1781676695668"),
    ("bathroom", "out_5e4b67082196_1781676695692"),
    ("balcony_laundry", "out_15590ffb5c4a_1781676695720"),
]

LOCATIONS = {
    "entryway": (0.485, 0.86962),
    "living_room": (0.76, 0.60048),
    "kitchen": (0.285, 0.65072),
    "bedroom": (0.735, 0.18541),
    "bathroom": (0.285, 0.22249),
    "balcony_laundry": (0.78, 0.89),
}


def load_font(size: int) -> ImageFont.ImageFont:
    for path in [
        r"C:/Windows/Fonts/arial.ttf",
        r"C:/Windows/Fonts/segoeui.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def resolve_canvas_image(url: str) -> Path:
    if not url.startswith("/"):
        raise ValueError(f"Only local canvas URLs are supported here: {url}")
    path = CANVAS_ROOT / url.lstrip("/")
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def remove_chroma(src: Path, dst: Path) -> None:
    cmd = [
        sys.executable,
        str(CHROMA_HELPER),
        "--input",
        str(src),
        "--out",
        str(dst),
        "--auto-key",
        "border",
        "--soft-matte",
        "--despill",
        "--force",
    ]
    subprocess.run(cmd, check=True)


def alpha_bbox(img: Image.Image, threshold: int = 8) -> tuple[int, int, int, int] | None:
    alpha = img.getchannel("A")
    mask = alpha.point(lambda p: 255 if p > threshold else 0)
    return mask.getbbox()


def normalize_alpha(src: Path, dst: Path, canvas_size: int = 256, visual_max: int = 214) -> dict[str, object]:
    img = Image.open(src).convert("RGBA")
    bbox = alpha_bbox(img)
    if not bbox:
        raise ValueError(f"No visible alpha in {src}")
    x0, y0, x1, y1 = bbox
    pad = 10
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(img.width, x1 + pad)
    y1 = min(img.height, y1 + pad)
    crop = img.crop((x0, y0, x1, y1))
    scale = min(visual_max / crop.width, visual_max / crop.height)
    new_size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    crop = crop.resize(new_size, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    out.alpha_composite(crop, ((canvas_size - new_size[0]) // 2, (canvas_size - new_size[1]) // 2))
    out.save(dst)
    alpha = out.getchannel("A")
    alpha_values = list(alpha.getdata())
    visible = sum(1 for v in alpha_values if v > 8)
    return {
        "src": str(src),
        "dst": str(dst),
        "original_size": img.size,
        "bbox": [x0, y0, x1, y1],
        "normalized_size": out.size,
        "visible_pixels": visible,
        "coverage": round(visible / float(canvas_size * canvas_size), 4),
        "corner_alpha": [
            alpha.getpixel((0, 0)),
            alpha.getpixel((canvas_size - 1, 0)),
            alpha.getpixel((0, canvas_size - 1)),
            alpha.getpixel((canvas_size - 1, canvas_size - 1)),
        ],
    }


def checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (245, 238, 225, 255))
    draw = ImageDraw.Draw(img)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(214, 198, 180, 255))
    return img


def fit_image(img: Image.Image, box: tuple[int, int], bg: Image.Image | None = None) -> Image.Image:
    canvas = bg.copy() if bg else Image.new("RGBA", box, (248, 238, 224, 255))
    scale = min((box[0] - 22) / img.width, (box[1] - 22) / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    canvas.alpha_composite(resized, ((box[0] - resized.width) // 2, (box[1] - resized.height) // 2))
    return canvas


def make_contact_sheet(items: list[dict[str, object]]) -> Path:
    font = load_font(22)
    label_font = load_font(18)
    cell_w, cell_h = 250, 310
    header_h = 52
    cols = 2
    rows = len(TARGETS)
    sheet = Image.new("RGBA", (cols * cell_w, header_h + rows * cell_h), (248, 238, 224, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((18, 14), "R6 home hotspot candidates - alpha normalized", fill=(96, 67, 43, 255), font=font)
    by_name = {(item["target"], item["variant"]): item for item in items}
    for row, (target, _) in enumerate(TARGETS):
        for col, variant in enumerate(["a", "b"]):
            x = col * cell_w
            y = header_h + row * cell_h
            draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline=(207, 181, 147, 255), width=2)
            item = by_name.get((target, variant))
            draw.text((x + 12, y + 10), f"{target}_{variant}", fill=(96, 67, 43, 255), font=label_font)
            if not item:
                draw.text((x + 12, y + 48), "missing", fill=(160, 50, 40, 255), font=label_font)
                continue
            img = Image.open(item["normalized"]).convert("RGBA")
            bg = checker((210, 210), 14)
            preview = fit_image(img, (210, 210), bg)
            sheet.alpha_composite(preview, (x + 20, y + 52))
            coverage = item["stats"]["coverage"]
            draw.text((x + 12, y + 270), f"coverage {coverage}", fill=(116, 88, 64, 255), font=label_font)
    out = OUT_DIR / "r6_candidates_contact_sheet.png"
    sheet.convert("RGB").save(out)
    return out


def make_overlay(items: list[dict[str, object]], variant: str, visual_size: int) -> Path:
    bg = Image.open(HOME_MAP).convert("RGBA")
    w, h = bg.size
    by_name = {(item["target"], item["variant"]): item for item in items}
    for target, _ in TARGETS:
        item = by_name.get((target, variant))
        if not item:
            continue
        marker = Image.open(item["normalized"]).convert("RGBA")
        marker = marker.resize((visual_size, visual_size), Image.Resampling.LANCZOS)
        x, y = LOCATIONS[target]
        px = round(x * w - visual_size / 2)
        py = round(y * h - visual_size / 2)
        bg.alpha_composite(marker, (px, py))
    out = OUT_DIR / f"r6_home_map_overlay_{variant}_{visual_size}.png"
    bg.save(out)
    return out


def collect_canvas_outputs() -> dict[str, list[str]]:
    canvas_path = CANVAS_ROOT / "data/canvases/76a36ce2c28e47fd9a6ccc34ab67d47f.json"
    data = json.loads(canvas_path.read_text(encoding="utf-8"))
    nodes = {node.get("id"): node for node in data.get("nodes", [])}
    outputs: dict[str, list[str]] = {}
    for target, output_id in TARGETS:
        node = nodes.get(output_id)
        if not node:
            raise KeyError(output_id)
        urls = []
        for item in node.get("images") or []:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
        outputs[target] = urls[-2:]
    return outputs


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = collect_canvas_outputs()
    items: list[dict[str, object]] = []
    stats: list[dict[str, object]] = []
    for target, urls in outputs.items():
        for index, url in enumerate(urls):
            variant = "ab"[index]
            raw = OUT_DIR / f"{target}_{variant}_raw.png"
            alpha = OUT_DIR / f"{target}_{variant}_alpha.png"
            normalized = OUT_DIR / f"{target}_{variant}_normalized.png"
            shutil.copy2(resolve_canvas_image(url), raw)
            remove_chroma(raw, alpha)
            item_stats = normalize_alpha(alpha, normalized)
            item = {
                "target": target,
                "variant": variant,
                "url": url,
                "raw": str(raw),
                "alpha": str(alpha),
                "normalized": str(normalized),
                "stats": item_stats,
            }
            items.append(item)
            stats.append(item)
    contact = make_contact_sheet(items)
    overlays = []
    for variant in ["a", "b"]:
        for size in [96, 108]:
            overlays.append(str(make_overlay(items, variant, size)))
    stats_path = OUT_DIR / "r6_alpha_stats.json"
    stats_path.write_text(json.dumps({"items": stats, "contact_sheet": str(contact), "overlays": overlays}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out_dir": str(OUT_DIR), "contact_sheet": str(contact), "overlays": overlays, "count": len(items)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
