"""NovelAI V5 official image protocol; credentials never enter returned metadata."""

import base64
from io import BytesIO
import re
import secrets
import zipfile

import httpx
from fastapi import HTTPException
from PIL import Image

BASE_URL = "https://image.novelai.net"
MODELS = ["nai-diffusion-5-full", "nai-diffusion-5-curated"]
MODEL_NAMES = dict(zip(MODELS, ["NovelAI V5 Full", "NovelAI V5 Curated"]))
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


def validate_base_url(value):
    if str(value or BASE_URL).strip().rstrip("/") != BASE_URL:
        raise HTTPException(400, "NovelAI 仅支持官方地址 https://image.novelai.net")
    return BASE_URL


def auth_headers(token):
    token = re.sub(r"^Bearer\s+", "", str(token or "").strip(), flags=re.I)
    if not token or any(char.isspace() for char in token):
        raise HTTPException(400, "请在 API 设置中保存 NovelAI Persistent API Token。")
    return {"Authorization": f"Bearer {token}", "Origin": "https://novelai.net"}


def check_response(response):
    if 200 <= response.status_code < 300:
        return
    messages = {
        401: "NovelAI Token 无效或已失效，请更新 API Key。",
        402: "NovelAI 点数不足或账户不满足生成条件。",
        403: "NovelAI 拒绝访问，请检查账户权限。",
        429: "NovelAI 请求过于频繁，请稍后重试。",
    }
    # Do not echo arbitrary upstream bodies, which may contain request data.
    raise HTTPException(502, messages.get(response.status_code,
        f"NovelAI 返回 HTTP {response.status_code}，未自动重试生成。"))


async def account_status(token, base_url=BASE_URL):
    base = validate_base_url(base_url)
    headers = auth_headers(token)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get(f"{base}/user/data", headers=headers)
        check_response(response)
        data = response.json()
        root = data.get("data", data)
        subscription = root.get("subscription") or root.get("information", {}).get("subscription")
        if not isinstance(subscription, dict):
            raise ValueError("missing subscription")
        balance = subscription.get("trainingStepsLeft")
        if isinstance(balance, dict):
            fixed = balance.get("fixedTrainingStepsLeft")
            purchased = balance.get("purchasedTrainingSteps")
            balance = (float(fixed or 0) + float(purchased or 0)) if fixed is not None or purchased is not None else None
        if balance is not None:
            balance = int(balance)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "无法连接 NovelAI 官方服务；认证检查未提交生成任务。") from exc
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(502, "NovelAI 账户响应格式异常，未能确认认证状态。") from exc
    return {
        "ok": True, "status": response.status_code, "protocol": "novelai",
        "message": "NovelAI 认证成功（未生成、未扣点）" + (f"；余额 {balance} Anlas" if balance is not None else ""),
        "balance": balance, "tier": subscription.get("tier"),
        "total": len(MODELS), "model_count": len(MODELS), "all": list(MODELS),
        "image_models": list(MODELS), "model_names": dict(MODEL_NAMES),
        "chat_models": [], "video_models": [], "model_source": "configured",
    }


def build_payload(prompt, size, model, references=None):
    if model not in MODELS:
        raise HTTPException(400, "NovelAI 接入仅支持 V5 Full 和 V5 Curated。")
    if references:
        raise HTTPException(400, "当前 NovelAI 画布入口支持文字生图，请先移除参考图。")
    if not str(prompt or "").strip():
        raise HTTPException(400, "请输入 NovelAI 提示词。")
    match = re.fullmatch(r"(\d+)x(\d+)", str(size or ""))
    if not match:
        raise HTTPException(400, "NovelAI 尺寸须为像素值，例如 1024x1024 或 832x1216。")
    width, height = map(int, match.groups())
    if min(width, height) < 64 or width % 64 or height % 64 or width * height > 1048576:
        raise HTTPException(400, "NovelAI 标准生图的宽高须为 64 的倍数、总像素不超过 1048576；建议 1024x1024、832x1216 或 1216x832。")
    seed = secrets.randbelow(2 ** 32)
    return {
        "input": prompt.strip(), "model": model, "action": "generate",
        "parameters": {
            "params_version": 4, "width": width, "height": height,
            "scale": 7, "sampler": "k_euler_ancestral", "steps": 23,
            "n_samples": 1, "seed": seed, "noise_schedule": "karras",
            "negative_prompt": "", "uc": "", "ucPresetId": "none",
            "qualityToggle": False, "qualityPresetId": "none", "cfg_rescale": 0,
            "legacy": False, "legacy_uc": False, "legacy_v3_extend": False,
            "dynamic_thresholding": False, "skip_cfg_above_sigma": None,
            "deliberate_euler_ancestral_bug": False, "prefer_brownian": True,
            "use_coords": False,
            "v4_prompt": {"caption": {"base_caption": prompt.strip(), "char_captions": []}, "use_coords": False, "use_order": True},
            "v4_negative_prompt": {"caption": {"base_caption": "", "char_captions": []}, "legacy_uc": False},
        },
    }


def decode_image(content, expected_size):
    try:
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError("oversized response")
        if content.startswith(b"PK"):
            with zipfile.ZipFile(BytesIO(content)) as archive:
                entries = [entry for entry in archive.infolist() if not entry.is_dir() and entry.filename.lower().endswith(".png")]
                if len(entries) != 1 or entries[0].file_size > MAX_RESPONSE_BYTES:
                    raise ValueError("unexpected image count or size")
                content = archive.read(entries[0])
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG" or image.size != expected_size:
                raise ValueError("unexpected image format or dimensions")
            image.verify()
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError, Image.DecompressionBombError) as exc:
        raise HTTPException(502, "NovelAI 未返回符合请求尺寸的有效 PNG 图片；未自动重试。") from exc
    return {"type": "b64", "value": base64.b64encode(content).decode("ascii"), "mime_type": "image/png"}


async def generate(token, base_url, prompt, size, model, references=None):
    base = validate_base_url(base_url)
    headers = {**auth_headers(token), "Accept": "application/zip, application/octet-stream"}
    payload = build_payload(prompt, size, model, references)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=20), follow_redirects=False) as client:
            # A timed-out paid POST may already be charged. Never retry it automatically.
            async with client.stream("POST", f"{base}/ai/generate-image", headers=headers, json=payload) as response:
                check_response(response)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise HTTPException(502, "NovelAI 图片响应过大；未自动重试。")
        params = payload["parameters"]
        image = decode_image(bytes(content), (params["width"], params["height"]))
    except httpx.HTTPError as exc:
        raise HTTPException(502, "NovelAI 生成连接中断；任务可能已扣点，请检查官网记录后再决定是否重试。") from exc
    return image, {"model": model, "seed": params["seed"], "size": size, "steps": params["steps"]}
