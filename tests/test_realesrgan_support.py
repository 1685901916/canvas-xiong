import asyncio
import json
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from PIL import Image

import realesrgan_support as support


class RealESRGANSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.base_dir = self.root / "app"
        self.assets_dir = self.base_dir / "assets"
        self.legacy_output_dir = self.base_dir / "output"
        for relative in ("input", "output", "uploads", "library"):
            (self.assets_dir / relative).mkdir(parents=True, exist_ok=True)
        self.legacy_output_dir.mkdir(parents=True, exist_ok=True)

    def build_config(self, **environment):
        defaults = {
            "REALESRGAN_PYTHON": str(self.root / "python.exe"),
            "REALESRGAN_MODEL_DIR": str(self.root / "models"),
        }
        defaults.update(environment)
        return support.build_config(
            self.base_dir,
            self.assets_dir,
            self.legacy_output_dir,
            environ=defaults,
        )

    def create_png(self, path, size=(8, 6)):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, (20, 40, 60)).save(path, "PNG")
        return path

    def assert_support_error(self, expected_status, expected_code, callable_):
        with self.assertRaises(support.RealESRGANSupportError) as raised:
            callable_()
        self.assertEqual(expected_status, raised.exception.status_code)
        self.assertEqual(expected_code, raised.exception.code)
        return raised.exception

    def test_public_constants_and_error(self):
        self.assertEqual("RealESRGAN_x4plus_anime_6B", support.DEFAULT_MODEL_ID)
        self.assertEqual(
            {
                "RealESRGAN_x4plus_anime_6B": {
                    "filename": "RealESRGAN_x4plus_anime_6B.pth",
                    "name": "RealESRGAN x4plus Anime 6B",
                    "native_scale": 4,
                },
                "Waifu2x_CUNet": {
                    "package_subdir": "waifu2x_ncnn_py/models/models-cunet",
                    "required_files": (
                        "noise0_scale2.0x_model.param",
                        "noise0_scale2.0x_model.bin",
                    ),
                    "filename": "models-cunet",
                    "name": "Waifu2x CUNet（动漫）",
                    "native_scale": 2,
                },
            },
            support.SUPPORTED_MODELS,
        )
        error = support.RealESRGANSupportError("bad value")
        self.assertEqual("bad value", error.detail)
        self.assertEqual(400, error.status_code)
        self.assertEqual("INVALID_ARGUMENT", error.code)
        self.assertEqual("bad value", str(error))

    def test_build_config_is_frozen_and_reads_environment_at_call_time(self):
        first = self.build_config(
            REALESRGAN_TIMEOUT_SECONDS="17",
            REALESRGAN_MAX_INPUT_BYTES="1234",
            REALESRGAN_MAX_INPUT_PIXELS="2345",
            REALESRGAN_MAX_OUTPUT_PIXELS="3456",
        )
        second = self.build_config(REALESRGAN_PYTHON=str(self.root / "other.exe"))

        self.assertEqual(self.root / "python.exe", first.python_executable)
        self.assertEqual(
            self.base_dir / "tools" / "realesrgan_worker.py", first.worker_path
        )
        self.assertEqual(self.root / "models", first.model_dir)
        self.assertEqual(self.assets_dir / "output", first.output_dir)
        self.assertEqual(
            (
                self.assets_dir / "input",
                self.assets_dir / "output",
                self.assets_dir / "uploads",
                self.assets_dir / "library",
                self.legacy_output_dir,
            ),
            first.allowed_input_roots,
        )
        self.assertEqual(17, first.timeout_seconds)
        self.assertEqual(1234, first.max_input_bytes)
        self.assertEqual(2345, first.max_input_pixels)
        self.assertEqual(3456, first.max_output_pixels)
        self.assertEqual(self.root / "other.exe", second.python_executable)
        with self.assertRaises((AttributeError, TypeError)):
            first.timeout_seconds = 99

    @mock.patch("realesrgan_support.os.name", "nt")
    @mock.patch("realesrgan_support.Path.home")
    def test_build_config_uses_windows_defaults(self, home):
        home.return_value = self.root / "home"
        config = support.build_config(
            self.base_dir, self.assets_dir, self.legacy_output_dir, environ={}
        )
        self.assertEqual(
            self.root
            / "home"
            / "AppData"
            / "Local"
            / "Programs"
            / "Python"
            / "Python312"
            / "python.exe",
            config.python_executable,
        )
        self.assertEqual(self.root / "home" / ".cache" / "realesrgan", config.model_dir)

    def test_validate_scale_only_accepts_two_and_four(self):
        for value, expected in ((2, 2), (4, 4), ("2", 2), ("4", 4)):
            with self.subTest(value=value):
                self.assertEqual(expected, support.validate_scale(value))
        for value in (None, True, 0, 3, 8, "", "2.0", " 2", "x2"):
            with self.subTest(value=value):
                self.assert_support_error(
                    400, "INVALID_SCALE", lambda value=value: support.validate_scale(value)
                )

    def test_model_discovery_and_resolution_use_fixed_whitelist(self):
        config = self.build_config()
        config.model_dir.mkdir(parents=True)
        (config.model_dir / "unknown.pth").write_bytes(b"unknown")
        self.assertEqual([], support.discover_models(config))

        expected = config.model_dir / "RealESRGAN_x4plus_anime_6B.pth"
        expected.write_bytes(b"model")
        models = support.discover_models(config)
        self.assertEqual(
            [
                {
                    "id": support.DEFAULT_MODEL_ID,
                    "filename": expected.name,
                    "name": "RealESRGAN x4plus Anime 6B",
                    "native_scale": 4,
                }
            ],
            models,
        )
        self.assertFalse(Path(models[0]["filename"]).is_absolute())
        self.assertEqual(expected, support.resolve_model_path(support.DEFAULT_MODEL_ID, config))
        self.assert_support_error(
            404, "MODEL_NOT_FOUND", lambda: support.resolve_model_path("unknown", config)
        )
        expected.unlink()
        self.assert_support_error(
            404,
            "MODEL_NOT_FOUND",
            lambda: support.resolve_model_path(support.DEFAULT_MODEL_ID, config),
        )

        waifu_path = (
            config.python_executable.parent
            / "Lib"
            / "site-packages"
            / "waifu2x_ncnn_py"
            / "models"
            / "models-cunet"
        )
        waifu_path.mkdir(parents=True)
        for filename in support.SUPPORTED_MODELS[support.WAIFU2X_MODEL_ID][
            "required_files"
        ]:
            (waifu_path / filename).write_bytes(b"model")
        self.assertEqual(
            waifu_path,
            support.resolve_model_path(support.WAIFU2X_MODEL_ID, config),
        )
        waifu_model = support.discover_models(config)[0]
        self.assertEqual(support.WAIFU2X_MODEL_ID, waifu_model["id"])
        self.assertEqual(2, waifu_model["native_scale"])

    def test_local_path_accepts_assets_and_legacy_output_urls(self):
        config = self.build_config()
        asset = self.create_png(self.assets_dir / "uploads" / "space name.png")
        legacy = self.create_png(self.legacy_output_dir / "old.png")
        self.assertEqual(
            asset,
            support.local_path_from_source_url(
                "/assets/uploads/space%20name.png",
                config,
                assets_dir=self.assets_dir,
                legacy_output_dir=self.legacy_output_dir,
            ),
        )
        self.assertEqual(
            legacy,
            support.local_path_from_source_url(
                "/output/old.png",
                config,
                assets_dir=self.assets_dir,
                legacy_output_dir=self.legacy_output_dir,
            ),
        )

    def test_local_path_rejects_unsafe_or_non_file_sources(self):
        config = self.build_config()
        self.create_png(self.assets_dir / "uploads" / "ok.png")
        invalid = (
            "",
            "/assets/../main.py",
            "/assets/%2e%2e/main.py",
            "/assets/uploads/%2E%2E/ok.png",
            "/assets/uploads\\ok.png",
            "/assets/uploads/%5cok.png",
            "/assets/uploads/a%00.png",
            "/assets/uploads",
            "/other/ok.png",
            "assets/uploads/ok.png",
            "C:/assets/uploads/ok.png",
            "https://example.test/a.png",
            "file:///tmp/a.png",
        )
        for source in invalid:
            with self.subTest(source=source):
                self.assert_support_error(
                    400,
                    "INVALID_SOURCE",
                    lambda source=source: support.local_path_from_source_url(
                        source,
                        config,
                        assets_dir=self.assets_dir,
                        legacy_output_dir=self.legacy_output_dir,
                    ),
                )

    def test_local_path_rejects_symlink_escape(self):
        config = self.build_config()
        outside = self.create_png(self.root / "outside.png")
        link = self.assets_dir / "uploads" / "link.png"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        self.assert_support_error(
            400,
            "INVALID_SOURCE",
            lambda: support.local_path_from_source_url(
                "/assets/uploads/link.png",
                config,
                assets_dir=self.assets_dir,
                legacy_output_dir=self.legacy_output_dir,
            ),
        )

    def test_local_path_classifies_resolution_errors(self):
        config = self.build_config()
        original_resolve = Path.resolve
        cases = (
            (FileNotFoundError("missing"), 404, "INPUT_NOT_FOUND", "输入图片不存在"),
            (NotADirectoryError("not a directory"), 404, "INPUT_NOT_FOUND", "输入图片不存在"),
            (PermissionError("denied"), 403, "INPUT_FORBIDDEN", "无权读取输入图片"),
            (OSError("io failure"), 500, "INPUT_ACCESS_FAILED", "读取输入图片失败"),
            (RuntimeError("symlink loop"), 400, "PATH_NOT_ALLOWED", "输入图片路径不在允许范围内"),
        )
        for source_error, status, code, detail in cases:
            with self.subTest(error=type(source_error).__name__):
                def resolving(path, strict=False):
                    if path.name == "access.png":
                        raise source_error
                    return original_resolve(path, strict=strict)

                with mock.patch.object(Path, "resolve", autospec=True, side_effect=resolving):
                    error = self.assert_support_error(
                        status,
                        code,
                        lambda: support.local_path_from_source_url(
                            "/assets/uploads/access.png",
                            config,
                            assets_dir=self.assets_dir,
                            legacy_output_dir=self.legacy_output_dir,
                        ),
                    )
                self.assertEqual(detail, error.detail)
                self.assertIs(source_error, error.__cause__)

    def test_resolve_image_returns_verified_dimensions_and_size(self):
        config = self.build_config()
        path = self.create_png(self.assets_dir / "input" / "small.png", (7, 5))
        result = support.resolve_image(path, config, scale="4")
        self.assertEqual(support.ResolvedImage(path, 7, 5, path.stat().st_size), result)
        with self.assertRaises((AttributeError, TypeError)):
            result.width = 10

    def test_resolve_image_classifies_stat_errors(self):
        config = self.build_config()
        image = self.assets_dir / "input" / "access.png"
        cases = (
            (FileNotFoundError("missing"), 404, "INPUT_NOT_FOUND", "输入图片不存在"),
            (NotADirectoryError("not a directory"), 404, "INPUT_NOT_FOUND", "输入图片不存在"),
            (PermissionError("denied"), 403, "INPUT_FORBIDDEN", "无权读取输入图片"),
            (OSError("io failure"), 500, "INPUT_ACCESS_FAILED", "读取输入图片失败"),
        )
        for source_error, status, code, detail in cases:
            with self.subTest(error=type(source_error).__name__):
                with mock.patch.object(Path, "stat", autospec=True, side_effect=source_error):
                    error = self.assert_support_error(
                        status,
                        code,
                        lambda: support.resolve_image(image, config, 2),
                    )
                self.assertEqual(detail, error.detail)
                self.assertIs(source_error, error.__cause__)

    def test_resolve_image_rejects_bad_media_and_limits(self):
        corrupt = self.assets_dir / "input" / "broken.png"
        corrupt.write_bytes(b"not an image")
        config = self.build_config()
        self.assert_support_error(
            415, "INPUT_DECODE_FAILED", lambda: support.resolve_image(corrupt, config, 2)
        )

        image = self.create_png(self.assets_dir / "input" / "large.png", (10, 10))
        byte_limited = self.build_config(REALESRGAN_MAX_INPUT_BYTES="1")
        self.assert_support_error(
            413, "INPUT_TOO_LARGE", lambda: support.resolve_image(image, byte_limited, 2)
        )
        pixel_limited = self.build_config(REALESRGAN_MAX_INPUT_PIXELS="99")
        self.assert_support_error(
            413, "INPUT_TOO_LARGE", lambda: support.resolve_image(image, pixel_limited, 2)
        )
        output_limited = self.build_config(REALESRGAN_MAX_OUTPUT_PIXELS="399")
        self.assert_support_error(
            413, "OUTPUT_TOO_LARGE", lambda: support.resolve_image(image, output_limited, 2)
        )

    def test_resolve_image_pixel_limits_take_priority_over_pillow_warning(self):
        image = self.create_png(
            self.assets_dir / "input" / "warning-sized.png", (10, 10)
        )
        cases = (
            (
                self.build_config(REALESRGAN_MAX_INPUT_PIXELS="99"),
                2,
                "INPUT_TOO_LARGE",
            ),
            (
                self.build_config(
                    REALESRGAN_MAX_INPUT_PIXELS="100",
                    REALESRGAN_MAX_OUTPUT_PIXELS="399",
                ),
                2,
                "INPUT_TOO_LARGE",
            ),
        )
        with mock.patch.object(Image, "MAX_IMAGE_PIXELS", 50):
            with warnings.catch_warnings(record=True) as emitted:
                warnings.simplefilter("default", Image.DecompressionBombWarning)
                for config, scale, code in cases:
                    with self.subTest(code=code):
                        self.assert_support_error(
                            413,
                            code,
                            lambda config=config, scale=scale: support.resolve_image(
                                image, config, scale
                            ),
                        )
        self.assertTrue(
            any(item.category is Image.DecompressionBombWarning for item in emitted)
        )

    def test_resolve_image_does_not_change_process_warning_filters(self):
        image = self.create_png(
            self.assets_dir / "input" / "warning-filter.png", (10, 10)
        )
        config = self.build_config(REALESRGAN_MAX_INPUT_PIXELS="99")
        with mock.patch.object(
            warnings, "simplefilter", wraps=warnings.simplefilter
        ) as simplefilter:
            self.assert_support_error(
                413,
                "INPUT_TOO_LARGE",
                lambda: support.resolve_image(image, config, 2),
            )
        simplefilter.assert_not_called()

    def test_resolve_image_is_stable_when_pillow_warning_is_promoted_to_error(self):
        image = self.create_png(
            self.assets_dir / "input" / "warning-policy.png", (10, 10)
        )
        config = self.build_config(
            REALESRGAN_MAX_INPUT_PIXELS="100",
            REALESRGAN_MAX_OUTPUT_PIXELS="399",
        )
        with mock.patch.object(Image, "MAX_IMAGE_PIXELS", 50):
            with warnings.catch_warnings(record=True) as emitted:
                warnings.simplefilter("default", Image.DecompressionBombWarning)
                default_error = self.assert_support_error(
                    413,
                    "INPUT_TOO_LARGE",
                    lambda: support.resolve_image(image, config, 2),
                )
            with warnings.catch_warnings(record=True) as promoted:
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                promoted_error = self.assert_support_error(
                    413,
                    "INPUT_TOO_LARGE",
                    lambda: support.resolve_image(image, config, 2),
                )

        self.assertEqual(
            (default_error.status_code, default_error.code),
            (promoted_error.status_code, promoted_error.code),
        )
        self.assertTrue(
            any(
                item.category is Image.DecompressionBombWarning for item in emitted
            )
        )
        self.assertEqual([], promoted)

    def test_resolve_image_pixel_limits_take_priority_over_pillow_error(self):
        image = self.create_png(
            self.assets_dir / "input" / "error-sized.png", (10, 10)
        )
        config = self.build_config(REALESRGAN_MAX_INPUT_PIXELS="99")
        original_open = Image.open
        observed_limits = []

        def observing_open(*args, **kwargs):
            observed_limits.append(Image.MAX_IMAGE_PIXELS)
            return original_open(*args, **kwargs)

        with mock.patch.object(Image, "MAX_IMAGE_PIXELS", 40):
            with self.assertRaises(Image.DecompressionBombError):
                Image.open(image)
            with mock.patch.object(support.Image, "open", side_effect=observing_open):
                self.assert_support_error(
                    413,
                    "INPUT_TOO_LARGE",
                    lambda: support.resolve_image(image, config, 2),
                )
            self.assertEqual([40], observed_limits)
            self.assertEqual(40, Image.MAX_IMAGE_PIXELS)

    def test_build_worker_args_is_a_non_shell_argument_array(self):
        config = self.build_config()
        config.model_dir.mkdir(parents=True)
        model_path = config.model_dir / "RealESRGAN_x4plus_anime_6B.pth"
        model_path.write_bytes(b"model")
        input_path = self.assets_dir / "input" / "in file.png"
        output_path = self.assets_dir / "output" / "out file.png"
        self.assertEqual(
            [
                str(config.python_executable),
                "-B",
                str(config.worker_path),
                "upscale",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model-id",
                support.DEFAULT_MODEL_ID,
                "--model-path",
                str(model_path),
                "--scale",
                "2",
                "--device",
                "auto",
            ],
            support.build_worker_args(
                config,
                input_path,
                output_path,
                model_id=support.DEFAULT_MODEL_ID,
                scale="2",
            ),
        )

    def test_build_probe_args_is_a_non_shell_argument_array(self):
        config = self.build_config()
        self.assertEqual(
            [
                str(config.python_executable),
                "-B",
                str(config.worker_path),
                "status",
            ],
            support.build_probe_args(config),
        )

    def test_parse_worker_json_requires_exactly_one_json_object(self):
        self.assertEqual({"ok": True}, support.parse_worker_json('{"ok": true}\n'))
        self.assertEqual(
            {"ok": True, "value": 2},
            support.parse_worker_json('{\n  "ok": true,\n  "value": 2\n}\n'),
        )
        for stdout in (
            "",
            " \r\n ",
            "not-json",
            "[]",
            '"value"',
            '{"value": NaN}',
            '{"value": Infinity}',
            '{"value": -Infinity}',
            '{"nested": [{"value": NaN}]}',
            "{\"ok\": true}\n{\"extra\": true}",
            "log line\n{\"ok\": true}",
        ):
            with self.subTest(stdout=stdout):
                self.assert_support_error(
                    502,
                    "WORKER_INVALID_RESPONSE",
                    lambda stdout=stdout: support.parse_worker_json(stdout),
                )

    def test_minimal_worker_env_keeps_only_required_non_secret_values(self):
        environment = {
            "SystemRoot": r"C:\\Windows",
            "WINDIR": r"C:\\Windows",
            "PATH": r"C:\\bin",
            "PATHEXT": ".EXE",
            "ComSpec": r"C:\\Windows\\System32\\cmd.exe",
            "TEMP": r"C:\\Temp",
            "TMP": r"C:\\Temp",
            "USERPROFILE": r"C:\\Users\\me",
            "USERNAME": "me",
            "LOCALAPPDATA": r"C:\\Users\\me\\AppData\\Local",
            "APPDATA": r"C:\\Users\\me\\AppData\\Roaming",
            "CUDA_PATH": r"C:\\CUDA",
            "CUDA_HOME": r"C:\\CUDA",
            "CUDA_VISIBLE_DEVICES": "0",
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
            "CUDA_MODULE_LOADING": "LAZY",
            "cUdA_pAtH_v12_6": r"C:\\CUDA\\v12.6",
            "API_KEY": "secret",
            "ACCESS_TOKEN": "secret",
            "SESSION_COOKIE": "secret",
            "CLIENT_SECRET": "secret",
            "DB_PASSWORD": "secret",
            "Cuda_Auth": "secret",
            "CUDA_CREDENTIAL": "secret",
            "cuda_license": "secret",
            "CUDA_RANDOM": "drop",
            "UNRELATED": "drop",
        }
        result = support.minimal_worker_env(environment)
        self.assertEqual(
            {
                key: value
                for key, value in environment.items()
                if key not in {
                    "API_KEY",
                    "ACCESS_TOKEN",
                    "SESSION_COOKIE",
                    "CLIENT_SECRET",
                    "DB_PASSWORD",
                    "Cuda_Auth",
                    "CUDA_CREDENTIAL",
                    "cuda_license",
                    "CUDA_RANDOM",
                    "ComSpec",
                    "UNRELATED",
                }
            },
            result,
        )

    def test_mapped_worker_error_has_stable_http_mapping(self):
        expected = {
            "CUDA_OOM": (503, "显存不足，请使用更小的原图"),
            "MODEL_NOT_FOUND": (404, None),
            "INPUT_DECODE_FAILED": (415, None),
            "TIMEOUT": (504, None),
            "PYTHON_ENV_UNAVAILABLE": (503, None),
            "OUTPUT_WRITE_FAILED": (502, None),
            "INFERENCE_FAILED": (502, None),
            "SOMETHING_NEW": (502, None),
        }
        for code, (status, required_detail) in expected.items():
            with self.subTest(code=code):
                error = support.mapped_worker_error(code, "worker detail")
                self.assertIsInstance(error, support.RealESRGANSupportError)
                self.assertEqual(status, error.status_code)
                self.assertEqual(code, error.code)
                if required_detail:
                    self.assertEqual(required_detail, error.detail)


class FakeProcess:
    def __init__(self, stdout=b'{"ok":true}', stderr=b"", returncode=0):
        self.stdout_data = stdout
        self.stderr_data = stderr
        self.returncode = returncode
        self.killed = False
        self.waited = False
        self.block = False

    async def communicate(self):
        if self.block:
            await asyncio.Event().wait()
        return self.stdout_data, self.stderr_data

    def kill(self):
        self.killed = True

    async def wait(self):
        self.waited = True
        return self.returncode


class FakeProcessFactory:
    def __init__(self, process):
        self.process = process
        self.calls = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.process


class RealESRGANProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.base_dir = self.root / "app"
        self.assets_dir = self.base_dir / "assets"
        self.legacy_output_dir = self.base_dir / "output"
        self.assets_dir.mkdir(parents=True)
        self.legacy_output_dir.mkdir(parents=True)
        self.config = support.build_config(
            self.base_dir,
            self.assets_dir,
            self.legacy_output_dir,
            environ={
                "REALESRGAN_PYTHON": str(self.root / "python.exe"),
                "REALESRGAN_MODEL_DIR": str(self.root / "models"),
                "REALESRGAN_TIMEOUT_SECONDS": "2",
            },
        )
        self.config.model_dir.mkdir(parents=True)
        (self.config.model_dir / "RealESRGAN_x4plus_anime_6B.pth").write_bytes(
            b"model"
        )

    def test_run_process_uses_argument_array_pipes_and_minimal_environment(self):
        process = FakeProcess(stdout=b'{"ok":true,"kind":"status"}')
        factory = FakeProcessFactory(process)
        environment = {
            "PATH": r"C:\\bin",
            "TEMP": r"C:\\temp",
            "API_KEY": "must-not-leak",
            "UNRELATED": "drop",
        }
        payload = asyncio.run(
            support.run_process(
                ["python", "-B", "worker.py", "status"],
                3,
                environ=environment,
                process_factory=factory,
            )
        )
        self.assertEqual({"ok": True, "kind": "status"}, payload)
        args, kwargs = factory.calls[0]
        self.assertEqual(("python", "-B", "worker.py", "status"), args)
        self.assertIs(asyncio.subprocess.PIPE, kwargs["stdout"])
        self.assertIs(asyncio.subprocess.PIPE, kwargs["stderr"])
        self.assertEqual({"PATH": r"C:\\bin", "TEMP": r"C:\\temp"}, kwargs["env"])

    def test_run_process_accepts_verified_waifu_payload_after_native_cleanup_crash(self):
        payload = {
            "ok": True,
            "kind": "upscale",
            "model": support.WAIFU2X_MODEL_ID,
            "output_path": "stage.png",
        }
        process = FakeProcess(
            stdout=json.dumps(payload).encode("utf-8"),
            returncode=-1073741819,
        )
        result = asyncio.run(
            support.run_process(
                ["python", "worker.py", "upscale"],
                3,
                process_factory=FakeProcessFactory(process),
            )
        )
        self.assertEqual(payload, result)

        non_waifu = FakeProcess(
            stdout=b'{"ok":true,"kind":"upscale","model":"other"}',
            returncode=-1073741819,
        )
        with self.assertRaises(support.RealESRGANSupportError):
            asyncio.run(
                support.run_process(
                    ["python", "worker.py", "upscale"],
                    3,
                    process_factory=FakeProcessFactory(non_waifu),
                )
            )

    def test_run_process_maps_creation_os_errors_without_leaking_paths(self):
        source_errors = (
            FileNotFoundError(r"C:\secret\missing-python.exe"),
            PermissionError(r"C:\secret\denied-python.exe"),
            OSError(r"C:\secret\broken-python.exe"),
        )
        for source_error in source_errors:
            with self.subTest(error=type(source_error).__name__):
                async def failing_factory(*args, **kwargs):
                    raise source_error

                with self.assertRaises(support.RealESRGANSupportError) as raised:
                    asyncio.run(
                        support.run_process(
                            [r"C:\secret\missing-python.exe", "worker.py"],
                            3,
                            process_factory=failing_factory,
                        )
                    )
                error = raised.exception
                self.assertEqual(
                    (503, "PYTHON_ENV_UNAVAILABLE"),
                    (error.status_code, error.code),
                )
                self.assertEqual(
                    "Real-ESRGAN Python 环境不可用", error.detail
                )
                self.assertIs(source_error, error.__cause__)
                self.assertNotIn("secret", str(error).lower())

    def test_run_process_timeout_kills_and_waits(self):
        process = FakeProcess()
        process.block = True
        factory = FakeProcessFactory(process)
        with self.assertRaises(support.RealESRGANSupportError) as raised:
            asyncio.run(
                support.run_process(
                    ["python", "worker.py"],
                    0.01,
                    process_factory=factory,
                )
            )
        self.assertEqual((504, "TIMEOUT"), (raised.exception.status_code, raised.exception.code))
        self.assertTrue(process.killed)
        self.assertTrue(process.waited)

    def test_run_process_cancellation_kills_waits_and_reraises(self):
        process = FakeProcess()
        process.block = True
        factory = FakeProcessFactory(process)

        async def scenario():
            task = asyncio.create_task(
                support.run_process(
                    ["python", "worker.py"], 30, process_factory=factory
                )
            )
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(scenario())
        self.assertTrue(process.killed)
        self.assertTrue(process.waited)

    def test_run_process_maps_worker_failure_without_leaking_stderr_or_paths(self):
        process = FakeProcess(
            stdout=(
                b'{"ok":false,"error_code":"INFERENCE_FAILED",'
                b'"message":"C:\\\\secret\\\\model.pth failed"}'
            ),
            stderr=b"Traceback: C:\\secret\\worker.py",
            returncode=6,
        )
        factory = FakeProcessFactory(process)
        with self.assertRaises(support.RealESRGANSupportError) as raised:
            asyncio.run(
                support.run_process(
                    ["python", "worker.py"], 3, process_factory=factory
                )
            )
        error = raised.exception
        self.assertEqual((502, "INFERENCE_FAILED"), (error.status_code, error.code))
        self.assertNotIn("secret", error.detail.lower())
        self.assertNotIn("traceback", error.detail.lower())

    def test_probe_worker_runs_status_command(self):
        process = FakeProcess(stdout=b'{"ok":true,"kind":"status","cuda":false}')
        factory = FakeProcessFactory(process)
        with mock.patch.object(
            support.asyncio, "create_subprocess_exec", new=factory
        ):
            payload = asyncio.run(support.probe_worker(self.config))
        self.assertEqual("status", payload["kind"])
        self.assertEqual(
            tuple(support.build_probe_args(self.config)), factory.calls[0][0]
        )

    def test_run_upscale_worker_validates_stage_and_publishes_without_overwrite(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        output = self.root / "result.png"
        observed_stages = []
        validated = []

        async def successful_runner(args, timeout_seconds, **kwargs):
            stage = Path(args[args.index("--output") + 1])
            observed_stages.append(stage)
            stage.write_bytes(b"new")
            return {"ok": True, "kind": "upscale", "output_path": str(stage)}

        def validate(stage, payload):
            self.assertFalse(output.exists())
            self.assertEqual(b"new", stage.read_bytes())
            validated.append((stage, payload["kind"]))
            return {"width": 4, "height": 6}

        with mock.patch.object(support, "run_process", side_effect=successful_runner):
            payload = asyncio.run(
                support.run_upscale_worker(
                    self.config,
                    source,
                    output,
                    support.DEFAULT_MODEL_ID,
                    2,
                    validate_output=validate,
                )
            )
        stage = observed_stages[0]
        self.assertNotEqual(output, stage)
        self.assertEqual(output.parent, stage.parent)
        self.assertTrue(stage.name.startswith(".realesrgan-stage-"))
        self.assertTrue(stage.name.endswith(".png"))
        self.assertFalse(stage.exists())
        self.assertEqual(b"new", output.read_bytes())
        self.assertEqual(str(output.resolve()), payload["output_path"])
        self.assertEqual([(stage, "upscale")], validated)
        self.assertEqual({"width": 4, "height": 6}, payload["_validation"])
        self.assertEqual(4, len(payload["_output_identity"]))

    def test_run_upscale_worker_does_not_overwrite_or_delete_foreign_final(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        output = self.root / "result.png"
        observed_stages = []

        async def successful_runner(args, timeout_seconds, **kwargs):
            stage = Path(args[args.index("--output") + 1])
            observed_stages.append(stage)
            stage.write_bytes(b"new")
            output.write_bytes(b"foreign")
            return {"ok": True, "kind": "upscale", "output_path": str(stage)}

        with mock.patch.object(support, "run_process", side_effect=successful_runner):
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                asyncio.run(
                    support.run_upscale_worker(
                        self.config, source, output, support.DEFAULT_MODEL_ID, 2
                    )
                )
        self.assertEqual((409, "OUTPUT_CONFLICT"), (raised.exception.status_code, raised.exception.code))
        self.assertEqual(b"foreign", output.read_bytes())
        self.assertFalse(observed_stages[0].exists())

    def test_run_upscale_worker_validation_failure_never_publishes(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        output = self.root / "result.png"
        observed_stages = []

        async def successful_runner(args, timeout_seconds, **kwargs):
            stage = Path(args[args.index("--output") + 1])
            observed_stages.append(stage)
            stage.write_bytes(b"bad")
            return {"ok": True, "kind": "upscale", "output_path": str(stage)}

        def reject(stage, payload):
            raise support.RealESRGANSupportError(
                "RealESRGAN 未生成输出图片", 502, "WORKER_OUTPUT_INVALID"
            )

        with mock.patch.object(support, "run_process", side_effect=successful_runner):
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                asyncio.run(
                    support.run_upscale_worker(
                        self.config,
                        source,
                        output,
                        support.DEFAULT_MODEL_ID,
                        2,
                        validate_output=reject,
                    )
                )
        self.assertEqual("WORKER_OUTPUT_INVALID", raised.exception.code)
        self.assertFalse(output.exists())
        self.assertFalse(observed_stages[0].exists())

    def test_run_upscale_worker_rejects_output_equal_to_source_before_runner(self):
        source = self.root / "source.png"
        source.write_bytes(b"original")
        with mock.patch.object(support, "run_process") as runner:
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                asyncio.run(
                    support.run_upscale_worker(
                        self.config,
                        source,
                        source,
                        support.DEFAULT_MODEL_ID,
                        2,
                    )
                )
        self.assertEqual(
            (400, "INVALID_ARGUMENT", "输出路径不能覆盖输入图片"),
            (
                raised.exception.status_code,
                raised.exception.code,
                raised.exception.detail,
            ),
        )
        runner.assert_not_called()
        self.assertEqual(b"original", source.read_bytes())

    def test_run_upscale_worker_rejects_output_symlink_to_source_before_runner(self):
        source = self.root / "source.png"
        source.write_bytes(b"original")
        output = self.root / "alias.png"
        try:
            output.symlink_to(source)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")

        with mock.patch.object(support, "run_process") as runner:
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                asyncio.run(
                    support.run_upscale_worker(
                        self.config,
                        source,
                        output,
                        support.DEFAULT_MODEL_ID,
                        2,
                    )
                )
        self.assertEqual(
            (400, "INVALID_ARGUMENT", "输出路径不能覆盖输入图片"),
            (
                raised.exception.status_code,
                raised.exception.code,
                raised.exception.detail,
            ),
        )
        runner.assert_not_called()
        self.assertTrue(output.is_symlink())
        self.assertEqual(source.resolve(), output.resolve())
        self.assertEqual(b"original", source.read_bytes())

    def test_run_upscale_worker_does_not_accept_preexisting_final_or_missing_stage(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        output = self.root / "result.png"
        output.write_bytes(b"old")
        observed_stages = []

        async def no_output_runner(args, timeout_seconds, **kwargs):
            stage = Path(args[args.index("--output") + 1])
            observed_stages.append(stage)
            return {"ok": True, "output_path": str(stage)}

        with mock.patch.object(
            support, "run_process", side_effect=no_output_runner
        ):
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                asyncio.run(
                    support.run_upscale_worker(
                        self.config, source, output, support.DEFAULT_MODEL_ID, 2
                    )
                )
        self.assertEqual((502, "WORKER_OUTPUT_MISSING"), (raised.exception.status_code, raised.exception.code))
        self.assertEqual("RealESRGAN 未生成输出图片", raised.exception.detail)
        self.assertEqual(b"old", output.read_bytes())
        self.assertFalse(observed_stages[0].exists())

    def test_run_upscale_worker_rejects_reported_path_mismatch_and_symlink_stage(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        output = self.root / "result.png"
        output.write_bytes(b"old")
        created_stages = []

        other = self.root / "other.png"
        other.write_bytes(b"png")

        async def mismatched_runner(args, timeout_seconds, **kwargs):
            stage = Path(args[args.index("--output") + 1])
            created_stages.append(stage)
            stage.write_bytes(b"new")
            return {"ok": True, "output_path": str(other)}

        with mock.patch.object(support, "run_process", side_effect=mismatched_runner):
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                asyncio.run(
                    support.run_upscale_worker(
                        self.config, source, output, support.DEFAULT_MODEL_ID, 2
                    )
                )
        self.assertEqual("WORKER_OUTPUT_MISSING", raised.exception.code)
        self.assertEqual(b"old", output.read_bytes())
        self.assertFalse(created_stages.pop().exists())

        probe = self.root / "symlink-probe.png"
        try:
            probe.symlink_to(other)
            probe.unlink()
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")

        async def symlink_runner(args, timeout_seconds, **kwargs):
            stage = Path(args[args.index("--output") + 1])
            created_stages.append(stage)
            stage.symlink_to(other)
            return {"ok": True, "output_path": str(stage)}

        with mock.patch.object(support, "run_process", side_effect=symlink_runner):
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                asyncio.run(
                    support.run_upscale_worker(
                        self.config, source, output, support.DEFAULT_MODEL_ID, 2
                    )
                )
        self.assertEqual("WORKER_OUTPUT_MISSING", raised.exception.code)
        self.assertEqual(b"old", output.read_bytes())
        self.assertFalse(created_stages.pop().exists())
        self.assertEqual(b"png", other.read_bytes())

    def test_run_upscale_worker_cleans_stage_on_error_timeout_and_cancel(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        output = self.root / "result.png"
        output.write_bytes(b"old")
        observed_stages = []

        for source_error in (
            RuntimeError("worker crashed"),
            support.mapped_worker_error("TIMEOUT"),
        ):
            with self.subTest(error=type(source_error).__name__):
                async def failing_runner(args, timeout_seconds, **kwargs):
                    stage = Path(args[args.index("--output") + 1])
                    observed_stages.append(stage)
                    stage.write_bytes(b"partial")
                    raise source_error

                with mock.patch.object(
                    support, "run_process", side_effect=failing_runner
                ):
                    with self.assertRaises(type(source_error)):
                        asyncio.run(
                            support.run_upscale_worker(
                                self.config,
                                source,
                                output,
                                support.DEFAULT_MODEL_ID,
                                2,
                            )
                        )
                self.assertFalse(observed_stages.pop().exists())
                self.assertEqual(b"old", output.read_bytes())

        started = asyncio.Event()

        async def cancelling_runner(args, timeout_seconds, **kwargs):
            stage = Path(args[args.index("--output") + 1])
            observed_stages.append(stage)
            stage.write_bytes(b"partial")
            started.set()
            await asyncio.Event().wait()

        async def cancel_scenario():
            with mock.patch.object(
                support, "run_process", side_effect=cancelling_runner
            ):
                task = asyncio.create_task(
                    support.run_upscale_worker(
                        self.config, source, output, support.DEFAULT_MODEL_ID, 2
                    )
                )
                await started.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

        asyncio.run(cancel_scenario())
        self.assertFalse(observed_stages.pop().exists())
        self.assertEqual(b"old", output.read_bytes())

    def test_run_upscale_worker_semaphore_serializes_two_processes(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        first = self.root / "first.png"
        second = self.root / "second.png"
        active = 0
        maximum = 0

        async def controlled_runner(args, timeout_seconds, **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            output = Path(args[args.index("--output") + 1])
            output.write_bytes(b"png")
            active -= 1
            return {"ok": True, "output_path": str(output)}

        async def scenario():
            semaphore = asyncio.Semaphore(1)
            with mock.patch.object(
                support, "run_process", side_effect=controlled_runner
            ):
                return await asyncio.gather(
                    support.run_upscale_worker(
                        self.config,
                        source,
                        first,
                        support.DEFAULT_MODEL_ID,
                        4,
                        semaphore=semaphore,
                    ),
                    support.run_upscale_worker(
                        self.config,
                        source,
                        second,
                        support.DEFAULT_MODEL_ID,
                        4,
                        semaphore=semaphore,
                    ),
                )

        results = asyncio.run(scenario())
        self.assertEqual(1, maximum)
        self.assertEqual({str(first), str(second)}, {item["output_path"] for item in results})


if __name__ == "__main__":
    unittest.main()
