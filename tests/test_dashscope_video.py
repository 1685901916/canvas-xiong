"""阿里云百炼（DashScope）通义万相 wan3.0 视频接入。

用户在设置里填的是 compatible-mode/v1 那条 OpenAI 兼容地址（协议留 openai，聊天能用），
视频接口不在那条路径下，靠域名识别百炼、按域名换算 /api/v1 根地址。
"""
import asyncio

import pytest
from fastapi import HTTPException

import main


def _payload(**overrides):
    base = dict(prompt="一只猫在草地上跑", provider_id="bailian", model="wan3.0-video",
                duration=5, aspect_ratio="9:16", resolution="720p")
    base.update(overrides)
    return main.CanvasVideoRequest(**base)


BAILIAN_COMPAT = "https://llm-abc.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"


def test_detects_bailian_by_host_even_with_openai_protocol():
    assert main.is_dashscope_provider({"protocol": "openai", "base_url": BAILIAN_COMPAT})
    assert main.is_dashscope_provider({"protocol": "openai", "base_url": "https://dashscope.aliyuncs.com/api/v1"})
    assert main.is_dashscope_provider({"protocol": "dashscope", "base_url": ""})
    assert not main.is_dashscope_provider({"protocol": "openai", "base_url": "https://ai.comfly.org"})
    assert not main.is_dashscope_provider({"protocol": "openai", "base_url": ""})


def test_api_root_ignores_whatever_path_the_user_pasted():
    expected = "https://llm-abc.cn-beijing.maas.aliyuncs.com/api/v1"
    for given in (BAILIAN_COMPAT, expected, "https://llm-abc.cn-beijing.maas.aliyuncs.com/",
                  "llm-abc.cn-beijing.maas.aliyuncs.com"):
        assert main.dashscope_api_root(given) == expected, given
    assert main.dashscope_api_root("") == ""


def test_reference_mode_maps_media_and_parameters():
    payload = _payload(generate_audio=True, enhance_prompt=False, watermark=False, multimodal=True, duration=40)
    body = main.build_dashscope_video_body(
        payload, "wan3.0-video",
        [("", "data:image/png;base64,AAA"), ("", "https://x/y.png")],
        ["https://x/clip.mp4"], ["https://x/voice.mp3"],
    )
    assert body["model"] == "wan3.0-video"
    assert body["input"]["prompt"] == "一只猫在草地上跑"
    assert [m["type"] for m in body["input"]["media"]] == [
        "reference_image", "reference_image", "reference_video", "reference_audio"]
    assert body["parameters"] == {
        "resolution": "720P", "ratio": "9:16", "duration": 30,
        "audio": True, "prompt_extend": False, "watermark": False,
    }, "时长要夹到接口上限 30 秒"


def test_frame_roles_become_first_last_frame_and_refuse_clips():
    payload = _payload(multimodal=False, resolution="", aspect_ratio="source", seed=7)
    body = main.build_dashscope_video_body(
        payload, "wan3.0-video-prime", [("first_frame", "u1"), ("last_frame", "u2")], [], [])
    assert body["input"]["media"] == [{"type": "first_frame", "url": "u1"}, {"type": "last_frame", "url": "u2"}]
    assert body["parameters"]["resolution"] == "720P", "页面的 Auto 不能落到 1080P（贵一档）"
    assert body["parameters"]["ratio"] == "adaptive"
    assert body["parameters"]["seed"] == 7
    with pytest.raises(HTTPException) as ctx:
        main.build_dashscope_video_body(payload, "wan3.0-video", [("first_frame", "u1")], ["v"], [])
    assert ctx.value.status_code == 400, "首尾帧和参考素材互斥，要报清楚而不是让上游 400"


def test_all_reference_toggle_wins_over_frame_roles():
    """节点开了「全能参考」时即使参考图带着 first_frame 角色，也按参考素材送。"""
    payload = _payload(multimodal=True)
    body = main.build_dashscope_video_body(payload, "wan3.0-video", [("first_frame", "u1"), ("", "u2")], [], [])
    assert [m["type"] for m in body["input"]["media"]] == ["reference_image", "reference_image"]


def test_duration_and_ratio_helpers():
    assert main.dashscope_video_duration(-1) == -1, "-1 是接口的智能时长"
    assert main.dashscope_video_duration(1) == 2 and main.dashscope_video_duration("abc") == 5
    assert main.dashscope_video_ratio("16:9") == "16:9" and main.dashscope_video_ratio("21:9") == "adaptive"
    assert main.dashscope_video_resolution("1080p") == "1080P" and main.dashscope_video_resolution("780P") == "720P"


def test_canvas_video_routes_bailian_before_generic_openai_path(monkeypatch):
    provider = {"id": "bailian", "name": "阿里云百炼", "protocol": "openai", "base_url": BAILIAN_COMPAT}
    monkeypatch.setattr(main, "get_api_provider", lambda pid: provider)
    seen = {}

    async def fake_generate(payload, prov):
        seen["model"] = payload.model
        seen["provider"] = prov["id"]
        return {"videos": ["/assets/output/wan3_x.mp4"], "task_id": "t1", "raw": {}}

    monkeypatch.setattr(main, "generate_dashscope_video", fake_generate)
    result = asyncio.run(main.canvas_video(_payload()))
    assert seen == {"model": "wan3.0-video", "provider": "bailian"}
    assert result["videos"] == ["/assets/output/wan3_x.mp4"]


def test_missing_key_is_a_clear_400(monkeypatch):
    monkeypatch.setattr(main, "provider_env_key_value", lambda pid: "")
    provider = {"id": "bailian", "name": "阿里云百炼", "protocol": "openai", "base_url": BAILIAN_COMPAT}
    with pytest.raises(HTTPException) as ctx:
        asyncio.run(main.generate_dashscope_video(_payload(), provider))
    assert ctx.value.status_code == 400 and "API_PROVIDER_BAILIAN_KEY" in str(ctx.value.detail)


def test_wan3_models_are_classified_as_video():
    assert main.classify_upstream_model("wan3.0-video") == "video"
    assert main.classify_upstream_model("wan3.0-video-prime") == "video"
