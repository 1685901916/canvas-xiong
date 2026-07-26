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
OUT_DIR = ROOT / "output" / "codex_home_room_night_regen_v2_20260621"
PROGRESS_PATH = OUT_DIR / "progress.json"
CONTACT_SHEET_PATH = OUT_DIR / "home_room_night_regen_v2_contact_sheet.png"
SIZE = "864x1536"
QUALITY = "auto"
TASK_DEADLINE_SECONDS = 1800
POLL_INTERVAL_SECONDS = 2.5

PROVIDER_POOL = [
    {"id": "custom-api-4", "name": "API", "model": "gpt-image-2-vip"},
    {"id": "custom-api-4", "name": "API", "model": "gpt-image-2-all"},
    {"id": "custom-api-2", "name": "65535", "model": "gpt-image-2"},
    {"id": "custom-api-8", "name": "krill", "model": "gpt-image-2"},
    {"id": "custom-api-3", "name": "nexus", "model": "gpt-image-2"},
]

ROOMS = [
    ("entryway", "01_entryway", "家地图玄关背景图", "assets/input/ai_ref_5841485f5218.png"),
    ("kitchen", "02_kitchen", "家地图厨房背景图", "assets/input/ai_ref_61d9c9d5b2d2.png"),
    ("bathroom", "03_bathroom", "家地图浴室背景图", "assets/input/ai_ref_eaaa113a6ee2.png"),
    ("bedroom", "04_bedroom", "家地图卧室背景图", "assets/input/ai_ref_d3f7f4d68b3a.png"),
    ("living", "05_living", "家地图客厅背景图", "assets/input/ai_ref_b28317689c0b.png"),
    ("balcony", "06_balcony", "家地图阳台背景图", "assets/input/ai_ref_bbf7124625e3.png"),
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


def room_keep_clause(room_key: str) -> str:
    details = {
        "entryway": "entry door, wall lamps, shoe cabinet, shoe rack, pink floor mat, plant, framed wall art, tiled floor",
        "kitchen": "refrigerator, cabinets, range hood, stove, oven, sink, microwave, countertop objects, table edge, plant, pink floor mat",
        "bathroom": "bathtub, shower fixture, sink cabinet, mirror, wall lamp, towel, pink bath mat, toilet edge, window, framed art",
        "bedroom": "bed, pillows, blanket, bedside table, lamp, curtains, window, wall art, pink textiles, floor layout",
        "living": "sofa, coffee table, rug, plant, doorway, cabinet, wall art, curtains, window, visible adjoining room",
        "balcony": "balcony railing, tile floor, small round table, chair, cup, potted plants, curtains, window frame, trees and city outside",
    }
    return (
        "preserve the exact vertical 9:16 composition, camera angle, perspective, room identity, furniture layout, "
        "object positions, wall/floor/window/door placement, line-art weight, soft illustrated anime visual-novel background style, "
        f"and these room anchors: {details[room_key]}"
    )


def prompt_for(room_key: str, title: str) -> str:
    return (
        f"Regenerate a NEW evening time-difference image from Image 1 for {title}. This must be a newly rendered image, not a color filter or color grade.\n"
        "Use case: polished mobile-game home map room background. The result must look cute, clean, gentle, and usable in a cozy home map UI.\n"
        f"Keep unchanged: {room_keep_clause(room_key)}.\n"
        "Preserve the original art direction: soft anime visual-novel background, delicate watercolor-like shading, cream walls, soft peach/pink textiles, warm natural wood, clean thin linework, airy domestic mood, low contrast, no dirty gray cast.\n"
        "Change only the time-of-day and lighting into a light blue-hour / early evening home-map variant. "
        "The window or balcony exterior should show gentle muted blue twilight so the time difference is clear. "
        "The interior should stay bright, pretty, pastel, and easy to inspect, almost as readable as the source image. "
        "Use small soft ivory lamp glow as accents only; keep the main room exposure clean and luminous. "
        "Shadows must be very soft open blue-gray midtones, not dark pools. Keep all pink mats, bedding, curtains, wood cabinets, plants, walls, floor, and small objects attractive and visible.\n"
        "Aesthetic target: not realistic night photography, not cinematic, not horror, not moody, not dramatic. "
        "It should feel like a high-quality cute mobile game home background with a mild evening-time difference.\n"
        "Avoid: ugly dirty gray, muddy brown, strong yellow/orange/amber/sepia cast, purple cast, black corners, vignette, high contrast, deep shadows, underexposed balcony, dark navy wash, harsh lamp bloom, overexposed white fog, simple filter/color grading look, new furniture, removed furniture, moved objects, different room, characters, pets, UI, map pins, text, logo, watermark, photorealism, 3D render, top-down map view, isometric view, cyberpunk neon."
    )


def build_tasks() -> list[dict[str, Any]]:
    tasks = []
    for key, label, title, rel_source in ROOMS:
        source_path = ROOT / rel_source
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        tasks.append(
            {
                "key": f"{key}_night_regen",
                "room_key": key,
                "label": label,
                "title": title,
                "source": rel_source,
                "source_url": asset_url(rel_source),
                "prompt": prompt_for(key, title),
                "final_name": f"home_{key}_night_regen.png",
            }
        )
    return tasks


def write_progress(progress: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_PATH)


def read_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.exists():
        return {}
    return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))


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
                "role": "Image 1: exact edit target. Generate a new clean bright blue-hour evening variant from this source, not from any previous night output.",
            }
        ],
    }
    created = http_json("POST", "/api/canvas-image-tasks", payload, timeout=90)
    if not created.get("task_id"):
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


def copy_result(task: dict[str, Any], url: str) -> Path:
    src = local_path_from_url(url)
    if not src or not src.exists():
        raise FileNotFoundError(f"result file not found for {url}")
    dest = OUT_DIR / task["final_name"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def run_one(task: dict[str, Any], force: bool = False) -> dict[str, Any]:
    final_path = OUT_DIR / task["final_name"]
    if final_path.exists() and not force:
        return {"key": task["key"], "status": "already_done", "final_path": str(final_path)}
    attempts = []
    for provider in PROVIDER_POOL:
        attempt = {"provider_id": provider["id"], "provider_name": provider["name"], "model": provider["model"], "submitted_at": now_ms()}
        try:
            created = submit_task(task, provider)
            attempt["task_id"] = created.get("task_id")
            state = poll_task(created["task_id"])
            attempt["result_state"] = state
            status = str(state.get("status") or "").lower()
            urls = (state.get("result") or {}).get("images") or []
            if status == "succeeded" and urls:
                final_path = copy_result(task, urls[0])
                attempt["copied_from_url"] = urls[0]
                attempts.append(attempt)
                return {
                    "key": task["key"],
                    "status": "succeeded",
                    "final_path": str(final_path),
                    "source": task["source"],
                    "source_url": task["source_url"],
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
    return {"key": task["key"], "status": "failed", "source": task["source"], "attempts": attempts}


def load_font(size: int) -> ImageFont.ImageFont:
    for path in ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_contact_sheet() -> Path:
    cell_w, cell_h = 250, 444
    label_h = 34
    gap_x, gap_y = 26, 26
    margin = 24
    cols = 3
    rows = len(ROOMS)
    sheet = Image.new("RGB", (margin * 2 + cols * cell_w + (cols - 1) * gap_x, margin * 2 + rows * (cell_h + label_h) + (rows - 1) * gap_y), "white")
    draw = ImageDraw.Draw(sheet)
    font = load_font(13)
    rejected_dir = ROOT / "output" / "codex_home_room_night_regen_20260621"
    for row, (key, label, _title, rel_source) in enumerate(ROOMS):
        paths = [
            ROOT / rel_source,
            rejected_dir / f"home_{key}_night_regen.png",
            OUT_DIR / f"home_{key}_night_regen.png",
        ]
        labels = [f"{label} / source", f"{label} / rejected", f"{label} / v2"]
        y = margin + row * (cell_h + label_h + gap_y)
        for col, path in enumerate(paths):
            x = margin + col * (cell_w + gap_x)
            if path.exists():
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    im.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
                    sheet.paste(im, (x + (cell_w - im.width) // 2, y + (cell_h - im.height) // 2))
            else:
                draw.rectangle([x, y, x + cell_w, y + cell_h], outline=(180, 180, 180), width=2)
                draw.text((x + 12, y + 14), "missing", fill=(160, 0, 0), font=font)
            draw.text((x, y + cell_h + 8), labels[col], fill=(0, 0, 0), font=font)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sheet.save(CONTACT_SHEET_PATH)
    return CONTACT_SHEET_PATH


def selected_tasks(tasks: list[dict[str, Any]], only: list[str]) -> list[dict[str, Any]]:
    if not only:
        return tasks
    wanted = set(only)
    selected = [task for task in tasks if task["room_key"] in wanted or task["key"] in wanted]
    if not selected:
        raise ValueError(f"no matching tasks for {only}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    args = parser.parse_args()
    tasks = selected_tasks(build_tasks(), args.only)
    progress = read_progress() or {"started_at": now_ms(), "base": BASE, "size": SIZE, "quality": QUALITY, "provider_pool": PROVIDER_POOL, "results": {}}
    progress["updated_at"] = now_ms()
    progress["requested_task_count"] = len(tasks)
    write_progress(progress)
    workers = max(1, min(4, args.max_workers, len(tasks)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(run_one, task, args.force): task for task in tasks}
        for future in concurrent.futures.as_completed(future_map):
            task = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"key": task["key"], "status": "failed", "error": str(exc), "source": task["source"]}
            progress["results"][task["key"]] = result
            progress["updated_at"] = now_ms()
            write_progress(progress)
            error = result.get("error")
            if not error and result.get("attempts"):
                error = result["attempts"][-1].get("error")
            print(json.dumps({"key": task["key"], "status": result.get("status"), "final_path": result.get("final_path"), "error": error}, ensure_ascii=False), flush=True)
    contact = make_contact_sheet()
    progress["contact_sheet"] = str(contact)
    progress["summary"] = {
        "succeeded": sum(1 for value in progress["results"].values() if value.get("status") in {"succeeded", "already_done"}),
        "failed": sum(1 for value in progress["results"].values() if value.get("status") == "failed"),
        "expected_total": len(ROOMS),
    }
    progress["finished_at"] = now_ms()
    write_progress(progress)
    print(json.dumps({"progress": str(PROGRESS_PATH), "contact_sheet": str(contact), "summary": progress["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
