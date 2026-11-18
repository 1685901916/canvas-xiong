import main


def test_ark_key_enables_image_generation_without_cloud_credentials(monkeypatch):
    monkeypatch.setattr(main, "volcengine_provider_api_key", lambda: "test-ark-key")
    monkeypatch.setattr(main, "volcengine_access_key_value", lambda: "")
    monkeypatch.setattr(main, "volcengine_secret_key_value", lambda: "")
    assert main.provider_has_usable_key({"id": "volcengine", "protocol": "volcengine"})


def test_cloud_credentials_do_not_replace_ark_inference_key(monkeypatch):
    monkeypatch.setattr(main, "volcengine_provider_api_key", lambda: "")
    monkeypatch.setattr(main, "volcengine_access_key_value", lambda: "test-access-key")
    monkeypatch.setattr(main, "volcengine_secret_key_value", lambda: "test-secret-key")
    assert not main.provider_has_usable_key({"id": "volcengine", "protocol": "volcengine"})
