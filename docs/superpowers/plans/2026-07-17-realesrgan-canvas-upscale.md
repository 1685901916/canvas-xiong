# Infinite Canvas 本地 RealESRGAN 画质提升 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 在不覆盖原图、不调用第三方图片 API 的前提下，为经典无限画布增加 Image → RealESRGAN 画质提升 → Output 的本地 CUDA 节点，并支持 2×/4×、保存恢复、下游连接和级联运行。

**Architecture:** FastAPI 主进程只做白名单、路径、大小、并发和子进程管理；独立 worker 使用系统 Python 延迟导入 Torch/RealESRGAN，并在进程内安装 torchvision 兼容 shim。前端把纯状态/请求映射放入独立 UMD/CommonJS 模块，canvas.js 只负责 DOM、连线、运行和现有 Output/日志集成。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、Pillow、OpenCV、PyTorch、BasicSR、RealESRGAN、原生浏览器 JavaScript、Node.js assert、PowerShell、Playwright CLI。

---

## 实施约束

- 只修改本地目录 F:\cursor\project29 画布工具\Infinite-Canvas-main。
- 当前目录没有 .git；不创建 commit、不 push、不向官方仓库提交。
- 实施前复制所有待修改文件到带时间戳的 backups\realesrgan-20260717-* 目录。
- 不修改系统 site-packages，不安装大型依赖到项目自带 python。
- 不读取 Cookie、Token、API Key；子进程使用最小环境，不向前端返回绝对模型路径或原始 traceback。
- 不替换现有 workflows\upscale.json、SeedVR2、ComfyUI、API生成、ModelScope、RunningHub、视频或 LLM 路线。
- 每个新行为严格执行 RED → GREEN → REFACTOR；完成声明前执行全量新鲜验证。

## 文件结构

**Create**

- realesrgan_support.py：轻量配置、白名单、路径/图片限制、worker 参数、JSON/错误解析和异步子进程封装；顶层不导入 Torch。
- tools/realesrgan_worker.py：兼容 shim、状态探测、RRDBNet/RealESRGANer 构造、tile/OOM 重试、PNG 原子输出。
- static/js/realesrgan-node.js：节点默认值、恢复归一化、菜单/连接判定、请求与结果元数据纯函数。
- tests/test_realesrgan_support.py：支持层与安全边界单元测试。
- tests/test_realesrgan_worker.py：不执行真实 forward 的 worker 逻辑测试。
- tests/realesrgan-node.test.js：前端纯函数测试。
- tests/realesrgan-canvas.integration.test.js：HTML/canvas.js/i18n/CSS 静态集成契约测试。

**Modify**

- main.py：请求模型、单 GPU 信号量、GET status、POST upscale。
- static/canvas.html：空白创建菜单和 realesrgan-node.js 脚本。
- static/js/canvas.js：节点创建、渲染、输入同步、运行、Output、日志、连接和级联。
- static/js/i18n/canvas.js：中英文文案。
- static/css/canvas.css：节点最小专用样式。

---

### Task 1: 建立本地备份和后端支持层

**Files:**

- Create: backups\realesrgan-20260717-<timestamp>\
- Create: tests/test_realesrgan_support.py
- Create: realesrgan_support.py

- [ ] **Step 1: 备份将修改的现有文件**

Run:

~~~powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path 'backups' ('realesrgan-20260717-' + $stamp)
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$files = @(
  'main.py',
  'static\canvas.html',
  'static\js\canvas.js',
  'static\js\i18n\canvas.js',
  'static\css\canvas.css'
)
foreach ($file in $files) {
  $target = Join-Path $backup $file
  New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
  Copy-Item -LiteralPath $file -Destination $target -Force
}
$backup
~~~

Expected: 输出唯一的本地备份目录；五个源文件与备份文件的 SHA256 一致。

- [ ] **Step 2: 写模型发现、倍率、路径白名单和 worker 协议失败测试**

Create tests/test_realesrgan_support.py with tests that import the wished-for API:

~~~python
import json
import tempfile
import unittest
from pathlib import Path

import realesrgan_support as rs


class RealESRGANSupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.assets = self.root / "assets"
        self.input_dir = self.assets / "input"
        self.output_dir = self.assets / "output"
        self.upload_dir = self.assets / "uploads"
        self.library_dir = self.assets / "library"
        self.model_dir = self.root / "models"
        for path in (self.input_dir, self.output_dir, self.upload_dir, self.library_dir, self.model_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.config = rs.RealESRGANConfig(
            python_executable=Path("python.exe"),
            worker_path=self.root / "tools" / "realesrgan_worker.py",
            model_dir=self.model_dir,
            output_dir=self.output_dir,
            allowed_input_roots=(self.input_dir, self.output_dir, self.upload_dir, self.library_dir),
            timeout_seconds=300.0,
            max_input_bytes=50 * 1024 * 1024,
            max_input_pixels=16_000_000,
            max_output_pixels=80_000_000,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_discovers_only_existing_whitelisted_model(self):
        (self.model_dir / "RealESRGAN_x4plus_anime_6B.pth").write_bytes(b"model")
        self.assertEqual(
            rs.discover_models(self.config),
            [{"id": "RealESRGAN_x4plus_anime_6B", "name": "RealESRGAN x4plus Anime 6B", "native_scale": 4}],
        )

    def test_rejects_unknown_model_and_invalid_scale(self):
        with self.assertRaises(rs.RealESRGANSupportError):
            rs.resolve_model_path(self.config, "../other.pth")
        with self.assertRaises(rs.RealESRGANSupportError):
            rs.validate_scale(3)

    def test_maps_allowed_asset_url_and_rejects_traversal(self):
        image = self.input_dir / "sample.png"
        image.write_bytes(b"png")
        self.assertEqual(rs.local_path_from_source_url("/assets/input/sample.png", self.config), image.resolve())
        with self.assertRaises(rs.RealESRGANSupportError):
            rs.local_path_from_source_url("/assets/input/%2e%2e/output/secret.png", self.config)
        with self.assertRaises(rs.RealESRGANSupportError):
            rs.local_path_from_source_url("https://example.com/a.png", self.config)

    def test_worker_args_are_an_array_with_server_selected_paths(self):
        args = rs.build_worker_args(
            self.config,
            source_path=self.input_dir / "sample.png",
            output_path=self.output_dir / "result.png",
            model_id="RealESRGAN_x4plus_anime_6B",
            scale=4,
        )
        self.assertEqual(args[0], "python.exe")
        self.assertIn("upscale", args)
        self.assertNotIn("shell=True", args)
        self.assertEqual(args[args.index("--scale") + 1], "4")

    def test_parses_single_worker_json_and_rejects_missing_output(self):
        payload = rs.parse_worker_json(json.dumps({"ok": True, "output_path": "x.png"}))
        self.assertTrue(payload["ok"])
        with self.assertRaises(rs.RealESRGANSupportError):
            rs.parse_worker_json("")


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 3: 运行测试并确认 RED**

Run:

~~~powershell
.\python\python.exe -m unittest tests.test_realesrgan_support -v
~~~

Expected: FAIL because realesrgan_support does not exist or the requested symbols are missing.

- [ ] **Step 4: 写最小支持层实现**

Create realesrgan_support.py with these public definitions and behavior:

~~~python
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, UnidentifiedImageError


DEFAULT_MODEL_ID = "RealESRGAN_x4plus_anime_6B"
SUPPORTED_SCALES = {2, 4}
SUPPORTED_MODELS = {
    DEFAULT_MODEL_ID: {
        "filename": "RealESRGAN_x4plus_anime_6B.pth",
        "name": "RealESRGAN x4plus Anime 6B",
        "native_scale": 4,
    }
}


class RealESRGANSupportError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400, code: str = "INVALID_ARGUMENT"):
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
    timeout_seconds: float
    max_input_bytes: int
    max_input_pixels: int
    max_output_pixels: int


@dataclass(frozen=True)
class ResolvedImage:
    path: Path
    width: int
    height: int
    size_bytes: int


def build_config(*, base_dir: str, assets_dir: str, legacy_output_dir: str, environ: Mapping[str, str] | None = None) -> RealESRGANConfig:
    env = dict(os.environ if environ is None else environ)
    home = Path(env.get("USERPROFILE") or Path.home())
    local_app_data = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
    python_path = Path(env.get("REALESRGAN_PYTHON") or local_app_data / "Programs" / "Python" / "Python312" / "python.exe")
    model_dir = Path(env.get("REALESRGAN_MODEL_DIR") or home / ".cache" / "realesrgan")
    assets = Path(assets_dir)
    return RealESRGANConfig(
        python_executable=python_path,
        worker_path=Path(base_dir) / "tools" / "realesrgan_worker.py",
        model_dir=model_dir,
        output_dir=assets / "output",
        allowed_input_roots=(assets / "input", assets / "output", assets / "uploads", assets / "library", Path(legacy_output_dir)),
        timeout_seconds=float(env.get("REALESRGAN_TIMEOUT_SECONDS", "300")),
        max_input_bytes=int(env.get("REALESRGAN_MAX_INPUT_BYTES", str(50 * 1024 * 1024))),
        max_input_pixels=int(env.get("REALESRGAN_MAX_INPUT_PIXELS", "16000000")),
        max_output_pixels=int(env.get("REALESRGAN_MAX_OUTPUT_PIXELS", "80000000")),
    )


def validate_scale(value: Any) -> int:
    try:
        scale = int(value)
    except (TypeError, ValueError):
        raise RealESRGANSupportError("倍率只支持 2× 或 4×", code="UNSUPPORTED_SCALE")
    if scale not in SUPPORTED_SCALES:
        raise RealESRGANSupportError("倍率只支持 2× 或 4×", code="UNSUPPORTED_SCALE")
    return scale


def discover_models(config: RealESRGANConfig) -> list[dict[str, Any]]:
    result = []
    for model_id, spec in SUPPORTED_MODELS.items():
        if (config.model_dir / spec["filename"]).is_file():
            result.append({"id": model_id, "name": spec["name"], "native_scale": spec["native_scale"]})
    return result


def resolve_model_path(config: RealESRGANConfig, model_id: str) -> Path:
    spec = SUPPORTED_MODELS.get(str(model_id or ""))
    if not spec:
        raise RealESRGANSupportError("未找到 RealESRGAN 本地模型", status_code=404, code="MODEL_NOT_FOUND")
    path = (config.model_dir / spec["filename"]).resolve()
    if not path.is_file():
        raise RealESRGANSupportError("未找到 RealESRGAN 本地模型", status_code=404, code="MODEL_NOT_FOUND")
    return path


def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def local_path_from_source_url(source_url: str, config: RealESRGANConfig) -> Path:
    raw = str(source_url or "")
    if "\x00" in raw or "\\" in raw:
        raise RealESRGANSupportError("只允许应用内本地图片", code="PATH_NOT_ALLOWED")
    clean = urllib.parse.unquote(raw.split("?", 1)[0])
    if clean.startswith("/assets/"):
        relative = clean[len("/assets/"):]
        candidate = config.allowed_input_roots[0].parent / relative
    elif clean.startswith("/output/"):
        relative = clean[len("/output/"):]
        candidate = config.allowed_input_roots[-1] / relative
    else:
        raise RealESRGANSupportError("只允许应用内本地图片", code="PATH_NOT_ALLOWED")
    if any(part in ("", ".", "..") for part in Path(relative).parts):
        raise RealESRGANSupportError("只允许应用内本地图片", code="PATH_NOT_ALLOWED")
    resolved = candidate.resolve()
    if not _inside(resolved, config.allowed_input_roots) or not resolved.is_file():
        raise RealESRGANSupportError("输入图片不存在", status_code=404, code="INPUT_NOT_FOUND")
    return resolved


def resolve_image(source_url: str, config: RealESRGANConfig, scale: int) -> ResolvedImage:
    scale = validate_scale(scale)
    path = local_path_from_source_url(source_url, config)
    size_bytes = path.stat().st_size
    if size_bytes > config.max_input_bytes:
        raise RealESRGANSupportError("输入图片过大", status_code=413, code="INPUT_TOO_LARGE")
    try:
        with Image.open(path) as image:
            width, height = image.size
            image.verify()
    except (OSError, UnidentifiedImageError):
        raise RealESRGANSupportError("输入不是可处理的图片", status_code=415, code="INPUT_DECODE_FAILED")
    pixels = width * height
    if pixels > config.max_input_pixels or pixels * scale * scale > config.max_output_pixels:
        raise RealESRGANSupportError("输入或输出尺寸过大", status_code=413, code="IMAGE_TOO_LARGE")
    return ResolvedImage(path=path, width=width, height=height, size_bytes=size_bytes)


def build_worker_args(config: RealESRGANConfig, *, source_path: Path, output_path: Path, model_id: str, scale: int, device: str = "auto") -> list[str]:
    model_path = resolve_model_path(config, model_id)
    scale = validate_scale(scale)
    return [
        str(config.python_executable), "-B", str(config.worker_path), "upscale",
        "--input", str(source_path), "--output", str(output_path),
        "--model-id", model_id, "--model-path", str(model_path),
        "--scale", str(scale), "--device", device,
    ]


def parse_worker_json(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in str(stdout or "").splitlines() if line.strip()]
    if len(lines) != 1:
        raise RealESRGANSupportError("RealESRGAN 返回内容无效", status_code=502, code="INVALID_WORKER_JSON")
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError:
        raise RealESRGANSupportError("RealESRGAN 返回内容无效", status_code=502, code="INVALID_WORKER_JSON")
    if not isinstance(payload, dict):
        raise RealESRGANSupportError("RealESRGAN 返回内容无效", status_code=502, code="INVALID_WORKER_JSON")
    return payload
~~~

- [ ] **Step 5: 扩展测试覆盖真实图片、像素上限、符号链接越界和错误映射**

Add focused tests using Pillow-created PNG files and skip symlink assertions only when Windows privileges prevent creating the link. Assert status codes 404, 413 and 415 and exact Chinese details.

- [ ] **Step 6: 运行测试并确认 GREEN**

Run:

~~~powershell
.\python\python.exe -m unittest tests.test_realesrgan_support -v
~~~

Expected: all support tests pass with zero warnings.

- [ ] **Step 7: REFACTOR 支持层并保持测试为绿**

Keep environment lookup inside build_config, keep Torch imports out of this module, and centralize worker error-code mapping in one dictionary.

---

### Task 2: 实现独立 RealESRGAN worker

**Files:**

- Create: tests/test_realesrgan_worker.py
- Create: tools/realesrgan_worker.py
- Modify: realesrgan_support.py
- Modify: tests/test_realesrgan_support.py

- [ ] **Step 1: 写 worker 纯逻辑失败测试**

Tests must cover:

~~~python
class WorkerLogicTests(unittest.TestCase):
    def test_anime_6b_architecture_is_exact(self):
        self.assertEqual(worker.anime_6b_architecture(), {
            "num_in_ch": 3, "num_out_ch": 3, "num_feat": 64,
            "num_block": 6, "num_grow_ch": 32, "scale": 4,
        })

    def test_retry_tiles_are_512_then_256(self):
        self.assertEqual(worker.retry_tiles("cuda"), (512, 256))
        self.assertEqual(worker.retry_tiles("cpu"), (0,))

    def test_expected_dimensions_support_only_two_and_four(self):
        self.assertEqual(worker.expected_dimensions(202, 360, 4), (808, 1440))
        self.assertEqual(worker.expected_dimensions(202, 360, 2), (404, 720))
        with self.assertRaises(ValueError):
            worker.expected_dimensions(202, 360, 3)
~~~

Add a fake-inference test that raises an exception containing out of memory on the first attempt, succeeds on the second, and asserts attempts use 512 then 256 exactly once.

- [ ] **Step 2: 运行 worker 测试并确认 RED**

Run:

~~~powershell
.\python\python.exe -m unittest tests.test_realesrgan_worker -v
~~~

Expected: FAIL because tools.realesrgan_worker and its functions do not exist.

- [ ] **Step 3: 实现 worker CLI 和延迟导入**

Create tools/realesrgan_worker.py with:

~~~python
def install_torchvision_compat_shim():
    import sys
    import types
    from torchvision.transforms.functional import rgb_to_grayscale
    name = "torchvision.transforms.functional_tensor"
    if name not in sys.modules:
        shim = types.ModuleType(name)
        shim.rgb_to_grayscale = rgb_to_grayscale
        sys.modules[name] = shim


def anime_6b_architecture():
    return {
        "num_in_ch": 3,
        "num_out_ch": 3,
        "num_feat": 64,
        "num_block": 6,
        "num_grow_ch": 32,
        "scale": 4,
    }


def retry_tiles(device_kind):
    return (512, 256) if device_kind == "cuda" else (0,)


def expected_dimensions(width, height, scale):
    scale = int(scale)
    if scale not in (2, 4):
        raise ValueError("scale must be 2 or 4")
    return width * scale, height * scale
~~~

The status command installs the shim, imports torch/realesrgan/basicsr, and prints one JSON object containing ok, cuda, device and version fields.

The upscale command:

1. validates model ID and scale again;
2. reads with cv2.IMREAD_UNCHANGED;
3. builds RRDBNet with anime_6b_architecture();
4. builds RealESRGANer with scale=4, tile_pad=10, pre_pad=10, half only for CUDA and device=torch.device("cuda:0") or CPU;
5. calls enhance with outscale=float(scale) and alpha_upsampler="realesrgan";
6. redirects library stdout to stderr;
7. retries CUDA OOM once with tile 512 → 256 after deleting model/upsampler, gc.collect() and torch.cuda.empty_cache();
8. writes to a sibling temporary PNG, reopens it, verifies exact dimensions, then os.replace() to the requested output;
9. never overwrites or deletes the input;
10. prints exactly one final JSON object to stdout.

Use a local RealESRGANer subclass for tile_process so upstream RuntimeError is not swallowed and progress text does not pollute stdout. Do not patch installed packages.

- [ ] **Step 4: 运行 worker 单元测试并确认 GREEN**

Run:

~~~powershell
.\python\python.exe -m unittest tests.test_realesrgan_worker -v
~~~

Expected: all worker logic tests pass without loading a model or executing a GPU forward.

- [ ] **Step 5: 写支持层异步子进程失败测试**

Add tests for probe_worker and run_worker using injected subprocess factories:

- create_subprocess_exec receives the argument array and shell is never used;
- timeout calls kill and wait;
- malformed stdout maps to HTTP 502;
- CUDA_OOM maps to 显存不足，请使用更小的原图 and HTTP 503;
- success without a valid output PNG maps to RealESRGAN 未生成输出图片;
- the child environment excludes variable names containing KEY, TOKEN, COOKIE, SECRET or PASSWORD.

- [ ] **Step 6: 实现异步 probe/run 与最小环境**

Add to realesrgan_support.py:

~~~python
def minimal_worker_env(environ=None):
    source = dict(os.environ if environ is None else environ)
    allowed = {
        "SystemRoot", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP",
        "USERPROFILE", "LOCALAPPDATA", "APPDATA", "CUDA_PATH",
    }
    return {key: value for key, value in source.items() if key in allowed or key.startswith("CUDA_PATH_V")}


async def run_process(args, *, timeout_seconds, environ=None):
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=minimal_worker_env(environ),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RealESRGANSupportError("画质提升超时", status_code=504, code="TIMEOUT")
    payload = parse_worker_json(stdout.decode("utf-8", "replace"))
    if process.returncode != 0 or not payload.get("ok"):
        raise mapped_worker_error(payload)
    return payload
~~~

- [ ] **Step 7: 运行两个后端测试模块并确认 GREEN**

Run:

~~~powershell
.\python\python.exe -m unittest tests.test_realesrgan_support tests.test_realesrgan_worker -v
~~~

Expected: all tests pass.

---

### Task 3: 接入 FastAPI 状态与提升接口

**Files:**

- Modify: main.py
- Modify: tests/test_realesrgan_support.py

- [ ] **Step 1: 写 API 包装失败测试**

Directly call async route functions with asyncio.run, following existing project tests:

~~~python
def test_status_hides_model_paths_and_credentials(self):
    with patch.object(main, "probe_realesrgan_status", new=AsyncMock(return_value={
        "ok": True, "cuda": True, "device": "NVIDIA GeForce RTX 4060 Laptop GPU",
    })):
        payload = asyncio.run(main.realesrgan_status())
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["models"][0]["id"], "RealESRGAN_x4plus_anime_6B")
    self.assertNotIn("model_path", payload)


def test_upscale_returns_local_output_metadata(self):
    request = main.RealESRGANUpscaleRequest(
        source_url="/assets/input/sample.png",
        model="RealESRGAN_x4plus_anime_6B",
        scale=4,
    )
    with patch.object(main, "run_realesrgan_upscale", new=AsyncMock(return_value={
        "ok": True, "device": "cuda", "run_ms": 10,
        "source_width": 8, "source_height": 8, "width": 32, "height": 32,
    })):
        payload = asyncio.run(main.realesrgan_upscale(request))
    self.assertTrue(payload["url"].startswith("/assets/output/realesrgan_"))
~~~

Also test invalid local URL, missing model, timeout and output cleanup on failure.

- [ ] **Step 2: 运行 API tests 并确认 RED**

Run:

~~~powershell
.\python\python.exe -m unittest tests.test_realesrgan_support -v
~~~

Expected: FAIL because the request model and routes are missing.

- [ ] **Step 3: 添加配置、请求模型、信号量和路由**

Modify main.py:

~~~python
from typing import Literal

from realesrgan_support import (
    DEFAULT_MODEL_ID,
    RealESRGANSupportError,
    build_config,
    discover_models,
    probe_worker,
    resolve_image,
    run_upscale_worker,
)


class RealESRGANUpscaleRequest(BaseModel):
    source_url: str = Field(min_length=1, max_length=2048)
    model: str = Field(default=DEFAULT_MODEL_ID, min_length=1, max_length=128)
    scale: Literal[2, 4] = 4


REALESRGAN_GPU_SEMAPHORE = asyncio.Semaphore(1)
~~~

Build configuration inside each route after environment loading rather than caching it at module import.

GET /api/realesrgan/status:

- returns HTTP 200 with ok false if runtime or model is unavailable;
- returns python, cuda, device and public model descriptors when available;
- caches probe data for a short in-process TTL but never caches credentials or model paths.

POST /api/realesrgan/upscale:

- resolves and verifies the source under allowed roots;
- generates filename realesrgan_<12 hex>.png on the server;
- awaits the single GPU semaphore;
- launches the worker with an argument array;
- verifies the final PNG exists, decodes and has exact dimensions;
- removes partial output on any failure;
- converts RealESRGANSupportError to HTTPException using its status_code/detail;
- returns only the response fields defined in the design.

- [ ] **Step 4: 运行后端 tests 并确认 GREEN**

Run:

~~~powershell
.\python\python.exe -m unittest tests.test_realesrgan_support tests.test_realesrgan_worker -v
~~~

Expected: all tests pass.

- [ ] **Step 5: 编译后端**

Run:

~~~powershell
.\python\python.exe -m py_compile main.py realesrgan_support.py tools\realesrgan_worker.py
~~~

Expected: exit code 0 with no output.

---

### Task 4: 建立前端纯函数模块

**Files:**

- Create: tests/realesrgan-node.test.js
- Create: static/js/realesrgan-node.js

- [ ] **Step 1: 写前端纯函数失败测试**

Create tests/realesrgan-node.test.js using require and assert:

~~~javascript
const assert = require('assert');
const real = require('../static/js/realesrgan-node.js');

{
  const node = real.createDefaultNode({id:'realesr_1', x:10, y:20});
  assert.equal(node.type, 'realesrgan');
  assert.equal(node.model, 'RealESRGAN_x4plus_anime_6B');
  assert.equal(node.scale, 4);
  assert.equal(node.device, 'auto');
  assert.deepEqual(node.inputs, []);
}

{
  assert.equal(real.normalizeScale('2'), 2);
  assert.equal(real.normalizeScale(3), 4);
}

{
  const ref = real.firstImageRef([
    {refs:[{url:'/a.mp4', kind:'video'}]},
    {refs:[{url:'/a.png', kind:'image'}, {url:'/b.png', kind:'image'}]},
  ]);
  assert.equal(ref.url, '/a.png');
}

{
  assert.equal(real.isMenuSourceType('image'), true);
  assert.equal(real.isMenuSourceType('group'), true);
  assert.equal(real.isMenuSourceType('output'), true);
  assert.equal(real.isMenuSourceType('prompt'), false);
}

{
  assert.deepEqual(real.buildRequest(
    {model:'RealESRGAN_x4plus_anime_6B', scale:4},
    {url:'/assets/input/a.png'}
  ), {
    source_url:'/assets/input/a.png',
    model:'RealESRGAN_x4plus_anime_6B',
    scale:4,
  });
}

console.log('realesrgan-node tests passed');
~~~

Add cases for restored invalid fields, discovered model fallback, CUDA/CPU labels, empty result rejection and metadata normalization.

- [ ] **Step 2: 运行 Node test 并确认 RED**

Run:

~~~powershell
node tests/realesrgan-node.test.js
~~~

Expected: FAIL because static/js/realesrgan-node.js does not exist.

- [ ] **Step 3: 实现 UMD/CommonJS 纯函数模块**

Create static/js/realesrgan-node.js exporting:

~~~javascript
(function(root, factory){
  const api = factory();
  if(typeof module === 'object' && module.exports) module.exports = api;
  else root.RealESRGANCanvas = api;
})(typeof self !== 'undefined' ? self : this, function(){
  const DEFAULT_MODEL = 'RealESRGAN_x4plus_anime_6B';
  const DEFAULT_SCALE = 4;

  function normalizeScale(value){
    const scale = Number(value);
    return scale === 2 || scale === 4 ? scale : DEFAULT_SCALE;
  }

  function normalizeModel(value, models){
    const ids = (models || []).map(function(item){ return item.id; }).filter(Boolean);
    if(ids.includes(value)) return value;
    return ids[0] || DEFAULT_MODEL;
  }

  function createDefaultNode(options){
    const source = options || {};
    return {
      id: source.id,
      type: 'realesrgan',
      x: Number(source.x) || 0,
      y: Number(source.y) || 0,
      w: 360,
      h: 390,
      model: DEFAULT_MODEL,
      scale: DEFAULT_SCALE,
      device: 'auto',
      inputs: [],
      generatedOutputs: [],
      runStatus: '',
      runError: ''
    };
  }

  function normalizeNode(node, models){
    const result = Object.assign(createDefaultNode(node), node || {});
    result.model = normalizeModel(result.model, models);
    result.scale = normalizeScale(result.scale);
    result.device = 'auto';
    result.inputs = Array.isArray(result.inputs) ? result.inputs : [];
    result.generatedOutputs = Array.isArray(result.generatedOutputs) ? result.generatedOutputs : [];
    return result;
  }

  function isMenuSourceType(type){
    return ['image', 'group', 'output'].includes(type);
  }

  function firstImageRef(sources){
    for(const source of sources || []){
      for(const ref of source.refs || []){
        if(ref && ref.url && (!ref.kind || ref.kind === 'image')) return ref;
      }
    }
    return null;
  }

  function buildRequest(node, ref){
    if(!ref || !ref.url) throw new Error('请先连接一张图片');
    return {
      source_url: ref.url,
      model: normalizeModel(node && node.model),
      scale: normalizeScale(node && node.scale)
    };
  }

  function normalizeStatus(payload){
    const source = payload || {};
    return {
      ok: Boolean(source.ok),
      cuda: Boolean(source.cuda),
      device: String(source.device || ''),
      models: Array.isArray(source.models) ? source.models : [],
      message: String(source.message || '')
    };
  }

  function deviceLabel(status){
    const value = normalizeStatus(status);
    if(!value.ok) return value.message || 'RealESRGAN 运行环境不可用';
    return value.cuda ? 'CUDA · ' + (value.device || 'GPU') : 'CPU · 较慢';
  }

  function resultMeta(payload){
    if(!payload || !payload.ok || !payload.url) throw new Error('RealESRGAN 未生成输出图片');
    return {
      url: payload.url,
      model: payload.model,
      scale: Number(payload.scale),
      source_width: Number(payload.source_width),
      source_height: Number(payload.source_height),
      width: Number(payload.width),
      height: Number(payload.height),
      device: payload.device,
      run_ms: Number(payload.run_ms) || 0
    };
  }

  return {
    DEFAULT_MODEL,
    DEFAULT_SCALE,
    normalizeScale,
    normalizeModel,
    createDefaultNode,
    normalizeNode,
    isMenuSourceType,
    firstImageRef,
    buildRequest,
    normalizeStatus,
    deviceLabel,
    resultMeta
  };
});
~~~

- [ ] **Step 4: 运行 Node test 并确认 GREEN**

Run:

~~~powershell
node tests/realesrgan-node.test.js
node --check static/js/realesrgan-node.js
~~~

Expected: test success message and both commands exit 0.

---

### Task 5: 接入画布节点、菜单、Output、日志和级联

**Files:**

- Create: tests/realesrgan-canvas.integration.test.js
- Modify: static/canvas.html
- Modify: static/js/canvas.js
- Modify: static/js/i18n/canvas.js
- Modify: static/css/canvas.css

- [ ] **Step 1: 写画布静态集成失败测试**

The test reads the four frontend files and asserts:

~~~javascript
assert.match(html, /menuAdd\('realesrgan'\)/);
assert.match(html, /realesrgan-node\.js.*canvas\.js/s);
assert.match(canvas, /function addRealESRGANNode/);
assert.match(canvas, /type:'realesrgan'/);
assert.match(canvas, /function renderRealESRGANBody/);
assert.match(canvas, /function runRealESRGANNode/);
assert.match(canvas, /\/api\/realesrgan\/status/);
assert.match(canvas, /\/api\/realesrgan\/upscale/);
assert.match(canvas, /node\.type === 'realesrgan'.*runRealESRGANNode/s);
assert.match(i18n, /canvas\.qualityUpscale/);
assert.match(css, /\.realesrgan-node/);
~~~

Also assert RealESRGAN is included in all image output/run type collections and that a dedicated input guard rejects prompt/loop/llm.

- [ ] **Step 2: 运行集成 test 并确认 RED**

Run:

~~~powershell
node tests/realesrgan-canvas.integration.test.js
~~~

Expected: FAIL on the first missing menu/script/node contract.

- [ ] **Step 3: 添加 HTML 与国际化**

In static/canvas.html:

~~~html
<button class="menu-btn" onclick="menuAdd('realesrgan')"><i data-lucide="sparkles" class="w-4 h-4"></i><span data-i18n="canvas.qualityUpscale">画质提升</span></button>
~~~

Load static/js/realesrgan-node.js immediately before canvas.js.

Add Chinese/English keys:

- canvas.qualityUpscale: 画质提升 / Upscale
- canvas.realesrganTitle: RealESRGAN 画质提升 / RealESRGAN Upscale
- canvas.realesrganModel: 模型 / Model
- canvas.upscaleScale: 倍率 / Scale
- canvas.runDevice: 运行设备 / Device
- canvas.startUpscale: 开始提升 / Start Upscale
- canvas.upscaling: 提升中 / Upscaling
- canvas.cpuSlow: CPU · 较慢 / CPU · Slow
- all exact error texts from the design.

- [ ] **Step 4: 添加节点创建、默认值、标题、body 与端口**

In canvas.js:

- addRealESRGANNode(point) calls RealESRGANCanvas.createDefaultNode and addNode;
- createNodeByType and menuAdd handle realesrgan;
- defaultNodeSize returns 360×390;
- renderNode title is RealESRGAN 画质提升;
- status badge includes realesrgan;
- body dispatch calls renderRealESRGANBody(node);
- canInput and canOutput both include realesrgan;
- transient status is not persisted; restored fields are normalized.

renderRealESRGANBody must contain:

- first valid image preview;
- discovered model select;
- scale select with 2× and 4×, default 4×;
- read-only device label;
- start button, cascade button and retry bar;
- no tile/half/model path control.

- [ ] **Step 5: 添加菜单和严格连接规则**

Update linkCreateOptions:

- image, group and output right ports include 画质提升;
- prompt, loop and llm do not;
- image-output generators include 画质提升 in outputOptions.

Update type collections:

~~~javascript
const CANVAS_GENERATOR_TYPES = ['generator','msgen','comfy','ltxDirector','video','rh','realesrgan'];
const CANVAS_IMAGE_OUTPUT_TYPES = ['generator','msgen','comfy','ltxDirector','rh','realesrgan'];
const CANVAS_MEDIA_OUTPUT_TYPES = ['generator','msgen','comfy','ltxDirector','video','rh','realesrgan'];
~~~

Before the generic tail of canConnect, add:

~~~javascript
if(to.type === 'realesrgan'){
  if(CANVAS_IMAGE_OUTPUT_TYPES.includes(from.type)) return !wouldCreateGeneratorCycle(fromId, toId);
  return ['image','group','output'].includes(from.type);
}
~~~

- [ ] **Step 6: 实现状态缓存、运行与强制 Output**

Add ensureRealESRGANStatus with one shared Promise and optional force refresh. Fetch GET /api/realesrgan/status once, normalize public data, and refresh only RealESRGAN nodes.

runRealESRGANNode:

1. takes the first image from orderedSources/generatorSources;
2. throws 请先连接一张图片 if absent;
3. always creates or reuses an explicit Output, even when a downstream generator exists;
4. posts RealESRGANCanvas.buildRequest to /api/realesrgan/upscale;
5. appends one result without duplicates and never mutates the source Image;
6. merges generatedOutputs for direct downstream use;
7. records Local RealESRGAN, model, scale, dimensions, device and run_ms in generation logs;
8. preserves prior Output images on failure;
9. rethrows during cascade and shows the existing error modal during single-node execution.

Use a dedicated ensureRealESRGANOutput(node, dx=420) instead of changing outputForNode semantics for all existing generators.

- [ ] **Step 7: 接入输入刷新与级联**

Add realesrgan branches to:

- refreshGeneratorInputViews;
- runCascadeNodeByType;
- canvasRunTypes;
- runOneCascadePass;
- cascadeParallelLimit, returning 1 if any node is realesrgan;
- run task/platform label helpers.

The resulting supported workflows are:

~~~text
Image → RealESRGAN → Output
Image → RealESRGAN → Output → other image node
Image → RealESRGAN → other image node
~~~

- [ ] **Step 8: 添加最小 CSS**

Reuse generator-body, input-list, select-lite, gen-run-row and gen-btn. Add only:

~~~css
.realesrgan-node { width:360px; height:390px; }
.node.sized.realesrgan-node .generator-body { height:100%; display:flex; flex-direction:column; }
.node.sized.realesrgan-node .input-list { flex:1; min-height:72px; max-height:none; }
.node.sized.realesrgan-node .gen-run-row { margin-top:auto; }
.realesrgan-device-status { min-height:30px; display:flex; align-items:center; color:var(--muted); font-size:11px; font-weight:800; }
~~~

- [ ] **Step 9: 运行前端 tests 与语法检查并确认 GREEN**

Run:

~~~powershell
node tests/realesrgan-node.test.js
node tests/realesrgan-canvas.integration.test.js
node tests/character-overlay.test.js
node --check static/js/realesrgan-node.js
node --check static/js/canvas.js
~~~

Expected: all commands exit 0; existing character overlay test remains green.

---

### Task 6: 全量验证与真实本地验收

**Files:**

- Verify only; no remote writes.
- Browser artifacts: output/playwright/

- [ ] **Step 1: 运行完整自动化验证**

Run:

~~~powershell
.\python\python.exe -m py_compile main.py realesrgan_support.py tools\realesrgan_worker.py
.\python\python.exe -m unittest tests.test_realesrgan_support tests.test_realesrgan_worker -v
node tests/realesrgan-node.test.js
node tests/realesrgan-canvas.integration.test.js
node tests/character-overlay.test.js
node --check static/js/realesrgan-node.js
node --check static/js/canvas.js
~~~

Expected: every command exits 0 with zero test failures.

- [ ] **Step 2: 重启本地服务并验证状态接口**

Read the live PID again; stop only the process whose command line and working directory identify this project, start the existing project launch command hidden, then call:

~~~powershell
Invoke-RestMethod http://127.0.0.1:3001/api/realesrgan/status | ConvertTo-Json -Depth 5
~~~

Expected: ok true, cuda true, device names the RTX 4060, and the model list contains RealESRGAN_x4plus_anime_6B without absolute model path or credentials.

- [ ] **Step 3: 执行一次真实 CUDA 4× 推理**

Use assets\input\ai_ref_327a57407b19.png if it still exists and is 202×360. Record its SHA256 before the run.

Run the POST endpoint once with scale 4 and verify:

- response ok true;
- output URL is under /assets/output;
- output file is a valid PNG of 808×1440;
- device reports CUDA;
- run_ms is positive;
- input SHA256 is unchanged;
- no model download and no third-party image API request occurs.

2× request construction and exact 2× dimensions remain covered by unit tests so the expensive real forward runs only once.

- [ ] **Step 4: Playwright browser acceptance**

First verify npx is available. Use the installed Playwright CLI wrapper and save artifacts under output/playwright.

Browser flow:

1. open http://127.0.0.1:3001/canvas.html with the existing local canvas ID;
2. snapshot;
3. create or use an Image node with a local image;
4. drag from its right port to empty canvas;
5. snapshot and click 画质提升;
6. verify the created title is RealESRGAN 画质提升 and the source connection exists;
7. verify model select contains RealESRGAN_x4plus_anime_6B;
8. verify scale select offers 2× and 4× and defaults to 4×;
9. click 开始提升;
10. verify an Output is created/reused, original Image remains unchanged, and the result is appended;
11. inspect browser console and network for errors and confirm no third-party image endpoint was called;
12. capture the final screenshot.

- [ ] **Step 5: 规格覆盖复核**

Re-read docs/superpowers/specs/2026-07-17-realesrgan-canvas-upscale-design.md and explicitly verify every acceptance item:

- menu entry and auto connection;
- local model discovery;
- 2×/4×;
- CUDA;
- original preserved;
- Output append/reuse;
- downstream and cascade;
- missing input/model/runtime/image/OOM/timeout/no-output messages;
- existing generation systems unchanged;
- no site-packages edit, credentials, third-party API, commit or push.

- [ ] **Step 6: 最终差异与备份核对**

List created/modified files, compare existing files to their backup copies, and verify no file outside the project or the expected assets/output result was changed. Report the exact test counts, real output path/dimensions, browser artifact path and any remaining limitation.

---

## 计划自查结论

- 规格覆盖：创建入口、节点控件、模型发现、2×/4×、独立 worker、路径安全、单 GPU、错误处理、Output、日志、级联、保存恢复和浏览器验收均有对应任务。
- 占位内容：计划中的 <timestamp> 是执行命令实时生成的备份目录名，不是代码占位；所有生产字段、函数和测试命令均已定义。
- 字段一致性：节点统一使用 type=realesrgan、model、scale、device、inputs、generatedOutputs、runStatus、runError；API 统一使用 source_url、model、scale；响应统一使用 url、source_width、source_height、width、height、device、run_ms。
- 用户约束：明确不 commit、不 push、不调用第三方图片 API、不修改 site-packages、不读取凭据。
