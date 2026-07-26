#!/usr/bin/env python3
"""Read-only health check for Infinite Canvas image-generation workflows."""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch_json(base_url: str, path: str, timeout: float = 10.0):
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def safe_fetch_json(base_url: str, path: str, label: str):
    try:
        return fetch_json(base_url, path)
    except urllib.error.HTTPError as exc:
        print(f"[warn] {label}: HTTP {exc.code}")
    except Exception as exc:
        print(f"[warn] {label}: {type(exc).__name__}: {exc}")
    return None


def redact_secrets(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"sk-[A-Za-z0-9_.*-]{6,}", "sk-***", text)
    text = re.sub(r"(?i)(api[_-]?key=)[^&\s]+", r"\1***", text)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9_.*-]{8,}", r"\1***", text)
    return text


def short(text: str, limit: int = 180) -> str:
    text = redact_secrets(text)
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def summarize_providers(base_url: str):
    data = safe_fetch_json(base_url, "/api/providers", "providers")
    providers = (data or {}).get("providers") or []
    image_providers = [
        p for p in providers
        if p.get("enabled", True) and (p.get("image_models") or [])
    ]
    keyed = [p for p in image_providers if p.get("has_key") is not False]
    print(f"\nProviders: {len(image_providers)} image-enabled, {len(keyed)} with public has_key=true/unknown")
    for p in image_providers:
        models = ", ".join((p.get("image_models") or [])[:3])
        print(
            f"  - {p.get('id')} | {p.get('name') or p.get('id')} | "
            f"has_key={p.get('has_key')} | primary={p.get('primary')} | models={models}"
        )


def summarize_tasks(base_url: str):
    data = safe_fetch_json(base_url, "/api/canvas-image-tasks", "canvas image task diagnostics")
    if not data:
        print("\nCanvas task diagnostics: unavailable")
        return
    active = data.get("active") or []
    history = data.get("history") or []
    print(
        "\nCanvas tasks: "
        f"active={len(active)} history={len(history)} concurrency={data.get('concurrency') or {}}"
    )
    statuses = collections.Counter(item.get("status") or "unknown" for item in active)
    if statuses:
        print("  active statuses:", dict(statuses))
    recent_failed = [
        item for item in active + history
        if item.get("status") == "failed" or item.get("error")
    ][:10]
    if recent_failed:
        print("  recent task errors:")
        for item in recent_failed:
            provider = item.get("resolved_provider_name") or item.get("requested_provider_name") or item.get("resolved_provider_id")
            model = item.get("resolved_model") or item.get("requested_model")
            print(
                f"    - {item.get('status')} | {provider} | {model} | "
                f"code={item.get('status_code') or ''} | {short(item.get('error'))}"
            )


def upstream_generator_counts(connections):
    upstream = collections.defaultdict(list)
    for conn in connections or []:
        upstream[conn.get("to")].append(conn.get("from"))
    return upstream


def summarize_canvas(base_url: str, canvas_id: str):
    data = safe_fetch_json(base_url, f"/api/canvases/{urllib.parse.quote(canvas_id)}", f"canvas {canvas_id}")
    canvas = (data or {}).get("canvas") or {}
    if not canvas:
        return
    nodes = canvas.get("nodes") or []
    connections = canvas.get("connections") or []
    logs = canvas.get("logs") or []
    by_type = collections.Counter(node.get("type") or "unknown" for node in nodes)
    outputs = [node for node in nodes if node.get("type") == "output"]
    generators = [node for node in nodes if node.get("type") == "generator"]
    unsized_outputs = [node for node in outputs if not node.get("w") or not node.get("h")]
    pending_outputs = [node for node in outputs if node.get("_pending")]
    failed_cards = [
        item for node in outputs for item in (node.get("images") or [])
        if isinstance(item, dict) and str(item.get("url") or "").startswith("failed://")
    ]
    failed_logs = [log for log in logs if log.get("status") == "failed" or log.get("error")]
    upstream = upstream_generator_counts(connections)
    output_upstream_issues = [
        node for node in outputs
        if len([source for source in upstream.get(node.get("id"), []) if source]) != 1
    ]
    print(f"\nCanvas: {canvas.get('title')} ({canvas.get('id')})")
    print(f"  nodes={len(nodes)} connections={len(connections)} types={dict(by_type)}")
    print(
        f"  generators={len(generators)} outputs={len(outputs)} "
        f"unsized_outputs={len(unsized_outputs)} pending_outputs={len(pending_outputs)} "
        f"failed_cards={len(failed_cards)} output_upstream_issues={len(output_upstream_issues)}"
    )
    if unsized_outputs:
        print("  unsized outputs:")
        for node in unsized_outputs[:8]:
            print(
                f"    - {node.get('id')} | {node.get('name') or ''} | "
                f"images={len(node.get('images') or [])}"
            )
    if failed_logs:
        grouped = collections.Counter(
            (
                log.get("platform") or "",
                log.get("model") or "",
                short(log.get("error"), 120),
            )
            for log in failed_logs
        )
        print("  recent failed logs:")
        for (platform, model, error), count in grouped.most_common(8):
            print(f"    - x{count} | {platform} | {model} | {error}")


def canvas_ids_from_list(base_url: str, limit: int):
    data = safe_fetch_json(base_url, "/api/canvases", "canvas list")
    canvases = (data or {}).get("canvases") or []
    return [item.get("id") for item in canvases[:limit] if item.get("id")]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:3001")
    parser.add_argument("--canvas-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=3, help="Canvas count to inspect when --canvas-id is omitted.")
    args = parser.parse_args(argv)

    print(f"Base URL: {args.base_url}")
    summarize_providers(args.base_url)
    summarize_tasks(args.base_url)
    ids = args.canvas_id or canvas_ids_from_list(args.base_url, max(1, args.limit))
    for canvas_id in ids:
        summarize_canvas(args.base_url, canvas_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
