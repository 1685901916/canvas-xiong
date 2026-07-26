#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
BATCH_ID = "codex-redbox-whitelist-afternoon-night-20260610"
ROOT = Path(__file__).resolve().parents[1]
CANVAS_PATH = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"
PROGRESS_PATH = ROOT / "output" / "codex_redbox_whitelist_diffs_progress.json"

ORIGIN_X = 15000
ORIGIN_Y = -800
COLUMNS = 4
ROW_H = 1000
COL_W = 3400
GROUP_W = 1120
GROUP_H = 560
GEN_W = 380
OUTPUT_W = 820
OUTPUT_H = 700


def now_ms() -> int:
    return int(time.time() * 1000)


def http_json(method: str, path: str, payload=None, timeout=120):
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


def load_canvas():
    return http_json("GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]


def save_canvas(canvas):
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
        "client_id": "codex-spread-redbox-diffs-layout",
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)["canvas"]


def node_map(canvas):
    return {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}


def output_url_value(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("url") or item.get("src") or "")
    return ""


def visible_count(output_node) -> int:
    return sum(
        1
        for item in (output_node.get("images") or [])
        if output_url_value(item)
        and not output_url_value(item).startswith("failed://")
        and not output_url_value(item).startswith("pending://")
    )


def requirement_order(canvas):
    if PROGRESS_PATH.exists():
        try:
            progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
            keys = list((progress.get("requirements") or {}).keys())
            if keys:
                return keys
        except Exception:
            pass
    groups = [
        node
        for node in canvas.get("nodes") or []
        if node.get("type") == "group" and node.get("codexBatchId") == BATCH_ID and node.get("codexRequirementKey")
    ]
    return [node.get("codexRequirementKey") for node in sorted(groups, key=lambda n: (float(n.get("y") or 0), float(n.get("x") or 0)))]


def find_node(canvas, req_key: str, node_type: str):
    for node in canvas.get("nodes") or []:
        if (
            node.get("type") == node_type
            and node.get("codexBatchId") == BATCH_ID
            and node.get("codexRequirementKey") == req_key
        ):
            return node
    return None


def verify_no_non_batch_overlap(canvas, bounds):
    rx1, ry1, rx2, ry2 = bounds
    hits = []
    for node in canvas.get("nodes") or []:
        if node.get("codexBatchId") == BATCH_ID:
            continue
        x = float(node.get("x") or 0)
        y = float(node.get("y") or 0)
        w = float(node.get("w") or 260)
        h = float(node.get("h") or 260)
        if x < rx2 and x + w > rx1 and y < ry2 and y + h > ry1:
            hits.append({"id": node.get("id"), "type": node.get("type"), "name": node.get("name")})
    return hits


def main():
    canvas = load_canvas()
    if canvas.get("id") != CANVAS_ID or canvas.get("title") != "背景图":
        raise RuntimeError(f"目标画布不匹配：{canvas.get('title')} {canvas.get('id')}")

    keys = requirement_order(canvas)
    if len(keys) != 32:
        raise RuntimeError(f"预期 32 个差分 workflow，实际找到 {len(keys)} 个。")

    rows_per_col = math.ceil(len(keys) / COLUMNS)
    bounds = (
        ORIGIN_X - 200,
        ORIGIN_Y - 320,
        ORIGIN_X + (COLUMNS - 1) * COL_W + GROUP_W + 140 + GEN_W + 140 + OUTPUT_W + 260,
        ORIGIN_Y + (rows_per_col - 1) * ROW_H + OUTPUT_H + 360,
    )
    overlaps = verify_no_non_batch_overlap(canvas, bounds)
    if overlaps:
        raise RuntimeError("目标布局区域存在非本批节点重叠：" + json.dumps(overlaps[:20], ensure_ascii=False))

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-spread-redbox-diffs-layout-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(CANVAS_PATH, backup_path)

    moved = 0
    for index, req_key in enumerate(keys):
        col = index // rows_per_col
        row = index % rows_per_col
        x0 = ORIGIN_X + col * COL_W
        y0 = ORIGIN_Y + row * ROW_H

        image = find_node(canvas, req_key, "image")
        prompt = find_node(canvas, req_key, "prompt")
        group = find_node(canvas, req_key, "group")
        gen = find_node(canvas, req_key, "generator")
        out = find_node(canvas, req_key, "output")
        if not all([image, prompt, group, gen, out]):
            raise RuntimeError(f"{req_key} 缺少 workflow 节点")

        image.update({"x": x0 + 34, "y": y0 + 92, "w": 320})
        prompt.update({"x": x0 + 400, "y": y0 + 92, "w": 660, "h": 390})
        group.update({"x": x0, "y": y0, "w": GROUP_W, "h": GROUP_H, "items": [image["id"], prompt["id"]]})
        gen.update({"x": x0 + GROUP_W + 140, "y": y0 + 35, "w": GEN_W, "h": 0})
        out.update({"x": gen["x"] + GEN_W + 140, "y": y0 + 20, "w": OUTPUT_W, "h": OUTPUT_H})
        moved += 5

    summary = next(
        (
            node
            for node in canvas.get("nodes") or []
            if node.get("type") == "prompt" and node.get("codexBatchId") == BATCH_ID and node.get("codexSummary")
        ),
        None,
    )
    if summary:
        summary.update({"x": ORIGIN_X, "y": ORIGIN_Y - 260, "w": 2200, "h": 190})
        moved += 1

    canvas.setdefault("logs", []).insert(
        0,
        {
            "id": f"codex_spread_redbox_layout_{now_ms()}",
            "createdAt": now_ms(),
            "status": "info",
            "nodeType": "canvas-layout",
            "model": "codex_spread_redbox_whitelist_diffs_layout",
            "prompt": "将红框白名单下午/晚上差分 workflow 从 2 列压缩排布整理为 4 列宽松排布；只移动节点，不重新生成，不删除图片。",
            "outputs": [],
            "error": "",
            "platform": "codex",
            "request": {
                "batch_id": BATCH_ID,
                "columns": COLUMNS,
                "rows_per_col": rows_per_col,
                "row_h": ROW_H,
                "col_w": COL_W,
                "output_size": [OUTPUT_W, OUTPUT_H],
                "backup": str(backup_path),
            },
        },
    )
    canvas["logs"] = canvas["logs"][:500]

    saved = save_canvas(canvas)
    saved_by = node_map(saved)
    counts = []
    errors = []
    for req_key in keys:
        group = find_node(saved, req_key, "group")
        gen = find_node(saved, req_key, "generator")
        out = find_node(saved, req_key, "output")
        if not group or not gen or not out:
            errors.append(f"{req_key}: missing after save")
            continue
        if gen.get("x", 0) <= group.get("x", 0) or out.get("x", 0) <= gen.get("x", 0):
            errors.append(f"{req_key}: x order invalid")
        counts.append(visible_count(saved_by.get(out["id"]) or {}))

    result = {
        "canvas_id": CANVAS_ID,
        "canvas_title": saved.get("title"),
        "backup": str(backup_path),
        "moved_nodes": moved,
        "workflow_count": len(keys),
        "layout": {"columns": COLUMNS, "rows_per_col": rows_per_col, "row_h": ROW_H, "col_w": COL_W},
        "accepted_total": sum(counts),
        "count_hist": {str(i): counts.count(i) for i in sorted(set(counts))},
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors or sum(counts) != 160:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
