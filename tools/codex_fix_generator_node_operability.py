import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = "http://127.0.0.1:3001"
CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"
ROOT = Path(__file__).resolve().parents[1]
CANVAS_PATH = ROOT / "data" / "canvases" / f"{CANVAS_ID}.json"
BACKUP_DIR = ROOT / "data" / "canvases" / "backups"

RELEVANT_NAME_RE = (
    "浅草|迪士尼|歌舞伎町|城堡|海盗|雷门|五重塔|今户|"
    "不忍池|东京国立|明治|东京都厅|御苑|上野"
)

GEN_W = 380
GEN_H = 560
GEN_X_GAP = 430
LANE_X_GAP = 80
OUTPUT_W = 760
OUTPUT_H = 680


def http_json(method, path, data=None, timeout=120):
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
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
        "client_id": "codex-fix-generator-operability",
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)["canvas"]


def node_map(canvas):
    return {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}


def output_id_for_generator(gen, connections):
    if gen.get("targetOutputId"):
        return gen["targetOutputId"]
    gen_id = gen.get("id")
    for conn in connections:
        if conn.get("from") == gen_id:
            return conn.get("to")
    return None


def group_id_for_generator(gen, connections):
    inputs = gen.get("inputs") or []
    for item in inputs:
        if isinstance(item, str) and ":" in item:
            return item.split(":", 1)[0]
    gen_id = gen.get("id")
    for conn in connections:
        if conn.get("to") == gen_id:
            return conn.get("from")
    return None


def visible_image_count(node):
    count = 0
    for item in node.get("images") or []:
        url = ""
        if isinstance(item, dict):
            url = str(item.get("url") or item.get("src") or "")
        elif isinstance(item, str):
            url = item
        if url and not url.startswith("failed://") and not url.startswith("pending://"):
            count += 1
    return count


def is_relevant_small_generator(node):
    if node.get("type") != "generator":
        return False
    if float(node.get("w") or 0) > 230 or float(node.get("h") or 0) > 130:
        return False
    name = str(node.get("name") or "")
    import re

    return bool(re.search(RELEVANT_NAME_RE, name))


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-generator-operability-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(CANVAS_PATH, backup_path)

    canvas = load_canvas()
    nodes = canvas.get("nodes") or []
    connections = canvas.get("connections") or []
    by_id = node_map(canvas)
    small_generators = [node for node in nodes if is_relevant_small_generator(node)]

    lanes = {}
    for gen in small_generators:
        output_id = output_id_for_generator(gen, connections)
        group_id = group_id_for_generator(gen, connections)
        if not output_id or not group_id:
            continue
        lanes.setdefault(output_id, {"group_id": group_id, "generators": []})["generators"].append(gen)

    before_counts = {
        output_id: visible_image_count(by_id[output_id])
        for output_id in lanes
        if output_id in by_id and by_id[output_id].get("type") == "output"
    }

    fixed = 0
    for output_id, lane in lanes.items():
        group = by_id.get(lane["group_id"])
        output = by_id.get(output_id)
        if not group or not output:
            continue
        group_x = float(group.get("x") or 0)
        group_y = float(group.get("y") or 0)
        group_w = float(group.get("w") or 1120)
        gen_x0 = group_x + group_w + LANE_X_GAP
        gen_y = group_y + 35
        generators = sorted(
            lane["generators"],
            key=lambda node: (
                float(node.get("y") or 0),
                float(node.get("x") or 0),
                str(node.get("apiProvider") or ""),
            ),
        )
        for index, gen in enumerate(generators):
            gen["x"] = gen_x0 + index * GEN_X_GAP
            gen["y"] = gen_y
            gen["w"] = GEN_W
            gen["h"] = GEN_H
            fixed += 1
        output["x"] = gen_x0 + len(generators) * GEN_X_GAP + LANE_X_GAP
        output["y"] = group_y + 18
        output["w"] = OUTPUT_W
        output["h"] = OUTPUT_H

    logs = canvas.setdefault("logs", [])
    logs.insert(
        0,
        {
            "id": f"log_generator_operability_{int(time.time() * 1000)}",
            "type": "canvas-fix",
            "level": "info",
            "created_at": int(time.time() * 1000),
            "message": (
                f"恢复 {fixed} 个 API生成节点为完整可操作面板："
                f"{GEN_W}x{GEN_H}，保留原 output 图片和连线。"
            ),
        },
    )

    saved = save_canvas(canvas)
    saved_by_id = node_map(saved)
    after_small = [node for node in saved.get("nodes") or [] if is_relevant_small_generator(node)]
    after_counts = {
        output_id: visible_image_count(saved_by_id[output_id])
        for output_id in before_counts
        if output_id in saved_by_id
    }
    count_mismatches = {
        output_id: {"before": before_counts[output_id], "after": after_counts.get(output_id)}
        for output_id in before_counts
        if before_counts[output_id] != after_counts.get(output_id)
    }
    summary = {
        "canvas_id": CANVAS_ID,
        "backup": str(backup_path),
        "lanes": len(lanes),
        "fixed_generators": fixed,
        "remaining_relevant_small_generators": len(after_small),
        "output_count_mismatches": count_mismatches,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if after_small or count_mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
