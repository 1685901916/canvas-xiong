import json
from pathlib import Path
import unittest

import minimax_design_support as support


class MiniMaxDesignSupportTests(unittest.TestCase):
    def test_single_image_uses_minimax_h3_first_frame_contract(self):
        body = support.build_video_request(
        prompt="Aiko looks at us",
        duration=10,
        aspect_ratio="9:16",
        resolution="768p",
        generate_audio=False,
        image_paths=[r"C:\refs\aiko.png"],
        filename="aiko.mp4",
    )

        self.assertEqual(body["backend"], "minimax_v3")
        self.assertEqual(body["model_id"], "MiniMax-H3")
        self.assertEqual(body["image_paths"], [r"C:\refs\aiko.png"])
        self.assertEqual(body["params"], {
        "duration": "10",
        "ratio": "adaptive",
        "resolution": "768P",
        "generate_audio": "false",
        "image_mode": "first-last-frame",
        })


    def test_multimodal_references_are_serialized_into_minimax_params(self):
        body = support.build_video_request(
        prompt="Keep identity and follow the motion reference",
        duration=8,
        aspect_ratio="9:16",
        resolution="2K",
        generate_audio=True,
        image_paths=["a.png", "b.png"],
        video_paths=["motion.mp4"],
        audio_paths=["timing.wav"],
        multimodal=True,
        filename="multimodal.mp4",
    )

        self.assertEqual(body["image_paths"], [])
        self.assertEqual(json.loads(body["params"]["reference_images"]), ["a.png", "b.png"])
        self.assertEqual(json.loads(body["params"]["reference_videos"]), ["motion.mp4"])
        self.assertEqual(json.loads(body["params"]["reference_audios"]), ["timing.wav"])
        self.assertEqual(body["params"]["ratio"], "9:16")
        self.assertEqual(body["params"]["image_mode"], "reference")


    def test_request_rejects_invalid_limits_before_paid_submit(self):
        with self.assertRaisesRegex(support.MiniMaxDesignValidationError, "最多 9 张"):
            support.build_video_request(
            prompt="x",
            duration=8,
            aspect_ratio="9:16",
            resolution="768p",
            generate_audio=False,
            image_paths=[f"{index}.png" for index in range(10)],
            multimodal=True,
            filename="too-many.mp4",
        )


    def test_query_response_normalizes_success_and_video_path(self):
        result = support.normalize_task_response(
        "task-123",
        {
            "ok": True,
            "task_id": "task-123",
            "status": "succeeded",
            "result": {"path": r"C:\MiniMax\output\clip.mp4"},
        },
    )

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["video_path"], r"C:\MiniMax\output\clip.mp4")


    def test_materialize_video_is_idempotent_for_same_task(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            source.write_bytes(b"video-bytes")
            output = root / "assets" / "output"

            first = support.materialize_video(str(source), "task/123", str(output))
            second = support.materialize_video(str(source), "task/123", str(output))

            self.assertEqual(first, second)
            self.assertEqual(Path(first).read_bytes(), b"video-bytes")


class MiniMaxDesignErrorDetailTests(unittest.TestCase):
    """网关的报错分散在 message / error / user_message 三个字段，具体程度差别很大。
    user_message 是"请稍后重试或联系客服"这类套话，排前面会把真原因盖掉。"""

    def test_validation_reason_array_is_surfaced(self):
        detail = support._error_detail({
            "message": ["backend should not be empty", "filename must be a string"],
            "error": "Bad Request",
        })
        self.assertIn("backend should not be empty", detail)
        self.assertIn("filename must be a string", detail)

    def test_specific_error_beats_generic_user_message(self):
        detail = support._error_detail({
            "error": "duration must be between 4 and 15 seconds",
            "user_message": "请求异常，请稍后重试或联系客服",
        })
        self.assertEqual(detail, "duration must be between 4 and 15 seconds")
        self.assertNotIn("联系客服", detail, "套话不能盖掉真原因")

    def test_path_traversal_reason_is_surfaced(self):
        detail = support._error_detail({"message": "Path traversal detected: X", "error": "Bad Request"})
        self.assertIn("Path traversal detected", detail)

    def test_generic_message_used_only_as_last_resort(self):
        self.assertEqual(support._error_detail({"user_message": "请稍后重试"}), "请稍后重试")
        self.assertEqual(support._error_detail({}, "RAW BODY"), "RAW BODY")


class MiniMaxDesignWorkspaceTests(unittest.TestCase):
    """网关只接受它沙箱内的相对路径，绝对路径一律判为 path traversal，
    所以素材必须先复制进沙箱。沙箱位置随安装目录变化，靠 ENOENT 报错反推。"""

    def test_workspace_parsed_from_enoent(self):
        root = "D:" + chr(92) + "MMD" + chr(92) + "output_files"
        msg = "ENOENT: no such file or directory, open '" + root + chr(92) + support._WORKSPACE_PROBE_NAME + "'"
        self.assertEqual(support._parse_workspace_from_enoent(msg), root)

    def test_workspace_parse_returns_empty_when_unrecognised(self):
        self.assertEqual(support._parse_workspace_from_enoent("something else"), "")
        self.assertEqual(support._parse_workspace_from_enoent(""), "")

    def test_staging_copies_and_returns_relative_posix_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "src.png"
            src.write_bytes(b"x" * 32)
            rel = support.stage_media_into_workspace(str(src), root)
            self.assertTrue(rel.startswith(support.STAGING_SUBDIR + "/"), rel)
            self.assertNotIn(chr(92), rel, "网关按 posix 拼路径，不能带反斜杠")
            self.assertTrue((Path(root) / support.STAGING_SUBDIR / rel.split("/")[-1]).exists())
            # 同一素材重复引用不应改名，也不应重复复制
            self.assertEqual(rel, support.stage_media_into_workspace(str(src), root))

    def test_staging_without_workspace_raises_actionable_error(self):
        with self.assertRaises(support.MiniMaxDesignError) as ctx:
            support.stage_media_into_workspace(__file__, "")
        self.assertIn(support.WORKSPACE_ENV, str(ctx.exception), "报错要告诉用户设哪个环境变量")


class MiniMaxDesignSourceContractTests(unittest.TestCase):
    def test_request_helper_surfaces_gateway_message(self):
        """守住修复：_request 必须走 _error_detail，不能退回只取 error/user_message。"""
        src = Path(support.__file__).read_text(encoding="utf-8")
        self.assertIn("detail = _error_detail(data, response.text)", src)
        self.assertNotIn(
            'detail = data.get("user_message") or data.get("error")',
            src,
            "又退回成套话优先了，真原因会被盖掉",
        )
