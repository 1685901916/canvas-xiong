"""Official Ark Seedream Pro payloads and lossless layer artifacts."""
import base64
import html
import json
import re
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, ConfigDict
from typing import Literal


class SeedreamOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layer_decomposition: bool = False
    output_format: Literal["png", "jpeg"] = "png"
    response_format: Literal["url", "b64_json"] = "url"
    watermark: bool = False
    optimize_mode: Literal["standard", "fast"] = "standard"
    background: Literal["opaque", "transparent"] = "opaque"


def is_pro(model):
    return "seedream-5-0-pro" in str(model).lower()


def payload(model, prompt, size, refs, options=None, count=1):
    options = options or SeedreamOptions()
    if not isinstance(options, SeedreamOptions):
        options = SeedreamOptions(**options)
    if len(refs) > 10:
        raise ValueError("Seedream 5.0 Pro 最多使用 10 张参考图。")
    if options.layer_decomposition:
        if len(refs) != 1 or count != 1:
            raise ValueError("图像分层需要恰好 1 张参考图，每次生成 1 组图层。")
        if options.background == "transparent":
            raise ValueError("图像分层已返回透明图层，不可同时启用透明背景编辑。")
    elif not prompt.strip():
        raise ValueError("普通生图和参考图编辑需要提示词。")
    size = str(size).strip().upper()
    allowed = {"1K", "1.5K", "2K"}
    if options.layer_decomposition:
        allowed.add("AUTO")
    if size not in allowed:
        dims = re.fullmatch(r"(\d+)[Xx](\d+)", size)
        if options.layer_decomposition or not dims:
            raise ValueError("Seedream Pro 支持 1K、1.5K、2K；分层还支持 auto，普通生图支持自定义像素尺寸。")
        width, height = map(int, dims.groups())
        if min(width, height) < 15 or not 1 / 16 <= width / height <= 16:
            raise ValueError("自定义尺寸需满足边长至少 15、宽高比 1:16–16:1；总像素限制由官方接口校验。")
        size = f"{width}x{height}"
    if options.background == "transparent" and (len(refs) != 1 or options.output_format != "png"):
        raise ValueError("透明背景编辑需要 1 张带透明通道的参考图，并选择 PNG 输出。")
    body = dict(model=model, prompt=prompt, size="auto" if size == "AUTO" else size,
                response_format=options.response_format, output_format=options.output_format,
                watermark=options.watermark, optimize_prompt_options={"mode": options.optimize_mode})
    if refs:
        body["image"] = refs
    if options.layer_decomposition:
        body["layer_decomposition"] = True
    if options.background == "transparent":
        body["background"] = "transparent"
    return body


def local_reference(path, require_alpha=False):
    """Preserve full source resolution; convert unsupported containers to PNG."""
    with Image.open(path) as source:
        source.load()
        if require_alpha and ("A" not in source.getbands() or source.getchannel("A").getextrema()[0] == 255):
            raise ValueError("透明背景编辑的参考图必须包含实际透明像素。")
        buffer = BytesIO()
        source.convert("RGBA" if "A" in source.getbands() or "transparency" in source.info else "RGB").save(buffer, format="PNG")
    if len(buffer.getvalue()) > 30 * 1024 * 1024:
        raise ValueError("参考图转换为 PNG 后超过 30 MB，请先缩小图片。")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def images(raw):
    result = []
    for row in raw.get("data", []):
        if not isinstance(row, dict):
            continue
        if row.get("url"):
            item = {"type": "url", "value": row["url"]}
        elif row.get("b64_json"):
            item = {"type": "b64", "value": row["b64_json"]}
        else:
            continue
        item.update({key: row[key] for key in ("name", "description", "z_index", "bounding_box", "size", "output_format") if key in row})
        if row.get("output_format") == "jpeg":
            item["mime_type"] = "image/jpeg"
        result.append(item)
    return result


def bundle(items, resolve_path, output_dir, url_for):
    """Keep original metadata and refuse to guess offsets in a PSD."""
    root = Path(output_dir)
    stem = "seedream_layers_" + uuid.uuid4().hex[:12]
    folder = root / stem
    folder.mkdir(parents=True)
    ordered = sorted(items, key=lambda row: row.get("z_index", -1))
    indices = [row.get("z_index") for row in ordered]
    if not indices or indices[0] != 0 or len(set(indices)) != len(indices) or any(not isinstance(z, int) for z in indices):
        raise ValueError("官方分层结果缺少有效 z_index，已保留原图，不能猜测 PSD 叠放顺序。")
    with Image.open(resolve_path(ordered[0]["url"])) as base:
        canvas = base.size
    manifest = {"provider": "volcengine", "canvas": list(canvas), "layers": []}
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new("RGBA", canvas)
    for index, item in enumerate(ordered):
        with Image.open(resolve_path(item["url"])) as source:
            im = source.convert("RGBA")
        box = (item.get("bounding_box") or {}).get("absolute")
        offset = (0, 0)
        if index and box and len(box) == 4:
            offset = (int(box[0]), int(box[1]))
            target_size = (int(box[2]) - offset[0], int(box[3]) - offset[1])
            if min(target_size) <= 0:
                raise ValueError("官方图层坐标无效。")
        elif im.size != canvas:
            if not box or len(box) != 4:
                raise ValueError("裁剪图层缺少官方坐标，不能生成位置准确的 PSD。")
        else:
            target_size = canvas
        name = item.get("name") or ("Base" if index == 0 else f"Layer {index}")
        filename = f"{index:02d}.png"
        im.save(folder / filename)
        original_size = im.size
        aligned_filename = filename
        if im.size != target_size:
            im = im.resize(target_size, Image.Resampling.LANCZOS)
            aligned_filename = f"{index:02d}_aligned.png"
            im.save(folder / aligned_filename)
        layer = PixelLayer.frompil(im, psd, name=f"Layer {index}", left=offset[0], top=offset[1])
        layer.name = name[:255]  # Unicode tag; the constructor only sets the legacy MacRoman name.
        layer.visible = True
        manifest["layers"].append({**{k: item[k] for k in ("name", "description", "z_index", "bounding_box") if k in item},
                                  "name": name, "file": filename, "aligned_file": aligned_filename, "original_size": list(original_size), "offset": list(offset), "visible": layer.visible})
    psd_path = root / (stem + ".psd")
    psd.save(psd_path)
    reopened = PSDImage.open(psd_path)
    if len(reopened) != len(ordered) or reopened.size != canvas:
        raise ValueError("PSD 回读校验失败。")
    for layer, meta in zip(reopened, manifest["layers"]):
        if layer.name != meta["name"][:255] or layer.offset != tuple(meta["offset"]):
            raise ValueError("PSD 图层名称或坐标回读不一致。")
        with Image.open(folder / meta["aligned_file"]) as original:
            if layer.topil().convert("RGBA").tobytes() != original.convert("RGBA").tobytes():
                raise ValueError("PSD 图层像素回读不一致。")
    (folder / "layers.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # The package is self-contained; references are local files, never API credentials.
    labels = "".join(f'<label><input type="checkbox" {"checked" if r["visible"] else ""} data-layer="l{i}">{html.escape(r["name"])}</label>' for i, r in enumerate(manifest["layers"]))
    pictures = "".join(f'<img id="l{i}" src="{r["aligned_file"]}" style="left:{r["offset"][0]}px;top:{r["offset"][1]}px;display:{"block" if r["visible"] else "none"}">' for i, r in enumerate(manifest["layers"]))
    viewer = f'<!doctype html><meta charset="utf-8"><title>Seedream 图层预览</title><style>body{{font:16px sans-serif;background:#eee}}label{{display:block}}#stage{{position:relative;width:{canvas[0]}px;height:{canvas[1]}px;background:repeating-conic-gradient(#ddd 0% 25%,white 0% 50%) 0/24px 24px}}img{{position:absolute}}</style><h1>Seedream 图层预览</h1>{labels}<div id="stage">{pictures}</div><script>document.querySelectorAll("input").forEach(x=>x.onchange=()=>document.getElementById(x.dataset.layer).style.display=x.checked?"block":"none")</script>'
    (folder / "preview.html").write_text(viewer, encoding="utf-8")
    zip_path = root / (stem + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in folder.iterdir():
            archive.write(path, path.name)
        archive.write(psd_path, "layers.psd")
    return {"zip": url_for(zip_path.name), "psd": url_for(psd_path.name), "manifest": url_for(stem + "/layers.json"),
            "preview": url_for(stem + "/preview.html"), "layer_count": len(ordered) - 1, "canvas": list(canvas)}
