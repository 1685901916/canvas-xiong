#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE = "http://127.0.0.1:3001"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "output" / "codex_home_room_time_triplets_20260621" / "selection_manifest.json"
CANVAS_TITLE = "家地图三时段成品 20260621"
CLIENT_ID = "codex-home-time-triplets-canvas"


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


def normalize_url(value: str) -> str:
    value = (value or "").replace("\\", "/")
    if value.startswith(("http://", "https://", "/", "data:image/")):
        return value
    return "/" + value.lstrip("/")


def image_node(node_id: str, x: int, y: int, url: str, name: str, w: int = 280, h: int = 498) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "image",
        "x": x,
        "y": y,
        "url": normalize_url(url),
        "name": name,
        "mediaKind": "image",
        "w": w,
        "h": h,
    }


def prompt_node(node_id: str, x: int, y: int, text: str, name: str, w: int, h: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "prompt",
        "x": x,
        "y": y,
        "text": text,
        "name": name,
        "w": w,
        "h": h,
    }


def build_nodes(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    created_at = now_ms()

    nodes.append(
        prompt_node(
            f"prompt_home_triplets_header_{created_at}",
            0,
            -180,
            "家地图三时段成品：上午=原始源图；下午/晚上=按用户红框选择的候选图。未重新套滤镜，未裁剪截图。",
            "家地图三时段成品说明",
            1440,
            110,
        )
    )
    overview_rel = "/output/codex_home_room_time_triplets_20260621/home_room_selected_morning_afternoon_night_overview.png"
    nodes.append(
        image_node(
            f"img_home_triplets_overview_{created_at}",
            0,
            80,
            overview_rel,
            "家地图上午下午晚上总览",
            w=430,
            h=1590,
        )
    )

    triptych_x = 520
    triptych_y = 80
    triptych_gap_y = 760
    for index, room in enumerate(manifest.get("rooms") or []):
        room_num = room.get("room_number") or f"{index + 1:02d}"
        room_name = room.get("room_name") or room.get("room_key") or f"room-{index + 1}"
        room_key = room.get("room_key") or f"room_{index + 1}"
        triptych = str(room.get("triptych") or "").replace("\\", "/")
        triptych_name = Path(triptych).name
        triptych_rel = f"/output/codex_home_room_time_triplets_20260621/triptychs/{triptych_name}"
        nodes.append(
            image_node(
                f"img_home_triplets_{room_key}_triptych_{created_at}",
                triptych_x,
                triptych_y + index * triptych_gap_y,
                triptych_rel,
                f"{room_num} {room_name} 上午下午晚上三联图",
                w=1056,
                h=658,
            )
        )
    return nodes


def find_or_create_canvas() -> dict[str, Any]:
    canvases = http_json("GET", "/api/canvases", timeout=60).get("canvases") or []
    for canvas in canvases:
        if canvas.get("title") == CANVAS_TITLE:
            return http_json("GET", f"/api/canvases/{canvas['id']}", timeout=60)["canvas"]
    return http_json("POST", "/api/canvases", {"title": CANVAS_TITLE, "icon": "image", "kind": "classic"}, timeout=60)["canvas"]


def save_canvas(canvas: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any]:
    logs = canvas.get("logs") or []
    logs.insert(
        0,
        {
            "id": f"log_home_triplets_canvas_{now_ms()}",
            "type": "canvas-organization",
            "title": "家地图三时段成品整理",
            "message": "按用户红框选择，将 6 个房间整理为上午、下午、晚上三列；图片来自源图和已生成输出，不使用截图裁剪。",
            "createdAt": now_ms(),
            "outputs": [],
            "platform": "codex",
        },
    )
    payload = {
        "title": CANVAS_TITLE,
        "icon": canvas.get("icon") or "image",
        "nodes": nodes,
        "connections": [],
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": logs[:500],
        "settings": canvas.get("settings") or {},
        "client_id": CLIENT_ID,
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{canvas['id']}", payload, timeout=120)["canvas"]


def verify_canvas(canvas: dict[str, Any]) -> dict[str, Any]:
    nodes = canvas.get("nodes") or []
    image_nodes = [node for node in nodes if node.get("type") == "image"]
    group_nodes = [node for node in nodes if node.get("type") == "group"]
    prompt_nodes = [node for node in nodes if node.get("type") == "prompt"]
    urls = [node.get("url") for node in image_nodes]
    issues = []
    if group_nodes:
        issues.append(f"group_count={len(group_nodes)}")
    if len(image_nodes) != 7:
        issues.append(f"image_count={len(image_nodes)}")
    if len([url for url in urls if "/triptychs/" in str(url)]) != 6:
        issues.append("triptych_count_mismatch")
    if not any(str(url).startswith("/output/codex_home_room_time_triplets_20260621/") for url in urls):
        issues.append("overview_missing")
    return {
        "canvas_title": canvas.get("title"),
        "canvas_id": canvas.get("id"),
        "canvas_url": f"{BASE}/static/canvas.html?canvas={canvas.get('id')}",
        "groups": len(group_nodes),
        "prompts": len(prompt_nodes),
        "images": len(image_nodes),
        "issues": issues,
    }


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    canvas = find_or_create_canvas()
    nodes = build_nodes(manifest)
    saved = save_canvas(canvas, nodes)
    print(json.dumps(verify_canvas(saved), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
