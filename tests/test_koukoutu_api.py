import asyncio
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

import main
import realesrgan_support as support


def png_bytes(size=(7, 5), mode="RGBA"):
    stream = io.BytesIO()
    color = (20, 40, 60, 0) if mode == "RGBA" else (20, 40, 60)
    Image.new(mode, size, color).save(stream, "PNG")
    return stream.getvalue()


class FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


class FakeAsyncClient:
    def __init__(self, response, records):
        self.response = response
        self.records = records

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        self.records.append({"url": url, **kwargs})
        return self.response


class KoukoutuAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.base_dir = self.root / "app"
        self.assets_dir = self.base_dir / "assets"
        self.output_dir = self.base_dir / "output"
        self.assets_output_dir = self.assets_dir / "output"
        for name in ("input", "output", "uploads", "library"):
            (self.assets_dir / name).mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.source_path = self.assets_dir / "uploads" / "source.png"
        Image.new("RGB", (7, 5), (80, 100, 120)).save(self.source_path, "PNG")
        self.config = support.build_config(
            self.base_dir,
            self.assets_dir,
            self.output_dir,
            environ={},
        )

    def environment(self):
        return mock.patch.multiple(
            main,
            BASE_DIR=str(self.base_dir),
            ASSETS_DIR=str(self.assets_dir),
            OUTPUT_DIR=str(self.output_dir),
            OUTPUT_OUTPUT_DIR=str(self.assets_output_dir),
        )

    @staticmethod
    def request(**changes):
        values = {"source_url": "/assets/uploads/source.png"}
        values.update(changes)
        return main.BackgroundRemovalRequest(**values)

    def run_request(self, response=None, **request_changes):
        records = []
        response = response or FakeResponse(200, png_bytes())
        client = FakeAsyncClient(response, records)
        with self.environment(), mock.patch.object(
            main, "build_config", return_value=self.config
        ), mock.patch.object(
            main, "_koukoutu_api_key", return_value="test-secret-key"
        ), mock.patch.object(
            main.httpx, "AsyncClient", return_value=client
        ):
            result = asyncio.run(
                main.koukoutu_remove_background(self.request(**request_changes))
            )
        return result, records

    def test_request_model_defaults_and_bounds(self):
        request = self.request()
        self.assertEqual((0, 1), (request.crop, request.border))
        self.assertEqual(1, self.request(crop=1, border=2).crop)
        with self.assertRaises(ValidationError):
            self.request(crop=2)
        with self.assertRaises(ValidationError):
            self.request(border=3)

    def test_routes_are_registered(self):
        routes = {
            route.path: set(route.methods or ())
            for route in main.app.routes
            if hasattr(route, "methods")
        }
        self.assertIn("GET", routes["/api/koukoutu/status"])
        self.assertIn("POST", routes["/api/koukoutu/remove-background"])

    def test_status_exposes_no_key(self):
        with mock.patch.object(main, "_koukoutu_api_key", return_value="secret-value"):
            result = asyncio.run(main.koukoutu_status())
        self.assertTrue(result["configured"])
        self.assertNotIn("secret-value", repr(result))
        self.assertEqual(5, result["concurrency"])

    def test_success_uses_expected_multipart_and_preserves_source(self):
        before = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        result, records = self.run_request()
        after = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertTrue(result["ok"])
        self.assertEqual("koukoutu", result["provider"])
        self.assertEqual((7, 5, 7, 5), (
            result["source_width"], result["source_height"],
            result["width"], result["height"],
        ))
        self.assertTrue(result["has_alpha"])
        self.assertRegex(
            result["url"], r"^/assets/output/background_removed_[0-9a-f]{32}\.png$"
        )
        saved = self.assets_output_dir / result["url"].rsplit("/", 1)[-1]
        self.assertTrue(saved.is_file())
        with Image.open(saved) as image:
            self.assertEqual(("PNG", (7, 5)), (image.format, image.size))

        self.assertEqual(1, len(records))
        call = records[0]
        self.assertEqual(main.KOUKOUTU_SYNC_URL, call["url"])
        self.assertEqual({"X-API-Key": "test-secret-key"}, call["headers"])
        self.assertEqual({
            "model_key": "background-removal",
            "output_format": "png",
            "crop": 0,
            "border": 1,
            "stamp_crop": 0,
            "response": "bytes",
        }, call["params"])
        self.assertIn("image_file", call["files"])
        self.assertEqual("image/png", call["files"]["image_file"][2])
        self.assertNotIn("test-secret-key", repr(result))

    def test_rejects_remote_url_before_calling_provider(self):
        with self.environment(), mock.patch.object(
            main, "_koukoutu_api_key", return_value="test-secret-key"
        ), mock.patch.object(main.httpx, "AsyncClient") as client:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.koukoutu_remove_background(
                    self.request(source_url="https://example.com/source.png")
                ))
        self.assertEqual(400, raised.exception.status_code)
        client.assert_not_called()

    def test_rejects_unsupported_gif(self):
        gif_path = self.assets_dir / "uploads" / "source.gif"
        Image.new("RGB", (4, 3), (1, 2, 3)).save(gif_path, "GIF")
        with self.environment(), mock.patch.object(
            main, "build_config", return_value=self.config
        ), mock.patch.object(
            main, "_koukoutu_api_key", return_value="test-secret-key"
        ), mock.patch.object(main.httpx, "AsyncClient") as client:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.koukoutu_remove_background(
                    self.request(source_url="/assets/uploads/source.gif")
                ))
        self.assertEqual(415, raised.exception.status_code)
        client.assert_not_called()

    def test_missing_key_is_safe_and_does_not_call_provider(self):
        with mock.patch.object(main, "_koukoutu_api_key", return_value=""), mock.patch.object(
            main.httpx, "AsyncClient"
        ) as client:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.koukoutu_remove_background(self.request()))
        self.assertEqual(503, raised.exception.status_code)
        self.assertNotIn("key", str(raised.exception.detail).lower())
        client.assert_not_called()

    def test_upstream_error_and_invalid_body_are_sanitized(self):
        with self.assertRaises(HTTPException) as upstream:
            self.run_request(FakeResponse(401, b'{"secret":"provider-detail"}'))
        self.assertEqual(502, upstream.exception.status_code)
        self.assertNotIn("provider-detail", str(upstream.exception.detail))

        with self.assertRaises(HTTPException) as invalid:
            self.run_request(FakeResponse(200, b"not-an-image"))
        self.assertEqual(502, invalid.exception.status_code)
        self.assertEqual("抠图服务未返回有效的 PNG 图片", invalid.exception.detail)


if __name__ == "__main__":
    unittest.main()
