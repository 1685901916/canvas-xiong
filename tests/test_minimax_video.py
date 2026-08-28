import main


def test_minimax_video_resolution():
    assert main.minimax_video_resolution("1080p") == "2K"
    assert main.minimax_video_resolution("2K") == "2K"
    assert main.minimax_video_resolution("768p") == "768P"
    assert main.minimax_video_resolution("") == "2K"


def test_minimax_video_ratio():
    assert main.minimax_video_ratio("9:16", "frame") == "adaptive"
    assert main.minimax_video_ratio("adaptive", "text") == "16:9"
    assert main.minimax_video_ratio("9:16", "reference") == "9:16"
    assert main.minimax_video_ratio("unknown", "reference") == "adaptive"


def test_minimax_provider_detection():
    provider = {"id": "minimax", "base_url": "https://api.minimaxi.com", "protocol": "minimax"}
    assert main.is_minimax_provider(provider) is True
    assert main.is_minimax_provider({"id": "autodl", "base_url": "https://autodl.art", "protocol": "autodl"}) is False


def test_minimax_error_message():
    class Response:
        def json(self):
            return {
                "type": "error",
                "error": {"type": "authorized_error", "message": "invalid key (1004)"},
            }

    assert "invalid key" in main.minimax_error_message(Response())


def test_minimax_is_in_default_providers():
    provider = next(item for item in main.default_api_providers() if item["id"] == "minimax")
    assert provider["protocol"] == "minimax"
    assert provider["base_url"] == "https://api.minimaxi.com"
    assert "MiniMax-H3" in provider["video_models"]
