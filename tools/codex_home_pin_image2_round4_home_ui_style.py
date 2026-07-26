import sys
from pathlib import Path

TOOLS = Path(r'F:/cursor/project29 画布工具/Infinite-Canvas-main/tools')
sys.path.insert(0, str(TOOLS))
import canvasctl

BASE = 'http://127.0.0.1:3001'
CANVAS_ID = '76a36ce2c28e47fd9a6ccc34ab67d47f'
STYLE_REF = r'F:/cursor/Aiko/tmp/home_pin_r4_home_map_style_reference.png'
TITLE = '家庭地图UI标志-image2 R4 home-map UI style'

COMMON = (
    'Use case: Aiko mobile game home interior map clickable hotspot marker. '
    'Use the reference image only for THIS HOME MAP style: warm 2.5D anime interior, soft beige wood and cream palette, peach textiles, gentle window light, fine brown linework, clean painted furniture surfaces, subtle ambient occlusion, cozy Japanese apartment feeling. '
    'Create one square 1:1 overlay asset on a perfectly flat chroma-key green background #00FF00. The green background must be a single solid color with no texture, no checkerboard, no gradient, no cast shadow. '
    'The marker should look like a small in-world furniture/room-corner hotspot painted by the same artist as the home map, not like an external Tokyo landmark pin. '
    'Composition: compact 2.5D/isometric furniture vignette, centered, readable at phone-map size, with a natural ground/rug/tile base if useful. '
    'UI affordance should be extremely subtle: a tiny warm cream edge light or soft local highlight is allowed, but no thick white sticker border, no circular badge, no label, no icon glyph, no map-pin needle. '
    'Avoid: outside Tokyo map landmark style, toy sticker style, emoji style, flat vector line icon, neon glow, large white outline, drop-shadow badge, text, readable letters, logos, watermark, character, full rectangular room screenshot, roof/exterior, sky, strange structure. '
    'After chroma removal the exterior must become true transparent alpha. '
)

TARGETS = [
    (
        'R4 玄关 home-map UI hotspot',
        COMMON
        + 'Subject: genkan entryway hotspot matching the home map: wooden front door edge, shoe cabinet, slippers, umbrella stand, tiny key tray, peach doormat, warm wall lamp feeling. It should feel like a cropped part of the home map.',
    ),
    (
        'R4 客厅 home-map UI hotspot',
        COMMON
        + 'Subject: living room hotspot matching the home map: cream sofa, peach cushions, low wooden coffee table, small plant, warm rug base. It should feel like a cropped part of the home map, not a separate sticker.',
    ),
    (
        'R4 厨房 home-map UI hotspot',
        COMMON
        + 'Subject: kitchen hotspot matching the home map: cream cabinets, sink or stove hint, wooden dining table edge, small rice cooker/kettle, peach rug/tile base. It should feel like a cropped part of the kitchen area.',
    ),
    (
        'R4 卧室 home-map UI hotspot',
        COMMON
        + 'Subject: bedroom hotspot matching the home map: wooden bed frame, pink blanket, pillows, bedside lamp, curtain/window hint, soft rug base. Gentle and domestic, not a toy bed icon.',
    ),
    (
        'R4 浴室 home-map UI hotspot',
        COMMON
        + 'Subject: bathroom hotspot matching the home map: cream bathtub/shower corner, vanity sink or mirror hint, towel, pale beige tile base, tiny plant. Clean calm domestic bath corner.',
    ),
    (
        'R4 阳台洗衣 home-map UI hotspot',
        COMMON
        + 'Subject: balcony laundry hotspot matching the home map: small balcony rail, tiled floor, clothes rack with towel/shirt, laundry basket, plants, warm daylight. It should feel like the balcony corner from the map.',
    ),
]


def main():
    argv = [
        '--base',
        BASE,
        'compose',
        '--json',
        '--canvas',
        CANVAS_ID,
        '--title',
        TITLE,
        '--mode',
        'reference_edit',
        '--image',
        STYLE_REF,
        '--provider',
        '65535',
        '--model',
        'gpt-image-2',
        '--count',
        '2',
        '--ratio',
        '1:1',
        '--resolution',
        '1k',
        '--quality',
        'high',
        '--multi-ref',
        '--run',
        '--concurrency',
        '6',
        '--task-timeout',
        '1200',
        '--x',
        '120',
        '--y',
        '6200',
    ]
    for title, prompt in TARGETS:
        argv.extend(['--target', f'{title}::{prompt}'])
    return canvasctl.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
