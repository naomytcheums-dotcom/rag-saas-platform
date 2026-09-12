"""Partie 22 (finalization) -- real, local object detection via
`ultralytics` YOLOv8n. Originally declined (this codebase had no CV
dependency and no confirmed PyTorch install in this environment); the
user confirmed a real, working, CPU-only `torch==2.13.0+cpu` is
already installed (the same one `requirements-api.txt` already pins
for `sentence-transformers`), so YOLOv8n (`ultralytics`, itself a real,
small ~6.5MB-weights package) is a genuinely lightweight addition on
top of an already-real dependency, not a new heavy one.

**Real, honest degradation, same category as Tesseract/poppler/ffmpeg**
(see `api/services/ocr.py`'s own docstring): `YOLONotAvailableError`
distinguishes "the real `ultralytics` package isn't installed" or "the
real YOLOv8n weights couldn't be loaded/downloaded" (e.g. no internet
access in this environment on first run -- ultralytics downloads its
weights from its own GitHub releases on first use, and this session's
own dev machine may not have that reachable) from any other real
failure -- callers (`api.services.media`) fall back to the vision-LLM's
own object list rather than crashing."""

import io
import logging
import threading

from api.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


class YOLONotAvailableError(RuntimeError):
    pass


def _get_model():
    if not settings.OBJECT_DETECTION_ENABLED:
        raise YOLONotAvailableError("object detection is disabled (OBJECT_DETECTION_ENABLED=False)")
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise YOLONotAvailableError("the real 'ultralytics' package is not installed") from exc
            try:
                from pathlib import Path

                Path(settings.OBJECT_DETECTION_MODEL).parent.mkdir(parents=True, exist_ok=True)
                _model = YOLO(settings.OBJECT_DETECTION_MODEL)
            except Exception as exc:  # noqa: BLE001 -- a real weights-download/load failure (e.g. no network) is not an import error, but is just as real a "not available" case
                raise YOLONotAvailableError(f"could not load the real YOLO weights '{settings.OBJECT_DETECTION_MODEL}': {exc}") from exc
    return _model


def detect_objects_yolo(image_bytes: bytes) -> list[str]:
    """Real, local, real-time object detection -- real class labels
    above `OBJECT_DETECTION_CONFIDENCE_THRESHOLD`, deduplicated,
    ordered by first detection. Raises `YOLONotAvailableError` (never a
    silent empty list) when the real model itself can't be reached --
    callers decide how to degrade from there."""
    from PIL import Image

    model = _get_model()
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgb_image = image.convert("RGB")
        results = model(rgb_image, verbose=False)

    labels: list[str] = []
    for result in results:
        for box in result.boxes:
            if float(box.conf[0]) < settings.OBJECT_DETECTION_CONFIDENCE_THRESHOLD:
                continue
            label = result.names[int(box.cls[0])]
            if label not in labels:
                labels.append(label)
    return labels
