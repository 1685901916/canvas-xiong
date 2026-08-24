import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

import autodl_support as support


class AutoDLWorkflowTests(unittest.TestCase):
    def test_registry_contains_exact_verified_workflows(self):
        self.assertEqual(
            {
                "minimax_h3_lightx2v_v5",
                "minimax_h3_lightx2v_v5_15s",
                "minimax_h3_lightx2v_no_pic",
                "minimax_h3_lightx2v",
                "minimax_h3_image_audio_to_video_v2",
                "minimax_h3_image_audio_to_video_v2_15s",
                "minimax_h3_image_audio_to_video",
            },
            set(support.WORKFLOWS),
        )

    def test_routes_by_media_duration_and_lip_sync_intent(self):
        cases = [
            (
                {"prompt": "cloud walk", "duration": 8, "images": [], "audios": []},
                "minimax_h3_lightx2v_no_pic",
            ),
            (
                {"prompt": "walk", "duration": 10, "images": ["a"], "audios": []},
                "minimax_h3_lightx2v_v5",
            ),
            (
                {"prompt": "walk", "duration": 11, "images": ["a"], "audios": []},
                "minimax_h3_lightx2v_v5_15s",
            ),
            (
                {"prompt": "talk", "duration": 8, "images": ["a"], "audios": ["b"]},
                "minimax_h3_image_audio_to_video_v2",
            ),
            (
                {
                    "prompt": "角色说话并自动对口型",
                    "duration": 8,
                    "images": ["a"],
                    "audios": ["b"],
                },
                "minimax_h3_image_audio_to_video",
            ),
            (
                {
                    "prompt": "montage",
                    "duration": 15,
                    "images": ["a"],
                    "audios": ["b", "c"],
                },
                "minimax_h3_image_audio_to_video_v2_15s",
            ),
        ]
        for request, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    expected,
                    support.resolve_workflow(**request).workflow_id,
                )

    def test_first_last_and_invalid_inputs_fail_before_submission(self):
        resolved = support.resolve_workflow(
            prompt="transition",
            duration=8,
            images=["a", "b"],
            audios=[],
            first_last=True,
        )
        self.assertEqual("minimax_h3_lightx2v", resolved.workflow_id)

        invalid_requests = (
            {"duration": 16, "images": ["a"], "audios": []},
            {"duration": 8, "images": [str(i) for i in range(10)], "audios": []},
            {"duration": 8, "images": ["a"], "audios": ["a", "b", "c", "d"]},
            {"duration": 8, "images": ["a"], "audios": [], "videos": ["v.mp4"]},
            {"duration": 8, "images": ["a"], "audios": [], "first_last": True},
        )
        for changes in invalid_requests:
            with self.subTest(changes=changes), self.assertRaises(
                support.AutoDLValidationError
            ):
                support.resolve_workflow(prompt="x", **changes)

    def test_manual_mode_enforces_workflow_requirements(self):
        resolved = support.resolve_workflow(
            prompt="move",
            duration=8,
            images=["first", "last"],
            audios=[],
            first_last=True,
            mode="manual",
            workflow_id="minimax_h3_lightx2v",
        )
        self.assertEqual("minimax_h3_lightx2v", resolved.workflow_id)

        with self.assertRaises(support.AutoDLValidationError):
            support.resolve_workflow(
                prompt="move",
                duration=8,
                images=["only-one"],
                audios=[],
                mode="manual",
                workflow_id="minimax_h3_lightx2v",
            )

    def test_exact_body_keys_for_every_workflow_family(self):
        refs = [f"https://example.test/{i}.png" for i in range(2)]
        audios = ["https://example.test/a.wav"]

        for workflow_id in (
            "minimax_h3_lightx2v_v5",
            "minimax_h3_lightx2v_v5_15s",
        ):
            with self.subTest(workflow_id=workflow_id):
                self.assertEqual(
                    {
                        "prompt",
                        "duration",
                        "resolution",
                        "seed",
                        "ref_image_0",
                        "ref_image_1",
                    },
                    set(
                        support.build_request_body(
                            workflow_id,
                            "move",
                            8,
                            "768p竖",
                            refs,
                            [],
                            seed=7,
                        )
                    ),
                )

        self.assertEqual(
            {"prompt", "duration", "resolution"},
            set(
                support.build_request_body(
                    "minimax_h3_lightx2v_no_pic",
                    "move",
                    8,
                    "768p横",
                    [],
                    [],
                )
            ),
        )

        self.assertEqual(
            {"prompt", "duration", "resolution", "first_frame", "last_frame"},
            set(
                support.build_request_body(
                    "minimax_h3_lightx2v",
                    "move",
                    8,
                    "768p横",
                    refs,
                    [],
                )
            ),
        )

        for workflow_id in (
            "minimax_h3_image_audio_to_video_v2",
            "minimax_h3_image_audio_to_video_v2_15s",
        ):
            with self.subTest(workflow_id=workflow_id):
                self.assertEqual(
                    {
                        "prompt",
                        "duration",
                        "resolution",
                        "seed",
                        "ref_image_0",
                        "ref_image_1",
                        "ref_audio_0",
                    },
                    set(
                        support.build_request_body(
                            workflow_id,
                            "move",
                            8,
                            "768p竖",
                            refs,
                            audios,
                            seed=7,
                        )
                    ),
                )
        self.assertEqual(
            {"resolution", "ref_image_0", "ref_audio_0", "audio_duration"},
            set(
                support.build_request_body(
                    "minimax_h3_image_audio_to_video",
                    "ignored",
                    8,
                    "768p竖",
                    refs[:1],
                    audios,
                )
            ),
        )

    def test_body_rejects_unsupported_resolution_and_square_ratio(self):
        with self.assertRaises(support.AutoDLValidationError):
            support.build_request_body(
                "minimax_h3_lightx2v_v5_15s",
                "move",
                12,
                "1080p横",
                ["https://example.test/reference.png"],
                [],
            )
        with self.assertRaises(support.AutoDLValidationError):
            support.build_request_body(
                "minimax_h3_lightx2v_no_pic",
                "move",
                8,
                "768p1:1",
                [],
                [],
            )
        with self.assertRaises(support.AutoDLValidationError):
            support.build_request_body(
                "minimax_h3_lightx2v_v5",
                "move",
                8,
                "720p横",
                ["https://example.test/reference.png"],
                [],
            )

    def test_discover_token_and_sanitize_errors(self):
        token, source = support.discover_token(
            environ={"AUTODL_TOKEN": "secret-token"},
            cwd=Path("."),
            home=Path("."),
        )
        self.assertEqual("secret-token", token)
        self.assertEqual("process environment", source)
        self.assertNotIn(
            "secret-token",
            support.safe_error(
                RuntimeError("Authorization: secret-token"),
                "secret-token",
            ),
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env.autodl").write_text(
                "AUTODL_TOKEN=file-token\n", encoding="utf-8"
            )
            token, source = support.discover_token(
                environ={}, cwd=root / "nested", home=root
            )
            self.assertEqual("file-token", token)
            self.assertEqual(str((root / ".env.autodl").resolve()), source)

    def test_collect_result_urls_reads_only_data_results(self):
        payload = {
            "debug": "https://should-not-be-returned.test/debug.mp4",
            "data": {
                "results": [
                    "https://cdn.test/video.mp4",
                    {"preview": "http://cdn.test/preview.mp4"},
                    "file:///local/video.mp4",
                    "https://cdn.test/video.mp4",
                ]
            },
        }
        self.assertEqual(
            ["https://cdn.test/video.mp4", "http://cdn.test/preview.mp4"],
            support.collect_result_urls(payload),
        )


class AutoDLClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_and_query_use_wrapped_endpoints_and_raw_token(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "code": "Success",
                        "data": {"task_id": "task-123", "status": "QUEUED"},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "code": "Success",
                    "data": {"task_id": "task-123", "status": "RUNNING"},
                },
            )

        transport = httpx.MockTransport(handler)

        def client_factory(**kwargs):
            return httpx.AsyncClient(transport=transport, **kwargs)

        client = support.AutoDLClient("secret-token", client_factory=client_factory)
        submitted = await client.submit("minimax_h3_lightx2v_v5", {"prompt": "x"})
        queried = await client.query("task-123")

        self.assertEqual("task-123", submitted["data"]["task_id"])
        self.assertEqual("RUNNING", queried["data"]["status"])
        self.assertEqual("POST", requests[0].method)
        self.assertEqual(
            "/api/v1/comfyui/comfyui_workflow/minimax_h3_lightx2v_v5",
            requests[0].url.path,
        )
        self.assertEqual("secret-token", requests[0].headers["Authorization"])
        self.assertNotEqual("Bearer secret-token", requests[0].headers["Authorization"])
        self.assertEqual(
            "/api/v1/comfyui/comfyui_workflow/result/task-123",
            requests[1].url.path,
        )

    async def test_doctor_queries_fake_task_without_posting(self):
        methods = []

        def handler(request):
            methods.append(request.method)
            return httpx.Response(
                200,
                json={"code": "InternalError", "data": None, "msg": "工作流不可用"},
            )

        transport = httpx.MockTransport(handler)

        def client_factory(**kwargs):
            return httpx.AsyncClient(transport=transport, **kwargs)

        report = await support.AutoDLClient(
            "secret-token", client_factory=client_factory
        ).doctor()
        self.assertEqual(["GET"], methods)
        self.assertTrue(report["authenticated"])
        self.assertFalse(report["paid_task_submitted"])
        self.assertEqual("InternalError", report["api_code"])
        self.assertNotIn("secret-token", repr(report))


if __name__ == "__main__":
    unittest.main()
