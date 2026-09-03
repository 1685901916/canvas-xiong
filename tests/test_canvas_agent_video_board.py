import main
from tools import canvasctl


def test_compose_video_board_builds_visible_runnable_lane():
    canvas = {
        "id": "test-canvas",
        "title": "测试画布",
        "nodes": [],
        "connections": [],
        "logs": [],
    }
    payload = main.CanvasAgentCommand(
        action="compose_video_board",
        title="两个人做柠檬汁",
        prompt="三张图片只作弱参考，由视频模型补全连续动作。",
        images=[
            {"url": "/assets/input/ref-1.png", "name": "开场参考"},
            {"url": "/assets/input/ref-2.png", "name": "过程参考"},
            {"url": "/assets/input/ref-3.png", "name": "结尾参考"},
        ],
        provider_id="volcengine",
        model="doubao-seedance-2-0-260128",
        duration=15,
        aspect_ratio="9:16",
        resolution="720p",
        generate_audio=True,
        multimodal=True,
    )

    result = main.agent_compose_video_board(canvas, payload)

    assert len(result["group_ids"]) == 1
    assert len(result["prompt_ids"]) == 1
    assert len(result["video_ids"]) == 1
    assert len(result["output_ids"]) == 1
    by_id = {node["id"]: node for node in canvas["nodes"]}
    group = by_id[result["group_ids"][0]]
    video = by_id[result["video_ids"][0]]
    output = by_id[result["output_ids"][0]]
    assert len(group["items"]) == 4
    assert video["apiProvider"] == "volcengine"
    assert video["model"] == "doubao-seedance-2-0-260128"
    assert video["duration"] == 15
    assert video["aspectRatio"] == "9:16"
    assert video["resolution"] == "720p"
    assert video["generateAudio"] is True
    assert video["multimodal"] is True
    assert video["useFrameRoles"] is False
    assert len(video["inputs"]) == 4
    assert output["w"] == 760 and output["h"] == 680
    assert {connection["from"] for connection in canvas["connections"]} == {group["id"], video["id"]}


def test_compose_video_cli_defaults_to_safe_structure_only_seedance_lane():
    args = canvasctl.build_parser().parse_args([
        "compose-video",
        "--canvas",
        "canvas-id",
        "--prompt",
        "test",
    ])

    assert args.provider == "volcengine"
    assert args.model == "doubao-seedance-2-0-260128"
    assert args.duration == 15
    assert args.ratio == "9:16"
    assert args.resolution == "720p"
    assert args.audio is True
    assert args.first_last_frames is False
    assert not hasattr(args, "run")
