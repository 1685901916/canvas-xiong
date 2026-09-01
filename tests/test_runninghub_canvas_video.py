import asyncio

import main


def test_runninghub_video_lifecycle_static_version_is_current():
    assert main.CANVAS_RUNTIME_VERSION == "2026.09.01-rerun-while-running-1"


def test_runninghub_default_provider_has_curated_video_models():
    provider = next(item for item in main.default_api_providers() if item["id"] == "runninghub")
    models = provider.get("video_models") or []
    assert "minimax/hailuo-h3/multimodal-to-video" in models
    assert "bytedance/seedance-2.5-global-token/multimodal-video" in models
    assert "kling-video-o3-pro/reference-to-video" in models
    assert len(models) >= 10


def test_runninghub_video_model_names():
    names = main.RUNNINGHUB_DEFAULT_VIDEO_MODEL_NAMES
    assert names["minimax/hailuo-h3/multimodal-to-video"] == "MiniMax H3 · 多模态参考生视频"
    assert names["kling-v3.0-pro/image-to-video"] == "可灵 3.0 Pro · 图生视频"


def test_submit_runninghub_video_task_returns_task_id_without_waiting(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "data": {"taskId": "rh-task-123"}}

    class FakeClient:
        def __init__(self):
            self.posts = []

        async def post(self, url, headers=None, json=None):
            self.posts.append({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    async def fake_model_definition(provider, model):
        return {
            "endpoint": "seedance/multimodal-video",
            "params": [
                {"fieldKey": "duration", "type": "INTEGER"},
                {"fieldKey": "aspectRatio", "type": "STRING"},
                {"fieldKey": "resolution", "type": "STRING"},
            ],
        }

    async def must_not_poll(*args, **kwargs):
        raise AssertionError("submit must return before polling the long-running task")

    monkeypatch.setattr(main, "runninghub_model_definition", fake_model_definition)
    monkeypatch.setattr(main, "runninghub_task_endpoint", lambda provider, endpoint: "/submit")
    monkeypatch.setattr(main, "wait_for_runninghub_openapi_task", must_not_poll)
    payload = main.CanvasVideoRequest(
        prompt="replace the character",
        provider_id="runninghub",
        model="seedance",
        duration=15,
        aspect_ratio="9:16",
        resolution="720p",
    )
    client = FakeClient()

    result = asyncio.run(main.submit_runninghub_video_task(payload, {"id": "runninghub"}, client))

    assert result["task_id"] == "rh-task-123"
    assert result["status"] == "QUEUED"
    assert len(client.posts) == 1
    assert client.posts[0]["json"]["duration"] == 15
    assert client.posts[0]["json"]["aspectRatio"] == "9:16"
    assert client.posts[0]["json"]["resolution"] == "720p"


def test_runninghub_video_submit_route_exists():
    routes = {(route.path, method) for route in main.app.routes for method in getattr(route, "methods", set())}
    assert ("/api/runninghub/video-submit", "POST") in routes


def test_submit_runninghub_video_task_uploads_video_and_audio_references(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "data": {"taskId": "rh-task-media"}}

    class FakeClient:
        async def post(self, url, headers=None, json=None):
            self.body = json
            return FakeResponse()

    async def fake_model_definition(provider, model):
        return {
            "endpoint": "seedance/multimodal-video",
            "params": [
                {"fieldKey": "videoUrls", "type": "ARRAY", "multipleInputs": True},
                {"fieldKey": "audioUrls", "type": "ARRAY", "multipleInputs": True},
            ],
        }

    uploaded = []

    async def fake_upload(client, provider, ref):
        uploaded.append(ref["url"])
        return f"https://uploaded.example/{len(uploaded)}"

    monkeypatch.setattr(main, "runninghub_model_definition", fake_model_definition)
    monkeypatch.setattr(main, "runninghub_task_endpoint", lambda provider, endpoint: "/submit")
    monkeypatch.setattr(main, "runninghub_upload_reference", fake_upload)
    payload = main.CanvasVideoRequest(
        prompt="copy the motion",
        provider_id="runninghub",
        model="seedance",
        videos=["/assets/reference.mp4"],
        audios=["/assets/reference.wav"],
    )
    client = FakeClient()

    asyncio.run(main.submit_runninghub_video_task(payload, {"id": "runninghub"}, client))

    assert uploaded == ["/assets/reference.mp4", "/assets/reference.wav"]
    assert client.body["videoUrls"] == ["https://uploaded.example/1"]
    assert client.body["audioUrls"] == ["https://uploaded.example/2"]
