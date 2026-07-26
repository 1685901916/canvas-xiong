import sys
from pathlib import Path

TOOLS = Path(r"F:/cursor/project29 画布工具/Infinite-Canvas-main/tools")
sys.path.insert(0, str(TOOLS))
import canvasctl

BASE = "http://127.0.0.1:3001"
CANVAS_ID = "76a36ce2c28e47fd9a6ccc34ab67d47f"
STYLE_REF = r"F:/cursor/Aiko/tmp/home_pin_r4_home_map_style_reference.png"
TITLE = "家庭地图UI标志-image2 R6 subtle home hotspot glow"

COMMON = (
    "Use case: Aiko mobile game home interior map clickable hotspot UI marker. "
    "Use the reference image only for the HOME INTERIOR MAP art language: warm 2.5D anime apartment, cream walls, honey wood, peach fabric, soft lamp light, fine warm-brown hand-painted linework, cozy clean Japanese home palette. "
    "Create ONE small transparent-overlay hotspot marker on a perfectly flat #00FF00 chroma-key background. The green background must be one uniform color with no shadow, no texture, no gradient, no floor plane, no reflection. Do not use #00FF00 in the marker. "
    "The marker must feel like a subtle tappable in-room hint, not a separate sticker or menu badge: a soft warm cream-gold glow pad, tiny translucent peach highlight, very thin brown outline, and one miniature household cue. "
    "Visual weight: lighter and quieter than a wooden plaque. Keep it compact, soft-edged, readable at small mobile size, about 55 to 65 percent of the square canvas with generous green padding. "
    "It may have a faint internal glow or tiny sparkle highlight, but no outside cast shadow on the green background. "
    "Important exclusions: no full furniture scene, no miniature room, no walls, no floor tile base, no thick wood plaque, no thick white sticker outline, no circular app button, no map-pin needle, no location label, no external Tokyo landmark pin style, no emoji toy sticker look, no text, no letters, no logo, no character. "
    "After chroma removal the outside becomes true transparent alpha and the result should sit naturally on the existing room art."
)

TARGETS = [
    (
        "R6 玄关 subtle hotspot",
        COMMON
        + " Location cue: entryway/genkan. Use a tiny hand-painted slippers-and-key cue sitting inside a soft cream-peach warm light hint. No door, no cabinet, no full mat scene.",
    ),
    (
        "R6 客厅 subtle hotspot",
        COMMON
        + " Location cue: living room. Use a tiny sofa cushion plus tea-table/leaf cue inside a soft cream-peach warm light hint. No full sofa, no TV stand, no complete room object cluster.",
    ),
    (
        "R6 厨房 subtle hotspot",
        COMMON
        + " Location cue: kitchen. Use a tiny kettle/rice-cooker and cup cue inside a soft cream-gold warm light hint. No cabinets, no countertop scene, no full appliance scene.",
    ),
    (
        "R6 卧室 subtle hotspot",
        COMMON
        + " Location cue: bedroom. Use a tiny pillow and folded blanket or bedside-lamp cue inside a soft peach-cream warm light hint. No full bed, no room corner.",
    ),
    (
        "R6 浴室 subtle hotspot",
        COMMON
        + " Location cue: bathroom. Use a tiny towel, soap bottle, water droplet, or very small tub silhouette inside a soft cream warm light hint. No full bathtub room, no tile wall, no sink cabinet.",
    ),
    (
        "R6 阳台洗衣 subtle hotspot",
        COMMON
        + " Location cue: balcony laundry. Use a tiny hanger, folded towel, plant leaf, or laundry basket cue inside a soft cream-peach warm light hint. No balcony railing, no full balcony scene.",
    ),
]


def main():
    argv = [
        "--base",
        BASE,
        "compose",
        "--json",
        "--canvas",
        CANVAS_ID,
        "--title",
        TITLE,
        "--mode",
        "reference_edit",
        "--image",
        STYLE_REF,
        "--provider",
        "65535",
        "--model",
        "gpt-image-2",
        "--count",
        "2",
        "--ratio",
        "1:1",
        "--resolution",
        "1k",
        "--quality",
        "high",
        "--multi-ref",
        "--run",
        "--concurrency",
        "6",
        "--task-timeout",
        "1200",
        "--x",
        "120",
        "--y",
        "8800",
    ]
    for title, prompt in TARGETS:
        argv.extend(["--target", f"{title}::{prompt}"])
    return canvasctl.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
