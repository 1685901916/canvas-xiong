#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一条命令在画布上建一块「参考图 + 提示词 → 视频生成」的板子。

以前是手写一串 HTTP 调用，坐标和组框全靠现算，改一次尺寸要来回好几轮。
现在布局常量集中在这里（数值是在真实画布上量的），加素材、改文案都只动参数。

例：
  python tools/board.py --canvas <画布id> \
      --image /assets/output/a.png \
      --prompt-file prompt.txt \
      --model volcengine:doubao-seedance-2-0-260128 \
      --mode first-frame --audio

  # 三张参考图、全能参考
  python tools/board.py --canvas <id> --image a.png --image b.png --image c.png \
      --prompt-file p.txt --mode multimodal

--image 可以是画布里的 /assets/... 路径，也可以是本机文件（自动拷进素材库）。
默认不会开跑，要跑到页面上点「视频生成」。
"""
import argparse
import json
import os
import sys
import time
import urllib.request as u

BASE = os.environ.get("CANVAS_BASE", "http://127.0.0.1:3001")

# 以下数值都是在真实画布上量出来的渲染尺寸，不要凭感觉改。
#   big   照 G5/G6：成员排一行、顶端对齐，提示词比图片高一截
#   small 节点未被手动拖过时的默认尺寸
# 尺寸量小了组框会把成员裁掉，量大了中间留一片空白。
#
# 组框头部（标题 42 + 提示行 + 「已成组」行 + 「设为对话目标」按钮）实测占 134px。
# 上边距小于它，成员就压在那个蓝色按钮上——画布上 12 个组原本无一幸免，包括手动
# 框选出来的。canvas.js 的 GROUP_HEADER_H 和 main.py 的 CANVAS_GROUP_HEADER_H
# 是同一个数，改一处就要改另两处。
GROUP_HEADER_H = 170
GROUP_PAD = (100, GROUP_HEADER_H, 100, 110)   # 左 上 右 下

SIZES = {
    "big":   {"image": (300, 533), "prompt": (400, 640), "gap": 140,
              "pad": GROUP_PAD},
    "small": {"image": (260, 336), "prompt": (310, 238), "gap": 40,
              "pad": GROUP_PAD},
}
VIDEO_DX, VIDEO_DY = 120, 40   # 生成器节点相对成员行右端的偏移
# 组能连到的生成器类型；重排组之后这些节点要跟着右移，别被组压住
GENERATOR_TYPES = {"video", "generator", "msgen", "comfy", "ltxDirector", "rh", "realesrgan", "llm"}


def call(method, path, body=None, timeout=60):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = u.Request(BASE + path, data=data, method=method,
                    headers={"Content-Type": "application/json"})
    try:
        with u.urlopen(req, timeout=timeout) as res:
            return json.load(res)
    except u.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit("%s %s -> %s %s" % (method, path, exc.code, detail))


def normalize_source(src):
    """判断这张图是画布里的资源还是本机文件，返回 ("url"|"path", 值)。

    Git Bash 会把 /assets/output/x.png 这种参数改写成 C:/Program Files/Git/assets/...，
    所以不能只看开头，得把 /assets/ 之后的部分捞回来。
    """
    s = str(src).replace("\\", "/")
    if s.startswith(("http://", "https://")):
        return "url", s
    for marker in ("/assets/output/", "/assets/input/", "/assets/uploads/"):
        idx = s.find(marker)
        if idx >= 0:
            return "url", s[idx:]
    if s.startswith("/assets/"):
        return "url", s
    return "path", str(src)


def row_layout(members, tpl, origin=None):
    """把组成员排成一行并算出组框。图片按当前 x 排序在前，提示词在后。

    返回 (放好的成员列表, 组框)。成员是 {"id","type","x","y","w","h"}。
    手动删过节点之后组里会留一个洞、组框也不再贴合，这个函数负责收拢。
    """
    iw, ih = tpl["image"]
    pw, ph = tpl["prompt"]
    gap = tpl["gap"]
    pad_l, pad_t, pad_r, pad_b = tpl["pad"]

    images = sorted([m for m in members if m.get("type") == "image"],
                    key=lambda m: (float(m.get("x") or 0), str(m.get("id"))))
    others = [m for m in members if m.get("type") != "image"]
    ordered = images + others
    if not ordered:
        return [], None

    x0 = float(origin[0]) if origin else min(float(m.get("x") or 0) for m in ordered)
    y0 = float(origin[1]) if origin else min(float(m.get("y") or 0) for m in ordered)

    placed = []
    cursor = x0
    for m in ordered:
        w, h = (iw, ih) if m.get("type") == "image" else (pw, ph)
        placed.append({"id": m.get("id"), "type": m.get("type"),
                       "x": cursor, "y": y0, "w": w, "h": h})
        cursor += w + gap

    right = max(p["x"] + p["w"] for p in placed)
    bottom = max(p["y"] + p["h"] for p in placed)
    box = {"x": x0 - pad_l, "y": y0 - pad_t,
           "w": (right - x0) + pad_l + pad_r, "h": (bottom - y0) + pad_t + pad_b}
    return placed, box


def do_relayout(args, tpl):
    """把一个已有的组重新排齐：成员排成一行、尺寸归位、组框重新贴合。"""
    P = "/api/canvases/%s" % args.canvas
    doc = call("GET", P)
    body = doc.get("canvas") or doc
    by_id = {str(n.get("id")): n for n in body.get("nodes") or []}
    group = by_id.get(args.relayout)
    if not group or group.get("type") != "group":
        raise SystemExit("找不到组 %s" % args.relayout)
    members = [by_id[m] for m in (group.get("items") or []) if m in by_id]
    if not members:
        raise SystemExit("这个组里没有成员")

    origin = None
    if args.at:
        origin = [float(v) for v in args.at.split(",")]
    placed, box = row_layout(members, tpl, origin)

    t = time.perf_counter()
    for p in placed:
        call("PATCH", P + "/nodes/" + p["id"],
             {"fields": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"]}})
    call("PATCH", P + "/nodes/" + group["id"], {"fields": box})

    # 组变宽之后，连出去的生成器节点必须跟着右移，否则会被组里的提示词压住。
    # 只排组内成员是不够的——这一步漏了，板子看着就是「节点没搞好」。
    moved = []
    right = box["x"] + box["w"]
    for conn in body.get("connections") or []:
        if str(conn.get("from")) != group["id"]:
            continue
        target = by_id.get(str(conn.get("to")))
        if not target or target.get("type") not in GENERATOR_TYPES:
            continue
        nx = right + VIDEO_DX
        ny = box["y"] + tpl["pad"][1]
        if abs(float(target.get("x") or 0) - nx) > 1 or abs(float(target.get("y") or 0) - ny) > 1:
            call("PATCH", P + "/nodes/" + target["id"], {"fields": {"x": nx, "y": ny}})
            moved.append((target["type"], nx, ny))
    ms = (time.perf_counter() - t) * 1000

    print("组 %s 已排齐，%d 个成员，%.0f ms" % (args.relayout[:14], len(placed), ms))
    for p in placed:
        print("  %-7s (%.0f, %.0f) %dx%d" % (p["type"], p["x"], p["y"], p["w"], p["h"]))
    print("组框 (%.0f, %.0f) %.0fx%.0f  间距 %d  边距 左%d 上%d 右%d 下%d"
          % (box["x"], box["y"], box["w"], box["h"], tpl["gap"], *tpl["pad"]))
    for kind, nx, ny in moved:
        print("  跟着右移 %-7s -> (%.0f, %.0f)" % (kind, nx, ny))
    return 0


def read_prompt(args):
    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as f:
            return f.read().strip()
    return (args.prompt or "").strip()


def place(canvas_id, args):
    """算出这块板子放哪儿：默认放在现有内容下方，不跟别人叠。"""
    if args.at:
        x, y = [float(v) for v in args.at.split(",")]
        return x, y
    doc = call("GET", "/api/canvases/%s" % canvas_id)
    nodes = (doc.get("canvas") or doc).get("nodes") or []
    if not nodes:
        return 0.0, 0.0
    left = min(float(n.get("x") or 0) for n in nodes)
    bottom = max(float(n.get("y") or 0) + float(n.get("h") or 336) for n in nodes)
    return left, bottom + 160


def main():
    p = argparse.ArgumentParser(description="在画布上建一块视频生成板")
    p.add_argument("--canvas", required=True, help="画布 id")
    p.add_argument("--image", action="append", default=[], metavar="路径",
                   help="参考图，可重复；/assets/... 或本机文件")
    p.add_argument("--image-name", action="append", default=[], metavar="名字",
                   help="对应 --image 的显示名，可省略")
    p.add_argument("--blank-image", action="append", default=[], metavar="占位名",
                   help="建一个空的图片节点占位，可重复；素材还没出来时先把板子搭好，"
                        "之后往节点上拖文件，或用 /nodes/<id>/media 接口挂上去")
    p.add_argument("--prompt", default="", help="提示词正文")
    p.add_argument("--prompt-file", help="从文件读提示词（长文案用这个，省得被 shell 转义坑）")
    p.add_argument("--model", default="volcengine:doubao-seedance-2-0-260128",
                   metavar="厂商:模型", help="默认 volcengine:doubao-seedance-2-0-260128")
    p.add_argument("--mode", choices=["first-frame", "multimodal"], default="first-frame",
                   help="first-frame=只把第一张当首帧，动作连贯（推荐）；"
                        "multimodal=全能参考，多张图容易被当成分镜、变成幻灯片")
    p.add_argument("--duration", type=int, default=10)
    p.add_argument("--ratio", default="9:16")
    p.add_argument("--resolution", default="720p")
    p.add_argument("--audio", action="store_true", help="开生成音频")
    p.add_argument("--at", metavar="x,y", help="左上角坐标；不给就自动放到现有内容下方")
    p.add_argument("--size", choices=["big", "small"], default="big",
                   help="big=照画布上 G5/G6 量的大板子（默认）；small=节点默认尺寸")
    p.add_argument("--set-prompt", metavar="节点id",
                   help="只替换某个提示词节点的正文，不建新板；配 --prompt-file 用")
    p.add_argument("--relayout", metavar="组id",
                   help="把已有的组重新排齐：成员排成一行、尺寸按 --size 归位、"
                        "组框重新贴合。手动删过或拖乱过节点之后用这个收拾")
    args = p.parse_args()

    if args.relayout:
        return do_relayout(args, SIZES[args.size])

    if args.set_prompt:
        text = read_prompt(args)
        if not text:
            raise SystemExit("--set-prompt 需要配 --prompt 或 --prompt-file")
        t = time.perf_counter()
        call("PATCH", "/api/canvases/%s/nodes/%s" % (args.canvas, args.set_prompt),
             {"fields": {"text": text}})
        print("提示词已替换 %d 字，%.0f ms" % (len(text), (time.perf_counter() - t) * 1000))
        return 0

    prompt_text = read_prompt(args)
    if not args.image and not args.blank_image and not prompt_text:
        raise SystemExit("至少要给 --image / --blank-image / --prompt")
    provider, _, model = args.model.partition(":")

    t0 = time.perf_counter()
    calls = []

    def timed(method, path, body=None):
        t = time.perf_counter()
        out = call(method, path, body)
        calls.append((method, path.rsplit("/", 1)[-1], (time.perf_counter() - t) * 1000))
        return out

    x0, y0 = place(args.canvas, args)
    P = "/api/canvases/%s" % args.canvas
    tpl = SIZES[args.size]
    iw, ih = tpl["image"]
    pw, ph = tpl["prompt"]
    GAP_X = tpl["gap"]
    pad_l, pad_t, pad_r, pad_b = tpl["pad"]

    # 成员排成一行：图片…图片、提示词。一行比上下堆更好读，也贴近 G3 的样子。
    cursor = x0
    image_ids = []
    for i, src in enumerate(args.image):
        name = args.image_name[i] if i < len(args.image_name) else ""
        key, value = normalize_source(src)
        body = {"type": "image", key: value, "x": cursor, "y": y0, "w": iw, "h": ih}
        if name:
            body["name"] = name
        image_ids.append(timed("POST", P + "/nodes", body)["node"]["id"])
        cursor += iw + GAP_X

    for label in args.blank_image:
        image_ids.append(timed("POST", P + "/nodes", {
            "type": "image", "name": label, "x": cursor, "y": y0, "w": iw, "h": ih,
        })["node"]["id"])
        cursor += iw + GAP_X

    members = list(image_ids)
    if prompt_text:
        members.append(timed("POST", P + "/nodes",
                             {"type": "prompt", "text": prompt_text,
                              "x": cursor, "y": y0, "w": pw, "h": ph})["node"]["id"])
        cursor += pw + GAP_X

    row_w = max(cursor - GAP_X - x0, iw)
    video = timed("POST", P + "/nodes", {
        # 视频节点和组的标题由前端写死（「视频生成」/「G3」），传 name 也不会显示；
        # 想给板子做标记就用 --image-name，图片下面的说明文字是会显示的。
        "type": "video",
        "apiProvider": provider, "model": model,
        "duration": args.duration, "aspectRatio": args.ratio, "resolution": args.resolution,
        "useFrameRoles": args.mode == "first-frame",
        "multimodal": args.mode == "multimodal",
        "generateAudio": bool(args.audio),
        "x": x0 + row_w + VIDEO_DX, "y": y0 + VIDEO_DY,
    })["node"]

    group = timed("POST", P + "/groups", {"items": members})["node"]
    # 服务端按前端的紧凑边距算框（左 24 上 58 下 32），成员一放大就贴边了；
    # 这里按模板的边距重新框一次，看起来才和手动框选出来的 G5/G6 一致。
    if members:
        x2 = x0 + row_w
        y2 = y0 + max(ih if image_ids else 0, ph if prompt_text else 0)
        timed("PATCH", P + "/nodes/" + group["id"], {"fields": {
            "x": x0 - pad_l, "y": y0 - pad_t,
            "w": (x2 - x0) + pad_l + pad_r, "h": (y2 - y0) + pad_t + pad_b,
        }})
    timed("POST", P + "/connections", {"from": group["id"], "to": video["id"]})

    total = (time.perf_counter() - t0) * 1000
    for m, tail, ms in calls:
        print("  %-6s %-14s %6.1f ms" % (m, tail[:14], ms))
    print("")
    print("%d 次调用，端到端 %.0f ms" % (len(calls), total))
    print("位置 (%.0f, %.0f)  尺寸 %s  参考图 %d 张（其中占位 %d）  模式 %s  音频 %s"
          % (x0, y0, args.size, len(image_ids), len(args.blank_image),
             args.mode, "开" if args.audio else "关"))
    for i, nid in enumerate(image_ids):
        print("image[%d]=%s" % (i, nid))
    print("group=%s" % group["id"])
    print("video=%s" % video["id"])
    print("没有开跑；要生成就在页面上点这个节点的「视频生成」。")


if __name__ == "__main__":
    sys.exit(main())
