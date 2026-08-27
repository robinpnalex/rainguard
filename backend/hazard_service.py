"""
Hazard lifecycle: ingestion, deduplication, severity, repair verification.

This is the heart of the prototype. The API layer in main.py is thin; the
rules live here.

Status transitions
------------------

    (new detection)                -> SUSPECTED
    SUSPECTED  + 3 observations    -> CONFIRMED
    any open   + "mark repaired"   -> REPAIR_PENDING
    REPAIR_PENDING + clean check   -> REPAIRED
    REPAIRED   + 3 clean checks    -> VERIFIED        (closed)
    REPAIR_PENDING/REPAIRED
        + hazard detected again    -> CONFIRMED, verification_failed = True

A "clean check" is a re-inspection image from roughly the same location in
which the detector did NOT find this hazard type.
"""
from datetime import datetime
from pathlib import Path

import severity as severity_module
from config import CLEAN_OBSERVATIONS_FOR_VERIFIED, OBSERVATIONS_FOR_CONFIRMED
from dedup import find_matching_hazard
from models import (
    STATUS_CONFIRMED,
    STATUS_REPAIR_PENDING,
    STATUS_REPAIRED,
    STATUS_SUSPECTED,
    STATUS_VERIFIED,
    Hazard,
    Observation,
    utcnow,
)
from sqlalchemy.orm import Session

# Statuses that mean "a repair is being checked".
UNDER_REPAIR = (STATUS_REPAIR_PENDING, STATUS_REPAIRED)


def record_detection(
    db: Session,
    *,
    hazard_type: str,
    confidence: float,
    latitude: float,
    longitude: float,
    image_path: str | None = None,
    location_source: str = "manual",
    timestamp: datetime | None = None,
) -> tuple[Hazard, bool]:
    """
    Fold one detection into the hazard map.

    Returns (hazard, is_new_hazard).
    """
    seen_at = timestamp or utcnow()
    hazard = find_matching_hazard(db, hazard_type, latitude, longitude)
    is_new = hazard is None

    if is_new:
        hazard = Hazard(
            type=hazard_type,
            latitude=latitude,
            longitude=longitude,
            observation_count=0,
            avg_confidence=0.0,
            status=STATUS_SUSPECTED,
            first_seen=seen_at,
            last_seen=seen_at,
        )
        db.add(hazard)
        db.flush()  # assign hazard.id before we attach the observation

    # Running mean of confidence, and a position that drifts toward the
    # centroid of its observations so repeated GPS noise averages out.
    n = hazard.observation_count
    hazard.avg_confidence = round((hazard.avg_confidence * n + confidence) / (n + 1), 3)
    hazard.latitude = (hazard.latitude * n + latitude) / (n + 1)
    hazard.longitude = (hazard.longitude * n + longitude) / (n + 1)
    hazard.observation_count = n + 1
    hazard.last_seen = max(hazard.last_seen, seen_at)

    db.add(
        Observation(
            hazard_id=hazard.id,
            type=hazard_type,
            confidence=confidence,
            latitude=latitude,
            longitude=longitude,
            timestamp=seen_at,
            image_path=image_path,
            location_source=location_source,
            is_clean=False,
        )
    )

    if hazard.status in UNDER_REPAIR:
        # The hazard is still there. The repair did not work.
        hazard.verification_failed = True
        hazard.clean_observation_count = 0
        hazard.status = STATUS_CONFIRMED
    elif hazard.observation_count >= OBSERVATIONS_FOR_CONFIRMED:
        hazard.status = STATUS_CONFIRMED
    else:
        hazard.status = STATUS_SUSPECTED

    _recompute_severity(hazard)
    db.commit()
    db.refresh(hazard)
    return hazard, is_new


def record_clean_observation(
    db: Session,
    hazard: Hazard,
    *,
    latitude: float,
    longitude: float,
    image_path: str | None = None,
    location_source: str = "manual",
    timestamp: datetime | None = None,
) -> Hazard:
    """A re-inspection that did NOT find the hazard: progress toward VERIFIED."""
    seen_at = timestamp or utcnow()

    db.add(
        Observation(
            hazard_id=hazard.id,
            type=hazard.type,
            confidence=0.0,
            latitude=latitude,
            longitude=longitude,
            timestamp=seen_at,
            image_path=image_path,
            location_source=location_source,
            is_clean=True,
        )
    )

    hazard.clean_observation_count += 1
    hazard.verification_failed = False
    hazard.last_seen = max(hazard.last_seen, seen_at)

    if hazard.clean_observation_count >= CLEAN_OBSERVATIONS_FOR_VERIFIED:
        hazard.status = STATUS_VERIFIED
    else:
        hazard.status = STATUS_REPAIRED

    db.commit()
    db.refresh(hazard)
    return hazard


def mark_repaired(db: Session, hazard: Hazard) -> Hazard:
    """Municipality claims the hazard is fixed. It is not VERIFIED until checked."""
    hazard.status = STATUS_REPAIR_PENDING
    hazard.repair_requested_at = utcnow()
    hazard.clean_observation_count = 0
    hazard.verification_failed = False
    db.commit()
    db.refresh(hazard)
    return hazard


def reopen(db: Session, hazard: Hazard) -> Hazard:
    """Undo a repair claim (demo convenience / operator mistake)."""
    hazard.status = (
        STATUS_CONFIRMED
        if hazard.observation_count >= OBSERVATIONS_FOR_CONFIRMED
        else STATUS_SUSPECTED
    )
    hazard.repair_requested_at = None
    hazard.clean_observation_count = 0
    hazard.verification_failed = False
    db.commit()
    db.refresh(hazard)
    return hazard


def _recompute_severity(hazard: Hazard) -> None:
    hazard.severity = severity_module.score(
        hazard.type, hazard.avg_confidence, hazard.observation_count
    )


def latest_images(hazard: Hazard) -> dict[str, str | None]:
    """
    Before/after pair for the dashboard.

    'before' = the most recent image in which the hazard WAS detected.
    'after'  = the most recent clean re-inspection image.

    Showing both is what makes repair verification credible: a human can see
    that the "after" photo is actually the same stretch of road, rather than
    trusting the absence of a detection on its own.
    """
    before = after = None
    for obs in hazard.observations:
        if obs.image_path is None:
            continue
        if obs.is_clean:
            after = obs.image_path
        else:
            before = obs.image_path
    return {"before": before, "after": after}
