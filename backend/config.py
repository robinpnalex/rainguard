"""
Central tuning knobs for the NIRVANA prototype.

Everything a demo operator might want to change lives here, so students can
tweak behaviour without hunting through the code.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
IMAGE_DIR = STORAGE_DIR / "images"
DATABASE_URL = f"sqlite:///{STORAGE_DIR / 'nirvana.db'}"

# --- Hazard deduplication -------------------------------------------------
# Two detections of the same type within this many metres are treated as the
# same physical hazard.
#
# Why 25 m and not 10 m: consumer GPS is accurate to roughly 5-15 m outdoors
# and much worse under tree cover, so a 10 m radius routinely splits repeat
# sightings of one pothole into several hazards -- which breaks the
# "3 observations -> CONFIRMED" story during a demo. 25 m slightly
# over-merges, and that is the right trade-off for a prototype.
DEDUP_RADIUS_METRES = 25.0

# --- Hazard lifecycle -----------------------------------------------------
OBSERVATIONS_FOR_CONFIRMED = 3
CLEAN_OBSERVATIONS_FOR_VERIFIED = 3

# --- Detection ------------------------------------------------------------
# "mock" -> deterministic fake detector, no ML dependencies required.
# "yolo" -> Ultralytics YOLO, see detector/yolo_detector.py
DETECTOR_MODE = "mock"
YOLO_WEIGHTS_PATH = BASE_DIR.parent / "model" / "nirvana.pt"
YOLO_CONFIDENCE_THRESHOLD = 0.35

# --- Map ------------------------------------------------------------------
MANIPAL_CENTRE = (13.3525, 74.7868)

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
