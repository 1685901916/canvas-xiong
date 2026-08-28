import asyncio
import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import main


class FakeAutoDLClient:
    def __init__(self, *, submit_result=None, query_result=None):
        self.submit_result = submit_result
        self.query_result = query_result
        self.submissions = []
        self.queries = []

    async def submit(self, workflow_id, body):
        self.submissions.append((workflow_id, body))
        return self.submit_result

    async def query(self, task_id):
        self.queries.append(task_id)
        return self.query_result


class AutoDLAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = Path(self.temp_dir.name) / "assets" / "output"
        self.output_dir.mkdir(parents=True)

    @staticmethod
    def request(**changes):
        values = {
            "prompt": "角色向前走",
            "duration": 8,
            "aspect_ratio": "9:16",
            "resolution": "768p",
            "images": [
                main.AIReference(
                    url="https://example.test/reference.png",
                    role="reference_image",
                )
            ],
            "audios": [],
            "videos": [],
            "workflow_mode": "auto",
        }
        values.update(changes)
        return main.AutoDLTaskRequest(**values)

    def test_routes_are_registered_with_expected_methods(self):
        routes = {
            route.path: set(route.methods or ())
            for route in main.app.routes
            if hasattr(route, "methods")
        }
        self.assertIn("GET", routes["/api/autodl/workflows"])
        self.assertIn("GET", routes["/api/autodl/status"])
        self.assertIn("POST", routes["/api/autodl/tasks"])
        self.assertIn("GET", routes["/api/autodl/tasks/{task_id}"])

    def test_builtin_provider_and_workflows_expose_no_token_fields(self):
        provider = next(
            item for item in main.default_api_providers() if item["id"] == "autodl"
        )
        self.assertEqual("autodl", provider["protocol"])
        self.assertEqual(7, len(provider["video_models"]))

        result = asyncio.run(main.autodl_workflows())
        self.assertEqual("minimax_h3_lightx2v_v5", result["default"])
        self.assertEqual(7, len(result["workflows"]))
        self.assertFalse(
            {"token", "api_key", "authorization"}
            & {key.lower() for key in repr(result).split()}
        )
        self.assertNotIn("secret-token", repr(result))

    def test_status_sanitizes_configuration_and_authentication_failures(self):
        with mock.patch.object(
            main.autodl,
            "doctor_safe",
            new=mock.AsyncMock(
                return_value={
                    "status": "error",
                    "authenticated": False,
                    "configured": True,
                    "message": "AutoDL 鉴权失败",
                    "paid_task_submitted": False,
                }
            ),
        ):
            result = asyncio.run(main.autodl_status())
        self.assertFalse(result["authenticated"])
        self.assertNotIn("secret-token", repr(result))
        self.assertFalse(result["paid_task_submitted"])

    def test_submission_returns_resolved_workflow_and_task_id(self):
        fake = FakeAutoDLClient(
            submit_result={
                "code": "Success",
                "data": {"task_id": "task-123", "status": "QUEUED"},
            }
        )
        with mock.patch.object(
            main.autodl, "client_from_environment", return_value=fake
        ):
            result = asyncio.run(main.autodl_submit_task(self.request()))

        self.assertEqual("task-123", result["task_id"])
        self.assertEqual("QUEUED", result["status"])
        self.assertEqual("autodl", result["provider_id"])
        self.assertEqual("minimax_h3_lightx2v_v5", result["workflow_id"])
        self.assertEqual(1, len(fake.submissions))
        workflow_id, body = fake.submissions[0]
        self.assertEqual("minimax_h3_lightx2v_v5", workflow_id)
        self.assertEqual(
            {
                "prompt",
                "duration",
                "resolution",
                "ref_image_0",
            },
            set(body),
        )

    def test_success_poll_downloads_once_and_reuses_local_result(self):
        fake = FakeAutoDLClient(
            query_result={
                "code": "Success",
                "data": {
                    "task_id": "task-123",
                    "status": "SUCCESS",
                    "results": ["https://cdn.test/result.mp4"],
                },
            }
        )

        async def fake_download(url, destination):
            self.assertEqual("https://cdn.test/result.mp4", url)
            Path(destination).write_bytes(b"\x00\x00\x00\x18ftypisom")

        with mock.patch.multiple(
            main,
            OUTPUT_OUTPUT_DIR=str(self.output_dir),
        ), mock.patch.object(
            main.autodl, "client_from_environment", return_value=fake
        ), mock.patch.object(
            main,
            "download_autodl_video",
            new=mock.AsyncMock(side_effect=fake_download),
        ) as downloader:
            first = asyncio.run(main.autodl_task_status("task-123"))
            second = asyncio.run(main.autodl_task_status("task-123"))

        self.assertEqual("SUCCESS", first["status"])
        self.assertEqual(
            ["/assets/output/autodl_task-123.mp4"], first["videos"]
        )
        self.assertEqual(first["videos"], second["videos"])
        self.assertEqual(1, downloader.await_count)
        self.assertEqual(["task-123", "task-123"], fake.queries)

    def test_cloud_media_path_accepts_audio_files(self):
        assets_dir = Path(self.temp_dir.name) / "assets"
        uploads_dir = assets_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        audio_path = uploads_dir / "voice.wav"
        audio_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        with mock.patch.multiple(
            main,
            ASSETS_DIR=str(assets_dir),
            OUTPUT_DIR=str(Path(self.temp_dir.name) / "output"),
        ):
            resolved = main.local_media_path_for_cloud_upload(
                "/assets/uploads/voice.wav"
            )
        self.assertEqual(str(audio_path), resolved)

    def test_local_media_without_public_mapping_fails_before_submit(self):
        payload = self.request(
            images=[main.AIReference(url="/assets/uploads/reference.png")]
        )
        client_factory = mock.Mock()
        with mock.patch.object(
            main, "local_asset_public_url", return_value=""
        ), mock.patch.object(
            main.autodl, "client_from_environment", client_factory
        ):
            with self.assertRaises(main.HTTPException) as raised:
                asyncio.run(main.autodl_submit_task(payload))
        self.assertEqual(400, raised.exception.status_code)
        self.assertIn("公网", str(raised.exception.detail))
        client_factory.assert_not_called()

    def test_public_media_base_mapping_is_used_without_uploading(self):
        fake = FakeAutoDLClient(
            submit_result={
                "code": "Success",
                "data": {"task_id": "task-public", "status": "QUEUED"},
            }
        )
        payload = self.request(
            prompt="角色说话并对口型",
            images=[main.AIReference(url="/assets/uploads/reference.png")],
            audios=["/assets/uploads/voice.wav"],
        )
        mappings = {
            "/assets/uploads/reference.png": "https://media.example/reference.png",
            "/assets/uploads/voice.wav": "https://media.example/voice.wav",
        }
        with mock.patch.object(
            main, "local_asset_public_url", side_effect=lambda url: mappings.get(url, "")
        ), mock.patch.object(
            main.autodl, "client_from_environment", return_value=fake
        ):
            asyncio.run(main.autodl_submit_task(payload))

        _, body = fake.submissions[0]
        self.assertEqual(
            "https://media.example/reference.png", body["ref_image_0"]
        )
        self.assertEqual("https://media.example/voice.wav", body["ref_audio_0"])


class CloudUploadUguuTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def test_uguu_upload_returns_public_url(self):
        tmp = self.temp_dir.name
        img = os.path.join(tmp, "aiko.png")
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )
        with open(img, "wb") as f:
            f.write(png_bytes)

        async def fake_post(url, **kw):
            class R:
                status_code = 200
                content = b"{}"
                is_success = True
                text = '{"success":true}'

                def json(self):
                    return {
                        "success": True,
                        "files": [
                            {
                                "url": "https://h.uguu.se/test.png",
                                "filename": "aiko.png",
                            }
                        ],
                        "errors": [],
                    }

            return R()

        with mock.patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__ = mock.AsyncMock(return_value=ac.return_value)
            ac.return_value.__aexit__ = mock.AsyncMock(return_value=False)
            ac.return_value.post = fake_post
            result = asyncio.run(main.upload_video_to_uguu(img, "/assets/x.png"))
        self.assertEqual("https://h.uguu.se/test.png", result["url"])
        self.assertEqual("uguu", result.get("service"))

    def test_auto_prefers_uguu(self):
        calls = []

        async def fake_uguu(path, source, _m=None):
            calls.append("uguu")
            return {
                "url": "https://h.uguu.se/ok.png",
                "source": source,
                "service": "uguu",
            }

        with mock.patch.object(
            main, "local_media_path_for_cloud_upload", return_value="/tmp/aiko.png"
        ), mock.patch.object(
            main,
            "upload_video_to_uguu",
            new=mock.AsyncMock(side_effect=fake_uguu),
        ), mock.patch.object(
            main,
            "upload_video_to_litterbox",
            new=mock.AsyncMock(side_effect=AssertionError("should not call litter")),
        ):
            res = asyncio.run(
                main.upload_local_video_to_cloud("/assets/x.png", "auto")
            )
        self.assertEqual("uguu", calls[0])
        self.assertEqual("https://h.uguu.se/ok.png", res["url"])


if __name__ == "__main__":
    unittest.main()
