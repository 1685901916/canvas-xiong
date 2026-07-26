#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import codex_run_single_bg_afternoon_night_diff as base


base.BATCH_ID = "codex-torii-bg-afternoon-night-20260611"
base.PROGRESS_PATH = base.ROOT / "output" / "codex_torii_afternoon_night_diff_progress.json"
base.SOURCE_PATH = Path(r"C:\Users\Arthur\AppData\Local\Temp\codex-clipboard-b51f2291-24c5-4b05-8351-5b07c76ceafc.png")
base.SOURCE_TITLE = "明治神宫大鸟居参道背景图"
base.TARGET_COUNT = 5
base.SIZE = "864x1536"
base.QUALITY = "auto"
base.MAX_REFILL_ROUNDS = 4
base.PROVIDER_POOL = [
    {"id": "custom-api-2", "name": "65535", "model": "gpt-image-2"},
    {"id": "custom-api-3", "name": "nexus", "model": "gpt-image-2"},
]

base.VARIANTS = [
    {
        "key": "single_bg_meiji_otorii_afternoon",
        "variant": "afternoon",
        "title": f"{base.SOURCE_TITLE}｜下午差分",
        "prompt": (
            f"将这张《{base.SOURCE_TITLE}》生成下午差分。\n"
            "严格保留原图竖版9:16构图、镜头高度、透视、中央参道、木质大鸟居的位置和比例、"
            "两侧石灯笼、绳栏、花丛、石块、树林层次、远处神社建筑、天空云朵、前景留白、"
            "线稿粗细、色块关系和干净二次元 galgame 背景图风格。\n"
            "只改变时间和光线：变成克制、温暖、明亮的下午版本。阳光从偏侧上方进入，"
            "树影和鸟居阴影比原图略长一点，木材保留自然浅棕色，整体只允许轻微暖色偏移，"
            "画面仍然清爽、可作为对话背景。\n"
            "不要太黄，不要太暗，不要金黄色，不要橙黄色，不要夕阳感，不要整体变黄，"
            "不要高对比，不要重画构图，不要移动鸟居/灯笼/参道/神社，不要新增人物，"
            "不要新增明显樱花，不要文字乱码，不要水印。"
        ),
    },
    {
        "key": "single_bg_meiji_otorii_night",
        "variant": "night",
        "title": f"{base.SOURCE_TITLE}｜晚上差分",
        "prompt": (
            f"将这张《{base.SOURCE_TITLE}》生成晚上/夜晚差分。\n"
            "严格保留原图竖版9:16构图、镜头高度、透视、中央参道、木质大鸟居的位置和比例、"
            "两侧石灯笼、绳栏、花丛、石块、树林层次、远处神社建筑、前景留白、线稿粗细、"
            "色块关系和干净二次元 galgame 背景图风格。\n"
            "只改变时间和光线：变成明亮、干净、温暖但克制的夜晚版本。天空是清晰的蓝灰夜色，"
            "树林和参道仍然可读，鸟居木纹和前景地面不要丢细节。石灯笼可以有柔和暖光，"
            "远处神社可以有少量温和灯光，但光晕必须小而自然，整体曝光保持足够明亮。\n"
            "不要太黑，不要深蓝压暗，不要偏紫，不要赛博霓虹，不要大面积强光，不要整体变黄，"
            "不要高对比，不要重画构图，不要移动鸟居/灯笼/参道/神社，不要新增人物，"
            "不要新增明显樱花，不要文字乱码，不要水印。"
        ),
    },
]


def create_board(canvas: dict, source_url: str) -> tuple[dict, list]:
    if canvas.get("title") != "背景图":
        raise RuntimeError(f"目标画布不匹配：期望 背景图，实际 {canvas.get('title')}")
    nodes = canvas.setdefault("nodes", [])
    connections = canvas.setdefault("connections", [])
    right = max(float(n.get("x") or 0) + float(n.get("w") or 0) for n in nodes)
    top = min(float(n.get("y") or 0) for n in nodes)
    origin_x = right + 1100
    origin_y = min(top, -2200)

    group_w = 1240
    group_h = 760
    row_h = 1020
    gen_w = 380
    out_w = 820
    out_h = 700

    brief_text = (
        f"生成简报：目标画布=背景图；源图={base.SOURCE_TITLE}；任务=下午差分5张、晚上差分5张。"
        "参考角色=精确源图，必须保留鸟居、参道、石灯笼、树林、远处神社、前景留白和画风；只改时间/光线。"
        "下午=克制明亮轻暖，不要太黄、不要夕阳；晚上=明亮可读、蓝灰夜色、灯笼暖光小而自然，不要太黑/偏紫/霓虹。"
    )
    brief = {
        "id": base.uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y - 250,
        "w": 1240,
        "h": 170,
        "name": f"{base.SOURCE_TITLE}｜下午晚上差分 生成简报",
        "text": brief_text,
        "codexBatchId": base.BATCH_ID,
    }
    nodes.append(brief)

    created = {"groups": [], "outputs": [], "generators": [], "images": [], "prompts": [brief["id"]]}
    run_plan = []
    for row, variant in enumerate(base.VARIANTS):
        y = origin_y + row * row_h
        img = {
            "id": base.uid("img"),
            "type": "image",
            "x": origin_x + 34,
            "y": y + 80,
            "url": source_url,
            "name": f"{base.SOURCE_TITLE} 源图",
            "role": "精确结构参考：保留鸟居、参道、灯笼、树林、远处神社、前景留白，只改时间和光线。",
            "w": 300,
            "h": 533,
            "codexBatchId": base.BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        prompt = {
            "id": base.uid("prompt"),
            "type": "prompt",
            "x": origin_x + 380,
            "y": y + 80,
            "w": 800,
            "h": 540,
            "name": f"{variant['title']} 提示词",
            "text": variant["prompt"],
            "codexBatchId": base.BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        group = {
            "id": base.uid("grp"),
            "type": "group",
            "x": origin_x,
            "y": y,
            "w": group_w,
            "h": group_h,
            "items": [img["id"], prompt["id"]],
            "name": f"{variant['title']} 输入｜目标5张",
            "codexBatchId": base.BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        gen = {
            "id": base.uid("gen"),
            "type": "generator",
            "x": origin_x + group_w + 140,
            "y": y + 38,
            "w": gen_w,
            "h": 0,
            "apiProvider": base.PROVIDER_POOL[0]["id"],
            "model": base.PROVIDER_POOL[0]["model"],
            "ratio": "source",
            "resolution": "1k",
            "quality": base.QUALITY,
            "customRatio": "",
            "customSize": "",
            "customRatioWidth": "",
            "customRatioHeight": "",
            "customWidth": "",
            "customHeight": "",
            "inputs": [f"{group['id']}:{img['id']}", f"{group['id']}:prompts"],
            "count": base.TARGET_COUNT,
            "forceFill": True,
            "apiDefaultsVersion": 2,
            "runStatus": "queued",
            "runError": "",
            "name": f"{variant['title']} / 单API可调",
            "poolTargetCount": base.TARGET_COUNT,
            "targetOutputId": "",
            "canvasProviderMode": "single-visible-api-node",
            "providerPoolCandidates": [
                {"apiProvider": p["id"], "providerName": p["name"], "model": p["model"]} for p in base.PROVIDER_POOL
            ],
            "generatedOutputs": [],
            "codexBatchId": base.BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        out = {
            "id": base.uid("out"),
            "type": "output",
            "x": gen["x"] + gen_w + 140,
            "y": y + 18,
            "w": out_w,
            "h": out_h,
            "images": [],
            "name": f"{variant['title']} 输出｜目标5张",
            "codexBatchId": base.BATCH_ID,
            "codexRequirementKey": variant["key"],
        }
        gen["targetOutputId"] = out["id"]

        nodes.extend([img, prompt, group, gen, out])
        base.connect(connections, group["id"], gen["id"])
        base.connect(connections, gen["id"], out["id"])
        created["images"].append(img["id"])
        created["prompts"].append(prompt["id"])
        created["groups"].append(group["id"])
        created["generators"].append(gen["id"])
        created["outputs"].append(out["id"])
        run_plan.append(
            {
                "requirement_key": variant["key"],
                "target_title": variant["title"],
                "variant": variant["variant"],
                "prompt": variant["prompt"],
                "size": base.SIZE,
                "quality": base.QUALITY,
                "reference_images": [{"url": source_url, "name": f"{base.SOURCE_TITLE}.png", "role": "exact source image"}],
                "target": base.TARGET_COUNT,
                "generator_id": gen["id"],
                "output_id": out["id"],
            }
        )

    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_torii_bg_diff_plan_{base.now_ms()}",
            "createdAt": base.now_ms(),
            "status": "info",
            "nodeType": "canvas-agent",
            "model": "codex_run_torii_afternoon_night_diff",
            "prompt": brief_text,
            "outputs": [],
            "error": "",
            "platform": "codex",
            "request": {"batch_id": base.BATCH_ID, "target_per_requirement": base.TARGET_COUNT},
        },
    )
    canvas["logs"] = canvas["logs"][:500]
    return created, run_plan


base.create_board = create_board


if __name__ == "__main__":
    base.main()
