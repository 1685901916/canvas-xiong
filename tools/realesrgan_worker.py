"""Isolated Real-ESRGAN worker.

Optional inference dependencies are imported only inside runtime functions so
that this module remains importable in the application's embedded Python.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import importlib
import json
import math
import os
import sys
import tempfile
import time
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Callable


DEFAULT_MODEL_ID = "RealESRGAN_x4plus_anime_6B"
WAIFU2X_MODEL_ID = "Waifu2x_CUNet"


class WorkerFailure(Exception):
    def __init__(self, error_code: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.exit_code = exit_code


def anime_6b_architecture() -> dict[str, int]:
    return {
        "num_in_ch": 3,
        "num_out_ch": 3,
        "num_feat": 64,
        "num_block": 6,
        "num_grow_ch": 32,
        "scale": 4,
    }


def retry_tiles(device_kind: str) -> tuple[int, ...]:
    return (512, 256) if device_kind == "cuda" else (0,)


def expected_dimensions(width: int, height: int, scale: int) -> tuple[int, int]:
    if isinstance(scale, bool) or not isinstance(scale, int) or scale not in {2, 4}:
        raise WorkerFailure("UNSUPPORTED_SCALE", "放大倍数只支持 2 或 4", 2)
    return width * scale, height * scale


def is_cuda_oom(exc: BaseException) -> bool:
    class_name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "outofmemory" in class_name or "out of memory" in message or (
        "cuda" in message and "memory allocation" in message
    )


def run_with_tile_retry(
    device_kind: str,
    attempt: Callable[[int], object],
    cleanup: Callable[[], None],
) -> tuple[object, int, int]:
    tiles = retry_tiles(device_kind)
    for attempt_index, tile in enumerate(tiles, 1):
        try:
            return attempt(tile), tile, attempt_index
        except BaseException as exc:
            if device_kind != "cuda" or not is_cuda_oom(exc):
                raise
            if attempt_index == len(tiles):
                raise WorkerFailure(
                    "CUDA_OOM", "显存不足，请使用更小的原图", 5
                ) from exc
            cleanup()
    raise AssertionError("unreachable")


def tile_slices(
    height: int, width: int, tile: int, pad: int, scale: int
) -> tuple[tuple[int, ...], ...]:
    slices: list[tuple[int, ...]] = []
    tiles_x = math.ceil(width / tile)
    tiles_y = math.ceil(height / tile)
    for y in range(tiles_y):
        for x in range(tiles_x):
            input_start_x = x * tile
            input_end_x = min(input_start_x + tile, width)
            input_start_y = y * tile
            input_end_y = min(input_start_y + tile, height)
            input_start_x_pad = max(input_start_x - pad, 0)
            input_end_x_pad = min(input_end_x + pad, width)
            input_start_y_pad = max(input_start_y - pad, 0)
            input_end_y_pad = min(input_end_y + pad, height)
            output_start_x = input_start_x * scale
            output_end_x = input_end_x * scale
            output_start_y = input_start_y * scale
            output_end_y = input_end_y * scale
            output_start_x_tile = (input_start_x - input_start_x_pad) * scale
            output_end_x_tile = output_start_x_tile + (
                input_end_x - input_start_x
            ) * scale
            output_start_y_tile = (input_start_y - input_start_y_pad) * scale
            output_end_y_tile = output_start_y_tile + (
                input_end_y - input_start_y
            ) * scale
            slices.append(
                (
                    input_start_x_pad,
                    input_end_x_pad,
                    input_start_y_pad,
                    input_end_y_pad,
                    output_start_x,
                    output_end_x,
                    output_start_y,
                    output_end_y,
                    output_start_x_tile,
                    output_end_x_tile,
                    output_start_y_tile,
                    output_end_y_tile,
                )
            )
    return tuple(slices)


def install_torchvision_compat_shim():
    functional = importlib.import_module("torchvision.transforms.functional")
    shim = types.ModuleType("torchvision.transforms.functional_tensor")
    shim.rgb_to_grayscale = functional.rgb_to_grayscale
    sys.modules[shim.__name__] = shim
    return shim


def load_runtime():
    install_torchvision_compat_shim()
    torch = importlib.import_module("torch")
    torchvision = importlib.import_module("torchvision")
    cv2 = importlib.import_module("cv2")
    numpy = importlib.import_module("numpy")
    basicsr = importlib.import_module("basicsr")
    rrdb_module = importlib.import_module("basicsr.archs.rrdbnet_arch")
    realesrgan = importlib.import_module("realesrgan")
    return SimpleNamespace(
        torch=torch,
        torchvision=torchvision,
        cv2=cv2,
        numpy=numpy,
        basicsr=basicsr,
        realesrgan=realesrgan,
        RRDBNet=rrdb_module.RRDBNet,
        RealESRGANer=realesrgan.RealESRGANer,
    )


def load_waifu_runtime():
    image_module = importlib.import_module("PIL.Image")
    waifu_module = importlib.import_module("waifu2x_ncnn_py")
    return SimpleNamespace(Image=image_module, Waifu2x=waifu_module.Waifu2x)


def strict_realesrganer_class(base_class, torch_module):
    class StrictRealESRGANer(base_class):
        def tile_process(self):
            batch, channel, height, width = self.img.shape
            output_height = height * self.scale
            output_width = width * self.scale
            output_shape = (batch, channel, output_height, output_width)
            self.output = self.img.new_zeros(output_shape)
            for item in tile_slices(
                height, width, self.tile_size, self.tile_pad, self.scale
            ):
                (
                    input_start_x_pad,
                    input_end_x_pad,
                    input_start_y_pad,
                    input_end_y_pad,
                    output_start_x,
                    output_end_x,
                    output_start_y,
                    output_end_y,
                    output_start_x_tile,
                    output_end_x_tile,
                    output_start_y_tile,
                    output_end_y_tile,
                ) = item
                input_tile = self.img[
                    :,
                    :,
                    input_start_y_pad:input_end_y_pad,
                    input_start_x_pad:input_end_x_pad,
                ]

                with torch_module.no_grad():
                    output_tile = self.model(input_tile)

                self.output[
                    :,
                    :,
                    output_start_y:output_end_y,
                    output_start_x:output_end_x,
                ] = output_tile[
                    :,
                    :,
                    output_start_y_tile:output_end_y_tile,
                    output_start_x_tile:output_end_x_tile,
                ]

    StrictRealESRGANer.__name__ = "StrictRealESRGANer"
    return StrictRealESRGANer


def _runtime_or_failure(runtime_loader):
    try:
        return runtime_loader()
    except WorkerFailure:
        raise
    except BaseException as exc:
        raise WorkerFailure(
            "PYTHON_ENV_UNAVAILABLE", "Real-ESRGAN Python 环境不可用", 3
        ) from exc


def _device(runtime, requested: str) -> tuple[str, str, str]:
    if requested not in {"auto", "cuda", "cpu"}:
        raise WorkerFailure("INVALID_ARGUMENT", "设备参数无效", 2)
    cuda_available = bool(runtime.torch.cuda.is_available())
    if requested == "cuda" and not cuda_available:
        raise WorkerFailure("CUDA_UNAVAILABLE", "CUDA 不可用", 3)
    use_cuda = requested == "cuda" or (requested == "auto" and cuda_available)
    return (
        ("cuda", "cuda:0", "fp16")
        if use_cuda
        else ("cpu", "cpu", "fp32")
    )


def status_request(runtime_loader=load_runtime) -> dict[str, object]:
    runtime = _runtime_or_failure(runtime_loader)
    device_kind, device_name, _ = _device(runtime, "auto")
    return {
        "ok": True,
        "kind": "status",
        "cuda": device_kind == "cuda",
        "device": device_name,
        "versions": {
            "torch": str(getattr(runtime.torch, "__version__", "unknown")),
            "torchvision": str(
                getattr(runtime.torchvision, "__version__", "unknown")
            ),
            "basicsr": str(getattr(runtime.basicsr, "__version__", "unknown")),
            "realesrgan": str(
                getattr(runtime.realesrgan, "__version__", "unknown")
            ),
        },
    }


def _waifu_device(requested: str) -> tuple[int, str, str]:
    if requested not in {"auto", "cuda", "cpu"}:
        raise WorkerFailure("INVALID_ARGUMENT", "设备参数无效", 2)
    if requested == "cpu":
        return -1, "cpu", "ncnn-cpu"
    return 0, "vulkan:0", "ncnn-vulkan"


def _waifu_upscale_request(
    *, source: Path, output: Path, model: Path, scale: int, device: str,
    started: float, runtime_loader,
) -> dict[str, object]:
    try:
        runtime = runtime_loader()
    except WorkerFailure:
        raise
    except BaseException as exc:
        raise WorkerFailure(
            "PYTHON_ENV_UNAVAILABLE", "Waifu2x Python 环境不可用", 3
        ) from exc

    try:
        with runtime.Image.open(source) as opened:
            opened.load()
            source_width, source_height = opened.size
            alpha = opened.getchannel("A") if "A" in opened.getbands() else None
            rendered = opened.convert("RGB")
    except (OSError, SyntaxError, ValueError) as exc:
        raise WorkerFailure("INPUT_DECODE_FAILED", "无法解码原图", 4) from exc

    expected_width, expected_height = expected_dimensions(
        source_width, source_height, scale
    )
    gpu_id, device_name, precision = _waifu_device(device)
    passes = scale // 2
    upscaler = None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            upscaler = runtime.Waifu2x(
                gpuid=gpu_id,
                tta_mode=False,
                num_threads=1,
                noise=0,
                scale=2,
                tilesize=0,
                model=str(model),
            )
            for _ in range(passes):
                rendered = upscaler.process_pil(rendered)
    except BaseException as exc:
        raise WorkerFailure("INFERENCE_FAILED", "Waifu2x 推理失败", 6) from exc
    finally:
        upscaler = None

    if rendered.size != (expected_width, expected_height):
        raise WorkerFailure("INFERENCE_FAILED", "Waifu2x 输出尺寸异常", 6)
    if alpha is not None:
        resampling = getattr(runtime.Image, "Resampling", runtime.Image)
        alpha = alpha.resize((expected_width, expected_height), resampling.LANCZOS)
        rendered.putalpha(alpha)

    temporary_path = None
    try:
        temporary = tempfile.NamedTemporaryFile(
            prefix=f".{output.stem}.",
            suffix=".tmp.png",
            dir=output.parent,
            delete=False,
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        rendered.save(temporary_path, format="PNG")
        with runtime.Image.open(temporary_path) as verified:
            if verified.format != "PNG" or verified.size != (
                expected_width,
                expected_height,
            ):
                raise OSError("invalid Waifu2x output")
            verified.load()
        os.replace(temporary_path, output)
        temporary_path = None
    except OSError as exc:
        raise WorkerFailure("OUTPUT_WRITE_FAILED", "写入输出图片失败", 6) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return {
        "ok": True,
        "kind": "upscale",
        "output_path": str(output),
        "model": WAIFU2X_MODEL_ID,
        "scale": scale,
        "native_scale": 2,
        "source_width": source_width,
        "source_height": source_height,
        "width": expected_width,
        "height": expected_height,
        "device": device_name,
        "precision": precision,
        "tile": 0,
        "attempts": passes,
        "run_ms": max(0, int((time.perf_counter() - started) * 1000)),
    }


def upscale_request(
    *,
    input_path,
    output_path,
    model_id: str,
    model_path,
    scale: int,
    device: str,
    runtime_loader=load_runtime,
    waifu_runtime_loader=load_waifu_runtime,
) -> dict[str, object]:
    started = time.perf_counter()
    if model_id not in {DEFAULT_MODEL_ID, WAIFU2X_MODEL_ID}:
        raise WorkerFailure("MODEL_NOT_FOUND", "不支持的 Real-ESRGAN 模型", 2)
    expected_dimensions(1, 1, scale)
    source = Path(input_path)
    model = Path(model_path)
    output = Path(output_path)
    if not source.is_absolute():
        source = Path.cwd() / source
    if not model.is_absolute():
        model = Path.cwd() / model
    if not output.is_absolute():
        output = Path.cwd() / output
    if not source.is_file():
        raise WorkerFailure("INPUT_NOT_FOUND", "输入图片不存在", 2)
    model_available = model.is_dir() if model_id == WAIFU2X_MODEL_ID else model.is_file()
    if not model_available:
        raise WorkerFailure("MODEL_NOT_FOUND", "Real-ESRGAN 模型文件不存在", 2)
    if not output.parent.is_dir():
        raise WorkerFailure("INVALID_ARGUMENT", "输出目录不存在", 2)
    if source.resolve(strict=False) == output.resolve(strict=False):
        raise WorkerFailure("INVALID_ARGUMENT", "输出路径不能覆盖输入图片", 2)

    if model_id == WAIFU2X_MODEL_ID:
        return _waifu_upscale_request(
            source=source,
            output=output,
            model=model,
            scale=scale,
            device=device,
            started=started,
            runtime_loader=waifu_runtime_loader,
        )

    runtime = _runtime_or_failure(runtime_loader)
    device_kind, device_name, precision = _device(runtime, device)
    if hasattr(runtime, "numpy") and hasattr(runtime.cv2, "imdecode"):
        try:
            encoded_source = runtime.numpy.frombuffer(
                source.read_bytes(), dtype=runtime.numpy.uint8
            )
            image = runtime.cv2.imdecode(
                encoded_source, runtime.cv2.IMREAD_UNCHANGED
            )
        except (OSError, ValueError):
            image = None
    else:
        image = runtime.cv2.imread(str(source), runtime.cv2.IMREAD_UNCHANGED)
    if image is None:
        raise WorkerFailure("INPUT_DECODE_FAILED", "无法解码原图", 4)
    source_height, source_width = image.shape[:2]
    expected_width, expected_height = expected_dimensions(
        source_width, source_height, scale
    )
    strict_class = strict_realesrganer_class(
        runtime.RealESRGANer, runtime.torch
    )
    references: dict[str, object | None] = {"network": None, "upsampler": None}

    def attempt(tile: int):
        network = None
        upsampler = None
        try:
            with contextlib.redirect_stdout(sys.stderr):
                network = runtime.RRDBNet(**anime_6b_architecture())
                references["network"] = network
                upsampler = strict_class(
                    scale=4,
                    model_path=str(model),
                    model=network,
                    tile=tile,
                    tile_pad=10,
                    pre_pad=10,
                    half=device_kind == "cuda",
                    device=runtime.torch.device(device_name),
                )
                references["upsampler"] = upsampler
                result, _ = upsampler.enhance(
                    image,
                    outscale=float(scale),
                    alpha_upsampler="realesrgan",
                )
            return result
        except BaseException:
            references["upsampler"] = None
            references["network"] = None
            del upsampler
            del network
            raise

    def cleanup():
        references["upsampler"] = None
        references["network"] = None
        gc.collect()
        runtime.torch.cuda.empty_cache()

    try:
        rendered, tile, attempts = run_with_tile_retry(
            device_kind, attempt, cleanup
        )
    except WorkerFailure:
        raise
    except BaseException as exc:
        raise WorkerFailure("INFERENCE_FAILED", "Real-ESRGAN 推理失败", 6) from exc
    finally:
        references["upsampler"] = None
        references["network"] = None

    if tuple(rendered.shape[:2]) != (expected_height, expected_width):
        raise WorkerFailure("INFERENCE_FAILED", "Real-ESRGAN 输出尺寸异常", 6)

    temporary_path = None
    try:
        temporary = tempfile.NamedTemporaryFile(
            prefix=f".{output.stem}.",
            suffix=".tmp.png",
            dir=output.parent,
            delete=False,
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        if hasattr(runtime, "numpy") and hasattr(runtime.cv2, "imencode"):
            try:
                encoded_ok, encoded_png = runtime.cv2.imencode(".png", rendered)
                if not encoded_ok:
                    raise OSError("PNG encoding failed")
                temporary_path.write_bytes(encoded_png.tobytes())
            except (OSError, ValueError, AttributeError) as exc:
                raise WorkerFailure(
                    "OUTPUT_WRITE_FAILED", "写入输出图片失败", 6
                ) from exc
            try:
                encoded_verify = runtime.numpy.frombuffer(
                    temporary_path.read_bytes(), dtype=runtime.numpy.uint8
                )
                verified = runtime.cv2.imdecode(
                    encoded_verify, runtime.cv2.IMREAD_UNCHANGED
                )
            except (OSError, ValueError):
                verified = None
        else:
            if not runtime.cv2.imwrite(str(temporary_path), rendered):
                raise WorkerFailure("OUTPUT_WRITE_FAILED", "写入输出图片失败", 6)
            verified = runtime.cv2.imread(
                str(temporary_path), runtime.cv2.IMREAD_UNCHANGED
            )
        if verified is None or tuple(verified.shape[:2]) != (
            expected_height,
            expected_width,
        ):
            raise WorkerFailure("OUTPUT_WRITE_FAILED", "输出图片校验失败", 6)
        os.replace(temporary_path, output)
        temporary_path = None
    except WorkerFailure:
        raise
    except OSError as exc:
        raise WorkerFailure("OUTPUT_WRITE_FAILED", "写入输出图片失败", 6) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return {
        "ok": True,
        "kind": "upscale",
        "output_path": str(output),
        "model": DEFAULT_MODEL_ID,
        "scale": scale,
        "native_scale": 4,
        "source_width": source_width,
        "source_height": source_height,
        "width": expected_width,
        "height": expected_height,
        "device": device_name,
        "precision": precision,
        "tile": tile,
        "attempts": attempts,
        "run_ms": max(0, int((time.perf_counter() - started) * 1000)),
    }


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise WorkerFailure("INVALID_ARGUMENT", "参数无效", 2)


def build_parser():
    parser = JsonArgumentParser(prog="realesrgan_worker")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    upscale = commands.add_parser("upscale")
    upscale.add_argument("--input", required=True)
    upscale.add_argument("--output", required=True)
    upscale.add_argument("--model-id", required=True)
    upscale.add_argument("--model-path", required=True)
    upscale.add_argument("--scale", required=True, type=int, choices=(2, 4))
    upscale.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    return parser


def _dispatch(argv):
    namespace = build_parser().parse_args(argv)
    if namespace.command == "status":
        return status_request()
    return upscale_request(
        input_path=namespace.input,
        output_path=namespace.output,
        model_id=namespace.model_id,
        model_path=namespace.model_path,
        scale=namespace.scale,
        device=namespace.device,
    )


def main(argv=None) -> int:
    exit_code = 0
    try:
        with contextlib.redirect_stdout(sys.stderr):
            payload = _dispatch(sys.argv[1:] if argv is None else argv)
    except WorkerFailure as exc:
        exit_code = exc.exit_code
        payload = {
            "ok": False,
            "error_code": exc.error_code,
            "message": exc.message,
        }
    except BaseException as exc:
        exit_code = 6
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        payload = {
            "ok": False,
            "error_code": "INFERENCE_FAILED",
            "message": "Real-ESRGAN worker 执行失败",
        }
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
