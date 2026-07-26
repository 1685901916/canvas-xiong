import asyncio
import hashlib
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

import main
import realesrgan_support as support


class RealESRGANAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.base_dir = self.root / "app"
        self.assets_dir = self.base_dir / "assets"
        self.legacy_output_dir = self.base_dir / "output"
        self.python_path = self.root / "python.exe"
        self.model_dir = self.root / "models"
        self.base_dir.mkdir(parents=True)
        self.python_path.write_bytes(b"python")
        (self.base_dir / "tools").mkdir()
        (self.base_dir / "tools" / "realesrgan_worker.py").write_text(
            "# worker\n", encoding="utf-8"
        )
        self.model_dir.mkdir()
        (self.model_dir / "RealESRGAN_x4plus_anime_6B.pth").write_bytes(b"model")
        for name in ("input", "output", "uploads", "library"):
            (self.assets_dir / name).mkdir(parents=True)
        self.legacy_output_dir.mkdir()
        self.source_path = self.assets_dir / "uploads" / "source.png"
        Image.new("RGB", (7, 5), (40, 80, 120)).save(self.source_path, "PNG")
        self.config = support.build_config(
            self.base_dir,
            self.assets_dir,
            self.legacy_output_dir,
            environ={
                "REALESRGAN_PYTHON": str(self.python_path),
                "REALESRGAN_MODEL_DIR": str(self.model_dir),
            },
        )

    @contextmanager
    def api_environment(self):
        with mock.patch.multiple(
            main,
            BASE_DIR=str(self.base_dir),
            ASSETS_DIR=str(self.assets_dir),
            OUTPUT_DIR=str(self.legacy_output_dir),
        ), mock.patch.object(main, "build_config", return_value=self.config) as builder:
            yield builder

    @staticmethod
    def request(**changes):
        values = {"source_url": "/assets/uploads/source.png"}
        values.update(changes)
        return main.RealESRGANUpscaleRequest(**values)

    def run_upscale(self, worker, **request_changes):
        with self.api_environment(), mock.patch.object(
            main, "run_upscale_worker", side_effect=worker
        ):
            return asyncio.run(main.realesrgan_upscale(self.request(**request_changes)))

    @staticmethod
    def successful_worker(records, *, size=(28, 20), report=None):
        async def worker(config, **kwargs):
            records.append(kwargs)
            output_path = Path(kwargs["output_path"])
            stage_path = output_path.with_name(f".fake-stage-{output_path.name}")
            Image.new("RGB", size, (1, 2, 3)).save(stage_path, "PNG")
            payload = {
                "ok": True,
                "source_width": 7,
                "source_height": 5,
                "width": size[0],
                "height": size[1],
                "device": "cuda:0",
                "run_ms": 12.9,
            }
            if report:
                payload.update(report)
            try:
                validation = kwargs["validate_output"](stage_path, payload)
                os.link(stage_path, output_path)
                payload["_validation"] = validation
                payload["_output_identity"] = main._realesrgan_file_identity(
                    output_path.lstat()
                )
            finally:
                stage_path.unlink(missing_ok=True)
            return payload

        return worker

    @staticmethod
    def staged_worker(writer=None, report=None):
        async def worker(config, **kwargs):
            output_path = Path(kwargs["output_path"])
            stage_path = output_path.with_name(f".fake-stage-{output_path.name}")
            payload = {
                "ok": True,
                "source_width": 7,
                "source_height": 5,
                "width": 28,
                "height": 20,
                "device": "cuda:0",
                "run_ms": 10,
            }
            if report:
                payload.update(report)
            try:
                if writer is not None:
                    writer(stage_path)
                validation = kwargs["validate_output"](stage_path, payload)
                os.link(stage_path, output_path)
                payload["_validation"] = validation
                payload["_output_identity"] = main._realesrgan_file_identity(
                    output_path.lstat()
                )
                return payload
            finally:
                stage_path.unlink(missing_ok=True)

        return worker

    def test_request_model_defaults_to_four_accepts_two_and_rejects_three(self):
        default = self.request()
        self.assertEqual(support.DEFAULT_MODEL_ID, default.model)
        self.assertEqual(4, default.scale)
        self.assertEqual(2, self.request(scale=2).scale)
        with self.assertRaises(ValidationError):
            self.request(scale=3)

    def test_routes_are_registered_with_expected_methods(self):
        routes = {
            route.path: set(route.methods or ())
            for route in main.app.routes
            if hasattr(route, "methods")
        }
        self.assertIn("GET", routes["/api/realesrgan/status"])
        self.assertIn("POST", routes["/api/realesrgan/upscale"])

    def test_status_success_exposes_only_safe_fields(self):
        runtime = {
            "ok": True,
            "cuda": True,
            "device": "cuda:0",
            "stderr": r"C:\\secret\\trace.txt",
            "env": {"API_TOKEN": "secret"},
        }
        with self.api_environment() as builder, mock.patch.object(
            main, "probe_worker", new=mock.AsyncMock(return_value=runtime)
        ):
            result = asyncio.run(main.realesrgan_status())
        self.assertEqual(
            {"ok", "python", "cuda", "device", "models", "message"},
            set(result),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(str(self.python_path), result["python"])
        self.assertIs(True, result["cuda"])
        self.assertEqual("cuda:0", result["device"])
        self.assertEqual(
            [
                {
                    "id": support.DEFAULT_MODEL_ID,
                    "name": "RealESRGAN x4plus Anime 6B",
                    "native_scale": 4,
                }
            ],
            result["models"],
        )
        serialized = repr(result)
        for forbidden in ("filename", "model_path", "stderr", "API_TOKEN", "secret"):
            self.assertNotIn(forbidden, serialized)
        builder.assert_called_once_with(
            base_dir=str(self.base_dir),
            assets_dir=str(self.assets_dir),
            legacy_output_dir=str(self.legacy_output_dir),
        )

    def test_status_without_models_is_http_200_unavailable(self):
        (self.model_dir / "RealESRGAN_x4plus_anime_6B.pth").unlink()
        probe = mock.AsyncMock()
        with self.api_environment(), mock.patch.object(main, "probe_worker", new=probe):
            result = asyncio.run(main.realesrgan_status())
        self.assertEqual(False, result["ok"])
        self.assertEqual([], result["models"])
        self.assertEqual("未找到 RealESRGAN 本地模型", result["message"])
        probe.assert_not_awaited()

    def test_status_without_python_is_http_200_unavailable(self):
        self.python_path.unlink()
        with self.api_environment():
            result = asyncio.run(main.realesrgan_status())
        self.assertEqual(False, result["ok"])
        self.assertEqual("RealESRGAN 运行环境不可用", result["message"])
        self.assertNotIn(str(self.python_path), result["message"])

    def test_status_without_worker_is_http_200_unavailable(self):
        worker_path = self.base_dir / "tools" / "realesrgan_worker.py"
        worker_path.unlink()
        with self.api_environment():
            result = asyncio.run(main.realesrgan_status())
        self.assertEqual(False, result["ok"])
        self.assertEqual("RealESRGAN 运行环境不可用", result["message"])
        self.assertNotIn(str(worker_path), result["message"])

    def test_status_probe_failure_is_sanitized_http_200(self):
        leaked = str(self.root / "private" / "traceback.log")
        with self.api_environment(), mock.patch.object(
            main,
            "probe_worker",
            new=mock.AsyncMock(side_effect=OSError(leaked)),
        ):
            result = asyncio.run(main.realesrgan_status())
        self.assertEqual(False, result["ok"])
        self.assertEqual("RealESRGAN 运行环境不可用", result["message"])
        self.assertNotIn(leaked, repr(result))

    def test_upscale_success_has_exact_fields_and_preserves_input(self):
        records = []
        source_hash = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        result = self.run_upscale(self.successful_worker(records))
        self.assertEqual(
            {
                "ok",
                "url",
                "model",
                "scale",
                "source_width",
                "source_height",
                "width",
                "height",
                "device",
                "run_ms",
            },
            set(result),
        )
        self.assertEqual(True, result["ok"])
        self.assertRegex(
            result["url"], r"^/assets/output/realesrgan_[0-9a-f]{32}\.png$"
        )
        self.assertEqual(support.DEFAULT_MODEL_ID, result["model"])
        self.assertEqual((4, 7, 5, 28, 20), (
            result["scale"],
            result["source_width"],
            result["source_height"],
            result["width"],
            result["height"],
        ))
        self.assertEqual("cuda:0", result["device"])
        self.assertEqual(12, result["run_ms"])
        self.assertEqual(source_hash, hashlib.sha256(self.source_path.read_bytes()).hexdigest())
        call = records[0]
        self.assertEqual(self.source_path, Path(call["source_path"]))
        self.assertEqual(self.assets_dir / "output", Path(call["output_path"]).parent)
        self.assertRegex(Path(call["output_path"]).name, r"^realesrgan_[0-9a-f]{32}\.png$")
        self.assertEqual("auto", call["device"])
        self.assertIsInstance(call["semaphore"], main._AsyncThreadSemaphoreLease)
        self.assertTrue(callable(call["validate_output"]))

    def test_output_name_is_server_generated_and_unique(self):
        records = []
        first = self.run_upscale(self.successful_worker(records))
        second = self.run_upscale(self.successful_worker(records))
        self.assertNotEqual(first["url"], second["url"])
        for call in records:
            self.assertTrue(Path(call["output_path"]).name.startswith("realesrgan_"))

    def test_model_path_string_is_rejected_by_whitelist(self):
        with self.api_environment():
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    main.realesrgan_upscale(
                        self.request(model=r"C:\\models\\RealESRGAN.pth")
                    )
                )
        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual("不支持的 Real-ESRGAN 模型", raised.exception.detail)

    def test_support_worker_error_preserves_stable_status_and_detail(self):
        async def failing(config, **kwargs):
            raise support.RealESRGANSupportError(
                "显存不足，请使用更小的原图", 503, "CUDA_OOM"
            )

        with self.assertRaises(HTTPException) as raised:
            self.run_upscale(failing)
        self.assertEqual(503, raised.exception.status_code)
        self.assertEqual("显存不足，请使用更小的原图", raised.exception.detail)
        self.assertEqual([], list((self.assets_dir / "output").glob("realesrgan_*.png")))

    def test_unknown_worker_error_is_sanitized_and_cleans_partial_output(self):
        leaked = str(self.root / "secret" / "traceback.txt")

        async def failing(config, **kwargs):
            raise OSError(leaked)

        with self.assertRaises(HTTPException) as raised:
            self.run_upscale(failing)
        self.assertEqual(502, raised.exception.status_code)
        self.assertEqual("RealESRGAN 未生成输出图片", raised.exception.detail)
        self.assertNotIn(leaked, str(raised.exception.detail))
        self.assertEqual([], list((self.assets_dir / "output").glob("realesrgan_*.png")))

    def test_missing_corrupt_wrong_size_and_bad_report_are_502_and_cleaned(self):
        async def missing(config, **kwargs):
            return {"width": 28, "height": 20, "source_width": 7, "source_height": 5}

        workers = (
            missing,
            self.staged_worker(lambda path: path.write_bytes(b"not png")),
            self.successful_worker([], size=(27, 20)),
            self.successful_worker([], report={"width": 27}),
            self.successful_worker([], report={"source_width": 6}),
        )
        for worker in workers:
            with self.subTest(worker=getattr(worker, "__name__", "fake")):
                with self.assertRaises(HTTPException) as raised:
                    self.run_upscale(worker)
                self.assertEqual(502, raised.exception.status_code)
                self.assertEqual("RealESRGAN 未生成输出图片", raised.exception.detail)
                self.assertEqual(
                    [], list((self.assets_dir / "output").glob("realesrgan_*.png"))
                )

    def test_valid_jpeg_content_with_png_name_is_rejected_and_cleaned(self):
        mislabeled = self.staged_worker(
            lambda path: Image.new("RGB", (28, 20)).save(path, "JPEG")
        )

        with self.assertRaises(HTTPException) as raised:
            self.run_upscale(mislabeled)
        self.assertEqual(502, raised.exception.status_code)
        self.assertEqual("RealESRGAN 未生成输出图片", raised.exception.detail)
        self.assertEqual([], list((self.assets_dir / "output").glob("realesrgan_*.png")))

    def test_symlink_output_is_rejected_and_link_is_cleaned(self):
        target = self.root / "outside.png"
        Image.new("RGB", (28, 20)).save(target, "PNG")
        probe = self.root / "probe-link"
        try:
            probe.symlink_to(target)
            probe.unlink()
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink unavailable: {exc}")

        symlink_worker = self.staged_worker(lambda path: path.symlink_to(target))

        with self.assertRaises(HTTPException) as raised:
            self.run_upscale(symlink_worker)
        self.assertEqual(502, raised.exception.status_code)
        self.assertEqual([], list((self.assets_dir / "output").glob("realesrgan_*.png")))
        self.assertTrue(target.is_file())

    def test_cancelled_error_cleans_partial_output_and_is_reraised(self):
        async def cancelled(config, **kwargs):
            raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            self.run_upscale(cancelled)
        self.assertEqual([], list((self.assets_dir / "output").glob("realesrgan_*.png")))

    def test_process_semaphore_serializes_different_thread_event_loops(self):
        barrier = threading.Barrier(2)
        state_lock = threading.Lock()
        active = 0
        maximum = 0
        errors = []

        async def scenario():
            nonlocal active, maximum
            barrier.wait(timeout=2)
            async with main._realesrgan_semaphore_for_current_loop():
                with state_lock:
                    active += 1
                    maximum = max(maximum, active)
                await asyncio.sleep(0.05)
                with state_lock:
                    active -= 1

        def runner():
            try:
                asyncio.run(scenario())
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=runner) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
        self.assertFalse(errors)
        self.assertEqual(1, maximum)
        self.assertTrue(all(not thread.is_alive() for thread in threads))

    def test_http_exception_from_worker_is_preserved(self):
        async def conflict(config, **kwargs):
            raise HTTPException(status_code=409, detail="sentinel")

        with self.assertRaises(HTTPException) as raised:
            self.run_upscale(conflict)
        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual("sentinel", raised.exception.detail)

    def test_invalid_device_types_are_not_stringified(self):
        records = []
        result = self.run_upscale(
            self.successful_worker(records, report={"device": {"secret": True}})
        )
        self.assertEqual("", result["device"])

        with self.api_environment(), mock.patch.object(
            main,
            "probe_worker",
            new=mock.AsyncMock(return_value={"ok": True, "cuda": True, "device": True}),
        ):
            status = asyncio.run(main.realesrgan_status())
        self.assertEqual("", status["device"])

    def test_output_validation_detects_in_place_mutation(self):
        output = self.assets_dir / "output" / "mutation.png"
        Image.new("RGB", (28, 20), (1, 2, 3)).save(output, "PNG")
        real_fstat = main.os.fstat
        calls = 0

        def mutating_fstat(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                output.write_bytes(b"corrupt-after-verify")
            return real_fstat(fd)

        with mock.patch.object(main.os, "fstat", side_effect=mutating_fstat):
            with self.assertRaises(support.RealESRGANSupportError) as raised:
                main._verified_realesrgan_output(output, (28, 20))
        self.assertEqual("WORKER_OUTPUT_INVALID", raised.exception.code)

    def test_config_is_built_again_for_each_request(self):
        with self.api_environment() as builder, mock.patch.object(
            main,
            "probe_worker",
            new=mock.AsyncMock(return_value={"ok": True, "cuda": False, "device": "cpu"}),
        ):
            asyncio.run(main.realesrgan_status())
            asyncio.run(main.realesrgan_status())
        self.assertEqual(2, builder.call_count)


if __name__ == "__main__":
    unittest.main()
