import contextlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from tools import realesrgan_worker as worker


class RealESRGANWorkerImportTests(unittest.TestCase):
    def test_worker_module_imports_without_optional_inference_dependencies(self):
        from tools import realesrgan_worker

        self.assertEqual(
            "RealESRGAN_x4plus_anime_6B", realesrgan_worker.DEFAULT_MODEL_ID
        )

    def test_pure_worker_contract(self):
        self.assertEqual(
            {
                "num_in_ch": 3,
                "num_out_ch": 3,
                "num_feat": 64,
                "num_block": 6,
                "num_grow_ch": 32,
                "scale": 4,
            },
            worker.anime_6b_architecture(),
        )
        self.assertEqual((512, 256), worker.retry_tiles("cuda"))
        self.assertEqual((0,), worker.retry_tiles("cpu"))
        self.assertEqual((14, 10), worker.expected_dimensions(7, 5, 2))
        self.assertEqual((28, 20), worker.expected_dimensions(7, 5, 4))
        for scale in (1, 3, 8, True, "2"):
            with self.subTest(scale=scale):
                with self.assertRaises(worker.WorkerFailure) as raised:
                    worker.expected_dimensions(7, 5, scale)
                self.assertEqual("UNSUPPORTED_SCALE", raised.exception.error_code)
                self.assertEqual(2, raised.exception.exit_code)

    def test_cuda_oom_detection_uses_class_name_or_cuda_message(self):
        TorchOOM = type("OutOfMemoryError", (RuntimeError,), {})
        self.assertTrue(worker.is_cuda_oom(TorchOOM("allocation failed")))
        self.assertTrue(worker.is_cuda_oom(RuntimeError("CUDA out of memory")))
        self.assertTrue(worker.is_cuda_oom(RuntimeError("cuda: memory allocation failed")))
        self.assertTrue(worker.is_cuda_oom(RuntimeError("out of memory")))
        self.assertFalse(worker.is_cuda_oom(RuntimeError("ordinary inference error")))

    def test_cuda_tile_retry_cleans_once_and_returns_second_attempt(self):
        attempts = []
        cleanups = []

        def attempt(tile):
            attempts.append(tile)
            if tile == 512:
                raise RuntimeError("CUDA out of memory")
            return "image"

        result = worker.run_with_tile_retry(
            "cuda", attempt, lambda: cleanups.append("cleaned")
        )
        self.assertEqual(("image", 256, 2), result)
        self.assertEqual([512, 256], attempts)
        self.assertEqual(["cleaned"], cleanups)

    def test_second_cuda_oom_becomes_stable_worker_failure(self):
        cleanups = []
        with self.assertRaises(worker.WorkerFailure) as raised:
            worker.run_with_tile_retry(
                "cuda",
                lambda tile: (_ for _ in ()).throw(
                    RuntimeError("CUDA out of memory")
                ),
                lambda: cleanups.append("cleaned"),
            )
        self.assertEqual("CUDA_OOM", raised.exception.error_code)
        self.assertEqual(5, raised.exception.exit_code)
        self.assertEqual("显存不足，请使用更小的原图", raised.exception.message)
        self.assertEqual(["cleaned"], cleanups)

    def test_non_oom_and_cpu_do_not_retry(self):
        calls = []
        with self.assertRaisesRegex(RuntimeError, "bad kernel"):
            worker.run_with_tile_retry(
                "cuda",
                lambda tile: calls.append(tile)
                or (_ for _ in ()).throw(RuntimeError("bad kernel")),
                lambda: self.fail("cleanup must not run"),
            )
        self.assertEqual([512], calls)
        self.assertEqual(
            ("cpu-image", 0, 1),
            worker.run_with_tile_retry(
                "cpu", lambda tile: "cpu-image", lambda: self.fail("no cleanup")
            ),
        )

    def test_cpu_memory_errors_are_not_misclassified_as_cuda_oom(self):
        for source_error in (
            RuntimeError("out of memory"),
            MemoryError(),
        ):
            with self.subTest(error=type(source_error).__name__):
                attempts = []
                cleanups = []

                def attempt(tile):
                    attempts.append(tile)
                    raise source_error

                with self.assertRaises(type(source_error)) as raised:
                    worker.run_with_tile_retry(
                        "cpu", attempt, lambda: cleanups.append("cleaned")
                    )
                self.assertIs(source_error, raised.exception)
                self.assertEqual([0], attempts)
                self.assertEqual([], cleanups)

    def test_torchvision_compat_shim_exposes_only_rgb_to_grayscale(self):
        sentinel = object()
        functional = types.ModuleType("torchvision.transforms.functional")
        functional.rgb_to_grayscale = sentinel
        fake_modules = {
            "torchvision.transforms.functional": functional,
        }
        imported = []

        def importing(name):
            imported.append(name)
            return fake_modules[name]

        with mock.patch.dict(sys.modules, {}, clear=False):
            sys.modules.pop("torchvision.transforms.functional_tensor", None)
            with mock.patch.object(worker.importlib, "import_module", side_effect=importing):
                shim = worker.install_torchvision_compat_shim()
            self.assertIs(sentinel, shim.rgb_to_grayscale)
            self.assertEqual(
                ["rgb_to_grayscale"],
                [name for name in vars(shim) if not name.startswith("__")],
            )
            self.assertIs(
                shim, sys.modules["torchvision.transforms.functional_tensor"]
            )
        self.assertEqual(["torchvision.transforms.functional"], imported)

    def test_runtime_loader_installs_shim_before_basicsr_and_realesrgan(self):
        order = []
        modules = {
            name: types.SimpleNamespace(__version__="1")
            for name in ("torch", "torchvision", "cv2", "numpy", "basicsr", "realesrgan")
        }
        modules["basicsr.archs.rrdbnet_arch"] = types.SimpleNamespace(
            RRDBNet=object
        )
        modules["realesrgan"].RealESRGANer = object
        with mock.patch.object(
            worker, "install_torchvision_compat_shim", side_effect=lambda: order.append("shim")
        ), mock.patch.object(
            worker.importlib,
            "import_module",
            side_effect=lambda name: order.append(name) or modules[name],
        ):
            runtime = worker.load_runtime()
        self.assertLess(order.index("shim"), order.index("basicsr"))
        self.assertLess(order.index("shim"), order.index("realesrgan"))
        self.assertIs(object, runtime.RRDBNet)
        self.assertIs(modules["numpy"], runtime.numpy)

    def test_strict_tile_process_propagates_model_runtime_error_without_progress(self):
        class NoGrad:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class Torch:
            @staticmethod
            def no_grad():
                return NoGrad()

        class Tensor:
            shape = (1, 3, 4, 4)

            def new_zeros(self, shape):
                return self

            def __getitem__(self, key):
                return self

            def __setitem__(self, key, value):
                pass

        Strict = worker.strict_realesrganer_class(object, Torch)
        instance = Strict()
        instance.img = Tensor()
        instance.scale = 4
        instance.tile_size = 4
        instance.tile_pad = 10
        instance.model = lambda image: (_ for _ in ()).throw(
            RuntimeError("CUDA out of memory")
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            with self.assertRaisesRegex(RuntimeError, "CUDA out of memory"):
                instance.tile_process()
        self.assertEqual("", stdout.getvalue())

    def test_cli_prints_exactly_one_json_document_and_redirects_library_stdout(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        def noisy_dispatch(argv):
            print("library noise")
            return {"ok": True, "kind": "status"}

        with mock.patch.object(worker, "_dispatch", side_effect=noisy_dispatch):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = worker.main(["status"])
        self.assertEqual(0, exit_code)
        self.assertEqual({"ok": True, "kind": "status"}, json.loads(stdout.getvalue()))
        self.assertEqual(1, len(stdout.getvalue().strip().splitlines()))
        self.assertIn("library noise", stderr.getvalue())

    def test_cli_wire_json_is_ascii_safe_and_preserves_chinese_message(self):
        wire_bytes = io.BytesIO()
        ascii_stdout = io.TextIOWrapper(
            wire_bytes, encoding="ascii", write_through=True
        )

        def failing_dispatch(argv):
            raise worker.WorkerFailure(
                "CUDA_OOM", "显存不足，请使用更小的原图", 5
            )

        with mock.patch.object(worker, "_dispatch", side_effect=failing_dispatch):
            with contextlib.redirect_stdout(ascii_stdout):
                exit_code = worker.main(["upscale"])
        wire = wire_bytes.getvalue().decode("ascii")
        self.assertEqual(5, exit_code)
        self.assertEqual(1, len(wire.strip().splitlines()))
        payload = json.loads(wire)
        self.assertEqual("显存不足，请使用更小的原图", payload["message"])
        self.assertTrue(wire.isascii())

    def test_project_tools_package_wins_over_later_site_package(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            external_root = Path(directory)
            external_tools = external_root / "tools"
            external_tools.mkdir()
            (external_tools / "__init__.py").write_text("", encoding="utf-8")
            (external_tools / "realesrgan_worker.py").write_text(
                "ORIGIN = 'external'\n", encoding="utf-8"
            )
            script = (
                "import pathlib, sys\n"
                f"sys.path.insert(0, {str(project_root)!r})\n"
                f"sys.path.insert(1, {str(external_root)!r})\n"
                "from tools import realesrgan_worker\n"
                "print(pathlib.Path(realesrgan_worker.__file__).resolve())\n"
            )
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True,
            )
        imported_path = Path(completed.stdout.strip())
        self.assertEqual(
            project_root / "tools" / "realesrgan_worker.py", imported_path
        )

    def test_tile_slices_cover_non_divisible_image_without_gaps_or_overlap(self):
        slices = worker.tile_slices(height=5, width=7, tile=4, pad=1, scale=4)
        self.assertEqual(4, len(slices))
        self.assertEqual(
            (0, 5, 0, 5, 0, 16, 0, 16, 0, 16, 0, 16),
            slices[0],
        )
        self.assertEqual(
            (3, 7, 3, 5, 16, 28, 16, 20, 4, 16, 4, 8),
            slices[-1],
        )

        coverage = [[0 for _ in range(7 * 4)] for _ in range(5 * 4)]
        for item in slices:
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
            self.assertGreaterEqual(input_start_x_pad, 0)
            self.assertLessEqual(input_end_x_pad, 7)
            self.assertGreaterEqual(input_start_y_pad, 0)
            self.assertLessEqual(input_end_y_pad, 5)
            self.assertEqual(output_end_x - output_start_x, output_end_x_tile - output_start_x_tile)
            self.assertEqual(output_end_y - output_start_y, output_end_y_tile - output_start_y_tile)
            for y in range(output_start_y, output_end_y):
                for x in range(output_start_x, output_end_x):
                    coverage[y][x] += 1
        self.assertTrue(all(value == 1 for row in coverage for value in row))

    def test_tile_slices_single_tile_clips_padding_to_image_edges(self):
        self.assertEqual(
            ((0, 3, 0, 2, 0, 12, 0, 8, 0, 12, 0, 8),),
            worker.tile_slices(height=2, width=3, tile=8, pad=10, scale=4),
        )


class FakeImage:
    def __init__(self, width, height):
        self.shape = (height, width, 3)


class FakeCuda:
    def __init__(self, available=True):
        self.available = available
        self.empty_cache_calls = 0

    def is_available(self):
        return self.available

    def empty_cache(self):
        self.empty_cache_calls += 1


class FakeTorch:
    __version__ = "2.fake"

    def __init__(self, cuda=True):
        self.cuda = FakeCuda(cuda)

    @staticmethod
    def device(value):
        return value


class FakeCV2:
    __version__ = "4.fake"
    IMREAD_UNCHANGED = -1

    def __init__(self, input_path, source_image, *, write_ok=True):
        self.input_path = str(input_path)
        self.source_image = source_image
        self.write_ok = write_ok
        self.saved = {}

    def imread(self, path, flag):
        path = str(path)
        if path == self.input_path:
            return self.source_image
        return self.saved.get(path)

    def imwrite(self, path, image):
        if not self.write_ok:
            return False
        path = str(path)
        Path(path).write_bytes(b"png")
        self.saved[path] = image
        return True


class WorkerUpscaleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "input.png"
        self.model_path = self.root / "model.pth"
        self.output_path = self.root / "output.png"
        self.input_path.write_bytes(b"input")
        self.model_path.write_bytes(b"model")

    def runtime(self, behaviors=None, *, write_ok=True, cuda=True, init_noise=False):
        records = {"architectures": [], "upsamplers": [], "enhance": []}
        behaviors = list(behaviors or [None])
        cv2 = FakeCV2(self.input_path, FakeImage(7, 5), write_ok=write_ok)
        torch = FakeTorch(cuda)

        class RRDBNet:
            def __init__(self, **kwargs):
                records["architectures"].append(kwargs)

        class RealESRGANer:
            def __init__(self, **kwargs):
                if init_noise:
                    print("upsampler init noise")
                records["upsamplers"].append(kwargs)

            def enhance(self, image, **kwargs):
                records["enhance"].append(kwargs)
                behavior = behaviors.pop(0)
                if isinstance(behavior, BaseException):
                    raise behavior
                scale = int(kwargs["outscale"])
                return FakeImage(image.shape[1] * scale, image.shape[0] * scale), "RGB"

        runtime = types.SimpleNamespace(
            torch=torch,
            torchvision=types.SimpleNamespace(__version__="0.fake"),
            cv2=cv2,
            basicsr=types.SimpleNamespace(__version__="1.fake"),
            realesrgan=types.SimpleNamespace(__version__="0.3.0"),
            RRDBNet=RRDBNet,
            RealESRGANer=RealESRGANer,
        )
        return runtime, records

    def invoke(self, scale, runtime, device="auto"):
        return worker.upscale_request(
            input_path=self.input_path,
            output_path=self.output_path,
            model_id=worker.DEFAULT_MODEL_ID,
            model_path=self.model_path,
            scale=scale,
            device=device,
            runtime_loader=lambda: runtime,
        )

    def test_fake_inference_uses_exact_architecture_and_outscale_for_two_and_four(self):
        for scale in (2, 4):
            with self.subTest(scale=scale):
                self.output_path.unlink(missing_ok=True)
                runtime, records = self.runtime()
                payload = self.invoke(scale, runtime, device="cpu")
                self.assertEqual(worker.anime_6b_architecture(), records["architectures"][0])
                self.assertEqual(float(scale), records["enhance"][0]["outscale"])
                self.assertEqual("realesrgan", records["enhance"][0]["alpha_upsampler"])
                self.assertEqual((7 * scale, 5 * scale), (payload["width"], payload["height"]))
                self.assertEqual("cpu", payload["device"])
                self.assertEqual("fp32", payload["precision"])
                self.assertEqual(0, payload["tile"])
                self.assertEqual(1, payload["attempts"])

    def test_cuda_retries_512_then_256_once(self):
        runtime, records = self.runtime(
            [RuntimeError("CUDA out of memory"), None]
        )
        payload = self.invoke(4, runtime, device="cuda")
        self.assertEqual([512, 256], [item["tile"] for item in records["upsamplers"]])
        self.assertEqual(1, runtime.torch.cuda.empty_cache_calls)
        self.assertEqual(256, payload["tile"])
        self.assertEqual(2, payload["attempts"])
        self.assertEqual("cuda:0", payload["device"])
        self.assertEqual("fp16", payload["precision"])
        self.assertNotIn("gpu_id", records["upsamplers"][0])

    def test_upscale_redirects_potential_constructor_output_to_stderr(self):
        runtime, _ = self.runtime(init_noise=True)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.invoke(2, runtime, device="cpu")
        self.assertEqual("", stdout.getvalue())
        self.assertIn("upsampler init noise", stderr.getvalue())

    def test_second_cuda_oom_and_non_oom_have_stable_failures(self):
        runtime, records = self.runtime(
            [RuntimeError("CUDA out of memory"), RuntimeError("CUDA out of memory")]
        )
        with self.assertRaises(worker.WorkerFailure) as raised:
            self.invoke(4, runtime, device="cuda")
        self.assertEqual(("CUDA_OOM", 5), (raised.exception.error_code, raised.exception.exit_code))
        self.assertEqual(2, len(records["enhance"]))

        runtime, records = self.runtime([RuntimeError("kernel failed")])
        with self.assertRaises(worker.WorkerFailure) as raised:
            self.invoke(4, runtime, device="cuda")
        self.assertEqual(("INFERENCE_FAILED", 6), (raised.exception.error_code, raised.exception.exit_code))
        self.assertEqual(1, len(records["enhance"]))

    def test_cpu_out_of_memory_is_an_inference_failure_not_cuda_oom(self):
        for source_error in (
            RuntimeError("out of memory"),
            MemoryError(),
        ):
            with self.subTest(error=type(source_error).__name__):
                runtime, records = self.runtime([source_error], cuda=False)
                with self.assertRaises(worker.WorkerFailure) as raised:
                    self.invoke(4, runtime, device="cpu")
                self.assertEqual(
                    ("INFERENCE_FAILED", 6),
                    (raised.exception.error_code, raised.exception.exit_code),
                )
                self.assertEqual(1, len(records["enhance"]))
                self.assertEqual(0, runtime.torch.cuda.empty_cache_calls)

    def test_output_write_failure_preserves_existing_output_and_input(self):
        self.output_path.write_bytes(b"old-output")
        original_input = self.input_path.read_bytes()
        runtime, _ = self.runtime(write_ok=False)
        with self.assertRaises(worker.WorkerFailure) as raised:
            self.invoke(2, runtime, device="cpu")
        self.assertEqual("OUTPUT_WRITE_FAILED", raised.exception.error_code)
        self.assertEqual(b"old-output", self.output_path.read_bytes())
        self.assertEqual(original_input, self.input_path.read_bytes())
        self.assertEqual([], list(self.root.glob(".*.tmp.png")))

    def test_invalid_paths_model_device_and_decode_have_stable_codes(self):
        runtime, _ = self.runtime(cuda=False)
        cases = [
            ({"model_id": "unknown"}, "MODEL_NOT_FOUND", 2),
            ({"input_path": self.root / "missing.png"}, "INPUT_NOT_FOUND", 2),
            ({"model_path": self.root / "missing.pth"}, "MODEL_NOT_FOUND", 2),
            ({"device": "cuda"}, "CUDA_UNAVAILABLE", 3),
        ]
        for changes, code, exit_code in cases:
            with self.subTest(code=code):
                kwargs = dict(
                    input_path=self.input_path,
                    output_path=self.output_path,
                    model_id=worker.DEFAULT_MODEL_ID,
                    model_path=self.model_path,
                    scale=4,
                    device="cpu",
                    runtime_loader=lambda: runtime,
                )
                kwargs.update(changes)
                with self.assertRaises(worker.WorkerFailure) as raised:
                    worker.upscale_request(**kwargs)
                self.assertEqual((code, exit_code), (raised.exception.error_code, raised.exception.exit_code))

        runtime.cv2.source_image = None
        with self.assertRaises(worker.WorkerFailure) as raised:
            self.invoke(4, runtime, device="cpu")
        self.assertEqual(("INPUT_DECODE_FAILED", 4), (raised.exception.error_code, raised.exception.exit_code))


class Waifu2xWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "input.png"
        self.output_path = self.root / "output.png"
        self.model_path = self.root / "models-cunet"
        self.model_path.mkdir()
        Image.new("RGBA", (5, 3), (20, 40, 60, 128)).save(
            self.input_path, "PNG"
        )

    def test_waifu_cunet_runs_two_passes_for_4x_and_preserves_alpha(self):
        records = {"init": [], "sizes": []}

        class FakeWaifu2x:
            def __init__(self, **kwargs):
                records["init"].append(kwargs)

            def process_pil(self, image):
                records["sizes"].append(image.size)
                return image.resize(
                    (image.width * 2, image.height * 2), Image.Resampling.NEAREST
                )

        runtime = types.SimpleNamespace(Image=Image, Waifu2x=FakeWaifu2x)
        payload = worker.upscale_request(
            input_path=self.input_path,
            output_path=self.output_path,
            model_id=worker.WAIFU2X_MODEL_ID,
            model_path=self.model_path,
            scale=4,
            device="auto",
            runtime_loader=lambda: (_ for _ in ()).throw(
                AssertionError("RealESRGAN runtime must not load")
            ),
            waifu_runtime_loader=lambda: runtime,
        )

        self.assertEqual([(5, 3), (10, 6)], records["sizes"])
        self.assertEqual(str(self.model_path), records["init"][0]["model"])
        self.assertEqual(0, records["init"][0]["gpuid"])
        self.assertEqual("Waifu2x_CUNet", payload["model"])
        self.assertEqual((20, 12), (payload["width"], payload["height"]))
        self.assertEqual("vulkan:0", payload["device"])
        self.assertEqual("ncnn-vulkan", payload["precision"])
        self.assertEqual(2, payload["attempts"])
        with Image.open(self.output_path) as output:
            self.assertEqual((20, 12), output.size)
            self.assertEqual("RGBA", output.mode)
            self.assertEqual(128, output.getchannel("A").getextrema()[0])

    def test_waifu_cpu_uses_negative_gpu_id(self):
        records = []

        class FakeWaifu2x:
            def __init__(self, **kwargs):
                records.append(kwargs)

            def process_pil(self, image):
                return image.resize((image.width * 2, image.height * 2))

        payload = worker.upscale_request(
            input_path=self.input_path,
            output_path=self.output_path,
            model_id=worker.WAIFU2X_MODEL_ID,
            model_path=self.model_path,
            scale=2,
            device="cpu",
            waifu_runtime_loader=lambda: types.SimpleNamespace(
                Image=Image, Waifu2x=FakeWaifu2x
            ),
        )
        self.assertEqual(-1, records[0]["gpuid"])
        self.assertEqual("cpu", payload["device"])
        self.assertEqual("ncnn-cpu", payload["precision"])


if __name__ == "__main__":
    unittest.main()
