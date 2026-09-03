"""画布节点级原语（给 AI 用）。

以前 agent 只有 4 个固定宏，套路之外只能 GET 整画布 → 改 → PUT 整画布，
每次都让页面全量重绘并和自己的保存打架。原语只改被触及的节点。
"""
import os
import tempfile

import pytest
from fastapi import HTTPException

import main


def _node(nid, ntype, **kw):
    d = {"id": nid, "type": ntype, "x": 0, "y": 0}
    d.update(kw)
    return d


def test_build_video_node_mirrors_frontend_factory():
    node = main.canvas_prim_build_node([], main.CanvasNodeCreate(type="video"))
    assert node["id"].startswith("vid_")
    assert node["multimodal"] is True, "与前端一致：默认开全能参考"
    assert node["useFrameRoles"] is False
    assert node["duration"] == 10 and node["aspectRatio"] == "9:16" and node["resolution"] == "720p"
    assert node["inputs"] == [] and node["running"] is False


def test_frame_roles_and_multimodal_are_mutually_exclusive():
    node = main.canvas_prim_build_node([], main.CanvasNodeCreate(type="video", useFrameRoles=True))
    assert node["useFrameRoles"] is True and node["multimodal"] is False


def test_unsupported_type_is_rejected_with_hint():
    with pytest.raises(HTTPException) as ctx:
        main.canvas_prim_build_node([], main.CanvasNodeCreate(type="llm"))
    assert ctx.value.status_code == 400
    assert "video" in str(ctx.value.detail), "报错要列出可用类型"


def test_default_point_avoids_overlap():
    existing = [_node("a", "image", x=100, y=50)]
    node = main.canvas_prim_build_node(existing, main.CanvasNodeCreate(type="prompt"))
    assert node["x"] > 100 + 260, "没给坐标时应放到现有节点右侧"


def test_connection_rules_mirror_frontend():
    nodes = [_node("img", "image"), _node("p", "prompt"), _node("vid", "video"),
             _node("out", "output"), _node("gen", "generator"), _node("grp", "group")]

    def can(a, b, conns=()):
        return main.canvas_prim_can_connect(nodes, list(conns), a, b)

    assert can("img", "vid") and can("p", "vid") and can("grp", "vid")
    assert can("vid", "out"), "生成器 → 输出"
    assert can("out", "vid"), "输出可以作为生成器的输入"
    assert can("gen", "vid"), "图片生成器可以喂给视频生成器"
    assert not can("vid", "img"), "生成器不能连到图片节点"
    assert not can("img", "img") and not can("img", "out")
    assert not can("vid", "vid")


def test_cycle_between_generators_is_refused():
    nodes = [_node("g1", "generator"), _node("g2", "video")]
    conns = [{"id": "c1", "from": "g1", "to": "g2"}]
    assert not main.canvas_prim_can_connect(nodes, conns, "g2", "g1"), "g1→g2 已存在，再连 g2→g1 会成环"


def test_group_handoff_rewires_member_connections():
    nodes = [_node("img", "image"), _node("p", "prompt"), _node("vid", "video")]
    conns = [{"id": "c1", "from": "img", "to": "vid"}, {"id": "c2", "from": "p", "to": "vid"}]
    group = _node("grp", "group", w=300, h=220, items=["img", "p"])
    nodes.append(group)
    merged = main.canvas_prim_group_handoff(nodes, conns, group, ["img", "p"])
    assert not any(c["from"] in {"img", "p"} for c in merged), "成员到生成器的线要被收走"
    assert any(c["from"] == "grp" and c["to"] == "vid" for c in merged), "改成组 → 生成器"
    assert sum(1 for c in merged if c["from"] == "grp" and c["to"] == "vid") == 1, "不重复建线"


def test_group_layout_encloses_members():
    nodes = [_node("a", "image", x=100, y=100), _node("b", "prompt", x=500, y=300)]
    group = _node("grp", "group")
    main.canvas_prim_layout_group(nodes, group, ["a", "b"])
    assert group["x"] < 100 and group["y"] < 100
    assert group["x"] + group["w"] > 500 + 310 and group["y"] + group["h"] > 300 + 160


def test_import_local_video_copies_into_assets_input():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "clip.mp4")
        with open(src, "wb") as f:
            f.write(b"\x00" * 64)
        info = main.import_local_media_file(src)
        local = main.output_file_from_url(info["url"])
        try:
            assert info["kind"] == "video"
            assert info["url"].startswith("/assets/input/")
            assert info["name"] == "clip.mp4"
            assert local and os.path.isfile(local)
        finally:
            if local and os.path.isfile(local):
                os.remove(local)


def test_import_rejects_unknown_extension():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "x.exe")
        with open(src, "wb") as f:
            f.write(b"x")
        with pytest.raises(HTTPException) as ctx:
            main.import_local_media_file(src)
        assert ctx.value.status_code == 400


def test_resolve_media_accepts_asset_url_and_marks_kind():
    info = main.canvas_prim_resolve_media(url="/assets/input/a.mp4")
    assert info["kind"] == "video" and info["url"] == "/assets/input/a.mp4"
    info = main.canvas_prim_resolve_media(url="/assets/input/a.png", name="ref")
    assert info["kind"] == "image" and info["name"] == "ref"
    with pytest.raises(HTTPException):
        main.canvas_prim_resolve_media(url="ftp://nope/a.png")
    with pytest.raises(HTTPException):
        main.canvas_prim_resolve_media()


def test_primitive_routes_exist():
    paths = {r.path for r in main.app.routes if hasattr(r, "path")}
    for p in ("/api/canvases/{canvas_id}/nodes",
              "/api/canvases/{canvas_id}/nodes/{node_id}",
              "/api/canvases/{canvas_id}/nodes/{node_id}/media",
              "/api/canvases/{canvas_id}/connections",
              "/api/canvases/{canvas_id}/connections/{connection_id}",
              "/api/canvases/{canvas_id}/groups"):
        assert p in paths, f"缺少原语路由 {p}"


def test_manager_can_broadcast_patch():
    assert callable(getattr(main.manager, "broadcast_canvas_patch", None))


def test_commit_round_trip_does_not_deadlock():
    """save_canvas → write_json_atomic 内部也拿 CANVAS_LOCK；原语整段持锁，锁必须可重入。
    第一次联调时这里死锁把整个服务卡死了。"""
    import threading

    canvas = main.new_canvas("原语死锁回归(可删)", "🧩", "classic", None, None, None)
    cid = canvas["id"]
    done = {}

    def run():
        try:
            main.canvas_prim_commit(cid, lambda c: {"nodes": [], "n": len(c["nodes"])})
            done["ok"] = True
        except Exception as exc:  # pragma: no cover - 只为把异常带回主线程
            done["err"] = exc

    t = threading.Thread(target=run, daemon=True)
    try:
        t.start()
        t.join(timeout=5)
        assert not t.is_alive(), "canvas_prim_commit 5 秒没返回：锁不可重入，死锁"
        assert done.get("ok"), done.get("err")
    finally:
        p = main.canvas_path(cid)
        if os.path.isfile(p):
            os.remove(p)


def test_node_sizes_match_measured_defaults():
    """组框按这张表算包围盒；量小了成员会被裁掉（G9 的提示词就露在框外 46px）。
    数值是在真实画布上量未被手动调整过的节点得到的。"""
    sizes = main.CANVAS_PRIM_NODE_SIZES
    assert sizes["image"] == (260, 336)
    assert sizes["prompt"] == (310, 238), "提示词节点 textarea 固定 140px，整块 238px，不随文字变高"
    for kind in ("video", "output", "generator"):
        assert sizes[kind][1] >= 488, f"{kind} 高度不能再按旧的估值"


def test_group_box_encloses_a_prompt_member():
    nodes = [_node("img", "image", x=100, y=100), _node("p", "prompt", x=100, y=460)]
    group = _node("grp", "group")
    main.canvas_prim_layout_group(nodes, group, ["img", "p"])
    assert group["y"] + group["h"] >= 460 + 238, "组框底边必须盖住提示词节点"
    assert group["x"] + group["w"] >= 100 + 310
