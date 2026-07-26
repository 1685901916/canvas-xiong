"""Lightweight validation and process-boundary helpers for Real-ESRGAN.

This module deliberately avoids importing torch, OpenCV, or the worker module so
that the web process can safely use it without loading the inference runtime.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote_to_bytes

from PIL import Image


DEFAULT_MODEL_ID = "RealESRGAN_x4plus_anime_6B"
WAIFU2X_MODEL_ID = "Waifu2x_CUNet"
SUPPORTED_MODELS = {
    DEFAULT_MODEL_ID: {
        "filename": "RealESRGAN_x4plus_anime_6B.pth",
        "name": "RealESRGAN x4plus Anime 6B",
        "native_scale": 4,
    },
    WAIFU2X_MODEL_ID: {
        "package_subdir": "waifu2x_ncnn_py/models/models-cunet",
        "required_files": (
            "noise0_scale2.0x_model.param",
            "noise0_scale2.0x_model.bin",
        ),
        "filename": "models-cunet",
        "name": "Waifu2x CUNet（动漫）",
        "native_scale": 2,
    },
}


class RealESRGANSupportError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = 400,
        code: str = "INVALID_ARGUMENT",
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class RealESRGANConfig:
    python_executable: Path
    worker_path: Path
    model_dir: Path
    output_dir: Path
    allowed_input_roots: tuple[Path, ...]
    timeout_seconds: int
    max_input_bytes: int
    max_input_pixels: int
    max_output_pixels: int


@dataclass(frozen=True)
class ResolvedImage:
    path: Path
    width: int
    height: int
    size_bytes: int


def _path(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _lexical_path(value: os.PathLike[str] | str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw = environment.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RealESRGANSupportError(
            f"{name} 必须是正整数", code="INVALID_CONFIGURATION"
        ) from exc
    if value <= 0:
        raise RealESRGANSupportError(
            f"{name} 必须是正整数", code="INVALID_CONFIGURATION"
        )
    return value


def build_config(
    base_dir: os.PathLike[str] | str,
    assets_dir: os.PathLike[str] | str,
    legacy_output_dir: os.PathLike[str] | str,
    environ: Mapping[str, str] | None = None,
) -> RealESRGANConfig:
    """Build configuration from the environment at call time."""

    environment = os.environ if environ is None else environ
    base = _lexical_path(base_dir)
    assets = _lexical_path(assets_dir)
    legacy_output = _lexical_path(legacy_output_dir)

    python_override = environment.get("REALESRGAN_PYTHON")
    if python_override:
        python_executable = _path(python_override)
    elif os.name == "nt":
        local_app_data = environment.get("LOCALAPPDATA")
        local_root = (
            _path(local_app_data)
            if local_app_data
            else _path(Path.home() / "AppData" / "Local")
        )
        python_executable = (
            local_root / "Programs" / "Python" / "Python312" / "python.exe"
        )
    else:
        python_executable = _path(sys.executable)

    model_override = environment.get("REALESRGAN_MODEL_DIR")
    model_dir = (
        _path(model_override)
        if model_override
        else _path(Path.home() / ".cache" / "realesrgan")
    )

    return RealESRGANConfig(
        python_executable=python_executable,
        worker_path=base / "tools" / "realesrgan_worker.py",
        model_dir=model_dir,
        output_dir=assets / "output",
        allowed_input_roots=(
            assets / "input",
            assets / "output",
            assets / "uploads",
            assets / "library",
            legacy_output,
        ),
        timeout_seconds=_positive_int(
            environment, "REALESRGAN_TIMEOUT_SECONDS", 300
        ),
        max_input_bytes=_positive_int(
            environment, "REALESRGAN_MAX_INPUT_BYTES", 50 * 1024 * 1024
        ),
        max_input_pixels=_positive_int(
            environment, "REALESRGAN_MAX_INPUT_PIXELS", 40_000_000
        ),
        max_output_pixels=_positive_int(
            environment, "REALESRGAN_MAX_OUTPUT_PIXELS", 100_000_000
        ),
    )


def validate_scale(scale: object) -> int:
    if isinstance(scale, bool):
        value = -1
    elif isinstance(scale, int):
        value = scale
    elif isinstance(scale, str) and scale in {"2", "4"}:
        value = int(scale)
    else:
        value = -1
    if value not in {2, 4}:
        raise RealESRGANSupportError(
            "放大倍数只支持 2 或 4", code="INVALID_SCALE"
        )
    return value


def _model_path(model_id: str, config: RealESRGANConfig) -> Path:
    metadata = SUPPORTED_MODELS[model_id]
    package_subdir = metadata.get("package_subdir")
    if package_subdir:
        return (
            config.python_executable.parent
            / "Lib"
            / "site-packages"
            / Path(str(package_subdir))
        )
    return config.model_dir / str(metadata["filename"])


def _model_path_available(path: Path, metadata: Mapping[str, object]) -> bool:
    required_files = metadata.get("required_files")
    if required_files:
        return path.is_dir() and all(
            (path / str(filename)).is_file() for filename in required_files
        )
    return path.is_file()


def discover_models(config: RealESRGANConfig) -> list[dict[str, object]]:
    models: list[dict[str, object]] = []
    for model_id, metadata in SUPPORTED_MODELS.items():
        model_path = _model_path(model_id, config)
        if _model_path_available(model_path, metadata):
            models.append(
                {
                    "id": model_id,
                    "filename": metadata["filename"],
                    "name": metadata["name"],
                    "native_scale": metadata["native_scale"],
                }
            )
    return models


def resolve_model_path(model_id: str, config: RealESRGANConfig) -> Path:
    metadata = SUPPORTED_MODELS.get(model_id)
    if metadata is None:
        raise RealESRGANSupportError(
            "不支持的 Real-ESRGAN 模型", 404, "MODEL_NOT_FOUND"
        )
    model_path = _model_path(model_id, config)
    if not _model_path_available(model_path, metadata):
        raise RealESRGANSupportError(
            "Real-ESRGAN 模型文件不存在", 404, "MODEL_NOT_FOUND"
        )
    return model_path


_BAD_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _decode_source_url(source_url: str) -> str:
    if not isinstance(source_url, str) or not source_url:
        raise RealESRGANSupportError("图片地址无效", code="INVALID_SOURCE")
    if _BAD_PERCENT_ESCAPE.search(source_url):
        raise RealESRGANSupportError("图片地址编码无效", code="INVALID_SOURCE")
    try:
        decoded = unquote_to_bytes(source_url).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RealESRGANSupportError(
            "图片地址编码无效", code="INVALID_SOURCE"
        ) from exc
    if "\x00" in decoded or "\\" in decoded:
        raise RealESRGANSupportError("图片地址无效", code="INVALID_SOURCE")
    return decoded


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _input_access_error(exc: OSError) -> RealESRGANSupportError:
    if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
        return RealESRGANSupportError(
            "输入图片不存在", 404, "INPUT_NOT_FOUND"
        )
    if isinstance(exc, PermissionError):
        return RealESRGANSupportError(
            "无权读取输入图片", 403, "INPUT_FORBIDDEN"
        )
    return RealESRGANSupportError(
        "读取输入图片失败", 500, "INPUT_ACCESS_FAILED"
    )


def local_path_from_source_url(
    source_url: str,
    config: RealESRGANConfig,
    *,
    assets_dir: os.PathLike[str] | str,
    legacy_output_dir: os.PathLike[str] | str,
) -> Path:
    decoded = _decode_source_url(source_url)
    if decoded.startswith("/assets/"):
        root = _lexical_path(assets_dir)
        relative = decoded[len("/assets/") :]
    elif decoded.startswith("/output/"):
        root = _lexical_path(legacy_output_dir)
        relative = decoded[len("/output/") :]
    else:
        raise RealESRGANSupportError(
            "只能处理本地 assets 或 output 图片", code="INVALID_SOURCE"
        )

    parts = relative.split("/")
    if not relative or any(part in {"", ".", ".."} for part in parts):
        raise RealESRGANSupportError("图片地址无效", code="INVALID_SOURCE")

    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=True)
        allowed_roots = tuple(
            root.resolve(strict=False) for root in config.allowed_input_roots
        )
    except RuntimeError as exc:
        raise RealESRGANSupportError(
            "输入图片路径不在允许范围内", 400, "PATH_NOT_ALLOWED"
        ) from exc
    except OSError as exc:
        raise _input_access_error(exc) from exc

    if not any(_is_within(resolved, allowed_root) for allowed_root in allowed_roots):
        raise RealESRGANSupportError(
            "图片路径越过允许目录", code="INVALID_SOURCE"
        )
    if not resolved.is_file():
        raise RealESRGANSupportError("图片地址不是文件", code="INVALID_SOURCE")
    return candidate


def resolve_image(
    path: os.PathLike[str] | str,
    config: RealESRGANConfig,
    scale: object,
) -> ResolvedImage:
    image_path = Path(path)
    normalized_scale = validate_scale(scale)
    try:
        size_bytes = image_path.stat().st_size
    except OSError as exc:
        raise _input_access_error(exc) from exc
    if size_bytes > config.max_input_bytes:
        raise RealESRGANSupportError(
            "原图文件过大", 413, "INPUT_TOO_LARGE"
        )

    try:
        with Image.open(image_path) as image:
            width, height = image.size
            pillow_limit = Image.MAX_IMAGE_PIXELS
            if pillow_limit is not None and width * height > pillow_limit:
                raise RealESRGANSupportError(
                    "输入图片过大", 413, "INPUT_TOO_LARGE"
                )
            image.verify()
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise RealESRGANSupportError(
            "输入图片过大", 413, "INPUT_TOO_LARGE"
        ) from exc
    except (OSError, SyntaxError, ValueError) as exc:
        raise RealESRGANSupportError(
            "无法解码原图", 415, "INPUT_DECODE_FAILED"
        ) from exc

    input_pixels = width * height
    if input_pixels > config.max_input_pixels:
        raise RealESRGANSupportError("原图像素过多", 413, "INPUT_TOO_LARGE")
    if input_pixels * normalized_scale * normalized_scale > config.max_output_pixels:
        raise RealESRGANSupportError(
            "放大后图片像素过多", 413, "OUTPUT_TOO_LARGE"
        )
    return ResolvedImage(image_path, width, height, size_bytes)


def build_worker_args(
    config: RealESRGANConfig,
    input_path: os.PathLike[str] | str,
    output_path: os.PathLike[str] | str,
    *,
    model_id: str = DEFAULT_MODEL_ID,
    scale: object = 4,
    device: str = "auto",
) -> list[str]:
    model_path = resolve_model_path(model_id, config)
    normalized_scale = validate_scale(scale)
    return [
        str(config.python_executable),
        "-B",
        str(config.worker_path),
        "upscale",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--model-id",
        model_id,
        "--model-path",
        str(model_path),
        "--scale",
        str(normalized_scale),
        "--device",
        device,
    ]


def build_probe_args(config: RealESRGANConfig) -> list[str]:
    return [
        str(config.python_executable),
        "-B",
        str(config.worker_path),
        "status",
    ]


def _reject_non_finite_json_number(value: str) -> None:
    raise ValueError(f"JSON 不允许非有限数: {value}")


def parse_worker_json(stdout: str) -> dict[str, object]:
    if not isinstance(stdout, str):
        raise RealESRGANSupportError(
            "Real-ESRGAN worker 返回了无效响应",
            502,
            "WORKER_INVALID_RESPONSE",
        )
    document = stdout.strip()
    if not document:
        raise RealESRGANSupportError(
            "Real-ESRGAN worker 返回了空响应",
            502,
            "WORKER_INVALID_RESPONSE",
        )
    try:
        payload = json.loads(
            document, parse_constant=_reject_non_finite_json_number
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise RealESRGANSupportError(
            "Real-ESRGAN worker 返回了无效 JSON",
            502,
            "WORKER_INVALID_RESPONSE",
        ) from exc
    if not isinstance(payload, dict):
        raise RealESRGANSupportError(
            "Real-ESRGAN worker 响应必须是 JSON 对象",
            502,
            "WORKER_INVALID_RESPONSE",
        )
    return payload


_WORKER_ENV_KEYS = {
    "SYSTEMROOT",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "USERNAME",
    "LOCALAPPDATA",
    "APPDATA",
}
_CUDA_WORKER_ENV_KEYS = {
    "CUDA_PATH",
    "CUDA_HOME",
    "CUDA_VISIBLE_DEVICES",
    "CUDA_DEVICE_ORDER",
    "CUDA_MODULE_LOADING",
}
_CUDA_VERSION_PATH = re.compile(r"CUDA_PATH_V\d+(?:_\d+)*\Z")
_SECRET_MARKERS = (
    "KEY",
    "TOKEN",
    "COOKIE",
    "SECRET",
    "PASSWORD",
    "AUTH",
    "CREDENTIAL",
    "LICENSE",
)


def minimal_worker_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = os.environ if environ is None else environ
    result: dict[str, str] = {}
    for key, value in environment.items():
        upper_key = key.upper()
        if any(marker in upper_key for marker in _SECRET_MARKERS):
            continue
        if (
            upper_key in _WORKER_ENV_KEYS
            or upper_key in _CUDA_WORKER_ENV_KEYS
            or _CUDA_VERSION_PATH.fullmatch(upper_key)
        ):
            result[key] = value
    return result


def mapped_worker_error(
    code: str | Mapping[str, object], detail: str | None = None
) -> RealESRGANSupportError:
    if isinstance(code, Mapping):
        payload = code
        code = str(
            payload.get("error_code") or payload.get("code") or "WORKER_FAILED"
        )

    statuses = {
        "INVALID_ARGUMENT": 400,
        "UNSUPPORTED_SCALE": 400,
        "CUDA_OOM": 503,
        "CUDA_UNAVAILABLE": 503,
        "PYTHON_ENV_UNAVAILABLE": 503,
        "MODEL_NOT_FOUND": 404,
        "INPUT_NOT_FOUND": 404,
        "INPUT_DECODE_FAILED": 415,
        "INFERENCE_FAILED": 502,
        "OUTPUT_WRITE_FAILED": 502,
        "TIMEOUT": 504,
    }
    default_details = {
        "INVALID_ARGUMENT": "Real-ESRGAN 参数无效",
        "UNSUPPORTED_SCALE": "放大倍数只支持 2 或 4",
        "CUDA_OOM": "显存不足，请使用更小的原图",
        "CUDA_UNAVAILABLE": "CUDA 不可用",
        "PYTHON_ENV_UNAVAILABLE": "Real-ESRGAN Python 环境不可用",
        "MODEL_NOT_FOUND": "Real-ESRGAN 模型文件不存在",
        "INPUT_NOT_FOUND": "输入图片不存在",
        "INPUT_DECODE_FAILED": "无法解码原图",
        "INFERENCE_FAILED": "Real-ESRGAN 推理失败",
        "OUTPUT_WRITE_FAILED": "写入 Real-ESRGAN 输出图片失败",
        "TIMEOUT": "Real-ESRGAN 处理超时",
        "WORKER_FAILED": "Real-ESRGAN worker 执行失败",
    }
    status_code = statuses.get(code, 502)
    error_detail = default_details.get(code, "Real-ESRGAN worker 执行失败")
    return RealESRGANSupportError(error_detail, status_code, code)


async def _terminate_process(process) -> None:
    try:
        process.kill()
    except (ProcessLookupError, OSError):
        pass
    await process.wait()


async def run_process(
    args: list[str],
    timeout_seconds: float,
    environ: Mapping[str, str] | None = None,
    process_factory=None,
) -> dict[str, object]:
    factory = asyncio.create_subprocess_exec if process_factory is None else process_factory
    kwargs: dict[str, object] = {
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
        "env": minimal_worker_env(environ),
    }
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        process = await factory(*args, **kwargs)
    except OSError as exc:
        raise mapped_worker_error("PYTHON_ENV_UNAVAILABLE") from exc
    try:
        stdout_data, _stderr_data = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        await _terminate_process(process)
        raise mapped_worker_error("TIMEOUT") from exc
    except asyncio.CancelledError:
        await _terminate_process(process)
        raise

    stdout = (
        stdout_data.decode("utf-8", errors="replace")
        if isinstance(stdout_data, bytes)
        else str(stdout_data)
    )
    payload = parse_worker_json(stdout)
    successful_waifu_payload = (
        payload.get("ok") is True
        and payload.get("kind") == "upscale"
        and payload.get("model") == WAIFU2X_MODEL_ID
    )
    if payload.get("ok") is not True or (
        process.returncode != 0 and not successful_waifu_payload
    ):
        raise mapped_worker_error(payload)
    return payload


async def probe_worker(config: RealESRGANConfig) -> dict[str, object]:
    return await run_process(
        build_probe_args(config), config.timeout_seconds
    )


def _resolve_upscale_paths(
    source_path: os.PathLike[str] | str,
    output_path: os.PathLike[str] | str,
) -> tuple[Path, Path]:
    source_candidate = _lexical_path(source_path)
    output_candidate = _lexical_path(output_path)
    try:
        source_resolved = source_candidate.resolve(strict=True)
    except RuntimeError as exc:
        raise RealESRGANSupportError(
            "输入图片路径不在允许范围内", 400, "PATH_NOT_ALLOWED"
        ) from exc
    except OSError as exc:
        raise _input_access_error(exc) from exc
    try:
        output_resolved = output_candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise RealESRGANSupportError(
            "输出图片路径无效", 400, "INVALID_ARGUMENT"
        ) from exc
    if source_resolved == output_resolved:
        raise RealESRGANSupportError(
            "输出路径不能覆盖输入图片", 400, "INVALID_ARGUMENT"
        )
    return source_candidate, output_candidate


async def run_upscale_worker(
    config: RealESRGANConfig,
    source_path: os.PathLike[str] | str,
    output_path: os.PathLike[str] | str,
    model_id: str,
    scale: object,
    device: str = "auto",
    semaphore=None,
    validate_output=None,
) -> dict[str, object]:
    source, final_output = _resolve_upscale_paths(source_path, output_path)
    stage_output = final_output.parent / (
        f".realesrgan-stage-{uuid.uuid4().hex}.png"
    )
    args = build_worker_args(
        config,
        source,
        stage_output,
        model_id=model_id,
        scale=scale,
        device=device,
    )

    async def execute() -> dict[str, object]:
        published_identity = None
        try:
            payload = await run_process(args, config.timeout_seconds)
            reported = payload.get("output_path")
            try:
                actual = Path(str(reported)).resolve(strict=False)
                expected_actual = stage_output.resolve(strict=False)
            except (OSError, RuntimeError, ValueError, TypeError):
                actual = None
                expected_actual = None
            try:
                stage_status = stage_output.lstat()
            except OSError:
                stage_status = None
            if (
                actual != expected_actual
                or stage_status is None
                or not stat.S_ISREG(stage_status.st_mode)
            ):
                raise RealESRGANSupportError(
                    "RealESRGAN 未生成输出图片",
                    502,
                    "WORKER_OUTPUT_MISSING",
                )
            validation = None
            if validate_output is not None:
                validation = validate_output(stage_output, payload)
            try:
                os.link(stage_output, final_output)
            except FileExistsError as exc:
                raise RealESRGANSupportError(
                    "RealESRGAN 输出文件冲突",
                    409,
                    "OUTPUT_CONFLICT",
                ) from exc
            except OSError as exc:
                raise RealESRGANSupportError(
                    "RealESRGAN 未生成输出图片",
                    502,
                    "WORKER_OUTPUT_MISSING",
                ) from exc
            try:
                final_status = final_output.lstat()
            except OSError as exc:
                raise RealESRGANSupportError(
                    "RealESRGAN 未生成输出图片",
                    502,
                    "WORKER_OUTPUT_MISSING",
                ) from exc
            if (
                not stat.S_ISREG(final_status.st_mode)
                or final_status.st_dev != stage_status.st_dev
                or final_status.st_ino != stage_status.st_ino
            ):
                raise RealESRGANSupportError(
                    "RealESRGAN 未生成输出图片",
                    502,
                    "WORKER_OUTPUT_MISSING",
                )
            published_identity = (
                final_status.st_dev,
                final_status.st_ino,
                final_status.st_size,
                getattr(final_status, "st_mtime_ns", int(final_status.st_mtime * 1_000_000_000)),
            )
            result = dict(payload)
            result["output_path"] = str(final_output)
            result["_output_identity"] = published_identity
            if validation is not None:
                result["_validation"] = validation
            return result
        except BaseException:
            if published_identity is not None:
                try:
                    current = final_output.lstat()
                    current_identity = (
                        current.st_dev,
                        current.st_ino,
                        current.st_size,
                        getattr(current, "st_mtime_ns", int(current.st_mtime * 1_000_000_000)),
                    )
                    if current_identity == published_identity:
                        final_output.unlink()
                except OSError:
                    pass
            raise
        finally:
            try:
                stage_output.unlink(missing_ok=True)
            except OSError:
                pass

    if semaphore is None:
        return await execute()
    async with semaphore:
        return await execute()
