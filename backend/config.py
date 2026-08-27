"""
Central tuning knobs for the RainGuard prototype.

Everything a demo operator might want to change lives here, so students can
tweak behaviour without hunting through the code.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
IMAGE_DIR = STORAGE_DIR / "images"
# Postgres in production (Neon, via DATABASE_URL), SQLite locally.
# SQLAlchemy needs the "postgresql+psycopg://" prefix; Neon hands out
# "postgres://", so normalise it.
_DB_URL = os.environ.get("DATABASE_URL", "")
if _DB_URL.startswith("postgres://"):
    _DB_URL = _DB_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif _DB_URL.startswith("postgresql://"):
    _DB_URL = _DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)
DATABASE_URL = _DB_URL or f"sqlite:///{STORAGE_DIR / 'rainguard.db'}"

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
DETECTOR_MODE = os.environ.get("DETECTOR_MODE", "mock")
YOLO_WEIGHTS_PATH = BASE_DIR.parent / "model" / "rainguard.pt"
YOLO_CONFIDENCE_THRESHOLD = 0.35

# --- Map ------------------------------------------------------------------
MANIPAL_CENTRE = (13.3525, 74.7868)

# Only meaningful for local disk storage; harmless (and skipped) on a
# read-only serverless filesystem.
try:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
