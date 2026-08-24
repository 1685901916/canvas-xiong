"""AutoDL MiniMax H3 workflow metadata and deterministic routing."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, MutableMapping, Sequence
from urllib.parse import quote

import httpx


DEFAULT_WORKFLOW = "minimax_h3_lightx2v_v5"
DEFAULT_BASE_URL = "https://autodl.art"
PROBE_TASK_ID = "00000000-0000-0000-0000-000000000000"
VIDEO_TIMEOUT = 60.0
QUERY_TIMEOUT = 30.0


class AutoDLValidationError(ValueError):
    """Raised before submission when canvas inputs cannot fit an H3 workflow."""


class AutoDLError(RuntimeError):
    """Raised for safe AutoDL configuration, transport, or response failures."""


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    name: str
    min_duration: int
    max_duration: int
    min_images: int
    max_images: int
    min_audios: int
    max_audios: int
    supports_prompt: bool
    supports_seed: bool
    supports_square: bool
    max_resolution: str


@dataclass(frozen=True)
class ResolvedWorkflow:
    workflow_id: str
    name: str
    reason: str


def _workflow(
    workflow_id: str,
    name: str,
    max_duration: int,
    min_images: int,
    max_images: int,
    min_audios: int,
    max_audios: int,
    *,
    supports_prompt: bool = True,
    supports_seed: bool = False,
    supports_square: bool = False,
    max_resolution: str = "768p",
) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=workflow_id,
        name=name,
        min_duration=1,
        max_duration=max_duration,
        min_images=min_images,
        max_images=max_images,
        min_audios=min_audios,
        max_audios=max_audios,
        supports_prompt=supports_prompt,
        supports_seed=supports_seed,
        supports_square=supports_square,
        max_resolution=max_resolution,
    )


_WORKFLOW_ITEMS = (
    _workflow(
        "minimax_h3_lightx2v_v5",
        "H3 多图参考生视频",
        10,
        1,
        9,
        0,
        0,
        supports_seed=True,
        supports_square=True,
        max_resolution="1080p",
    ),
    _workflow(
        "minimax_h3_lightx2v_v5_15s",
        "H3 多图生视频 15 秒",
        15,
        1,
        9,
        0,
        0,
        supports_seed=True,
        supports_square=True,
    ),
    _workflow(
        "minimax_h3_lightx2v_no_pic",
        "H3 文生视频",
        15,
        0,
        0,
        0,
        0,
    ),
    _workflow(
        "minimax_h3_lightx2v",
        "H3 首尾帧视频",
        15,
        2,
        2,
        0,
        0,
    ),
    _workflow(
        "minimax_h3_image_audio_to_video_v2",
        "H3 多图多音频生视频",
        10,
        0,
        9,
        0,
        3,
        supports_seed=True,
        max_resolution="1080p",
    ),
    _workflow(
        "minimax_h3_image_audio_to_video_v2_15s",
        "H3 多图多音频生视频 15 秒",
        15,
        0,
        9,
        0,
        3,
        supports_seed=True,
    ),
    _workflow(
        "minimax_h3_image_audio_to_video",
        "H3 自动对口型",
        15,
        1,
        1,
        1,
        1,
        supports_prompt=False,
        max_resolution="1080p",
    ),
)

WORKFLOWS: Mapping[str, WorkflowDefinition] = MappingProxyType(
    {item.workflow_id: item for item in _WORKFLOW_ITEMS}
)

LIP_SYNC_RE = re.compile(
    r"对口型|口型|嘴型|说话|讲话|念台词|配音|唱歌|演唱|"
    r"lip\s*sync|lipsync|speaking|talking|singing",
    re.I,
)


def _validate_common(
    duration: int,
    images: Sequence[str],
    audios: Sequence[str],
    videos: Sequence[str],
) -> None:
    if not 1 <= duration <= 15:
        raise AutoDLValidationError("AutoDL H3 视频时长必须为 1–15 秒")
    if videos:
        raise AutoDLValidationError("AutoDL H3 工作流不支持参考视频，请先截取图片帧")
    if len(images) > 9 or len(audios) > 3:
        raise AutoDLValidationError("AutoDL H3 最多支持 9 张图片和 3 段音频")


def validate_resolved(
    workflow_id: str,
    prompt: str,
    duration: int,
    images: Sequence[str],
    audios: Sequence[str],
    reason: str,
) -> ResolvedWorkflow:
    definition = WORKFLOWS.get(workflow_id)
    if definition is None:
        raise AutoDLValidationError("未知的 AutoDL H3 工作流")
    if not definition.min_duration <= duration <= definition.max_duration:
        raise AutoDLValidationError(
            f"{definition.name} 仅支持 {definition.min_duration}–{definition.max_duration} 秒"
        )
    if not definition.min_images <= len(images) <= definition.max_images:
        if definition.min_images == definition.max_images:
            requirement = f"正好 {definition.min_images} 张图片"
        else:
            requirement = f"{definition.min_images}–{definition.max_images} 张图片"
        raise AutoDLValidationError(f"{definition.name} 需要{requirement}")
    if not definition.min_audios <= len(audios) <= definition.max_audios:
        if definition.min_audios == definition.max_audios:
            requirement = f"正好 {definition.min_audios} 段音频"
        else:
            requirement = f"{definition.min_audios}–{definition.max_audios} 段音频"
        raise AutoDLValidationError(f"{definition.name} 需要{requirement}")
    if definition.supports_prompt and not str(prompt or "").strip():
        raise AutoDLValidationError(f"{definition.name} 需要提示词")
    return ResolvedWorkflow(workflow_id, definition.name, reason)


def validate_manual_workflow(
    workflow_id: str,
    prompt: str,
    duration: int,
    images: Sequence[str],
    audios: Sequence[str],
    first_last: bool,
) -> ResolvedWorkflow:
    if not workflow_id:
        raise AutoDLValidationError("手动模式必须选择 AutoDL H3 工作流")
    if first_last and workflow_id != "minimax_h3_lightx2v":
        raise AutoDLValidationError("已开启首尾帧时必须选择 H3 首尾帧视频工作流")
    return validate_resolved(
        workflow_id,
        prompt,
        duration,
        images,
        audios,
        "用户手动选择工作流",
    )


def resolve_workflow(
    *,
    prompt: str,
    duration: int,
    images: Sequence[str],
    audios: Sequence[str],
    videos: Sequence[str] = (),
    first_last: bool = False,
    mode: str = "auto",
    workflow_id: str = "",
) -> ResolvedWorkflow:
    try:
        normalized_duration = int(duration)
    except (TypeError, ValueError) as exc:
        raise AutoDLValidationError("AutoDL H3 视频时长必须为整数秒") from exc
    normalized_images = list(images or ())
    normalized_audios = list(audios or ())
    normalized_videos = list(videos or ())
    _validate_common(
        normalized_duration,
        normalized_images,
        normalized_audios,
        normalized_videos,
    )

    if mode == "manual":
        return validate_manual_workflow(
            workflow_id,
            prompt,
            normalized_duration,
            normalized_images,
            normalized_audios,
            first_last,
        )
    if mode != "auto":
        raise AutoDLValidationError("工作流模式必须为 auto 或 manual")

    if (
        len(normalized_images) == 1
        and len(normalized_audios) == 1
        and LIP_SYNC_RE.search(str(prompt or ""))
    ):
        selected = "minimax_h3_image_audio_to_video"
        reason = "单图单音频，提示词包含说话、唱歌或对口型意图"
    elif normalized_audios:
        selected = (
            "minimax_h3_image_audio_to_video_v2"
            if normalized_duration <= 10
            else "minimax_h3_image_audio_to_video_v2_15s"
        )
        reason = (
            f"连接了 {len(normalized_images)} 张图片、{len(normalized_audios)} 段音频，"
            f"时长 {normalized_duration} 秒"
        )
    elif first_last:
        if len(normalized_images) != 2:
            raise AutoDLValidationError("首尾帧工作流必须正好连接 2 张图片")
        selected = "minimax_h3_lightx2v"
        reason = "已开启首尾帧并连接 2 张图片"
    elif normalized_images:
        selected = (
            "minimax_h3_lightx2v_v5"
            if normalized_duration <= 10
            else "minimax_h3_lightx2v_v5_15s"
        )
        reason = (
            f"连接了 {len(normalized_images)} 张图片，"
            f"时长 {normalized_duration} 秒，无音频"
        )
    else:
        selected = "minimax_h3_lightx2v_no_pic"
        reason = "只有提示词，没有参考图片或音频"

    return validate_resolved(
        selected,
        prompt,
        normalized_duration,
        normalized_images,
        normalized_audios,
        reason,
    )


def build_request_body(
    workflow_id: str,
    prompt: str,
    duration: int,
    resolution: str,
    images: Sequence[str],
    audios: Sequence[str],
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    """Build only fields declared by the selected AutoDL online API panel."""
    definition = WORKFLOWS.get(workflow_id)
    if definition is None:
        raise AutoDLValidationError("未知的 AutoDL H3 工作流")
    normalized_images = list(images or ())
    normalized_audios = list(audios or ())
    normalized_duration = int(duration)
    validate_resolved(
        workflow_id,
        prompt,
        normalized_duration,
        normalized_images,
        normalized_audios,
        "构造请求体",
    )
    normalized_resolution = str(resolution or "").strip().replace("P", "p")
    resolution_match = re.fullmatch(r"(480p|768p|1080p)(横|竖|1:1)", normalized_resolution)
    if not resolution_match:
        raise AutoDLValidationError("AutoDL H3 分辨率必须是 480p/768p/1080p 与横/竖/1:1的组合")
    resolution_base, orientation = resolution_match.groups()
    resolution_rank = {"480p": 1, "768p": 2, "1080p": 3}
    if resolution_rank[resolution_base] > resolution_rank[definition.max_resolution]:
        raise AutoDLValidationError(
            f"{definition.name} 最高支持 {definition.max_resolution}"
        )
    if orientation == "1:1" and not definition.supports_square:
        raise AutoDLValidationError(f"{definition.name} 不支持 1:1 比例")

    if workflow_id == "minimax_h3_lightx2v_no_pic":
        return {
            "prompt": str(prompt),
            "duration": normalized_duration,
            "resolution": normalized_resolution,
        }
    if workflow_id == "minimax_h3_lightx2v":
        return {
            "prompt": str(prompt),
            "duration": normalized_duration,
            "resolution": normalized_resolution,
            "first_frame": normalized_images[0],
            "last_frame": normalized_images[1],
        }
    if workflow_id == "minimax_h3_image_audio_to_video":
        return {
            "resolution": normalized_resolution,
            "ref_image_0": normalized_images[0],
            "ref_audio_0": normalized_audios[0],
            "audio_duration": normalized_duration,
        }

    body: dict[str, Any] = {
        "prompt": str(prompt),
        "duration": normalized_duration,
        "resolution": normalized_resolution,
    }
    if seed is not None:
        body["seed"] = int(seed)
    for index, image in enumerate(normalized_images):
        body[f"ref_image_{index}"] = image
    if workflow_id in {
        "minimax_h3_image_audio_to_video_v2",
        "minimax_h3_image_audio_to_video_v2_15s",
    }:
        for index, audio in enumerate(normalized_audios):
            body[f"ref_audio_{index}"] = audio
    return body


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values.setdefault(key, value)
    return values


def discover_token(
    *,
    environ: MutableMapping[str, str] | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
    explicit_path: Path | str | None = None,
) -> tuple[str, str]:
    """Find the token without exposing it to browser-managed provider settings."""
    target = environ if environ is not None else os.environ
    current_dir = (cwd or Path.cwd()).resolve()
    home_dir = (home or Path.home()).resolve()
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    configured = target.get("AUTODL_ENV_FILE")
    if configured:
        candidates.append(Path(configured).expanduser())
    existing = str(target.get("AUTODL_TOKEN") or "").strip()
    if existing:
        return existing, "process environment"
    for current in (current_dir, *current_dir.parents):
        candidates.append(current / ".env.autodl")
    candidates.append(home_dir / ".codex" / "secrets" / "autodl.env")

    seen: set[str] = set()
    for candidate in candidates:
        marker = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        if not candidate.is_file():
            continue
        token = str(_read_env_file(candidate).get("AUTODL_TOKEN") or "").strip()
        if token:
            return token, str(candidate.resolve())
    raise AutoDLError(
        "AUTODL_TOKEN 未配置；请使用环境变量、.env.autodl 或用户 secrets 文件"
    )


def safe_error(error: BaseException, token: str = "") -> str:
    message = str(error) or error.__class__.__name__
    if token:
        message = message.replace(token, "[REDACTED]")
    message = re.sub(
        r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+",
        r"\1[REDACTED]",
        message,
    )
    return message


def validate_task_id(task_id: str) -> str:
    value = str(task_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", value):
        raise AutoDLValidationError("AutoDL task_id 格式无效")
    return value


def _parse_response(
    response: httpx.Response,
    *,
    require_success: bool = True,
    require_task_id: bool = False,
) -> dict[str, Any]:
    if response.status_code in {401, 403}:
        raise AutoDLError(f"AutoDL 鉴权失败：HTTP {response.status_code}")
    try:
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise AutoDLError(f"AutoDL HTTP {response.status_code}") from exc
    except ValueError as exc:
        raise AutoDLError("AutoDL 返回了无效 JSON") from exc
    if not isinstance(payload, dict):
        raise AutoDLError("AutoDL 返回格式无效")
    if require_success and payload.get("code") != "Success":
        raise AutoDLError(str(payload.get("msg") or "AutoDL 请求失败"))
    if require_task_id:
        task_id = str((payload.get("data") or {}).get("task_id") or "")
        if not task_id:
            raise AutoDLError("AutoDL 响应缺少 data.task_id")
    return payload


class AutoDLClient:
    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        client_factory=httpx.AsyncClient,
    ) -> None:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise AutoDLError("AUTODL_TOKEN 为空")
        self.token = normalized_token
        self.base_url = str(base_url or DEFAULT_BASE_URL).rstrip("/")
        self.client_factory = client_factory

    def headers(self) -> dict[str, str]:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    async def submit(self, workflow_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        if workflow_id not in WORKFLOWS:
            raise AutoDLValidationError("未知的 AutoDL H3 工作流")
        safe_id = quote(workflow_id, safe="_.-")
        url = f"{self.base_url}/api/v1/comfyui/comfyui_workflow/{safe_id}"
        try:
            async with self.client_factory(
                timeout=VIDEO_TIMEOUT, follow_redirects=True
            ) as client:
                response = await client.post(url, headers=self.headers(), json=dict(body))
            return _parse_response(response, require_task_id=True)
        except (httpx.HTTPError, AutoDLError) as exc:
            raise AutoDLError(safe_error(exc, self.token)) from exc

    async def query(self, task_id: str) -> dict[str, Any]:
        safe_id = quote(validate_task_id(task_id), safe="_.-")
        url = f"{self.base_url}/api/v1/comfyui/comfyui_workflow/result/{safe_id}"
        try:
            async with self.client_factory(
                timeout=QUERY_TIMEOUT, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=self.headers())
            return _parse_response(response)
        except (httpx.HTTPError, AutoDLError) as exc:
            raise AutoDLError(safe_error(exc, self.token)) from exc

    async def doctor(self) -> dict[str, Any]:
        url = (
            f"{self.base_url}/api/v1/comfyui/comfyui_workflow/result/"
            f"{PROBE_TASK_ID}"
        )
        try:
            async with self.client_factory(
                timeout=QUERY_TIMEOUT, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=self.headers())
            payload = _parse_response(response, require_success=False)
        except (httpx.HTTPError, AutoDLError) as exc:
            raise AutoDLError(safe_error(exc, self.token)) from exc
        return {
            "status": "ok",
            "authenticated": True,
            "base_url": self.base_url,
            "default_workflow": DEFAULT_WORKFLOW,
            "api_code": payload.get("code"),
            "api_message": payload.get("msg"),
            "paid_task_submitted": False,
        }


def client_from_environment(
    *,
    environ: MutableMapping[str, str] | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
    client_factory=httpx.AsyncClient,
) -> AutoDLClient:
    target = environ if environ is not None else os.environ
    token, _ = discover_token(environ=target, cwd=cwd, home=home)
    base_url = str(target.get("AUTODL_BASE_URL") or DEFAULT_BASE_URL)
    return AutoDLClient(token, base_url=base_url, client_factory=client_factory)


def collect_result_urls(payload: Any) -> list[str]:
    urls: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str):
            if value.startswith(("https://", "http://")) and value not in urls:
                urls.append(value)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)

    if isinstance(payload, dict):
        data = payload.get("data")
        visit(data.get("results") if isinstance(data, dict) else None)
    return urls


def public_workflows() -> list[dict[str, Any]]:
    """Return deterministic browser-safe workflow metadata."""
    return [asdict(item) for item in _WORKFLOW_ITEMS]


async def doctor_safe() -> dict[str, Any]:
    """Run the non-billing probe and return no credential material."""
    try:
        client = client_from_environment()
    except AutoDLError as exc:
        return {
            "status": "not_configured",
            "configured": False,
            "authenticated": False,
            "message": safe_error(exc),
            "paid_task_submitted": False,
        }
    try:
        report = await client.doctor()
        return {"configured": True, **report}
    except AutoDLError as exc:
        return {
            "status": "error",
            "configured": True,
            "authenticated": False,
            "message": safe_error(exc, client.token),
            "paid_task_submitted": False,
        }


def public_submission(
    payload: Mapping[str, Any], resolved: ResolvedWorkflow
) -> dict[str, Any]:
    data = payload.get("data")
    data = data if isinstance(data, Mapping) else {}
    task_id = validate_task_id(str(data.get("task_id") or ""))
    status = str(data.get("status") or "QUEUED").upper()
    return {
        "provider_id": "autodl",
        "provider_name": "AutoDL",
        "workflow_id": resolved.workflow_id,
        "workflow_name": resolved.name,
        "workflow_reason": resolved.reason,
        "task_id": task_id,
        "status": status,
    }
