#!/usr/bin/env python3
"""Refill only missing v26 no-roof home sub-map candidates."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import shutil
from typing import Any

from PIL import Image, ImageDraw

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner
import codex_home_map_v26_no_roof_mobile_submap_65535  # noqa: F401 - configures runner paths/prompts


def real_image_count(node: dict[str, Any]) -> int:
    count = 0
    for item in node.get("images") or []:
        url = item.get("url") if isinstance(item, dict) else item
        if isinstance(url, str) and url.startswith("/assets/output/") and not url.startswith("failed://"):
            count += 1
    return count


def current_counts(groups: list[dict[str, Any]]) -> dict[str, int]:
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    by_id = {node.get("id"): node for node in canvas.get("nodes") or []}
    return {group["key"]: real_image_count(by_id.get(group["output_id"], {})) for group in groups}


def run_deficit(groups: list[dict[str, Any]], target: int, concurrency: int) -> list[dict[str, Any]]:
    counts = current_counts(groups)
    jobs: list[tuple[dict[str, Any], int]] = []
    for group in groups:
        existing = counts.get(group["key"], 0)
        missing = max(0, target - existing)
        for i in range(missing):
            jobs.append((group, existing + i + 1))

    if not jobs:
        print(json.dumps({"ok": True, "message": "already filled", "counts": counts}, ensure_ascii=False, indent=2), flush=True)
        return []

    print(json.dumps({"submit": len(jobs), "target": target, "counts_before": counts, "concurrency": concurrency}, ensure_ascii=False, indent=2), flush=True)
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(runner.create_task, group, index) for group, index in jobs]
        for fut in concurrent.futures.as_completed(futs):
            result = fut.result()
            results.append(result)
            print(
                f"[{'OK' if result.get('ok') else 'FAIL'}] {result.get('plan', {}).get('title')} "
                f"#{result.get('index')} task={result.get('task_id') or '-'} "
                f"error={str(result.get('error') or '')[:180]}",
                flush=True,
            )
    return results


def make_all_contact_sheet(groups: list[dict[str, Any]]) -> str:
    canvas = base.req_json("GET", f"/api/canvases/{base.CANVAS_ID}", timeout=60)["canvas"]
    by_id = {node.get("id"): node for node in canvas.get("nodes") or []}
    items: list[tuple[str, str, str]] = []
    for group in groups:
        out = by_id.get(group["output_id"], {})
        for item in out.get("images") or []:
            url = item.get("url") if isinstance(item, dict) else item
            if isinstance(url, str) and url.startswith("/assets/output/") and not url.startswith("failed://"):
                items.append((group["title"], group["key"], url))

    cols, cw, ch, lh = 2, 430, 764, 54
    rows = max(1, math.ceil(max(1, len(items)) / cols))
    sheet = Image.new("RGB", (cols * cw, rows * (ch + lh)), (242, 238, 229))
    draw = ImageDraw.Draw(sheet)
    for i, (title, key, url) in enumerate(items):
        x = (i % cols) * cw
        y = (i // cols) * (ch + lh)
        img = base.load_image(url)
        if img:
            img.thumbnail((cw, ch), Image.Resampling.LANCZOS)
            sheet.paste(img, (x + (cw - img.width) // 2, y + (ch - img.height) // 2))
        draw.rectangle((x, y + ch, x + cw, y + ch + lh), fill=(250, 247, 240))
        draw.text((x + 10, y + ch + 8), f"{key} | {title} | 65535"[:62], fill=(55, 48, 40))

    runner.SHEET_PATH.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(runner.SHEET_PATH, quality=92)
    base.AIKO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runner.SHEET_PATH, base.AIKO_TMP_DIR / runner.SHEET_PATH.name)
    return str(runner.SHEET_PATH)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args()

    state = json.loads(runner.STATE_PATH.read_text(encoding="utf-8"))
    groups = state["groups"]
    all_results: list[dict[str, Any]] = []
    for round_index in range(args.rounds):
        before = current_counts(groups)
        if all(count >= args.target for count in before.values()):
            break
        print(f"round {round_index + 1}/{args.rounds}", flush=True)
        results = run_deficit(groups, args.target, args.concurrency)
        if not results:
            break
        runner.append_results(results)
        all_results.extend(results)

    sheet = make_all_contact_sheet(groups)
    final_counts = current_counts(groups)
    merged_runs = (state.get("runs") or []) + all_results
    runner.write_state(
        {
            "canvas_id": base.CANVAS_ID,
            "canvas_url": base.CANVAS_URL,
            "backup": state.get("backup") or "",
            "groups": groups,
            "runs": merged_runs,
            "refill_runs": all_results,
            "contact_sheet": sheet,
            "aiko_tmp_contact_sheet": str(base.AIKO_TMP_DIR / runner.SHEET_PATH.name),
            "counts": final_counts,
            "completed_at": base.now_ms(),
        }
    )
    print(
        json.dumps(
            {
                "ok": True,
                "contact_sheet": sheet,
                "success": sum(1 for result in all_results if result.get("ok")),
                "total": len(all_results),
                "counts": final_counts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
