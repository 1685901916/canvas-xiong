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
    """网关把具体原因放在 message（常为数组），error 只是 'Bad Request' 这种通用标签。
    只取 error 的话用户看到的报错等于没有信息，排查无从下手。"""

    @staticmethod
    def _detail(data):
        reasons = data.get("message")
        if isinstance(reasons, (list, tuple)):
            reasons = "；".join(str(item) for item in reasons if str(item).strip())
        reasons = str(reasons or "").strip()
        fallback = data.get("user_message") or data.get("error") or ""
        return f"{fallback}：{reasons}" if reasons and reasons != fallback else (reasons or fallback)

    def test_message_array_is_surfaced(self):
        detail = self._detail({
            "message": ["backend should not be empty", "filename must be a string"],
            "error": "Bad Request",
            "statusCode": 400,
        })
        self.assertIn("backend should not be empty", detail)
        self.assertIn("filename must be a string", detail)
        self.assertIn("Bad Request", detail)

    def test_message_string_is_surfaced(self):
        self.assertIn("上游生成任务未找到", self._detail({"message": "上游生成任务未找到", "error": "Not Found"}))

    def test_falls_back_when_no_message(self):
        self.assertEqual(self._detail({"error": "Bad Request"}), "Bad Request")
        self.assertEqual(self._detail({"user_message": "配额不足"}), "配额不足")

    def test_no_duplicate_when_message_equals_error(self):
        self.assertEqual(self._detail({"message": "Bad Request", "error": "Bad Request"}), "Bad Request")


class MiniMaxDesignSourceContractTests(unittest.TestCase):
    def test_request_helper_surfaces_gateway_message(self):
        """守住修复本身：_request 必须解析 message 字段，不能退回只取 error。"""
        src = Path(support.__file__).read_text(encoding="utf-8")
        self.assertIn('reasons = data.get("message")', src)
        self.assertIn("isinstance(reasons, (list, tuple))", src)
        self.assertNotIn(
            'detail = data.get("user_message") or data.get("error") or response.text[:500]',
            src,
            "又退回成只取 error 了，具体原因会再次被吞掉",
        )
