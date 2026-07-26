import concurrent.futures
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canvasctl


BASE = "http://127.0.0.1:3001"
CANVAS_ID = "ed300ba67b364ed38573fb53ba4f690f"
ROOT = Path(__file__).resolve().parents[1]
PROGRESS_PATH = ROOT / "output" / "bg_diff_all_apis_progress.json"

COUNT_PER_OUTPUT = 7
CONCURRENCY = 16
TASK_TIMEOUT = 900
MAX_REFILL_ROUNDS = 2

SOURCE_IDS = [
    "img_e08fdf028d80d_1780929780594",
    "img_a1fae90c02007_1780929795009",
    "img_f523c7bbdcc34_1780931183913",
    "img_b241e232867be8_1780929983738",
    "img_937b44819db6a8_1780932416090",
]

PROVIDER_MODELS = {
    "modelscope": "Qwen/Qwen-Image-Edit-2511",
    "runninghub": "seedream-v5-lite/image-to-image",
    "custom-api-2": "gpt-image-2",
    "apimart": "gpt-image-2",
    "custom-api-8": "gpt-image-2",
    "custom-api-6": "gpt-image-2",
    "custom-api-4": "gpt-image-2-all",
    "custom-api-7": "gpt-image-2",
    "custom-api": "gpt-image-2",
    "custom-api-3": "gpt-image-2",
    "custom-api-5": "gpt-image-2",
}

AFTERNOON_PROMPT = """将参考背景图制作成同一构图的【下午差分版本】。严格保留原图的场景结构、镜头角度、主体建筑轮廓、道路/广场/树木位置、画风、线条和细节密度，只改变时间、光色和氛围。
这是 galgame 地图/约会地点背景图，要保持干净、柔和、可作为手机 UI 背景使用。下午光要温暖但克制，天空保持浅蓝到暖白，阳光从侧上方照入，阴影柔和，整体不要太黑、不要太黄、不要橙成傍晚；饱和度可以略高但要清爽。保持 Aiko Tokyo v2 柔和小插画感、清晰块面、低噪点、高清完成度。
禁止：改变构图、重画成新地点、增删主体建筑、加入人物角色、可读文字、招牌字、logo、水印、路牌字、强霓虹、夜景、赛博朋克、过暗、过黄、过饱和、杂乱小窗。"""

NIGHT_PROMPT = """将参考背景图制作成同一构图的【晚上/夜晚差分版本】。严格保留原图的场景结构、镜头角度、主体建筑轮廓、道路/广场/树木位置、画风、线条和细节密度，只改变时间、天空、灯光和阴影。
这是 galgame 地图/约会地点背景图，要保持干净、柔和、可作为手机 UI 背景使用。夜空为清透深蓝，画面不要太黑；建筑窗光、路灯、店铺暖光自然点亮，局部可以有柔和蓝紫环境光但不要偏紫，不要强霓虹。保留主体轮廓可读性和 UI 背景清晰度，灯光与阴影协调，Aiko Tokyo v2 柔和小插画感、低噪点、高清完成度。
禁止：改变构图、重画成新地点、增删主体建筑、加入人物角色、可读文字、招牌字、logo、水印、路牌字、过暗、过黄、过饱和、赛博朋克、强霓虹、雨天、雾化糊掉。"""


def now_ms():
    return int(time.time() * 1000)


def write_progress(progress):
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def load_canvas():
    return canvasctl.request_json(BASE, "GET", f"/api/canvases/{CANVAS_ID}", timeout=60)["canvas"]


def save_canvas(canvas, client_id="codex-bg-diff-all-apis"):
    payload = {
        "title": canvas.get("title") or "地图",
        "icon": canvas.get("icon") or "layers",
        "nodes": canvas.get("nodes") or [],
        "connections": canvas.get("connections") or [],
        "viewport": canvas.get("viewport") or {"x": 0, "y": 0, "scale": 1},
        "logs": (canvas.get("logs") or [])[:500],
        "settings": canvas.get("settings") or {},
        "client_id": client_id,
        "base_updated_at": int(canvas.get("updated_at") or 0),
    }
    return canvasctl.request_json(BASE, "PUT", f"/api/canvases/{CANVAS_ID}", payload, timeout=120)["canvas"]


def output_value(item):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("url") or ""
    return ""


def unique_append(items, additions):
    seen = {output_value(item) for item in items if output_value(item)}
    added = 0
    for item in additions:
        url = output_value(item)
        if not url or url in seen:
            continue
        items.append(item)
        seen.add(url)
        added += 1
    return added


def enabled_image_providers():
    providers = canvasctl.request_json(BASE, "GET", "/api/providers", timeout=30).get("providers") or []
    result = []
    for provider in providers:
        provider_id = provider.get("id") or ""
        models = provider.get("image_models") or []
        if not provider.get("enabled") or not models or provider_id not in PROVIDER_MODELS:
            continue
        result.append({
            "id": provider_id,
            "name": provider.get("name") or provider_id,
            "model": PROVIDER_MODELS[provider_id],
            "has_key": bool(provider.get("api_key") or provider.get("key") or provider.get("has_key")),
        })
    return result


def create_board(providers, progress):
    canvas = load_canvas()
    by = {node.get("id"): node for node in canvas.get("nodes") or []}
    sources = []
    missing = []
    for source_id in SOURCE_IDS:
        node = by.get(source_id)
        if not node or node.get("type") != "image" or not node.get("url"):
            missing.append(source_id)
            continue
        sources.append({"id": source_id, "url": node.get("url"), "name": node.get("name") or source_id})
    if missing:
        raise RuntimeError("Missing source image nodes: " + ", ".join(missing))

    images = [{"url": source["url"], "name": source["name"], "role": "source background"} for source in sources]
    targets = []
    for index, source in enumerate(sources, start=1):
        base_name = Path(source["name"]).stem[:36]
        for label, prompt in (("下午差分", AFTERNOON_PROMPT), ("夜晚差分", NIGHT_PROMPT)):
            targets.append({
                "title": f"{base_name} {label}",
                "prompt": prompt,
                "providers": [provider["id"] for provider in providers],
                "count": COUNT_PER_OUTPUT,
                "ratio": "source",
                "resolution": "1k",
                "quality": "auto",
                "compare_providers": True,
                "image_indexes": [index],
            })

    payload = {
        "action": "compose_generation_board",
        "title": "背景图 下午/夜晚差分 - 全API批量",
        "mode": "reference_edit",
        "prompt": "背景图下午和夜晚差分批量生成，全 API 对比",
        "images": images,
        "providers": [provider["id"] for provider in providers],
        "targets": targets,
        "count": COUNT_PER_OUTPUT,
        "ratio": "source",
        "resolution": "1k",
        "quality": "auto",
        "compare_providers": True,
        "run": False,
        "x": 20680,
        "y": 14520,
    }
    created = canvasctl.request_json(BASE, "POST", f"/api/canvas-agent/canvases/{CANVAS_ID}/actions", payload, timeout=120)
    run_plan = created.get("result", {}).get("run_plan") or []
    provider_models = {provider["id"]: provider["model"] for provider in providers}
    for plan in run_plan:
        provider_id = plan.get("provider_id") or ""
        if provider_id in provider_models:
            plan["model"] = provider_models[provider_id]
    progress["created"] = created.get("result") or {}
    progress["run_plan"] = run_plan
    write_progress(progress)
    return run_plan


def run_single(plan, ordinal):
    task_plan = dict(plan)
    task_plan["count"] = 1
    return canvasctl.create_task(BASE, task_plan, ordinal, TASK_TIMEOUT)


def append_results(results):
    latest = load_canvas()
    nodes = latest.get("nodes") or []
    logs = latest.get("logs") or []
    by = {node.get("id"): node for node in nodes}
    for result in results:
        plan = result.get("plan") or {}
        out = by.get(plan.get("output_id"))
        gen = by.get(plan.get("generator_id"))
        images = canvasctl.output_items_for_result(result)
        if out is not None and images:
            unique_append(out.setdefault("images", []), images)
        if gen is not None:
            if images:
                gen.setdefault("generatedOutputs", []).extend([item["url"] for item in images])
                gen["runStatus"] = "done"
                gen["runError"] = ""
            elif not (out and out.get("images")):
                gen["runStatus"] = "failed"
                gen["runError"] = str(result.get("error") or result.get("status") or "任务失败")[:500]
        logs.insert(0, {
            "id": f"bgdiff_all_{now_ms()}_{len(logs)}",
            "createdAt": now_ms(),
            "status": "done" if result.get("ok") else "failed",
            "nodeType": "generator",
            "model": plan.get("model") or "",
            "prompt": plan.get("prompt") or "",
            "outputs": [item["url"] for item in images],
            "error": "" if result.get("ok") else str(result.get("error") or result.get("status") or "任务失败")[:1000],
            "platform": plan.get("provider_name") or plan.get("provider_id") or "",
            "runMs": result.get("run_ms") or 0,
            "task_id": result.get("task_id") or "",
            "request": {
                "provider_id": plan.get("provider_id") or "",
                "model": plan.get("model") or "",
                "size": plan.get("size") or "",
                "quality": plan.get("quality") or "",
                "reference_count": plan.get("reference_count") or 0,
            },
        })
    latest["logs"] = logs[:500]
    latest = save_canvas(latest)
    by = {node.get("id"): node for node in latest.get("nodes") or []}
    return {
        output_id: len((by.get(output_id) or {}).get("images") or [])
        for output_id in {item.get("plan", {}).get("output_id") for item in results if item.get("plan")}
        if output_id
    }


def main():
    providers = enabled_image_providers()
    progress = {
        "canvas_id": CANVAS_ID,
        "started_at": now_ms(),
        "providers": providers,
        "rounds": [],
        "status": "creating_board",
    }
    write_progress(progress)
    run_plan = create_board(providers, progress)
    plan_by_output = {plan.get("output_id"): plan for plan in run_plan if plan.get("output_id")}
    remaining = {output_id: COUNT_PER_OUTPUT for output_id in plan_by_output}

    for round_index in range(1, MAX_REFILL_ROUNDS + 2):
        jobs = []
        for output_id, need in remaining.items():
            if need <= 0:
                continue
            plan = plan_by_output[output_id]
            for ordinal in range(1, need + 1):
                jobs.append((plan, ordinal))
        if not jobs:
            break
        progress["status"] = f"running_round_{round_index}"
        progress["current_round_total"] = len(jobs)
        progress["current_round_done"] = 0
        write_progress(progress)

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            future_map = {pool.submit(run_single, plan, ordinal): (plan, ordinal) for plan, ordinal in jobs}
            for future in concurrent.futures.as_completed(future_map):
                try:
                    result = future.result()
                except Exception as exc:
                    plan, ordinal = future_map[future]
                    result = {"ok": False, "status": "error", "error": str(exc), "images": [], "plan": plan, "index": ordinal}
                results.append(result)
                progress["current_round_done"] += 1
                if progress["current_round_done"] % 5 == 0:
                    write_progress(progress)

        partial_counts = append_results(results)
        latest = load_canvas()
        by = {node.get("id"): node for node in latest.get("nodes") or []}
        counts = {
            output_id: len((by.get(output_id) or {}).get("images") or [])
            for output_id in plan_by_output
        }
        remaining = {output_id: max(0, COUNT_PER_OUTPUT - count) for output_id, count in counts.items()}
        round_summary = {
            "round": round_index,
            "submitted": len(jobs),
            "ok": sum(1 for item in results if item.get("ok")),
            "failed": sum(1 for item in results if not item.get("ok")),
            "counts": counts,
            "remaining": remaining,
        }
        progress["rounds"].append(round_summary)
        progress["remaining_total"] = sum(remaining.values())
        progress["status"] = "round_complete"
        write_progress(progress)
        if not progress["remaining_total"]:
            break

    progress["finished_at"] = now_ms()
    progress["final_remaining"] = remaining
    progress["status"] = "finished"
    write_progress(progress)
    print(json.dumps({
        "providers": providers,
        "generators": len(run_plan),
        "rounds": len(progress["rounds"]),
        "remaining_total": sum(remaining.values()),
        "progress": str(PROGRESS_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
