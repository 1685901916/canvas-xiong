from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


CANVAS_ID = "7e4c506edfe84dd59473e3997fc58442"


def item_key(item):
    if isinstance(item, dict):
        return item.get("url") or item.get("task_id") or json.dumps(item, sort_keys=True, ensure_ascii=False)
    return str(item)


def restore_output_node(node, restored_at):
    images = list(node.get("images") or [])
    rejected = list(node.get("rejectedImages") or [])
    if not rejected:
        return 0

    seen = {item_key(item) for item in images}
    restored = 0
    for item in rejected:
        key = item_key(item)
        if key in seen:
            continue
        restored_item = deepcopy(item)
        if isinstance(restored_item, dict):
            restored_item.setdefault("reviewStatus", "previous_or_rejected")
            restored_item["visibleArchive"] = True
            restored_item["restoredToVisibleImagesAt"] = restored_at
        images.append(restored_item)
        seen.add(key)
        restored += 1

    if restored:
        node["images"] = images
        node["w"] = node.get("w") or 760
        node["h"] = node.get("h") or 680
        node["visibilityRestoredAt"] = restored_at
        node["visibleImageCount"] = len(images)
        node["hiddenRejectedImageCount"] = len(rejected)
        name = str(node.get("name") or node.get("id") or "Output")
        if " | visible " not in name:
            node["name"] = f"{name} | visible {len(images)} incl history"
    return restored


def main():
    root = Path(__file__).resolve().parents[1]
    canvas_path = root / "data" / "canvases" / f"{CANVAS_ID}.json"
    backups_dir = root / "data" / "canvases" / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    raw = canvas_path.read_text(encoding="utf-8")
    canvas = json.loads(raw)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backups_dir / f"{CANVAS_ID}.before-restore-visible-output-{stamp}.bak"
    backup_path.write_text(raw, encoding="utf-8")

    restored_at = datetime.now(timezone.utc).isoformat()
    total_restored = 0
    touched = []

    for node in canvas.get("nodes", []):
        if node.get("type") != "output":
            continue
        restored = restore_output_node(node, restored_at)
        if restored:
            total_restored += restored
            touched.append(
                {
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "restored": restored,
                    "visible": len(node.get("images") or []),
                    "rejected": len(node.get("rejectedImages") or []),
                }
            )

    if total_restored:
        canvas["updated_at"] = int(datetime.now().timestamp() * 1000)
        canvas.setdefault("nodes", []).append(
            {
                "id": f"log_restore_visible_outputs_{stamp}",
                "type": "canvas-organization",
                "message": "Restored previous/rejected generated images into visible output images. rejectedImages alone is not rendered by the current frontend.",
                "at": int(datetime.now().timestamp() * 1000),
                "canvas": CANVAS_ID,
                "restored_image_count": total_restored,
                "touched_outputs": touched,
            }
        )
        canvas_path.write_text(json.dumps(canvas, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"backup": str(backup_path), "restored": total_restored, "outputs": touched}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
