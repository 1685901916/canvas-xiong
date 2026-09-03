"""MiniMax 官方视频改成异步提交 + 轮询。

上游本来就是异步的（提交返回 task_id，另有查询接口），但服务端原先把两步塞进
一个长请求，task_id 直到出片才随响应返回。连接一断就什么都不剩：任务查不到、
恢复不了，而上游照样在跑、照样计费。
"""
from pathlib import Path
import inspect

import main


def test_submit_and_query_are_separate_functions():
    assert inspect.iscoroutinefunction(main.submit_minimax_video)
    assert inspect.iscoroutinefunction(main.query_minimax_video_once)
    assert inspect.iscoroutinefunction(main.prepare_minimax_video_request)


def test_submit_does_not_wait_for_generation():
    """提交函数里不能出现等待逻辑，否则又变回同步长请求。"""
    src = inspect.getsource(main.submit_minimax_video)
    assert "wait_minimax_video" not in src, "提交阶段不能等生成完成"
    assert "task_id" in src


def test_query_is_single_shot():
    """查询是单次的：轮询节奏交给前端，服务端不要自己 sleep 循环。"""
    src = inspect.getsource(main.query_minimax_video_once)
    assert "while" not in src, "查询接口不能内建轮询循环"
    assert "asyncio.sleep" not in src


def test_query_normalises_status():
    src = inspect.getsource(main.query_minimax_video_once)
    for token in ('"SUCCESS"', '"FAILED"', '"RUNNING"', '"QUEUED"'):
        assert token in src, f"缺少状态 {token}"


def test_sync_version_kept_for_fallback():
    """旧的同步实现要保留，出问题可以回退到 /api/canvas-video。"""
    src = inspect.getsource(main.generate_minimax_video)
    assert "submit_minimax_video" in src, "同步版应复用提交函数，不要再抄一份"
    assert "wait_minimax_video" in src


def test_routes_exist():
    paths = {r.path for r in main.app.routes if hasattr(r, "path")}
    assert "/api/minimax/video-submit" in paths
    assert "/api/minimax/tasks/{task_id}" in paths
    assert "/api/canvas-video" in paths, "同步接口要保留以便回退"


def test_task_id_validation_rejects_path_traversal():
    src = Path(main.__file__).read_text(encoding="utf-8")
    assert 'r"[A-Za-z0-9_.:-]{1,200}"' in src, "task_id 必须做格式校验"
