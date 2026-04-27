"""Vision API utilities for image captioning."""

import base64

import httpx


def vision_prompt() -> str:
    """Get the vision model prompt for image description."""
    return (
        "你是图像理解助手。请用中文输出简洁结构化描述，包含：\n"
        "1) 人物：有几个人、外观特征、在做什么。\n"
        "2) 动物：种类、数量、动作。\n"
        "3) 物体与场景：关键物体、环境、空间关系。\n"
        "4) 可读文本：图中看得见的文字（若有）。\n"
        "5) 风险与不确定性：无法确认的内容请明确写\"无法确认\"。\n"
        "注意：不要臆测真实身份；除非图中有明确文字证据，否则人物身份写\"无法确认\"。"
    )


def _describe_image_openai(img_bytes: bytes, settings) -> dict:
    """Describe image using OpenAI vision API."""
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        return {"status": "openai_key_missing", "caption": "", "model": settings.openai_vision_model, "error": ""}

    base_url = (settings.openai_base_url or "https://api.openai.com").rstrip("/")
    model = settings.openai_vision_model or settings.openai_chat_model
    b64 = base64.b64encode(img_bytes).decode("ascii")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": vision_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请详细描述这张图片。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            },
        ],
    }
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                f"{base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {"status": "openai_error", "caption": "", "model": model, "error": str(e)}

    try:
        text = str((((data.get("choices") or [])[0]).get("message") or {}).get("content") or "").strip()
    except Exception:
        text = ""
    if not text:
        return {"status": "openai_empty", "caption": "", "model": model, "error": ""}
    return {"status": "ok", "caption": text, "model": model, "error": ""}


def _describe_image_ollama(img_bytes: bytes, settings) -> dict:
    """Describe image using Ollama vision API."""
    model = settings.ollama_vision_model or "llava:7b"
    base_url = (settings.ollama_base_url or "http://localhost:11434").rstrip("/")
    b64 = base64.b64encode(img_bytes).decode("ascii")
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": vision_prompt()},
            {"role": "user", "content": "请详细描述这张图片。", "images": [b64]},
        ],
        "options": {"temperature": 0},
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {"status": "ollama_error", "caption": "", "model": model, "error": str(e)}

    text = str(((data.get("message") or {}).get("content") or "")).strip()
    if not text:
        return {"status": "ollama_empty", "caption": "", "model": model, "error": ""}
    return {"status": "ok", "caption": text, "model": model, "error": ""}


def describe_image_with_vision(img_bytes: bytes, settings) -> dict:
    """Describe image using vision API with fallback."""
    if not getattr(settings, "image_caption_enabled", False):
        return {"status": "disabled", "caption": "", "model": "", "error": ""}

    backend = str(getattr(settings, "image_caption_backend", "auto") or "auto").lower()
    tried: list[dict] = []

    def _maybe_try(name: str) -> dict:
        if name == "openai":
            return _describe_image_openai(img_bytes, settings)
        return _describe_image_ollama(img_bytes, settings)

    backends = []
    if backend == "auto":
        preferred = str(getattr(settings, "model_backend", "ollama") or "ollama").lower()
        if preferred == "openai":
            backends = ["openai", "ollama"]
        else:
            backends = ["ollama", "openai"]
    elif backend in {"openai", "ollama"}:
        backends = [backend]
    else:
        backends = ["ollama", "openai"]

    for name in backends:
        res = _maybe_try(name)
        if res.get("status") == "ok":
            return res
        tried.append(res)

    detail = "; ".join(
        f"{x.get('status','unknown')}:{(x.get('error','') or '')[:120]}"
        for x in tried
        if x.get("status")
    )
    return {"status": "vision_failed", "caption": "", "model": "", "error": detail}


def build_vision_summary(vision_info: dict) -> str:
    """Build vision summary text from vision API result."""
    status = str(vision_info.get("status", "unknown"))
    model = str(vision_info.get("model", "") or "")
    caption = str(vision_info.get("caption", "") or "").strip()
    if caption:
        return f"[image_scene] status={status}; model={model}\n{caption}"
    err = str(vision_info.get("error", "") or "").strip()
    if err:
        return f"[image_scene] status={status}; model={model}\n{err}"
    return f"[image_scene] status={status}; model={model}"
