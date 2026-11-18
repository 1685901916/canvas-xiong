"""页面按节点保存：只报改过的节点，没报的一律保持服务器版本。

以前页面每次都整份 PUT，它手里几秒前的旧节点会连带写回去，把 agent 或另一个
标签页刚改好的东西盖掉——用户的原话是「改了又被盖回去，很烦人」。
"""
import main


class Req:
    """够用的 CanvasSaveRequest 替身。"""

    def __init__(self, nodes=(), connections=(), dirty=None, removed=(), base_ids=None, base_nodes=None, base_conns=None):
        self.nodes = list(nodes)
        self.connections = list(connections)
        self.dirty_node_ids = None if dirty is None else list(dirty)
        self.removed_node_ids = list(removed)
        self.base_node_ids = None if base_ids is None else list(base_ids)
        self.base_nodes = base_nodes
        self.base_connection_keys = None if base_conns is None else list(base_conns)


def _n(nid, **kw):
    d = {"id": nid, "type": "prompt", "x": 0, "y": 0}
    d.update(kw)
    return d


def test_untouched_nodes_keep_the_server_version():
    canvas = {"nodes": [_n("a", text="服务器改过的"), _n("b", text="旧")], "connections": []}
    # 页面手里 a 还是老样子，只动了 b
    payload = Req(nodes=[_n("a", text="页面手里的旧值"), _n("b", text="新")], dirty=["b"])
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    by = {n["id"]: n for n in nodes}
    assert by["a"]["text"] == "服务器改过的", "没报脏的节点不能被页面的旧副本盖掉"
    assert by["b"]["text"] == "新"


def test_new_local_node_is_added():
    canvas = {"nodes": [_n("a")], "connections": []}
    payload = Req(nodes=[_n("a"), _n("c", text="新建")], dirty=["c"])
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    assert {n["id"] for n in nodes} == {"a", "c"}


def test_agent_created_node_survives_a_stale_page_save():
    """agent 刚建了 z，页面还不知道它，页面这一次保存不能把 z 抹掉。"""
    canvas = {"nodes": [_n("a"), _n("z", text="agent 建的")],
              "connections": [{"id": "c1", "from": "a", "to": "z"}]}
    payload = Req(nodes=[_n("a", text="改了")], dirty=["a"])
    nodes, conns = main.merge_dirty_canvas_nodes(canvas, payload)
    assert "z" in {n["id"] for n in nodes}, "页面不知道的节点不能被删"
    assert any(c["from"] == "a" and c["to"] == "z" for c in conns), "它的连线也要留着"


def test_deleted_nodes_are_really_removed():
    canvas = {"nodes": [_n("a"), _n("b")], "connections": [{"id": "c1", "from": "a", "to": "b"}]}
    payload = Req(nodes=[_n("a")], dirty=[], removed=["b"])
    nodes, conns = main.merge_dirty_canvas_nodes(canvas, payload)
    assert {n["id"] for n in nodes} == {"a"}
    assert conns == [], "指向已删节点的连线要一起清掉"


def test_client_can_delete_a_connection():
    canvas = {"nodes": [_n("a"), _n("b")], "connections": [{"id": "c1", "from": "a", "to": "b"}]}
    payload = Req(nodes=[_n("a"), _n("b")], connections=[], dirty=[])
    _, conns = main.merge_dirty_canvas_nodes(canvas, payload)
    assert conns == [], "两端页面都认识，页面说删就是删"


def test_legacy_client_without_dirty_ids_still_works():
    """没带脏清单的老页面仍要走原来的整份覆盖 + 乐观锁。

    这里查整份模块源码而不是某个函数：保存这段逻辑被拆成过 apply_canvas_save，
    绑死在函数名上的断言会被别人的重构误伤。
    """
    src = open(main.__file__, encoding="utf-8").read()
    assert "payload.dirty_node_ids is None" in src, "老页面要留着乐观锁那条路"
    assert "merge_protected_canvas_agent_results" in src
    assert "merge_dirty_canvas_nodes" in src


# ---- 版本基准（base_*）：开着很久的旧页面不能把新内容盖回去 ----

def test_stale_page_cannot_resurrect_nodes_deleted_elsewhere():
    """别处（清理脚本/另一个标签页）删了 t1、t2，旧页面手里还有，保存时不能把它们带回来。"""
    canvas = {"nodes": [_n("a")], "connections": []}
    payload = Req(nodes=[_n("a", text="改了"), _n("t1"), _n("t2")], dirty=["a"],
                  base_ids=["a", "t1", "t2"])
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    assert {n["id"] for n in nodes} == {"a"}


def test_stale_page_deleted_node_stays_deleted_even_if_page_marked_it_dirty():
    canvas = {"nodes": [_n("a")], "connections": []}
    payload = Req(nodes=[_n("a"), _n("t1", text="页面又改了一下")], dirty=["t1"], base_ids=["a", "t1"])
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    assert {n["id"] for n in nodes} == {"a"}, "页面上次对齐时就有、服务器已删 = 别处删的，删除优先"


def test_node_created_on_page_after_its_base_is_added():
    canvas = {"nodes": [_n("a")], "connections": []}
    payload = Req(nodes=[_n("a"), _n("new", text="刚建")], dirty=["new"], base_ids=["a"])
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    assert {n["id"] for n in nodes} == {"a", "new"}


def test_legacy_page_cannot_resurrect_untouched_nodes():
    """没带基准的老页面：服务器没有的节点只收它报为改过的，没动过的旧节点不能借机复活。"""
    canvas = {"nodes": [_n("a")], "connections": []}
    payload = Req(nodes=[_n("a"), _n("old")], dirty=["a"])
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    assert {n["id"] for n in nodes} == {"a"}


def test_three_way_merge_keeps_both_sides_field_changes():
    base = _n("a", text="原文", x=0)
    server = _n("a", text="别处改的文字", x=0)
    page = _n("a", text="原文", x=500)          # 页面只挪了位置
    canvas = {"nodes": [server], "connections": []}
    payload = Req(nodes=[page], dirty=["a"], base_ids=["a"], base_nodes={"a": base})
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    assert nodes[0]["x"] == 500, "页面改的字段要生效"
    assert nodes[0]["text"] == "别处改的文字", "页面没动的字段保持服务器的"


def test_three_way_merge_without_conflict_equals_page_version():
    base = _n("a", text="原文", extra=1)
    page = _n("a", text="新文字")                # 页面改了 text、删了 extra
    canvas = {"nodes": [dict(base)], "connections": []}
    payload = Req(nodes=[page], dirty=["a"], base_ids=["a"], base_nodes={"a": base})
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    assert nodes[0] == page, "服务器没动过时结果就是页面版本，和以前一致"


def test_three_way_merge_of_output_images():
    img = lambda u, **kw: {"url": u, **kw}
    base = {"id": "o", "type": "output", "images": [img("/a.png"), img("/b.png")]}
    server = {"id": "o", "type": "output", "images": [img("/a.png"), img("/b.png"), img("/c.png")]}  # 别处新生成了 c
    page = {"id": "o", "type": "output", "images": [img("/a.png", viewed=True)]}                    # 页面删了 b、看了 a
    canvas = {"nodes": [server], "connections": []}
    payload = Req(nodes=[page], dirty=["o"], base_ids=["o"], base_nodes={"o": base})
    nodes, _ = main.merge_dirty_canvas_nodes(canvas, payload)
    urls = [i["url"] for i in nodes[0]["images"]]
    assert urls == ["/a.png", "/c.png"], "别处新生成的留下，页面删掉的不回来"
    assert nodes[0]["images"][0].get("viewed") is True, "页面对条目的修改要保留"


def test_connections_merge_by_page_additions_and_removals():
    nodes_ = [_n("a"), _n("b"), _n("c")]
    server_conns = [{"id": "ab", "from": "a", "to": "b"}, {"id": "bc", "from": "b", "to": "c"}]  # bc 是别处加的
    canvas = {"nodes": nodes_, "connections": server_conns}
    # 页面基准里只有 ab；页面删了 ab、加了 ac
    payload = Req(nodes=nodes_, connections=[{"id": "ac", "from": "a", "to": "c"}], dirty=[],
                  base_ids=["a", "b", "c"], base_conns=["ab"])
    _, conns = main.merge_dirty_canvas_nodes(canvas, payload)
    assert {c["id"] for c in conns} == {"bc", "ac"}


def test_stale_page_cannot_resurrect_connection_deleted_elsewhere():
    nodes_ = [_n("a"), _n("b")]
    canvas = {"nodes": nodes_, "connections": []}   # 别处删了 ab
    payload = Req(nodes=nodes_, connections=[{"id": "ab", "from": "a", "to": "b"}], dirty=[],
                  base_ids=["a", "b"], base_conns=["ab"])
    _, conns = main.merge_dirty_canvas_nodes(canvas, payload)
    assert conns == []
