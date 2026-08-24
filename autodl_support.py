"""AutoDL MiniMax H3 workflow metadata and deterministic routing."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Mapping, Sequence


DEFAULT_WORKFLOW = "minimax_h3_lightx2v_v5"


class AutoDLValidationError(ValueError):
    """Raised before submission when canvas inputs cannot fit an H3 workflow."""


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
