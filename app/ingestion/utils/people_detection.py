"""People detection utilities using OpenCV."""

from pathlib import Path


def detect_people_in_image(image, settings) -> dict:
    """Detect people in image using face and/or HOG detection."""
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


def build_people_summary(people_info: dict) -> str:
    """Build people detection summary text."""
    return (
        "[image_people]\n"
        f"status={people_info.get('status', 'unknown')}; "
        f"human_present={str(bool(people_info.get('human_present', False))).lower()}; "
        f"person_count={int(people_info.get('person_count', 0))}; "
        f"face_count={int(people_info.get('face_count', 0))}; "
        f"detector_mode={people_info.get('detector_mode', 'face')}"
    )
