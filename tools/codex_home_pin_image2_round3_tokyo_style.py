import json
import sys
from pathlib import Path

TOOLS = Path(r'F:/cursor/project29 画布工具/Infinite-Canvas-main/tools')
sys.path.insert(0, str(TOOLS))
import canvasctl

BASE = 'http://127.0.0.1:3001'
CANVAS_ID = '76a36ce2c28e47fd9a6ccc34ab67d47f'
STYLE_REF = r'F:/cursor/Aiko/tmp/home_pin_r3_tokyo_pin_style_reference.png'
TITLE = '家庭地图UI标志-image2 R3 Tokyo pin style'

COMMON = (
    'Use case: Aiko Tokyo v2 mobile game home-map clickable destination pin. '
    'Use the provided reference image ONLY for the existing Tokyo v2 pin art style: miniature illustrated landmark clusters, delicate hand-painted anime map art, compact scenic silhouette, warm low-saturation palette, thin clean linework, subtle cel shading, tiny flowers/plants/ground base, soft watercolor texture, readable as an official Tokyo map destination marker. '
    'Create one square 1:1 image on a perfectly flat chroma-key green background #00FF00. The green background must be one solid color, no checkerboard, no texture, no gradient. '
    'The subject should be a cohesive miniature HOME INTERIOR DESTINATION CLUSTER, like a tiny isometric/three-quarter room corner marker, not a single toy object sticker. '
    'Make it feel from the same system as Shibuya/Akihabara/Sensoji/Tokyo Tower pins: small scenic place marker with environmental base and details, not a rounded app icon. '
    'No UI label, no text, no readable letters, no logos, no watermark, no character, no circular badge, no map pin needle, no neon, no 3D toy render, no thick emoji sticker style, no oversized white border, no isolated object on blank space, no full rectangular room screenshot. '
    'Keep the object cluster centered with generous padding; after chroma removal it must have true transparent exterior. '
)

TARGETS = [
    ('R3 玄关 Tokyo-style micro scene', COMMON + 'Scene subject: warm genkan entryway micro-scene cluster: wooden front door edge, shoe cabinet, slippers, umbrella stand, tiny potted plant, small tiled floor base. Official Tokyo pin style, detailed but compact, warm cream and wood colors.'),
    ('R3 客厅 Tokyo-style micro scene', COMMON + 'Scene subject: cozy living room micro-scene cluster: small sofa, low table, TV cabinet edge or window light, potted plant, rug base. Official Tokyo pin style, warm peach/cream palette, scenic marker not toy sofa.'),
    ('R3 厨房 Tokyo-style micro scene', COMMON + 'Scene subject: home kitchen micro-scene cluster: cream counter, sink/stove hint, rice cooker or kettle, small dining chair/table edge, warm tile base and plant. Official Tokyo pin style, domestic and clean, not a single rice cooker icon.'),
    ('R3 卧室 Tokyo-style micro scene', COMMON + 'Scene subject: bedroom micro-scene cluster: bed with pink blanket, bedside lamp, small window/curtain hint, rug and plant base. Official Tokyo pin style, gentle wholesome home marker, not toy bed sticker.'),
    ('R3 浴室 Tokyo-style micro scene', COMMON + 'Scene subject: bathroom micro-scene cluster: bathtub/shower corner, vanity mirror hint, towel rack, pale aqua tiles and small plant, compact room-corner base. Official Tokyo pin style, clean and calm, not isolated bathtub icon.'),
    ('R3 阳台洗衣 Tokyo-style micro scene', COMMON + 'Scene subject: balcony laundry micro-scene cluster: short balcony railing, clothes rack with towel/shirt, laundry basket, potted plants, warm sunlight floor base. Official Tokyo pin style, tiny scenic destination marker, not outdoor scenery.'),
]

def main():
    argv = [
        '--base', BASE,
        'compose',
        '--json',
        '--canvas', CANVAS_ID,
        '--title', TITLE,
        '--mode', 'reference_edit',
        '--image', STYLE_REF,
        '--provider', '65535',
        '--model', 'gpt-image-2',
        '--count', '2',
        '--ratio', '1:1',
        '--resolution', '1k',
        '--quality', 'high',
        '--multi-ref',
        '--run',
        '--concurrency', '6',
        '--task-timeout', '1200',
        '--x', '120',
        '--y', '4700',
    ]
    for title,prompt in TARGETS:
        argv.extend(['--target', f'{title}::{prompt}'])
    return canvasctl.main(argv)

if __name__ == '__main__':
    raise SystemExit(main())
