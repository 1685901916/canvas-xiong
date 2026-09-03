"""页面按节点保存：只报改过的节点，没报的一律保持服务器版本。

以前页面每次都整份 PUT，它手里几秒前的旧节点会连带写回去，把 agent 或另一个
标签页刚改好的东西盖掉——用户的原话是「改了又被盖回去，很烦人」。
"""
import main


class Req:
    """够用的 CanvasSaveRequest 替身。"""

    def __init__(self, nodes=(), connections=(), dirty=None, removed=()):
        self.nodes = list(nodes)
        self.connections = list(connections)
        self.dirty_node_ids = None if dirty is None else list(dirty)
        self.removed_node_ids = list(removed)


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
    import inspect
    src = inspect.getsource(main.update_canvas)
    assert "payload.dirty_node_ids is None" in src, "没带脏清单的老页面要走原来的整份覆盖"
    assert "merge_protected_canvas_agent_results" in src
