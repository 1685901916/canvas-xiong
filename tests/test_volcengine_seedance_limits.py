import main

SEEDANCE_2_0 = "doubao-seedance-2-0-260128"
SEEDANCE_2_0_FAST = "doubao-seedance-2-0-fast-260128"
SEEDANCE_2_0_MINI = "doubao-seedance-2-0-mini-260615"
SEEDANCE_2_5 = "doubao-seedance-2-5-260628"


def test_seedance_2_0_duration_clamped_to_official_range():
    # 方舟「模型限制」：Seedance 2.0 系列 4-15s，超出会被接口直接拒绝
    for model in (SEEDANCE_2_0, SEEDANCE_2_0_FAST, SEEDANCE_2_0_MINI):
        assert main.volcengine_video_duration(30, model) == 15
        assert main.volcengine_video_duration(2, model) == 4
        assert main.volcengine_video_duration(10, model) == 10


def test_seedance_2_5_allows_thirty_seconds():
    assert main.volcengine_video_duration(30, SEEDANCE_2_5) == 30
    assert main.volcengine_video_duration(2, SEEDANCE_2_5) == 4


def test_unknown_model_keeps_loose_default():
    assert main.volcengine_video_duration(30, "doubao-seedance-1-0-pro-250528") == 30
    assert main.volcengine_video_duration(90, "") == 60


def test_duration_falls_back_to_five_on_garbage():
    assert main.volcengine_video_duration("abc", SEEDANCE_2_0) == 5
    assert main.volcengine_video_duration(None, SEEDANCE_2_5) == 5


def test_seedance_2_0_supports_4k_but_fast_and_mini_cap_at_720p():
    assert main.volcengine_video_resolution("4k", SEEDANCE_2_0) == "4k"
    assert main.volcengine_video_resolution("1080p", SEEDANCE_2_0) == "1080p"
    # fast / mini 官方只到 720P，选高了降档而不是整单失败
    for model in (SEEDANCE_2_0_FAST, SEEDANCE_2_0_MINI):
        assert main.volcengine_video_resolution("4k", model) == "720p"
        assert main.volcengine_video_resolution("1080p", model) == "720p"
        assert main.volcengine_video_resolution("480p", model) == "480p"
    # 2.5 无 4K
    assert main.volcengine_video_resolution("4k", SEEDANCE_2_5) == "1080p"


def test_resolution_aliases_and_empty():
    assert main.volcengine_video_resolution("720", SEEDANCE_2_0) == "720p"
    assert main.volcengine_video_resolution("2160", SEEDANCE_2_0) == "4k"
    assert main.volcengine_video_resolution("", SEEDANCE_2_0) == ""
    assert main.volcengine_video_resolution("auto", SEEDANCE_2_0) == ""
    assert main.volcengine_video_resolution("hd", SEEDANCE_2_0) == ""


def test_fast_and_mini_not_swallowed_by_seedance_2_0_prefix():
    # 子串匹配下 "seedance-2-0" 也命中 fast/mini，顺序错了就会给它们放开 1080P/4K
    assert main.volcengine_video_limits(SEEDANCE_2_0_FAST)[2] == ("480p", "720p")
    assert main.volcengine_video_limits(SEEDANCE_2_0_MINI)[2] == ("480p", "720p")
    assert "4k" in main.volcengine_video_limits(SEEDANCE_2_0)[2]


def test_defaults_are_exactly_the_four_current_models():
    # 只保留在售的 2.x 四个型号；1.x 老型号已按需求移除，别再被顺手加回来
    assert main.VOLCENGINE_DEFAULT_VIDEO_MODELS == [
        SEEDANCE_2_5,
        SEEDANCE_2_0,
        SEEDANCE_2_0_FAST,
        SEEDANCE_2_0_MINI,
    ]


def test_merge_backfills_new_models_into_existing_config():
    existing = [{
        "id": "volcengine",
        "name": "火山引擎",
        "base_url": main.VOLCENGINE_DEFAULT_BASE_URL,
        "protocol": "volcengine",
        "video_models": [SEEDANCE_2_0, SEEDANCE_2_0_FAST],
    }]
    merged = main.merge_default_api_providers(existing)
    volc = next(item for item in merged if item.get("id") == "volcengine")
    assert SEEDANCE_2_0_MINI in volc["video_models"]
    assert SEEDANCE_2_5 in volc["video_models"]
    # 用户原有条目不能丢
    assert SEEDANCE_2_0_FAST in volc["video_models"]
