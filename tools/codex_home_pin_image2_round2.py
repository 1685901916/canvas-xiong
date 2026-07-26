import json
import sys
from pathlib import Path

TOOLS = Path(r'F:/cursor/project29 画布工具/Infinite-Canvas-main/tools')
sys.path.insert(0, str(TOOLS))
import canvasctl

BASE = 'http://127.0.0.1:3001'
CANVAS_ID = '76a36ce2c28e47fd9a6ccc34ab67d47f'
STYLE_REF = r'F:/cursor/Aiko/tmp/home_pin_style_reference_from_tokyo.png'
COMMON = (
    'Use case: Aiko 2.0 mobile game home map clickable marker asset. '
    'Create one square sticker-style household object pin on a perfectly flat chroma key background color #00FF00. '
    'The green background must be a single solid color with no checkerboard, no texture, no gradient, no shadows outside the sticker. '
    'The final sticker itself should match the Aiko Tokyo v2 pin reference: cute illustrated object sticker, compact strong silhouette, pastel colors, clean anime/vector-like shapes, subtle cel shading, thick white sticker border around the object, tiny soft shadow attached only to the sticker art. '
    'Make it simple and readable at small phone-map size: one main object plus at most two small supporting props. '
    'Not a room scene, not a floor plan, not a button badge. Centered 1:1 composition with generous padding. '
    'Hard excludes: fake transparent checkerboard, UI circle, round badge, neon glow, map pin needle, text, readable letters, logos, watermark, flat thin line icon, photorealism, 3D render, character, cluttered mini-room, many tiny props.'
)
TARGETS = [
    ('R2 玄关 simple genkan', COMMON + ' Subject: simple genkan shoe-cabinet sticker: one warm wooden shoe cabinet with two pairs of slippers/shoes and a tiny key tray. Large clear silhouette, fewer details than a room.'),
    ('R2 客厅 simple sofa', COMMON + ' Subject: simple sofa sticker: one cozy peach-cream sofa with a cushion and a tiny low table or plant. Large sofa silhouette, not a full living room.'),
    ('R2 厨房 simple rice cooker', COMMON + ' Subject: simple home kitchen sticker: one cute rice cooker or kettle on a small wooden counter with one bowl/cup. Large silhouette, avoid crowded shelves and many foods.'),
    ('R2 卧室 simple bed', COMMON + ' Subject: simple bed sticker: one soft bed with pink blanket and pillow, maybe a tiny bedside lamp. Large bed silhouette, no full bedroom scene.'),
    ('R2 浴室 simple bath', COMMON + ' Subject: simple bathtub sticker: one rounded bathtub with shower head and folded towel, pale aqua accent. Large tub silhouette, no full bathroom room scene.'),
    ('R2 阳台洗衣 simple laundry', COMMON + ' Subject: simple laundry balcony sticker: one small clothes rack with a shirt/towel and one potted plant or laundry basket. Large readable silhouette, no scenery.'),
]

def main():
    argv = [
        '--base', BASE,
        'compose',
        '--json',
        '--canvas', CANVAS_ID,
        '--title', '家庭地图UI标志-image2 R2 simple chroma',
        '--mode', 'reference_edit',
        '--image', STYLE_REF,
        '--provider', '65535',
        '--model', 'gpt-image-2',
        '--count', '1',
        '--ratio', '1:1',
        '--resolution', '1k',
        '--quality', 'high',
        '--multi-ref',
        '--run',
        '--concurrency', '6',
        '--task-timeout', '1200',
        '--x', '120',
        '--y', '2800',
    ]
    for title,prompt in TARGETS:
        argv.extend(['--target', f'{title}::{prompt}'])
    return canvasctl.main(argv)

if __name__ == '__main__':
    raise SystemExit(main())
