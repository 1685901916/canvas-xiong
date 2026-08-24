import unittest

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


if __name__ == "__main__":
    unittest.main()
