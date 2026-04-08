import base64
from io import BytesIO
import os
from pathlib import Path
import re

import httpx
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from app.core.config import get_settings

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".toml", ".ini"}
SUPPORTED_EXTENSIONS = {".pdf", *IMAGE_EXTENSIONS, *TEXT_EXTENSIONS}


def _load_pdf_text(path: Path) -> list[Document]:
    loader = PyPDFLoader(str(path))
    return loader.load()


def _load_pdf_image_ocr(path: Path) -> list[Document]:
    try:
        from pypdf import PdfReader
    except Exception:
        return []

    docs: list[Document] = []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return docs

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            images = list(page.images or [])
        except Exception:
            images = []
        for img_idx, img_obj in enumerate(images, start=1):
            img_bytes = getattr(img_obj, "data", None)
            if not img_bytes:
                continue
            docs.extend(_ocr_image_bytes(img_bytes, source=path, page=page_idx, image_index=img_idx))
    return docs


def _normalize_ocr_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines).strip()


def _score_ocr_text(text: str) -> int:
    compact = "".join(ch for ch in (text or "") if not ch.isspace())
    if not compact:
        return 0
    alnum = sum(1 for ch in compact if ch.isalnum())
    cjk = sum(1 for ch in compact if "\u4e00" <= ch <= "\u9fff")
    # Prefer longer results and those containing meaningful characters.
    return len(compact) + alnum + (2 * cjk)


def _parse_psm_modes(raw: str) -> list[int]:
    values = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            psm = int(part)
        except ValueError:
            continue
        if 0 <= psm <= 13:
            values.append(psm)
    return values or [6, 11, 3]


def _autorotate_image(image, pytesseract_module):
    try:
        osd = pytesseract_module.image_to_osd(image)
        match = re.search(r"Rotate:\s*(\d+)", osd or "")
        degrees = int(match.group(1)) if match else 0
    except Exception:
        degrees = 0
    if degrees in {90, 180, 270}:
        return image.rotate(360 - degrees, expand=True)
    return image


def _build_ocr_candidates(image, settings, pil_imageops):
    candidates: list[tuple[str, object]] = [("raw", image)]
    if not settings.ocr_preprocess_enabled:
        return candidates

    width, height = image.size
    min_side = min(width, height)
    if min_side > 0 and settings.ocr_upscale_min_side > 0 and min_side < settings.ocr_upscale_min_side:
        try:
            resampling = getattr(getattr(image, "Resampling", None), "LANCZOS", None)
            if resampling is None:
                from PIL import Image

                resampling = Image.LANCZOS
            scale = settings.ocr_upscale_min_side / float(min_side)
            upscaled = image.resize((int(width * scale), int(height * scale)), resampling)
            candidates.append(("upscaled", upscaled))
        except Exception:
            pass

    base_variants = list(candidates)
    for base_name, base_image in base_variants:
        try:
            gray = pil_imageops.grayscale(base_image)
            candidates.append((f"{base_name}_gray", gray))
            high_contrast = pil_imageops.autocontrast(gray)
            candidates.append((f"{base_name}_autocontrast", high_contrast))
            binary = high_contrast.point(lambda x: 255 if x > 170 else 0)
            candidates.append((f"{base_name}_binary", binary))
            inverted = pil_imageops.invert(high_contrast)
            candidates.append((f"{base_name}_inverted", inverted))
        except Exception:
            continue

    return candidates


def _run_ocr_with_candidates(image, settings, pytesseract_module, pil_imageops):
    image = _autorotate_image(image, pytesseract_module)
    candidates = _build_ocr_candidates(image, settings, pil_imageops)
    psm_modes = _parse_psm_modes(settings.ocr_psm_modes)

    lang = settings.tesseract_lang or "chi_sim+eng"
    best_text = ""
    best_score = 0
    best_variant = "raw"
    best_psm = ""
    last_error = ""

    for variant_name, candidate in candidates:
        for psm in psm_modes:
            config = f"--oem 3 --psm {psm}"
            try:
                raw = pytesseract_module.image_to_string(candidate, lang=lang, config=config) or ""
                text = _normalize_ocr_text(raw)
                score = _score_ocr_text(text)
                if score > best_score:
                    best_text = text
                    best_score = score
                    best_variant = variant_name
                    best_psm = str(psm)
            except Exception as e:
                last_error = str(e)

    if best_text:
        return best_text, best_variant, best_psm, ""

    # Last fallback: default OCR call without custom config.
    try:
        raw = pytesseract_module.image_to_string(image) or ""
        text = _normalize_ocr_text(raw)
        if text:
            return text, "raw_fallback", "", ""
    except Exception as e:
        last_error = str(e)

    return "", "", "", last_error


def _detect_people_in_image(image, settings) -> dict:
    if not getattr(settings, "people_detection_enabled", True):
        return {"status": "disabled", "person_count": 0, "face_count": 0, "human_present": False}

    try:
        import cv2  # type: ignore
        import numpy as np
    except Exception:
        return {"status": "unavailable", "person_count": 0, "face_count": 0, "human_present": False}

    try:
        rgb = image.convert("RGB")
        np_rgb = np.array(rgb)
        bgr = cv2.cvtColor(np_rgb, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    except Exception:
        return {"status": "cv_decode_error", "person_count": 0, "face_count": 0, "human_present": False}

    mode = str(getattr(settings, "people_detection_mode", "face") or "face").lower()
    if mode not in {"face", "hog", "both"}:
        mode = "face"

    face_count = 0
    person_count = 0
    status = "ok"

    if mode in {"face", "both"}:
        try:
            cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
            detector = cv2.CascadeClassifier(cascade_path)
            faces = detector.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(24, 24))
            face_count = int(len(faces))
        except Exception:
            status = "face_detector_error"

    if mode in {"hog", "both"}:
        try:
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            rects, _weights = hog.detectMultiScale(bgr, winStride=(8, 8), padding=(8, 8), scale=1.05)
            person_count = int(len(rects))
        except Exception:
            if status == "ok":
                status = "person_detector_error"

    # Face count is a strong person proxy.
    person_count = max(person_count, face_count)
    return {
        "status": status,
        "person_count": person_count,
        "face_count": face_count,
        "human_present": person_count > 0,
        "detector_mode": mode,
    }


def _build_people_summary(people_info: dict) -> str:
    return (
        "[image_people]\n"
        f"status={people_info.get('status', 'unknown')}; "
        f"human_present={str(bool(people_info.get('human_present', False))).lower()}; "
        f"person_count={int(people_info.get('person_count', 0))}; "
        f"face_count={int(people_info.get('face_count', 0))}; "
        f"detector_mode={people_info.get('detector_mode', 'face')}"
    )


def _vision_prompt() -> str:
    return (
        "你是图像理解助手。请用中文输出简洁结构化描述，包含：\n"
        "1) 人物：有几个人、外观特征、在做什么。\n"
        "2) 动物：种类、数量、动作。\n"
        "3) 物体与场景：关键物体、环境、空间关系。\n"
        "4) 可读文本：图中看得见的文字（若有）。\n"
        "5) 风险与不确定性：无法确认的内容请明确写“无法确认”。\n"
        "注意：不要臆测真实身份；除非图中有明确文字证据，否则人物身份写“无法确认”。"
    )


def _describe_image_openai(img_bytes: bytes, settings) -> dict:
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
            {"role": "system", "content": _vision_prompt()},
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
    model = settings.ollama_vision_model or "llava:7b"
    base_url = (settings.ollama_base_url or "http://localhost:11434").rstrip("/")
    b64 = base64.b64encode(img_bytes).decode("ascii")
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": _vision_prompt()},
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


def _describe_image_with_vision(img_bytes: bytes, settings) -> dict:
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


def _build_vision_summary(vision_info: dict) -> str:
    status = str(vision_info.get("status", "unknown"))
    model = str(vision_info.get("model", "") or "")
    caption = str(vision_info.get("caption", "") or "").strip()
    if caption:
        return f"[image_scene] status={status}; model={model}\n{caption}"
    err = str(vision_info.get("error", "") or "").strip()
    if err:
        return f"[image_scene] status={status}; model={model}\n{err}"
    return f"[image_scene] status={status}; model={model}"


def _ocr_image_bytes(img_bytes: bytes, source: Path, page: int | None = None, image_index: int | None = None) -> list[Document]:
    try:
        from PIL import Image, ImageOps
    except Exception:
        return []

    try:
        image = Image.open(BytesIO(img_bytes))
    except Exception:
        return []

    width, height = image.size
    mode = image.mode or "unknown"
    file_format = (image.format or "unknown").lower()
    summary = f"[image_meta] format={file_format}; mode={mode}; size={width}x{height}."

    metadata = {
        "source": str(source),
        "modality": "image_ocr",
        "width": width,
        "height": height,
        "image_mode": mode,
        "image_format": file_format,
    }
    if page is not None:
        metadata["page"] = page
    if image_index is not None:
        metadata["image_index"] = image_index

    settings = get_settings()
    people_info = _detect_people_in_image(image, settings)
    metadata["person_detection_status"] = str(people_info.get("status", "unknown"))
    metadata["person_count"] = int(people_info.get("person_count", 0))
    metadata["face_count"] = int(people_info.get("face_count", 0))
    metadata["human_present"] = bool(people_info.get("human_present", False))
    metadata["person_detector_mode"] = str(people_info.get("detector_mode", "face"))
    people_summary = _build_people_summary(people_info)
    vision_info = _describe_image_with_vision(img_bytes, settings)
    metadata["image_caption_status"] = str(vision_info.get("status", "unknown"))
    metadata["image_caption_model"] = str(vision_info.get("model", "") or "")
    if vision_info.get("caption"):
        metadata["image_caption"] = str(vision_info.get("caption", ""))
    if vision_info.get("error"):
        metadata["image_caption_error"] = str(vision_info.get("error", ""))
    vision_summary = _build_vision_summary(vision_info)

    try:
        import pytesseract
    except Exception:
        metadata["ocr_status"] = "pytesseract_missing"
        content = f"{summary}\n{people_summary}\n{vision_summary}\n[image_ocr_error]\npytesseract not installed"
        return [Document(page_content=content, metadata=metadata)]

    if settings.tessdata_prefix:
        os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    ocr_text, ocr_variant, ocr_psm, ocr_error = _run_ocr_with_candidates(
        image=image,
        settings=settings,
        pytesseract_module=pytesseract,
        pil_imageops=ImageOps,
    )
    ocr_status = "ok"

    if not ocr_text:
        err_lower = ocr_error.lower()
        if "tesseract is not installed" in err_lower or "tesseractnotfounderror" in err_lower:
            ocr_status = "engine_not_found"
            reason = "Tesseract executable not found"
        elif "failed loading language" in err_lower or "error opening data file" in err_lower:
            ocr_status = "language_data_missing"
            reason = "Tesseract language data missing or TESSDATA_PREFIX not set correctly"
        elif ocr_error:
            ocr_status = "ocr_runtime_error"
            reason = f"OCR runtime error: {ocr_error}"
        else:
            ocr_status = "no_text_detected"
            reason = "OCR ran but no text detected (image may be blank/low quality)"
        metadata["ocr_status"] = ocr_status
        metadata["ocr_error"] = ocr_error
        content = f"{summary}\n{people_summary}\n{vision_summary}\n[image_ocr_error]\n{reason}"
        return [Document(page_content=content, metadata=metadata)]

    metadata["ocr_status"] = ocr_status
    metadata["ocr_variant"] = ocr_variant
    metadata["ocr_psm"] = ocr_psm
    content = f"{summary}\n{people_summary}\n{vision_summary}\n[image_ocr]\n{ocr_text}"

    return [Document(page_content=content, metadata=metadata)]


def _load_image_file(path: Path) -> list[Document]:
    try:
        img_bytes = path.read_bytes()
    except Exception:
        return []
    return _ocr_image_bytes(img_bytes, source=path)


def _load_single_path(path: Path) -> list[Document]:
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return []

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text_docs = _load_pdf_text(path)
        ocr_docs = _load_pdf_image_ocr(path)
        return text_docs + ocr_docs

    if suffix in IMAGE_EXTENSIONS:
        return _load_image_file(path)

    loader = TextLoader(str(path), encoding="utf-8")
    try:
        return loader.load()
    except UnicodeDecodeError:
        # Fallback for common non-UTF8 text files.
        loader = TextLoader(str(path), encoding="gb18030")
        return loader.load()


def load_documents(data_dir: Path | None = None, paths: list[Path] | None = None) -> list[Document]:
    docs: list[Document] = []
    if paths is not None:
        for path in paths:
            docs.extend(_load_single_path(path))
        return docs

    if data_dir is None:
        return docs

    for path in data_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        docs.extend(_load_single_path(path))
    return docs
