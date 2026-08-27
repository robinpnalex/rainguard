"""
Severity scoring, 1-10.

Kept deliberately simple and in its own module so it can be replaced later
with something better (traffic volume, road class, rainfall, pedestrian
density, repair cost...) without touching the rest of the app.

The current model is a weighted sum of three factors:

    severity = base_risk(type) + confidence_bonus + repetition_bonus

* base_risk       -- an open manhole is far more dangerous than a small
                     pothole, regardless of how it was detected.
* confidence_bonus -- the detector being sure it saw something.
* repetition_bonus -- a hazard reported over and over is both more likely to
                     be real and more likely to be on a busy road.
"""

# Intrinsic danger of each hazard type, on the 1-10 scale.
BASE_RISK = {
    "manhole": 6.5,      # open/damaged manhole: can swallow a wheel or a person
    "waterlogging": 4.5,  # hides whatever is underneath, causes skids
    "pothole": 3.5,
}
DEFAULT_BASE_RISK = 3.5

MAX_CONFIDENCE_BONUS = 2.0
MAX_REPETITION_BONUS = 2.5
# Observations at which the repetition bonus saturates.
REPETITION_SATURATION = 6


def score(hazard_type: str, confidence: float, observation_count: int) -> float:
    """Return a severity score clamped to [1.0, 10.0], rounded to 1 decimal."""
    base = BASE_RISK.get(hazard_type, DEFAULT_BASE_RISK)

    confidence_bonus = MAX_CONFIDENCE_BONUS * _clamp01(confidence)

    repetition = min(max(observation_count - 1, 0), REPETITION_SATURATION - 1)
    repetition_bonus = MAX_REPETITION_BONUS * (repetition / (REPETITION_SATURATION - 1))

    return round(min(max(base + confidence_bonus + repetition_bonus, 1.0), 10.0), 1)


def band(severity: float) -> str:
    """Coarse risk band used for map marker colours."""
    if severity >= 7.0:
        return "high"
    if severity >= 5.0:
        return "medium"
    return "low"


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)
