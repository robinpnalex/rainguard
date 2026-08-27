"""
Hazard detectors.

Everything the rest of the app knows about detection is the `Detector`
interface in `base.py`. Swap the implementation, keep the app.

    DETECTOR_MODE = "mock"   -> MockDetector      (no ML deps, always works)
    DETECTOR_MODE = "yolo"   -> YoloDetector      (Ultralytics + your weights)
"""
from config import DETECTOR_MODE
from detector.base import Detection, Detector
from detector.mock_detector import MockDetector

_instance: Detector | None = None


def get_detector() -> Detector:
    """Return the process-wide detector, building it on first use."""
    global _instance
    if _instance is None:
        _instance = _build(DETECTOR_MODE)
    return _instance


def set_detector(detector: Detector) -> None:
    """Override the detector (used by tests and the seed script)."""
    global _instance
    _instance = detector


def _build(mode: str) -> Detector:
    if mode == "yolo":
        # Imported lazily so `ultralytics` is only required in yolo mode.
        from detector.yolo_detector import YoloDetector

        try:
            return YoloDetector()
        except Exception as exc:  # pragma: no cover - demo safety net
            print(f"[rainguard] YOLO unavailable ({exc}); falling back to mock.")
            return MockDetector()
    return MockDetector()


__all__ = ["Detection", "Detector", "MockDetector", "get_detector", "set_detector"]
