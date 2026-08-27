"""
Deterministic stand-in for a trained model.

Why this exists: an off-the-shelf YOLO model knows COCO classes (person, car,
dog...) and cannot detect potholes, manholes or waterlogging at all. Until
custom weights are trained, this detector lets the *entire* application --
dedup, severity, repair verification, the map -- be built and demonstrated.

It is deterministic, which matters on demo day: the same image always
produces the same result.

How it decides what is in an image:

1. Filename hints win. This is the demo lever -- name a file
   `pothole_manipal.jpg` and you get a pothole; name it `clean_road.jpg`
   and you get nothing (which is how a repair gets verified).
2. Otherwise it hashes the file's bytes and derives a stable pseudo-random
   type and confidence from the digest.
"""
import hashlib

from detector.base import Detection

# Substrings checked against the lower-cased filename, in order.
TYPE_HINTS = {
    "pothole": "pothole",
    "crater": "pothole",
    "manhole": "manhole",
    "drain": "manhole",
    "waterlog": "waterlogging",
    "flood": "waterlogging",
    "water": "waterlogging",
}
# A filename containing any of these means "no hazard here" -- used to
# demonstrate a successful repair verification.
CLEAN_HINTS = ("clean", "repaired", "fixed", "ok_", "smooth")

CYCLE = ("pothole", "manhole", "waterlogging")


class MockDetector:
    name = "mock"

    def detect(self, data: bytes, filename: str = "") -> list[Detection]:
        filename = filename.lower()

        if any(hint in filename for hint in CLEAN_HINTS):
            return []

        for hint, hazard_type in TYPE_HINTS.items():
            if hint in filename:
                return [Detection(hazard_type, self._confidence(data, 0.78, 0.97))]

        digest = self._digest(data)
        # 1 image in 8 is "clean" so the mock is not implausibly eager.
        if digest[0] % 8 == 0:
            return []

        hazard_type = CYCLE[digest[1] % len(CYCLE)]
        return [Detection(hazard_type, self._confidence(data, 0.55, 0.95))]

    # -- internals ---------------------------------------------------------

    def _digest(self, data: bytes) -> bytes:
        return hashlib.sha256(data or b"empty").digest()

    def _confidence(self, data: bytes, low: float, high: float) -> float:
        # Map digest byte -> [low, high], stable across runs.
        fraction = self._digest(data)[2] / 255.0
        return round(low + (high - low) * fraction, 2)
