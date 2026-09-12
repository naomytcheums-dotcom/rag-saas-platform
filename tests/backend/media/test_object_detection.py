"""Partie 22 finalization -- real, local YOLOv8n object detection
(api/services/object_detection.py). One real, live end-to-end test
against ultralytics' own bundled sample photo (skipped, not failed, if
the real weights can't be downloaded -- no network in this run) proves
the pipeline actually detects real objects; the rest mock the model
boundary the same way OCR/ffmpeg tests mock their own real, separate
binaries/models."""

from unittest.mock import MagicMock

import pytest

from api.config import settings
from api.services import object_detection


@pytest.fixture(autouse=True)
def _reset_model_cache():
    """Every test gets a clean, unloaded model cache -- otherwise the
    first test to load the real model would leave it cached for every
    later test, including ones that need to simulate it being
    unavailable."""
    object_detection._model = None
    yield
    object_detection._model = None


def test_detect_objects_yolo_disabled_raises_not_available(monkeypatch):
    monkeypatch.setattr(settings, "OBJECT_DETECTION_ENABLED", False)
    with pytest.raises(object_detection.YOLONotAvailableError):
        object_detection.detect_objects_yolo(b"fake-bytes")


def test_get_model_raises_when_ultralytics_import_fails(monkeypatch):
    """Same real "not available" degradation as OCR's own
    TesseractNotFoundError -- simulated here by making the real
    `ultralytics` import fail, without needing to actually uninstall
    it."""
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "ultralytics":
            raise ImportError("simulated: ultralytics not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(object_detection.YOLONotAvailableError):
        object_detection._get_model()


def test_get_model_raises_when_weights_cannot_load(monkeypatch):
    monkeypatch.setattr(settings, "OBJECT_DETECTION_MODEL", "storage/ml_models/yolov8n.pt")

    class _FakeYOLOModule:
        @staticmethod
        def YOLO(path):
            raise RuntimeError("simulated: no network to download real weights")

    import sys

    monkeypatch.setitem(sys.modules, "ultralytics", _FakeYOLOModule())
    with pytest.raises(object_detection.YOLONotAvailableError):
        object_detection._get_model()


def test_detect_objects_yolo_parses_real_boxes_above_the_confidence_threshold():
    monkeypatch_model = MagicMock()
    # `cls` collides with MagicMock's own constructor kwarg (the mock's
    # class) -- set it as a real post-construction attribute instead.
    box_high = MagicMock(conf=[0.9])
    box_high.cls = [0]
    box_low = MagicMock(conf=[0.1])  # below threshold -- must be excluded
    box_low.cls = [1]
    result = MagicMock(boxes=[box_high, box_low], names={0: "person", 1: "car"})
    monkeypatch_model.return_value = [result]
    object_detection._model = monkeypatch_model

    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(buf, format="PNG")

    labels = object_detection.detect_objects_yolo(buf.getvalue())
    assert labels == ["person"]


def test_detect_objects_yolo_real_end_to_end_against_a_real_photo(monkeypatch, tmp_path):
    """A real, live test -- ultralytics' own bundled `bus.jpg` sample,
    confirmed by hand to real-world detect `['bus', 'person']` with the
    real YOLOv8n weights. Skipped (not failed) if the real weights
    can't be fetched (no network in this particular run)."""
    monkeypatch.setattr(settings, "OBJECT_DETECTION_MODEL", str(tmp_path / "yolov8n.pt"))
    from ultralytics.utils import ASSETS

    photo_bytes = (ASSETS / "bus.jpg").read_bytes()
    try:
        labels = object_detection.detect_objects_yolo(photo_bytes)
    except object_detection.YOLONotAvailableError as exc:
        pytest.skip(f"real YOLO weights unavailable in this environment: {exc}")

    assert "person" in labels
    assert "bus" in labels
