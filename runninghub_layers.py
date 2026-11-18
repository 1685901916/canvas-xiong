"""RunningHub Seedream 5.5 图层拆分（seedream-v5.5/layer-decomposition）接入画布。

RunningHub 的返回里每层带 name、zindex、boundingBox.absolute（原图坐标）。画布原来走通用生图流程，
这些信息会丢掉，各层也只是一堆大小不一的图。这里做三件事：
1. 从返回里取出每层和它的位置、前后顺序（items_from_raw）；
2. 交给 seedream_pro.bundle 打包成 图层预览 / PNG+PSD 压缩包 / PSD（和火山 5.0 Pro 分层同一套）；
3. 每层另存一张和底图一样大的透明 PNG，层放在原来的位置（aligned_outputs）。
   这样把这些图拖到画布上、多选后打开「自由合成」，各层会自动叠回原位，能单独拖动、隐藏、调顺序。
"""
import os
import uuid

from PIL import Image


def is_layer_model(model):
    return "layer-decomposition" in str(model or "").lower()


def items_from_raw(raw, rewrite_url=lambda u: u):
    """RunningHub 返回 → [{type,value,name,z_index,bounding_box}]，第 0 张是底图。"""
    data = raw if isinstance(raw, dict) else {}
    results = data.get("results") or (data.get("data") or {}).get("results") or []
    items = []
    for row in results:
        if not isinstance(row, dict):
            continue
        url = row.get("url") or row.get("fileUrl") or row.get("value")
        if not url:
            continue
        item = {"type": "url", "value": rewrite_url(url)}
        if row.get("name"):
            item["name"] = str(row["name"])
        if row.get("description"):
            item["description"] = str(row["description"])
        z = row.get("zindex", row.get("z_index"))
        if isinstance(z, int):
            item["z_index"] = z
        box = (row.get("boundingBox") or row.get("bounding_box") or {})
        if isinstance(box, dict) and isinstance(box.get("absolute"), (list, tuple)) and len(box["absolute"]) == 4:
            item["bounding_box"] = {"absolute": [int(v) for v in box["absolute"]]}
        items.append(item)
    if not items:
        raise ValueError("RunningHub 图层拆分没有返回图层。")
    return items


def aligned_outputs(local_items, resolve_path, output_dir, url_for, artifact=None):
    """每层存一张和底图同尺寸的透明 PNG（层在原位置）。返回 (urls, metas)，第 0 张是底图本身。"""
    ordered = sorted(local_items, key=lambda r: r.get("z_index", 0))
    base_path = resolve_path(ordered[0]["url"])
    with Image.open(base_path) as base:
        canvas = base.size
    stem = "seedream55_aligned_" + uuid.uuid4().hex[:10]
    urls, metas = [], []
    for index, item in enumerate(ordered):
        meta = {k: item[k] for k in ("name", "description", "z_index", "bounding_box") if k in item}
        meta["kind"] = "image"
        if artifact:
            meta["layer_bundle"] = artifact
        if index == 0:
            url = item["url"]
        else:
            box = (item.get("bounding_box") or {}).get("absolute")
            with Image.open(resolve_path(item["url"])) as src:
                im = src.convert("RGBA")
            full = Image.new("RGBA", canvas, (0, 0, 0, 0))
            if box:
                x0, y0, x1, y1 = [int(v) for v in box]
                if x1 > x0 and y1 > y0:
                    full.alpha_composite(im.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS), (x0, y0))
            elif im.size == canvas:
                full = im
            name = f"{stem}_{index:02d}.png"
            full.save(os.path.join(output_dir, name))
            url = url_for(name)
        meta["url"] = url
        meta["natural_w"], meta["natural_h"] = canvas
        urls.append(url)
        metas.append(meta)
    return urls, metas
