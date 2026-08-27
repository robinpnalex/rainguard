"""
Ultralytics YOLO detector.

To use your own fine-tuned model:

  1. Train a YOLO model on pothole / manhole / waterlogging images
     (Roboflow Universe has ready-made datasets, and several pretrained
     pothole models you can download directly).
  2. Drop the weights at  model/rainguard.pt
  3. Set DETECTOR_MODE = "yolo" in backend/config.py
  4. Map your model's class names onto RainGuard's three types in
     CLASS_NAME_MAP below.

Nothing else in the application changes -- this class satisfies the same
`Detector` interface as MockDetector.
"""
from pathlib import Path

from config import YOLO_CONFIDENCE_THRESHOLD, YOLO_WEIGHTS_PATH
from detector.base import Detection

# Your model's class names (lower-cased) -> RainGuard hazard types.
# Extend this when your label set differs.
CLASS_NAME_MAP = {
    "pothole": "pothole",
    "potholes": "pothole",
    "crack": "pothole",
    "manhole": "manhole",
    "open manhole": "manhole",
    "damaged manhole": "manhole",
    "waterlogging": "waterlogging",
    "water": "waterlogging",
    "puddle": "waterlogging",
    "flood": "waterlogging",
}


class YoloDetector:
    name = "yolo"

    def __init__(self, weights: Path | None = None):
        from ultralytics import YOLO  # imported here so mock mode needs no ML deps

        self.weights = Path(weights or YOLO_WEIGHTS_PATH)
        if not self.weights.exists():
            raise FileNotFoundError(
                f"YOLO weights not found at {self.weights}. "
                "See model/README.md, or keep DETECTOR_MODE = 'mock'."
            )
        self.model = YOLO(str(self.weights))

    def detect(self, data: bytes, filename: str = "") -> list[Detection]:
        import io

        from PIL import Image

        image = Image.open(io.BytesIO(data)).convert("RGB")
        results = self.model.predict(
            source=image,
            conf=YOLO_CONFIDENCE_THRESHOLD,
            verbose=False,
        )

        detections: list[Detection] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                raw_label = str(names[int(box.cls)]).lower()
                hazard_type = CLASS_NAME_MAP.get(raw_label)
                if hazard_type is None:
                    continue  # a class we do not care about
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                detections.append(
                    Detection(hazard_type, round(float(box.conf), 2), (x1, y1, x2, y2))
                )
        return detections
