"""板子重排：手动删过或拖乱过节点之后，把组收拾整齐。

删掉一个占位图之后组里会留一个洞、组框也不再贴合，用户看到的就是「图没放上」。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import board


TPL = board.SIZES["big"]


def _m(nid, ntype, x, y, w=None, h=None):
    d = {"id": nid, "type": ntype, "x": x, "y": y}
    if w:
        d["w"] = w
    if h:
        d["h"] = h
    return d


def test_gap_left_by_a_deleted_node_is_closed():
    # 中间那张图被删了，提示词还停在原来的位置，组里空出一大块
    members = [_m("img", "image", 214, 100), _m("p", "prompt", 1094, 100)]
    placed, box = board.row_layout(members, TPL)
    by = {p["id"]: p for p in placed}
    assert by["p"]["x"] == by["img"]["x"] + TPL["image"][0] + TPL["gap"], "提示词要紧跟在图后面"
    assert box["w"] < 1200, "组框跟着收窄，不再框着一片空白"


def test_images_come_first_in_their_current_order():
    members = [_m("p", "prompt", 0, 0), _m("b", "image", 700, 0), _m("a", "image", 200, 0)]
    placed, _ = board.row_layout(members, TPL)
    assert [p["id"] for p in placed] == ["a", "b", "p"], "图片按原来的左右顺序排在前面"


def test_sizes_are_normalized_to_the_template():
    members = [_m("img", "image", 0, 0, w=360, h=560), _m("p", "prompt", 500, 0, w=375, h=238)]
    placed, _ = board.row_layout(members, TPL)
    by = {p["id"]: p for p in placed}
    assert (by["img"]["w"], by["img"]["h"]) == TPL["image"]
    assert (by["p"]["w"], by["p"]["h"]) == TPL["prompt"]


def test_box_encloses_every_member_with_template_padding():
    members = [_m("a", "image", 0, 0), _m("b", "image", 400, 0), _m("p", "prompt", 900, 0)]
    placed, box = board.row_layout(members, TPL)
    pad_l, pad_t, pad_r, pad_b = TPL["pad"]
    right = max(p["x"] + p["w"] for p in placed)
    bottom = max(p["y"] + p["h"] for p in placed)
    assert box["x"] == placed[0]["x"] - pad_l
    assert box["x"] + box["w"] == right + pad_r
    assert box["y"] + box["h"] == bottom + pad_b


def test_members_are_top_aligned():
    members = [_m("a", "image", 0, 40), _m("p", "prompt", 400, 300)]
    placed, _ = board.row_layout(members, TPL)
    assert len({p["y"] for p in placed}) == 1, "一行里成员顶端对齐"


def test_origin_can_be_pinned():
    members = [_m("a", "image", 999, 999)]
    placed, box = board.row_layout(members, TPL, origin=(10, 20))
    assert (placed[0]["x"], placed[0]["y"]) == (10, 20)
    assert box["x"] == 10 - TPL["pad"][0]


def test_empty_group_is_a_no_op():
    assert board.row_layout([], TPL) == ([], None)
