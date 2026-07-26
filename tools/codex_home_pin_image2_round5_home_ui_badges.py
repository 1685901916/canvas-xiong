import sys
from pathlib import Path

TOOLS = Path(r'F:/cursor/project29 画布工具/Infinite-Canvas-main/tools')
sys.path.insert(0, str(TOOLS))
import canvasctl

BASE = 'http://127.0.0.1:3001'
CANVAS_ID = '76a36ce2c28e47fd9a6ccc34ab67d47f'
STYLE_REF = r'F:/cursor/Aiko/tmp/home_pin_r4_home_map_style_reference.png'
TITLE = '家庭地图UI标志-image2 R5 home-map interactive badges'

COMMON = (
    'Use case: Aiko mobile game home interior map clickable UI marker. '
    'Use the reference image only for the HOME MAP visual language: warm 2.5D anime interior, cream walls, honey wood, peach fabric, soft lamp light, fine brown linework, cozy Japanese apartment palette. '
    'Create one small transparent-overlay marker on a perfectly flat #00FF00 chroma-key background. The green background must be uniform, no shadow, no texture, no gradient. '
    'The marker should be an in-world game UI hotspot marker that belongs on this home map: a tiny warm wooden plaque, cream enamel tag, peach fabric tag, or small tray-like marker with one simple household cue attached. '
    'It must feel clickable in a mobile game but still match the room art. '
    'Important: do NOT draw a miniature room, do NOT draw walls, do NOT draw a full floor base, do NOT draw a complete furniture scene. This should be a compact UI marker, not a duplicated room corner. '
    'Composition: centered, clear silhouette, about 70 percent of the square canvas, rounded organic shape, warm cream/wood/peach colors, subtle inner shadow, tiny highlight, no thick white sticker outline. '
    'No text, no letters, no logo, no character, no circular app badge, no location pin needle, no neon glow, no external Tokyo landmark pin style, no emoji/toy sticker look. '
    'After chroma removal the outside becomes true transparent alpha. '
)

TARGETS = [
    (
        'R5 玄关 home UI marker',
        COMMON
        + 'Cue: entryway/genkan. Use a small honey-wood nameplate or tray shape with tiny slippers and key charm, peach doormat accent. No door or full cabinet.',
    ),
    (
        'R5 客厅 home UI marker',
        COMMON
        + 'Cue: living room. Use a small cream-and-wood plaque with a tiny sofa cushion and low-table/plant cue. No full sofa room scene.',
    ),
    (
        'R5 厨房 home UI marker',
        COMMON
        + 'Cue: kitchen. Use a small warm tile/wood plaque with tiny rice cooker or kettle plus cup/plate cue. No full kitchen cabinets or room.',
    ),
    (
        'R5 卧室 home UI marker',
        COMMON
        + 'Cue: bedroom. Use a small peach fabric tag or wooden plaque with pillow/blanket/bedside-lamp cue. No full bed scene.',
    ),
    (
        'R5 浴室 home UI marker',
        COMMON
        + 'Cue: bathroom. Use a small cream enamel/wood plaque with bath towel, soap bottle, water droplet or tiny tub silhouette. No full bathroom room.',
    ),
    (
        'R5 阳台洗衣 home UI marker',
        COMMON
        + 'Cue: balcony laundry. Use a small warm plaque with tiny hanger/towel/plant/laundry basket cue. No full balcony room or railing scene.',
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
        '7700',
    ]
    for title, prompt in TARGETS:
        argv.extend(['--target', f'{title}::{prompt}'])
    return canvasctl.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
