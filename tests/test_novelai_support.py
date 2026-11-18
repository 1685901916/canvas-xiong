import asyncio
from io import BytesIO
import json
import zipfile

import httpx
import pytest
from PIL import Image
from fastapi import HTTPException

import novelai_support as nai


def png(size=(64, 64)):
    output = BytesIO()
    Image.new("RGB", size, "blue").save(output, format="PNG")
    return output.getvalue()


def zip_png(image):
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("image_0.png", image)
    return output.getvalue()


@pytest.mark.parametrize("model", nai.MODELS)
def test_v5_payload(model):
    body = nai.build_payload("a blue flower", "832x1216", model)
    assert body["model"] == model
    assert body["parameters"]["v4_prompt"]["caption"]["base_caption"] == body["input"]
    assert body["parameters"]["n_samples"] == 1
    assert body["parameters"]["noise_schedule"] == "karras"


@pytest.mark.parametrize("size", ["auto", "4K", "2048x2048", "1000x1000", "0x1024", "-64x512"])
def test_invalid_size_rejected_before_network(size):
    with pytest.raises(HTTPException):
        nai.build_payload("flower", size, nai.MODELS[0])


def test_references_are_not_silently_ignored():
    with pytest.raises(HTTPException, match="参考图"):
        nai.build_payload("flower", "1024x1024", nai.MODELS[0], [{"url": "ref"}])


@pytest.mark.parametrize("base", ["http://image.novelai.net", "https://image.novelai.net.evil.test", "https://other.example", "https://image.novelai.net/custom"])
def test_token_destination_is_fixed(base):
    with pytest.raises(HTTPException):
        nai.validate_base_url(base)


def test_decode_zip_and_png():
    original = png()
    assert nai.decode_image(original, (64, 64)) == nai.decode_image(zip_png(original), (64, 64))


@pytest.mark.parametrize("body,size", [(b"<html>error</html>", (64, 64)), (png(), (128, 128)), (b"PKbad", (64, 64))])
def test_invalid_image_is_not_reported_as_success(body, size):
    with pytest.raises(HTTPException):
        nai.decode_image(body, size)


def mock_client(monkeypatch, handler):
    client_type = httpx.AsyncClient
    monkeypatch.setattr(nai.httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))


def test_account_check_only_gets_balance(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"subscription": {"tier": 0, "trainingStepsLeft": {"fixedTrainingStepsLeft": 100, "purchasedTrainingSteps": 200}}})
    mock_client(monkeypatch, handler)
    result = asyncio.run(nai.account_status("test-token"))
    assert result["balance"] == 300
    assert result["image_models"] == nai.MODELS
    assert [(req.method, req.url.path) for req in requests] == [("GET", "/user/data")]
    assert "test-token" not in json.dumps(result)


def test_auth_error_does_not_echo_token(monkeypatch):
    mock_client(monkeypatch, lambda req: httpx.Response(401, text="test-token"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(nai.account_status("test-token"))
    assert "test-token" not in str(error.value)


def test_real_protocol_zip_response_and_no_paid_retry(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == "/ai/generate-image"
        assert json.loads(request.content)["model"] == nai.MODELS[0]
        return httpx.Response(200, content=zip_png(png()))
    mock_client(monkeypatch, handler)
    image, metadata = asyncio.run(nai.generate("test-token", nai.BASE_URL, "flower", "64x64", nai.MODELS[0]))
    assert image["type"] == "b64"
    assert metadata["model"] == nai.MODELS[0]
    assert len(calls) == 1


def test_server_failure_does_not_retry_or_echo_body(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(500, text="test-token")
    mock_client(monkeypatch, handler)
    with pytest.raises(HTTPException) as error:
        asyncio.run(nai.generate("test-token", nai.BASE_URL, "flower", "64x64", nai.MODELS[0]))
    assert "test-token" not in str(error.value)
    assert len(calls) == 1


def test_canvas_dispatch_and_validation(monkeypatch):
    import main
    provider = main.normalize_provider({"id": "nai-test", "protocol": "novelai", "base_url": nai.BASE_URL, "image_models": nai.MODELS, "model_protocols": {nai.MODELS[0]: "openai"}})
    assert main.effective_protocol(provider, nai.MODELS[0]) == "novelai"
    monkeypatch.setattr(main, "get_api_provider", lambda _: provider)
    monkeypatch.setattr(main, "preferred_image_api_provider", lambda _: provider)
    monkeypatch.setattr(main, "provider_env_key_value", lambda _: "test-token")
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=zip_png(png())))
    image, _ = asyncio.run(main.generate_ai_image("flower", "64x64", "auto", nai.MODELS[0], provider_id="nai-test"))
    assert image["type"] == "b64"
    resolution = main.resolve_online_image_request(main.OnlineImageRequest(prompt="flower", size="1024x1024", provider_id="nai-test", model=nai.MODELS[0]))
    assert resolution["resolved"]["endpoint_path"] == "/ai/generate-image"
    with pytest.raises(HTTPException):
        main.resolve_online_image_request(main.OnlineImageRequest(prompt="flower", size="4096x4096", provider_id="nai-test", model=nai.MODELS[0]))
