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


def test_html_is_not_silently_cached():
    """canvas.js 的 ?v= 写在 HTML 里；HTML 被浏览器缓存住的话，前端改了用户永远看不到。"""
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        res = client.get("/static/canvas.html")
        assert res.status_code == 200
        assert "no-cache" in res.headers.get("cache-control", ""), "HTML 必须要求回源校验"


def test_atomic_write_retries_on_windows_lock():
    """Windows 上目标文件被短暂占用时 os.replace 抛 WinError 5，
    不重试的话一次保存失败就 500，用户的改动直接丢。"""
    import os as _os

    calls = {"n": 0}
    real_replace = _os.replace

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(5, "拒绝访问")
        return real_replace(src, dst)

    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "c.json")
        _os.replace = flaky
        try:
            main.write_json_atomic(target, {"ok": True})
        finally:
            _os.replace = real_replace
    assert calls["n"] == 3, "前两次被拒后应继续重试"


def test_logs_live_in_a_sidecar_file():
    """日志曾占画布文件的 98%（500 条 3.1MB，节点只有 0.13MB），
    每改一个节点都要整档读写。拆到旁文件后主文件只剩节点和连线。"""
    canvas = main.new_canvas("日志拆分回归(可删)", "🧩", "classic", None, None, None)
    cid = canvas["id"]
    try:
        canvas["logs"] = [{"id": "log_1", "prompt": "x" * 4000}]
        canvas["nodes"] = [{"id": "n1", "type": "prompt", "x": 0, "y": 0, "text": "hi"}]
        main.save_canvas(canvas)

        raw = open(main.canvas_path(cid), encoding="utf-8").read()
        assert "log_1" not in raw, "主文件里不该再有日志"
        assert os.path.isfile(main.canvas_logs_path(cid)), "日志要写到旁文件"

        again = main.load_canvas(cid)
        assert again["logs"][0]["id"] == "log_1", "读回来时日志要接上"
        assert again["nodes"][0]["text"] == "hi"
    finally:
        for p in (main.canvas_path(cid), main.canvas_logs_path(cid)):
            if os.path.isfile(p):
                os.remove(p)


def test_old_canvases_keep_working_without_sidecar():
    """老档的日志还在主文件里，不能因为没有旁文件就把它清空。"""
    canvas = main.new_canvas("老档兼容(可删)", "🧩", "classic", None, None, None)
    cid = canvas["id"]
    try:
        legacy = {"id": cid, "title": "老档", "nodes": [], "connections": [],
                  "logs": [{"id": "old_log"}], "updated_at": 1}
        main.write_json_atomic(main.canvas_path(cid), legacy, indent=2)
        loaded = main.load_canvas(cid)
        assert loaded["logs"][0]["id"] == "old_log"
    finally:
        for p in (main.canvas_path(cid), main.canvas_logs_path(cid)):
            if os.path.isfile(p):
                os.remove(p)


def test_purge_removes_the_log_sidecar():
    canvas = main.new_canvas("彻底删除回归(可删)", "🧩", "classic", None, None, None)
    cid = canvas["id"]
    canvas["logs"] = [{"id": "log_x"}]
    main.save_canvas(canvas)
    assert os.path.isfile(main.canvas_logs_path(cid))

    import asyncio

    asyncio.run(main.purge_canvas(cid))
    assert not os.path.isfile(main.canvas_path(cid))
    assert not os.path.isfile(main.canvas_logs_path(cid)), "旁文件不能留成孤儿"


def test_primitives_do_not_touch_the_log_file():
    """原语只改节点。日志有 7.6MB，每次调用都读写它的话再怎么拆文件也快不起来。"""
    canvas = main.new_canvas("原语不碰日志(可删)", "🧩", "classic", None, None, None)
    cid = canvas["id"]
    try:
        canvas["logs"] = [{"id": "log_keep", "prompt": "x" * 2000}]
        main.save_canvas(canvas)
        side = main.canvas_logs_path(cid)
        stamp = os.stat(side).st_mtime_ns

        main.canvas_prim_commit(cid, lambda c: c["nodes"].append(
            {"id": "n1", "type": "prompt", "x": 0, "y": 0, "text": "hi"}))

        assert os.stat(side).st_mtime_ns == stamp, "原语不该重写日志文件"
        raw = open(main.canvas_path(cid), encoding="utf-8").read()
        assert "log_keep" not in raw and "_logs_detached" not in raw
        again = main.load_canvas(cid)
        assert again["logs"][0]["id"] == "log_keep", "日志不能被原语弄丢"
        assert any(n["id"] == "n1" for n in again["nodes"])
    finally:
        for p in (main.canvas_path(cid), main.canvas_logs_path(cid)):
            if os.path.isfile(p):
                os.remove(p)


def test_unchanged_logs_are_not_rewritten():
    canvas = main.new_canvas("日志不重复写(可删)", "🧩", "classic", None, None, None)
    cid = canvas["id"]
    try:
        canvas["logs"] = [{"id": "a"}]
        main.save_canvas(canvas)
        side = main.canvas_logs_path(cid)
        stamp = os.stat(side).st_mtime_ns

        fresh = main.load_canvas(cid)
        fresh["nodes"].append({"id": "n", "type": "prompt", "x": 0, "y": 0})
        main.save_canvas(fresh)
        assert os.stat(side).st_mtime_ns == stamp, "日志没变就不该重写"

        fresh["logs"].insert(0, {"id": "b"})
        main.save_canvas(fresh)
        assert os.stat(side).st_mtime_ns != stamp, "日志变了必须写"
    finally:
        for p in (main.canvas_path(cid), main.canvas_logs_path(cid)):
            if os.path.isfile(p):
                os.remove(p)


# ---- 第 1 步止血：列表/元数据/保存不再拖着日志跑，打开不升版本 ----

def _scratch_canvas(title):
    return main.new_canvas(title, "🧩", "classic", None, None, None)


def _remove_canvas_files(cid):
    for p in (main.canvas_path(cid), main.canvas_logs_path(cid)):
        if os.path.isfile(p):
            os.remove(p)


def test_canvas_list_skips_log_sidecars_and_junk():
    """日志拆到 <id>.logs.json 后，列表遍历把它当画布 json.load 出来是个 list，
    data.get 直接炸，整个 /api/canvases 500——而页面每次保存后都会拉一次列表。"""
    canvas = _scratch_canvas("列表跳过日志(可删)")
    cid = canvas["id"]
    junk = os.path.join(main.CANVAS_DIR, f"{cid}.junk.json")
    try:
        canvas["logs"] = [{"id": "l1"}]
        main.save_canvas(canvas)
        assert os.path.isfile(main.canvas_logs_path(cid))
        with open(junk, "w", encoding="utf-8") as f:
            f.write("[1, 2, 3]")
        records = main.list_canvases()
        assert [r["id"] for r in records].count(cid) == 1
        assert not main.is_canvas_document_filename(f"{cid}.logs.json")
        assert not main.is_canvas_document_filename(f"{cid}.before-x-1.json")
        assert main.is_canvas_document_filename(f"{cid}.json")
    finally:
        _remove_canvas_files(cid)
        if os.path.isfile(junk):
            os.remove(junk)


def test_canvas_list_record_cache_follows_file_changes():
    canvas = _scratch_canvas("列表缓存(可删)")
    cid = canvas["id"]
    try:
        first = next(r for r in main.list_canvases() if r["id"] == cid)
        assert first["node_count"] == 0
        canvas["nodes"].append({"id": "n", "type": "prompt", "x": 0, "y": 0})
        main.save_canvas(canvas)
        second = next(r for r in main.list_canvases() if r["id"] == cid)
        assert second["node_count"] == 1, "文件变了，缓存必须失效"
    finally:
        _remove_canvas_files(cid)
    assert all(r["id"] != cid for r in main.list_canvases()), "文件删了缓存也得跟着清"


def test_touch_records_open_without_bumping_version():
    """打开画布不再刷新 updated_at：否则别的标签页每次都整份重拉重绘、没存完的改动撞 409。"""
    canvas = _scratch_canvas("touch不升版本(可删)")
    cid = canvas["id"]
    try:
        before = main.load_canvas(cid)["updated_at"]
        touched = main.touch_canvas_opened(cid)
        after = main.load_canvas(cid)
        assert after["updated_at"] == before
        assert after["opened_at"] >= before and touched["opened_at"] == after["opened_at"]
        record = main.canvas_record(after)
        assert record["last_active_at"] == after["opened_at"], "列表按最近活动排，打开也算活动"
        raw = open(main.canvas_path(cid), encoding="utf-8").read()
        assert '"logs"' not in raw and "_logs" not in raw, "本体文件不能混进日志或内部字段"
    finally:
        _remove_canvas_files(cid)


def test_meta_update_does_not_inline_logs_into_body():
    """改标题/置顶直接写本体。日志拆出去后，这里要是把 load 进来的日志一起写回本体，
    等于把拆分撤销了，还会带上 _logs_fp 这类内部字段。"""
    from fastapi.testclient import TestClient

    canvas = _scratch_canvas("meta不带日志(可删)")
    cid = canvas["id"]
    try:
        canvas["logs"] = [{"id": "keep_me"}]
        main.save_canvas(canvas)
        with TestClient(main.app) as client:
            res = client.post(f"/api/canvases/{cid}/meta", json={"title": "新标题"})
            assert res.status_code == 200, res.text
        raw = open(main.canvas_path(cid), encoding="utf-8").read()
        assert "keep_me" not in raw and "_logs_fp" not in raw
        assert main.load_canvas(cid)["logs"][0]["id"] == "keep_me"
    finally:
        _remove_canvas_files(cid)


def test_save_round_trip_returns_no_logs_and_merges_log_delta():
    """页面 PUT 只带新增的日志，回包不带日志：3MB 的日志不该跟着每次自动保存来回跑。"""
    from fastapi.testclient import TestClient

    canvas = _scratch_canvas("保存不带日志(可删)")
    cid = canvas["id"]
    try:
        canvas["logs"] = [{"id": "old", "createdAt": 1}]
        main.save_canvas(canvas)
        base = main.load_canvas(cid)
        body = {
            "title": base["title"], "icon": base["icon"],
            "nodes": [{"id": "n1", "type": "prompt", "x": 0, "y": 0, "text": "hi"}],
            "connections": [], "viewport": {"x": 0, "y": 0, "scale": 1},
            "logs": [{"id": "new", "createdAt": 2}],
            "client_id": "test", "base_updated_at": base["updated_at"],
        }
        with TestClient(main.app) as client:
            res = client.put(f"/api/canvases/{cid}", json=body)
            assert res.status_code == 200, res.text
            assert "logs" not in res.json()["canvas"]
            assert "logs" not in client.get(f"/api/canvases/{cid}?logs=0").json()["canvas"]
            assert "logs" in client.get(f"/api/canvases/{cid}").json()["canvas"], "打开画布仍要拿到日志"
            assert client.get(f"/api/canvases/{cid}/meta").json()["updated_at"] > base["updated_at"]
            # 没有新日志的保存：不读也不写日志文件
            stamp = os.stat(main.canvas_logs_path(cid)).st_mtime_ns
            body["logs"] = []
            body["base_updated_at"] = main.load_canvas(cid)["updated_at"]
            assert client.put(f"/api/canvases/{cid}", json=body).status_code == 200
            assert os.stat(main.canvas_logs_path(cid)).st_mtime_ns == stamp
        stored = main.load_canvas(cid)
        assert [l["id"] for l in stored["logs"]] == ["new", "old"], "新增日志要并进服务器那份"
        assert any(n["id"] == "n1" for n in stored["nodes"])
    finally:
        _remove_canvas_files(cid)
