#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


BASE = "http://127.0.0.1:3001"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "codex_home_room_time_diffs_20260621"
PROGRESS_PATH = OUT_DIR / "progress.json"
CONTACT_SHEET_PATH = OUT_DIR / "home_room_time_diffs_contact_sheet.png"
SIZE = "864x1536"
QUALITY = "auto"
TASK_DEADLINE_SECONDS = 1800
POLL_INTERVAL_SECONDS = 2.5

PROVIDER_POOL = [
    {"id": "custom-api-7", "name": "comfly", "model": "gpt-image-2"},
    {"id": "custom-api", "name": "test", "model": "gpt-image-2"},
]

ROOMS = [
    {
        "key": "entryway",
        "label": "01_entryway",
        "title": "家地图玄关背景图",
        "source": "assets/input/ai_ref_5841485f5218.png",
    },
    {
        "key": "kitchen",
        "label": "02_kitchen",
        "title": "家地图厨房背景图",
        "source": "assets/input/ai_ref_61d9c9d5b2d2.png",
    },
    {
        "key": "bathroom",
        "label": "03_bathroom",
        "title": "家地图浴室背景图",
        "source": "assets/input/ai_ref_eaaa113a6ee2.png",
    },
    {
        "key": "bedroom",
        "label": "04_bedroom",
        "title": "家地图卧室背景图",
        "source": "assets/input/ai_ref_d3f7f4d68b3a.png",
    },
    {
        "key": "living",
        "label": "05_living",
        "title": "家地图客厅背景图",
        "source": "assets/input/ai_ref_b28317689c0b.png",
    },
    {
        "key": "balcony",
        "label": "06_balcony",
        "title": "家地图阳台背景图",
        "source": "assets/input/ai_ref_bbf7124625e3.png",
    },
]


def now_ms() -> int:
    return int(time.time() * 1000)


def http_json(method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} HTTP {exc.code}: {detail[:1200]}") from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def asset_url(rel_path: str) -> str:
    return "/" + rel_path.replace("\\", "/")


def local_path_from_url(url: str) -> Path | None:
    if not url.startswith("/assets/"):
        return None
    return ROOT / url.lstrip("/").replace("/", os.sep)


def room_keep_clause(room: dict[str, str]) -> str:
    common = (
        "strictly preserve the exact vertical 9:16 composition, camera angle, perspective, room identity, "
        "furniture layout, object positions, wall/floor/window/door placement, line-art weight, soft illustrated "
        "anime visual-novel background style, clean Aiko home map feeling, and the original cozy apartment materials"
    )
    per_room = {
        "entryway": "entry door, wall lamps, shoe cabinet, shoe rack, pink floor mat, plant, framed wall art, and tiled floor",
        "kitchen": "refrigerator, cabinets, range hood, stove, oven, sink, microwave, countertop items, table edge, plant, and pink floor mat",
        "bathroom": "bathtub, shower fixture, sink cabinet, mirror, wall lamp, towel, pink bath mat, toilet edge, window, and framed art",
        "bedroom": "bed, pillows, blanket, bedside table, lamp, curtains, window, wall art, pink textiles, and floor layout",
        "living": "sofa, coffee table, rug, plant, doorway, cabinet, wall art, curtains, window light direction, and visible adjoining room",
        "balcony": "balcony railing, tile floor, small round table, chair, cup, potted plants, curtains, window frame, city/trees outside",
    }
    return f"{common}; preserve the {per_room[room['key']]}."


def build_prompt(room: dict[str, str], variant: str) -> str:
    keep = room_keep_clause(room)
    if variant == "afternoon":
        change = (
            "Change only the time-of-day lighting into a restrained bright afternoon variant. "
            "Use clean natural daylight, soft window or doorway light from the original light direction, and very gentle afternoon shadows. "
            "Keep the cream walls, pale pink textiles, natural wood, and floor colors readable and close to the input. "
            "The scene may be slightly warmer than the original but must not become sunset, gold, orange, yellow, or darker."
        )
        avoid = (
            "Avoid: new furniture, removed furniture, moved objects, different room, characters, pets, UI, map pins, text, logos, watermarks, "
            "photorealism, 3D render, top-down map view, isometric view, sunset, golden hour, strong orange light, yellow cast, heavy contrast, dark shadows."
        )
        zh = "下午差分：明亮干净，轻微暖色即可，不要太黑，不要太黄，不要夕阳。"
    elif variant == "night":
        change = (
            "Change only the time-of-day lighting into a readable cozy evening/night variant. "
            "Keep the room bright enough to inspect all furniture and structural details. "
            "Use restrained warm indoor lamps and a subtle cool blue-gray hint outside windows or balcony openings. "
            "Do not crush shadows; the walls, floor, furniture silhouettes, and pink/wood material colors must remain clear. "
            "Warm indoor light is allowed, but it must be soft and controlled, not yellow."
        )
        avoid = (
            "Avoid: new furniture, removed furniture, moved objects, different room, characters, pets, UI, map pins, text, logos, watermarks, "
            "photorealism, 3D render, top-down map view, isometric view, deep black shadows, dark navy wash, purple cast, cyberpunk neon, large glowing areas, yellow/orange cast."
        )
        zh = "晚上差分：夜晚但要明亮可读，不要太黑，不要太黄，不要偏紫，不要赛博霓虹。"
    else:
        raise ValueError(variant)
    return (
        f"Edit Image 1 into a time-of-day differential image for {room['title']}.\n"
        f"Use case: lighting-weather edit for a home map room background.\n"
        f"Primary request: {zh}\n"
        f"Keep unchanged: {keep}\n"
        f"Change only: {change}\n"
        f"{avoid}\n"
        "Output: a polished vertical PNG-style image in the same soft illustrated anime visual-novel background style, with no extra elements."
    )


def build_tasks() -> list[dict[str, Any]]:
    tasks = []
    for room in ROOMS:
        source_path = ROOT / room["source"]
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        for variant in ("afternoon", "night"):
            tasks.append(
                {
                    "key": f"{room['key']}_{variant}",
                    "room_key": room["key"],
                    "label": room["label"],
                    "title": room["title"],
                    "variant": variant,
                    "source": room["source"],
                    "source_url": asset_url(room["source"]),
                    "prompt": build_prompt(room, variant),
                    "final_name": f"home_{room['key']}_{variant}_diff.png",
                }
            )
    return tasks


def read_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {}
    return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))


def write_progress(progress: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def submit_task(task: dict[str, Any], provider: dict[str, str]) -> dict[str, Any]:
    payload = {
        "prompt": task["prompt"],
        "provider_id": provider["id"],
        "model": provider["model"],
        "size": SIZE,
        "quality": QUALITY,
        "n": 1,
        "reference_images": [
            {
                "url": task["source_url"],
                "name": Path(task["source"]).name,
                "role": "Image 1: exact edit target. Preserve composition and room layout; change only time-of-day lighting.",
            }
        ],
    }
    created = http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
    task_id = created.get("task_id")
    if not task_id:
        raise RuntimeError(f"missing task_id: {created}")
    return created


def poll_task(task_id: str) -> dict[str, Any]:
    deadline = time.time() + TASK_DEADLINE_SECONDS
    while True:
        state = http_json("GET", f"/api/canvas-image-tasks/{task_id}", timeout=60)
        status = str(state.get("status") or "").lower()
        if status in {"succeeded", "success", "done", "completed", "failed", "error", "canceled", "cancelled"}:
            return state
        if time.time() >= deadline:
            state = dict(state)
            state["status"] = "still_pending_after_deadline"
            state["error"] = f"waited more than {TASK_DEADLINE_SECONDS} seconds"
            return state
        time.sleep(POLL_INTERVAL_SECONDS)


def copy_result(task: dict[str, Any], result_url: str) -> Path:
    src = local_path_from_url(result_url)
    if not src or not src.exists():
        raise FileNotFoundError(f"result file not found for {result_url}")
    dest = OUT_DIR / task["final_name"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def run_one(task: dict[str, Any], force: bool = False) -> dict[str, Any]:
    final_path = OUT_DIR / task["final_name"]
    if final_path.exists() and not force:
        return {
            "key": task["key"],
            "status": "already_done",
            "final_path": str(final_path),
            "source": task["source"],
            "variant": task["variant"],
        }

    attempts = []
    for provider in PROVIDER_POOL:
        attempt: dict[str, Any] = {
            "provider_id": provider["id"],
            "provider_name": provider["name"],
            "model": provider["model"],
            "submitted_at": now_ms(),
        }
        try:
            created = submit_task(task, provider)
            attempt["task_id"] = created.get("task_id")
            attempt["submit"] = created
            state = poll_task(created["task_id"])
            attempt["result_state"] = state
            status = str(state.get("status") or "").lower()
            urls = (state.get("result") or {}).get("images") or []
            if status == "succeeded" and urls:
                final_path = copy_result(task, urls[0])
                attempt["copied_from_url"] = urls[0]
                attempt["final_path"] = str(final_path)
                attempts.append(attempt)
                return {
                    "key": task["key"],
                    "status": "succeeded",
                    "final_path": str(final_path),
                    "source": task["source"],
                    "source_url": task["source_url"],
                    "variant": task["variant"],
                    "provider_id": provider["id"],
                    "provider_name": provider["name"],
                    "model": provider["model"],
                    "task_id": created.get("task_id"),
                    "asset_url": urls[0],
                    "attempts": attempts,
                }
            attempt["error"] = state.get("error") or status or "no image returned"
        except Exception as exc:
            attempt["error"] = str(exc)
        attempts.append(attempt)

    return {
        "key": task["key"],
        "status": "failed",
        "source": task["source"],
        "source_url": task["source_url"],
        "variant": task["variant"],
        "attempts": attempts,
    }


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_contact_sheet(results: dict[str, Any]) -> Path:
    cell_w, cell_h = 250, 444
    label_h = 34
    gap_x, gap_y = 26, 26
    margin = 24
    cols = 3
    rows = len(ROOMS)
    width = margin * 2 + cols * cell_w + (cols - 1) * gap_x
    height = margin * 2 + rows * (cell_h + label_h) + (rows - 1) * gap_y
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = load_font(16)
    small = load_font(13)
    headings = ["source", "afternoon", "night"]
    for row, room in enumerate(ROOMS):
        y = margin + row * (cell_h + label_h + gap_y)
        paths = [
            ROOT / room["source"],
            OUT_DIR / f"home_{room['key']}_afternoon_diff.png",
            OUT_DIR / f"home_{room['key']}_night_diff.png",
        ]
        for col, path in enumerate(paths):
            x = margin + col * (cell_w + gap_x)
            if path.exists():
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    im.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
                    px = x + (cell_w - im.width) // 2
                    py = y + (cell_h - im.height) // 2
                    sheet.paste(im, (px, py))
            else:
                draw.rectangle([x, y, x + cell_w, y + cell_h], outline=(180, 180, 180), width=2)
                draw.text((x + 12, y + 14), "missing", fill=(160, 0, 0), font=font)
            label = f"{room['label']} / {headings[col]}"
            draw.text((x, y + cell_h + 8), label, fill=(0, 0, 0), font=small)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sheet.save(CONTACT_SHEET_PATH)
    return CONTACT_SHEET_PATH


def selected_tasks(all_tasks: list[dict[str, Any]], only: list[str]) -> list[dict[str, Any]]:
    if not only:
        return all_tasks
    keys = set(only)
    out = [task for task in all_tasks if task["key"] in keys or task["room_key"] in keys or f"{task['room_key']}:{task['variant']}" in keys]
    missing = sorted(keys - {task["key"] for task in out} - {task["room_key"] for task in out} - {f"{task['room_key']}:{task['variant']}" for task in out})
    if missing:
        raise ValueError(f"unknown --only value(s): {', '.join(missing)}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", default=[], help="Task key, room key, or room:variant, e.g. entryway:afternoon")
    parser.add_argument("--force", action="store_true", help="Regenerate even if stable output file exists")
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()

    all_tasks = build_tasks()
    tasks = selected_tasks(all_tasks, args.only)
    progress = read_progress() or {
        "started_at": now_ms(),
        "base": BASE,
        "size": SIZE,
        "quality": QUALITY,
        "provider_pool": PROVIDER_POOL,
        "results": {},
    }
    progress["updated_at"] = now_ms()
    progress["requested_task_count"] = len(tasks)
    progress["out_dir"] = str(OUT_DIR)
    write_progress(progress)

    workers = max(1, min(8, int(args.max_workers or 1), len(tasks)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(run_one, task, args.force): task for task in tasks}
        for future in concurrent.futures.as_completed(future_map):
            task = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"key": task["key"], "status": "failed", "error": str(exc), "source": task["source"], "variant": task["variant"]}
            progress["results"][task["key"]] = result
            progress["updated_at"] = now_ms()
            write_progress(progress)
            error = result.get("error")
            if not error and result.get("attempts"):
                error = result["attempts"][-1].get("error")
            print(json.dumps({"key": task["key"], "status": result.get("status"), "final_path": result.get("final_path"), "error": error}, ensure_ascii=False), flush=True)

    contact_sheet = make_contact_sheet(progress["results"])
    progress["contact_sheet"] = str(contact_sheet)
    progress["finished_at"] = now_ms()
    success_statuses = {"succeeded", "already_done", "local_fallback"}
    progress["summary"] = {
        "succeeded": sum(1 for value in progress["results"].values() if value.get("status") in success_statuses),
        "failed": sum(1 for value in progress["results"].values() if value.get("status") == "failed"),
        "expected_total": len(all_tasks),
    }
    write_progress(progress)
    print(json.dumps({"progress": str(PROGRESS_PATH), "contact_sheet": str(contact_sheet), "summary": progress["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
