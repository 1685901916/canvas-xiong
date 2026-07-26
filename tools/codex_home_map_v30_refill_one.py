#!/usr/bin/env python3
"""Refill one v30 two-floor candidate and rebuild contact sheet."""

from __future__ import annotations

import json

import codex_home_map_v21_normal_65535 as base
import codex_home_map_v22_from_v21_65535 as runner
import codex_home_map_v30_orderly_two_floor_65535  # noqa: F401 - configures runner state/sheet


def main() -> int:
    state = json.loads(runner.STATE_PATH.read_text(encoding="utf-8"))
    groups = state["groups"]
    results = runner.run(groups, count=1, concurrency=1)
    runner.append_results(results)
    sheet = runner.contact((state.get("runs") or []) + results)
    merged = {
        "canvas_id": base.CANVAS_ID,
        "canvas_url": base.CANVAS_URL,
        "backup": state.get("backup") or "",
        "groups": groups,
        "runs": (state.get("runs") or []) + results,
        "contact_sheet": sheet,
        "aiko_tmp_contact_sheet": str(base.AIKO_TMP_DIR / runner.SHEET_PATH.name),
        "completed_at": base.now_ms(),
    }
    runner.write_state(merged)
    print(json.dumps({"ok": True, "contact_sheet": sheet, "success": sum(1 for r in results if r.get("ok")), "total": len(results)}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
