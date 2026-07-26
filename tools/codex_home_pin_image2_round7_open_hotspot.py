import sys
from pathlib import Path

TOOLS = Path(r"F:/cursor/project29 画布工具/Infinite-Canvas-main/tools")
sys.path.insert(0, str(TOOLS))
import canvasctl

BASE = "http://127.0.0.1:3001"
CANVAS_ID = "76a36ce2c28e47fd9a6ccc34ab67d47f"
STYLE_REF = r"F:/cursor/Aiko/tmp/home_pin_r4_home_map_style_reference.png"
TITLE = "家庭地图UI标志-image2 R7 open in-room hotspot"

COMMON = (
    "Use case: Aiko mobile game home interior map tappable hotspot marker. "
    "Use the reference image only for the HOME INTERIOR MAP art language: warm 2.5D anime apartment, cream and peach palette, honey wood, soft lamp light, fine warm-brown hand-painted linework. "
    "Create ONE small OPEN-SHAPE hotspot marker on a perfectly flat #00FF00 chroma-key background. The green background must be uniform, no texture, no shadow, no gradient, no floor plane. Do not use #00FF00 inside the marker. "
    "Design direction: not a badge and not a sticker. Use a tiny household cue drawn with warm brown line art, a few cream-gold sparkle strokes, and a very soft peach/cream translucent glow brush behind it. "
    "The marker should look like a game hotspot highlight painted onto the room, as if the existing object is gently selectable. "
    "Keep the shape open and airy: no closed circle, no closed rounded square, no thick outline frame, no wooden plaque, no enamel plate, no button rim, no sticker base. "
    "The cue should be readable at small mobile size but visually lighter than R6: about 45 to 55 percent of the square canvas with generous green padding. "
    "No text, no letters, no logo, no character, no full furniture, no miniature room, no wall, no floor base, no map-pin needle, no external Tokyo map pin style, no emoji toy sticker. "
    "No cast shadow on the green background. After chroma removal, only the warm line art and soft hotspot glow remain on transparent alpha."
)

TARGETS = [
    (
        "R7 玄关 open hotspot",
        COMMON
        + " Location cue: entryway/genkan. Draw tiny slippers plus key line art with two soft gold sparkles and a light peach glow. No door, no cabinet, no mat.",
    ),
    (
        "R7 客厅 open hotspot",
        COMMON
        + " Location cue: living room. Draw a tiny cushion, tea cup, and leaf line-art cue with soft cream highlight strokes. No sofa body, no table scene, no TV.",
    ),
    (
        "R7 厨房 open hotspot",
        COMMON
        + " Location cue: kitchen. Draw a tiny kettle or rice-cooker outline with a small cup and warm sparkle strokes. No cabinets, no counter, no appliance block.",
    ),
    (
        "R7 卧室 open hotspot",
        COMMON
        + " Location cue: bedroom. Draw tiny pillow and folded blanket line art with a small lamp-like sparkle and soft peach glow. No bed frame, no full bedding scene.",
    ),
    (
        "R7 浴室 open hotspot",
        COMMON
        + " Location cue: bathroom. Draw tiny towel, soap bottle, and water droplet line art with a clean cream glow. No tub, no sink, no tile wall.",
    ),
    (
        "R7 阳台洗衣 open hotspot",
        COMMON
        + " Location cue: balcony laundry. Draw tiny hanger and folded towel line art with a small leaf accent and soft peach glow. No railing, no balcony scene, no basket block.",
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
        "12020",
    ]
    for title, prompt in TARGETS:
        argv.extend(["--target", f"{title}::{prompt}"])
    return canvasctl.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
