"""The detector contract. Implement this to plug in your own model."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Detection:
    """One hazard found in one image."""

    type: str          # "pothole" | "manhole" | "waterlogging"
    confidence: float  # 0.0 - 1.0
    # Optional pixel box, kept so a future UI can draw it. (x1, y1, x2, y2)
    box: tuple[float, float, float, float] | None = None


class Detector(Protocol):
    """Anything that can turn an image into a list of Detections."""

    name: str

    def detect(self, image_path: Path) -> list[Detection]:
        ...
