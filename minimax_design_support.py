"""Bridge helpers for MiniMax Design's loopback generation gateway."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.parse
from typing import Any, Dict, Iterable, Optional

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8001"
MODEL_ID = "MiniMax-H3"
BACKEND_ID = "minimax_v3"
RATIOS = {"16:9", "4:3", "1:1", "3:4", "9:16", "21:9"}


# 网关只接受它自己沙箱内的相对路径：任何绝对路径都会被判成 "Path traversal detected"。
# 所以画布的素材必须先复制进沙箱，再按相对路径引用。沙箱位置随安装目录变化，
# 优先读环境变量，读不到就向网关探测一次（提交一个必不存在的相对路径，
# 从它回显的 ENOENT 绝对路径里反推根目录；文件不存在，不会启动任何生成）。
WORKSPACE_ENV = "MINIMAX_DESIGN_WORKSPACE"
STAGING_SUBDIR = "infinite-canvas"
_WORKSPACE_PROBE_NAME = "__infinite_canvas_probe__.png"
_workspace_cache: Optional[str] = None


class MiniMaxDesignError(RuntimeError):
    pass


class MiniMaxDesignValidationError(MiniMaxDesignError):
    pass


def _clean_paths(values: Optional[Iterable[str]]) -> list[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def _parse_workspace_from_enoent(message: str) -> str:
    """从 ENOENT 报错里取出网关拼出的绝对路径，去掉探测文件名即为沙箱根目录。"""
    match = re.search(r"open '([^']+)'", str(message or ""))
    if not match:
        return ""
    resolved = match.group(1)
    tail = _WORKSPACE_PROBE_NAME
    idx = resolved.replace("/", "\\").rfind(tail)
    if idx <= 0:
        return ""
    return resolved.replace("/", "\\")[:idx].rstrip("\\/")


def stage_media_into_workspace(local_path: str, root: str) -> str:
    """把本机素材复制进网关沙箱，返回可提交的相对路径。

    以内容哈希 + 原名命名，重复引用同一素材不会重复复制。
    """
    root = str(root or "").strip()
    if not root:
        raise MiniMaxDesignError(
            f"未能确定 MiniMax Design 的素材目录，请设置环境变量 {WORKSPACE_ENV} 指向它的 output_files 目录"
        )
    digest = hashlib.sha1(os.path.abspath(local_path).encode("utf-8")).hexdigest()[:12]
    name = f"{digest}_{os.path.basename(local_path)}"
    target_dir = os.path.join(root, STAGING_SUBDIR)
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, name)
    if not os.path.exists(target) or os.path.getsize(target) != os.path.getsize(local_path):
        shutil.copy2(local_path, target)
    # 网关按 posix 风格拼路径，统一用正斜杠
    return f"{STAGING_SUBDIR}/{name}"


def _error_detail(data: Dict[str, Any], raw_text: str = "") -> str:
    parts = []
    reasons = data.get("message")
    if isinstance(reasons, (list, tuple)):
        reasons = "；".join(str(item) for item in reasons if str(item).strip())
    for value in (reasons, data.get("error")):
        text = str(value or "").strip()
        if text and text not in parts:
            parts.append(text)
    if parts:
        return "：".join(parts)
    generic = str(data.get("user_message") or "").strip()
    return generic or str(raw_text or "")[:500]


async def resolve_workspace_root(client: "MiniMaxDesignClient") -> str:
    global _workspace_cache
    override = str(os.environ.get(WORKSPACE_ENV, "") or "").strip()
    if override:
        return override
    if _workspace_cache:
        return _workspace_cache
    root = await client.probe_workspace_root()
    if root:
        _workspace_cache = root
    return root


def build_video_request(
    *,
    prompt: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
    generate_audio: bool,
    image_paths: Optional[Iterable[str]] = None,
    video_paths: Optional[Iterable[str]] = None,
    audio_paths: Optional[Iterable[str]] = None,
    multimodal: bool = False,
    filename: str,
    source_node_id: str = "",
) -> Dict[str, Any]:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise MiniMaxDesignValidationError("提示词不能为空")
    if len(prompt) > 7000:
        raise MiniMaxDesignValidationError("MiniMax H3 提示词最多 7000 字符")
    duration = int(duration)
    if duration < 4 or duration > 15:
        raise MiniMaxDesignValidationError("MiniMax H3 时长必须为 4–15 秒")

    images = _clean_paths(image_paths)
    videos = _clean_paths(video_paths)
    audios = _clean_paths(audio_paths)
    if len(images) > 9:
        raise MiniMaxDesignValidationError("MiniMax H3 最多 9 张参考图片")
    if len(videos) > 3:
        raise MiniMaxDesignValidationError("MiniMax H3 最多 3 个参考视频")
    if len(audios) > 3:
        raise MiniMaxDesignValidationError("MiniMax H3 最多 3 个参考音频")

    normalized_resolution = "2K" if str(resolution or "").strip().lower() in {"2k", "1080p"} else "768P"
    ratio = str(aspect_ratio or "").strip()
    frame_mode = bool(images) and len(images) <= 2 and not videos and not audios and not multimodal
    params: Dict[str, str] = {
        "duration": str(duration),
        "ratio": "adaptive" if frame_mode else (ratio if ratio in RATIOS else "16:9"),
        "resolution": normalized_resolution,
        "generate_audio": "true" if generate_audio else "false",
        "image_mode": "first-last-frame" if frame_mode else "reference",
    }
    request_images = images if frame_mode else []
    if not frame_mode:
        if images:
            params["reference_images"] = json.dumps(images, ensure_ascii=False)
        if videos:
            params["reference_videos"] = json.dumps(videos, ensure_ascii=False)
        if audios:
            params["reference_audios"] = json.dumps(audios, ensure_ascii=False)

    body: Dict[str, Any] = {
        "backend": BACKEND_ID,
        "model_id": MODEL_ID,
        "prompt": prompt,
        "filename": os.path.basename(str(filename or "video.mp4")) or "video.mp4",
        "image_paths": request_images,
        "params": params,
        "source_tool": "infinite_canvas:minimax_design",
    }
    if source_node_id:
        body["source_node_id"] = str(source_node_id)
    return body


def normalize_task_response(task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    raw_status = str((data or {}).get("status") or "").strip().lower()
    result = (data or {}).get("result") if isinstance((data or {}).get("result"), dict) else {}
    if raw_status == "succeeded":
        status = "SUCCESS"
    elif raw_status in {"failed", "failed_terminal", "cancelled", "canceled"} or (data or {}).get("ok") is False:
        status = "FAILED"
    elif raw_status in {"queued", "pending"}:
        status = "QUEUED"
    else:
        status = "RUNNING"
    return {
        "task_id": str((data or {}).get("task_id") or task_id),
        "status": status,
        "video_path": str(result.get("path") or ""),
        "error": str((data or {}).get("user_message") or (data or {}).get("error") or ""),
        "raw": data,
    }


def materialize_video(source_path: str, task_id: str, output_dir: str) -> str:
    source = os.path.abspath(str(source_path or ""))
    if not os.path.isfile(source):
        raise MiniMaxDesignError("MiniMax Design 返回的视频文件不存在")
    os.makedirs(output_dir, exist_ok=True)
    safe_task = re.sub(r"[^A-Za-z0-9_-]+", "_", str(task_id or "task")).strip("_") or "task"
    ext = os.path.splitext(source)[1].lower()
    if ext not in {".mp4", ".webm", ".mov", ".m4v", ".mkv"}:
        ext = ".mp4"
    target = os.path.abspath(os.path.join(output_dir, f"minimax_design_{safe_task}{ext}"))
    output_root = os.path.abspath(output_dir)
    if os.path.commonpath([output_root, target]) != output_root:
        raise MiniMaxDesignError("MiniMax Design 输出路径不安全")
    if not os.path.exists(target):
        shutil.copy2(source, target)
    return target


class MiniMaxDesignClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, transport=None):
        self.base_url = str(base_url or DEFAULT_BASE_URL).rstrip("/")
        self.transport = transport

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        timeout = httpx.Timeout(connect=3.0, read=30.0, write=30.0, pool=3.0)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        try:
            data = response.json()
        except ValueError:
            data = {"error": response.text[:500]}
        if response.status_code >= 400:
            # 网关的报错分散在几个字段，且具体程度差别很大：
            #   message      —— 参数校验的逐条原因（可能是数组），最具体
            #   error        —— 有时是真原因（"duration must be between 4 and 15"），
            #                    有时只是 "Bad Request" 这种标签
            #   user_message —— 面向终端用户的套话（"请稍后重试或联系客服"），最没信息量
            # 按具体程度排序拼接，套话只在没有别的信息时才用，否则真原因会被它盖掉。
            detail = _error_detail(data, response.text)
            raise MiniMaxDesignError(f"MiniMax Design 本机接口错误（{response.status_code}）：{detail}")
        return data

    async def health(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/health")

    async def video_models(self) -> Dict[str, Any]:
        return await self._request("GET", "/api/models/video")

    async def probe_workspace_root(self) -> str:
        """向网关提交一个必定不存在的相对路径，从 ENOENT 报错反推它的沙箱根目录。
        文件不存在，所以不会启动任何生成，也不会产生费用。"""
        body = {
            "backend": BACKEND_ID,
            "model_id": MODEL_ID,
            "prompt": "probe",
            "filename": "probe.mp4",
            "image_paths": [_WORKSPACE_PROBE_NAME],
            "params": {
                "duration": "5",
                "ratio": "adaptive",
                "resolution": "768P",
                "generate_audio": "false",
                "image_mode": "first-last-frame",
            },
        }
        try:
            data = await self._request("POST", "/api/generate/video/submit", json=body)
        except MiniMaxDesignError as exc:
            return _parse_workspace_from_enoent(str(exc))
        return _parse_workspace_from_enoent(str(data.get("error") or ""))

    async def submit_video(self, body: Dict[str, Any]) -> Dict[str, Any]:
        data = await self._request("POST", "/api/generate/video/submit", json=body)
        task_id = str(data.get("task_id") or "").strip()
        if not task_id:
            raise MiniMaxDesignError("MiniMax Design 提交成功但没有返回 task_id")
        return data

    async def query_video(self, task_id: str) -> Dict[str, Any]:
        safe_task_id = urllib.parse.quote(str(task_id), safe="._:-")
        data = await self._request("GET", f"/api/generate/tasks/{safe_task_id}/query")
        return normalize_task_response(task_id, data)
