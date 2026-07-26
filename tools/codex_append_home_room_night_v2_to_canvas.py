#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = ROOT / "output" / "codex_home_room_night_regen_v2_20260621" / "progress.json"
CANVAS_PATH = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"

ROOMS = [
    ("entryway_night_regen", "01 玄关 晚上 v2"),
    ("kitchen_night_regen", "02 厨房 晚上 v2"),
    ("bathroom_night_regen", "03 浴室 晚上 v2"),
    ("bedroom_night_regen", "04 卧室 晚上 v2"),
    ("living_night_regen", "05 客厅 晚上 v2"),
    ("balcony_night_regen", "06 阳台 晚上 v2"),
]


def now_ms() -> int:
    return int(time.time() * 1000)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}_{now_ms()}"


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
        raise RuntimeError(f"{method} {path} HTTP {exc.code}: {detail[:1000]}") from exc
    return json.loads(raw.decode("utf-8")) if raw else {}


def load_canvas() -> dict[str, Any]:
    return http_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]


def save_canvas(canvas: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "title": canvas.get("title") or "背景图",
        "icon": canvas.get("icon") or "image",
        "kind": canvas.get("kind") or "classic",
        "owner": canvas.get("owner") or "",
        "color": canvas.get("color") or "",
        "pinned": bool(canvas.get("pinned") or False),
        "nodes": canvas.get("nodes") or [],
        "connections": canvas.get("connections") or [],
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": (canvas.get("logs") or [])[:500],
        "settings": canvas.get("settings") or {},
        "client_id": "codex-home-room-night-v2-append",
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)["canvas"]


def backup_canvas_file() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"{CANVAS_ID}.before-home-room-night-v2-{stamp}.bak"
    if CANVAS_PATH.exists():
        shutil.copy2(CANVAS_PATH, dest)
    return dest


def image_url_value(node: dict[str, Any]) -> str:
    value = node.get("url")
    if isinstance(value, str):
        return value
    return ""


def main() -> None:
    progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    results = progress.get("results") or {}
    missing = [key for key, _label in ROOMS if not (results.get(key) or {}).get("asset_url")]
    if missing:
        raise RuntimeError(f"missing generated asset urls: {missing}")

    canvas = load_canvas()
    if canvas.get("id") != CANVAS_ID or canvas.get("title") != "背景图":
        raise RuntimeError(f"unexpected canvas: {canvas.get('title')} {canvas.get('id')}")

    nodes = canvas.setdefault("nodes", [])
    existing_urls = {image_url_value(node) for node in nodes if node.get("type") == "image"}
    urls = [(key, label, results[key]["asset_url"]) for key, label in ROOMS]
    already = [url for _key, _label, url in urls if url in existing_urls]
    if len(already) == len(urls):
        print(json.dumps({"status": "already_present", "canvas_id": CANVAS_ID, "urls": already}, ensure_ascii=False, indent=2))
        return

    backup = backup_canvas_file()

    # Keep this review set in the first screen. This canvas is very large, so
    # appending to the end or below the fold makes the result look missing.
    origin_x = 820
    origin_y = 80
    cell_w = 180
    cell_h = 320
    gap_x = 26

    title = {
        "id": uid("prompt"),
        "type": "prompt",
        "x": origin_x,
        "y": origin_y,
        "w": 1020,
        "h": 110,
        "name": "家地图晚上差分 v2｜新生成图",
        "text": "这组是重新生成的晚上/蓝调入夜差分，不是本地滤镜。目标：家地图可用、明亮可读、不要太黑、不要太黄。",
        "source": "codex_home_room_night_regen_v2",
    }
    nodes.append(title)

    item_ids = [title["id"]]
    added = []
    for index, (key, label, url) in enumerate(urls):
        if url in existing_urls:
            continue
        node = {
            "id": uid("img"),
            "type": "image",
            "x": origin_x + index * (cell_w + gap_x),
            "y": origin_y + 150,
            "w": cell_w,
            "h": cell_h,
            "url": url,
            "name": label,
            "role": "家地图晚上差分 v2 新生成图",
            "source": "codex_home_room_night_regen_v2",
            "createdAt": now_ms(),
            "task_id": results[key].get("task_id") or "",
            "provider_id": results[key].get("provider_id") or "",
            "provider_name": results[key].get("provider_name") or "",
            "model": results[key].get("model") or "",
        }
        nodes.append(node)
        item_ids.append(node["id"])
        added.append({"name": label, "url": url, "id": node["id"]})

    group = {
        "id": uid("grp"),
        "type": "group",
        "x": origin_x - 40,
        "y": origin_y - 40,
        "w": 1320,
        "h": 560,
        "items": item_ids,
        "name": "家地图晚上差分 v2｜6张新生成图",
        "source": "codex_home_room_night_regen_v2",
    }
    nodes.append(group)

    canvas["viewport"] = {"x": 0, "y": 0, "scale": 1}
    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_home_room_night_v2_{now_ms()}",
            "createdAt": now_ms(),
            "status": "done",
            "nodeType": "canvas-agent",
            "model": "codex_append_home_room_night_v2_to_canvas",
            "prompt": "Append six generated home-map night v2 images to the 背景图 canvas.",
            "outputs": [item["url"] for item in added],
            "error": "",
            "platform": "codex",
        },
    )
    canvas["logs"] = canvas["logs"][:500]

    saved = save_canvas(canvas)
    print(
        json.dumps(
            {
                "status": "appended",
                "canvas_id": CANVAS_ID,
                "canvas_title": saved.get("title"),
                "canvas_updated_at": saved.get("updated_at"),
                "backup": str(backup),
                "group": group,
                "added": added,
                "canvas_url": f"{BASE}/static/canvas.html?canvas={CANVAS_ID}",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
