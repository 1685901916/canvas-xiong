import argparse
import json
import sys
from pathlib import Path

TOOLS = Path(r'F:/cursor/project29 画布工具/Infinite-Canvas-main/tools')
sys.path.insert(0, str(TOOLS))
import canvasctl

BASE = 'http://127.0.0.1:3001'
STYLE_REF = r'F:/cursor/Aiko/tmp/home_pin_style_reference_from_tokyo.png'
TITLE = '家庭地图UI标志-image2'
COMMON = (
    'Use case: Aiko 2.0 mobile game home map clickable marker asset. '
    'Create one square transparent-background sticker-style map pin, not a circular UI icon. '
    'Match the provided Aiko Tokyo v2 pin style reference: cute illustrated object sticker, compact strong silhouette, pastel colors, clean vector-like anime shapes, subtle cel shading, thick white sticker border, soft transparent edge shadow, readable at small phone map size. '
    'This is a home location marker for a cozy Tokyo apartment map. The subject should be a single cohesive household-object sticker, not a room background, not a floor plan, not a button badge. '
    'Composition: centered 1:1 sticker, generous transparent padding, bottom-center anchor feel, no label. '
    'Hard excludes: no text, no readable letters, no logos, no watermark, no UI circle, no round badge, no neon glow, no map pin needle, no route marker, no flat line icon, no photorealism, no 3D toy render, no dark gritty palette, no character.'
)
TARGETS = [
    ('玄关 entryway pin', COMMON + ' Subject: warm Japanese genkan entry sticker, small wooden shoe cabinet, pair of house slippers, tiny key tray, simple door mat, warm cream and wood colors. Make it cozy and recognizable as entrance.'),
    ('客厅 living room pin', COMMON + ' Subject: cozy living room sticker, soft sofa with one cushion, small low table, tiny potted plant, folded blanket, warm peach/mint accents. Make it a compact sofa-table silhouette.'),
    ('厨房 kitchen pin', COMMON + ' Subject: compact kitchen/dining sticker, small kitchen counter or dining table, rice cooker or kettle, plate and cup, warm wood and cream tile accents. Avoid restaurant signs; make it home kitchen.'),
    ('卧室 bedroom pin', COMMON + ' Subject: bedroom sticker, small bed with soft pink blanket and pillow, bedside lamp or tiny moon cushion, cozy fabric folds, pastel lavender/cream palette. Make bed silhouette clear at small size.'),
    ('浴室 bathroom pin', COMMON + ' Subject: bathroom sticker, small rounded bathtub with shower head and folded towel, pale aqua tile accent, warm clean domestic bath feeling. Avoid toilet as main subject.'),
    ('阳台洗衣 balcony laundry pin', COMMON + ' Subject: balcony laundry sticker, small balcony railing with hanging towel/shirt, laundry basket, one potted plant, fresh pastel colors. Make it recognizable as balcony/laundry, not outdoor scenery.'),
]

def main():
    # Create board through native canvasctl visible workflow.
    argv = [
        '--base', BASE,
        'compose',
        '--json',
        '--new-title', TITLE,
        '--title', TITLE,
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
    ]
    for title,prompt in TARGETS:
        argv.extend(['--target', f'{title}::{prompt}'])
    code = canvasctl.main(argv)
    return code

if __name__ == '__main__':
    raise SystemExit(main())
