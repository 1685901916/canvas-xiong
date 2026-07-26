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

GEN_W = 380
GEN_X_GAP = 80
OUTPUT_X_GAP = 80
OUTPUT_W = 760
OUTPUT_H = 680
KEEPER_PROVIDER_PRIORITY = [
    "custom-api-2",
    "custom-api-6",
    "custom-api-3",
    "apimart",
    "custom-api-5",
]


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
        "client_id": "codex-single-api-node-compact",
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return http_json("PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)["canvas"]


def node_map(canvas):
    return {node.get("id"): node for node in canvas.get("nodes") or [] if node.get("id")}


def output_id_for_generator(gen, by_id, connections):
    if gen.get("targetOutputId") and gen.get("targetOutputId") in by_id:
        return gen.get("targetOutputId")
    for conn in connections:
        if conn.get("from") == gen.get("id") and conn.get("to") in by_id:
            if by_id[conn["to"]].get("type") == "output":
                return conn["to"]
    return None


def group_id_for_generator(gen, by_id, connections):
    for item in gen.get("inputs") or []:
        if isinstance(item, str) and ":" in item:
            group_id = item.split(":", 1)[0]
            if group_id in by_id:
                return group_id
    for conn in connections:
        if conn.get("to") == gen.get("id") and conn.get("from") in by_id:
            if by_id[conn["from"]].get("type") == "group":
                return conn["from"]
    return None


def visible_image_count(node):
    count = 0
    for item in node.get("images") or []:
        if isinstance(item, dict):
            url = str(item.get("url") or item.get("src") or "")
        else:
            url = str(item or "")
        if url and not url.startswith("failed://") and not url.startswith("pending://"):
            count += 1
    return count


def provider_rank(gen):
    provider = str(gen.get("apiProvider") or "")
    try:
        rank = KEEPER_PROVIDER_PRIORITY.index(provider)
    except ValueError:
        rank = len(KEEPER_PROVIDER_PRIORITY)
    generated = len(gen.get("generatedOutputs") or [])
    return (rank, -generated, float(gen.get("x") or 0), float(gen.get("y") or 0))


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{CANVAS_ID}.before-single-api-compact-{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(CANVAS_PATH, backup_path)

    canvas = load_canvas()
    nodes = canvas.get("nodes") or []
    connections = canvas.get("connections") or []
    by_id = node_map(canvas)

    lanes = {}
    for gen in [node for node in nodes if node.get("type") == "generator"]:
        output_id = output_id_for_generator(gen, by_id, connections)
        if not output_id:
            continue
        lanes.setdefault(output_id, []).append(gen)

    duplicate_lanes = {output_id: gens for output_id, gens in lanes.items() if len(gens) > 1}
    before_counts = {
        output_id: visible_image_count(by_id[output_id])
        for output_id in duplicate_lanes
        if output_id in by_id
    }

    remove_ids = set()
    kept_ids = []
    for output_id, gens in duplicate_lanes.items():
        keep = sorted(gens, key=provider_rank)[0]
        kept_ids.append(keep["id"])
        removed = [gen for gen in gens if gen.get("id") != keep.get("id")]
        remove_ids.update(gen.get("id") for gen in removed if gen.get("id"))

        provider_pool = []
        for gen in gens:
            provider_pool.append(
                {
                    "id": gen.get("id"),
                    "apiProvider": gen.get("apiProvider"),
                    "model": gen.get("model"),
                    "name": gen.get("name"),
                    "generatedOutputs": gen.get("generatedOutputs") or [],
                    "wasVisibleNode": gen.get("id") == keep.get("id"),
                }
            )
        keep["providerPoolCandidates"] = provider_pool
        keep["canvasProviderMode"] = "single-visible-api-node"
        keep["targetOutputId"] = output_id
        keep["w"] = GEN_W
        keep.pop("h", None)
        keep.setdefault("count", 1)
        group_id = group_id_for_generator(keep, by_id, connections)
        output = by_id.get(output_id)
        group = by_id.get(group_id) if group_id else None
        if group and output:
            group_x = float(group.get("x") or 0)
            group_y = float(group.get("y") or 0)
            group_w = float(group.get("w") or 1120)
            keep["x"] = group_x + group_w + GEN_X_GAP
            keep["y"] = group_y + 35
            output["x"] = keep["x"] + GEN_W + OUTPUT_X_GAP
            output["y"] = group_y + 18
            output["w"] = output.get("w") or OUTPUT_W
            output["h"] = output.get("h") or OUTPUT_H

    if remove_ids:
        canvas["nodes"] = [node for node in nodes if node.get("id") not in remove_ids]
        canvas["connections"] = [
            conn
            for conn in connections
            if conn.get("from") not in remove_ids and conn.get("to") not in remove_ids
        ]

    logs = canvas.setdefault("logs", [])
    logs.insert(
        0,
        {
            "id": f"log_single_api_node_{int(time.time() * 1000)}",
            "type": "canvas-layout",
            "level": "info",
            "created_at": int(time.time() * 1000),
            "message": (
                f"按用户要求压缩 API 生成结构：{len(duplicate_lanes)} 个输出 lane "
                f"改为每组只显示 1 个 API生成节点；移除 {len(remove_ids)} 个重复 API 节点，"
                "保留 output 中所有图片。"
            ),
        },
    )

    saved = save_canvas(canvas)
    saved_by_id = node_map(saved)
    after_lanes = {}
    for gen in [node for node in saved.get("nodes") or [] if node.get("type") == "generator"]:
        output_id = output_id_for_generator(gen, saved_by_id, saved.get("connections") or [])
        if output_id:
            after_lanes.setdefault(output_id, []).append(gen)
    remaining_duplicate_lanes = {
        output_id: gens for output_id, gens in after_lanes.items() if len(gens) > 1 and output_id in duplicate_lanes
    }
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
        "compacted_lanes": len(duplicate_lanes),
        "kept_generators": len(kept_ids),
        "removed_generators": len(remove_ids),
        "remaining_duplicate_lanes": len(remaining_duplicate_lanes),
        "output_count_mismatches": count_mismatches,
        "total_generators_after": len([node for node in saved.get("nodes") or [] if node.get("type") == "generator"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if remaining_duplicate_lanes or count_mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
