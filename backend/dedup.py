"""
Hazard deduplication.

Deliberately not a clustering algorithm. When a detection arrives we look for
an existing hazard of the *same type* within DEDUP_RADIUS_METRES and treat the
detection as another observation of it. Otherwise we create a new hazard.

Repaired/verified hazards are excluded from matching, so a pothole that
reappears after a bad repair becomes a new hazard rather than silently
reopening the old one -- which is what a municipality would want to see.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import DEDUP_RADIUS_METRES
from geo import bounding_box, distance_metres
from models import STATUS_VERIFIED, Hazard

# Statuses that are "closed" and should not absorb new sightings.
CLOSED_STATUSES = (STATUS_VERIFIED,)


def find_matching_hazard(
    db: Session,
    hazard_type: str,
    latitude: float,
    longitude: float,
    radius_m: float = DEDUP_RADIUS_METRES,
) -> Hazard | None:
    """Nearest open hazard of this type within `radius_m`, or None."""
    min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius_m)

    # Cheap SQL box filter first, exact great-circle distance second.
    candidates = db.scalars(
        select(Hazard).where(
            Hazard.type == hazard_type,
            Hazard.status.not_in(CLOSED_STATUSES),
            Hazard.latitude.between(min_lat, max_lat),
            Hazard.longitude.between(min_lon, max_lon),
        )
    ).all()

    best: Hazard | None = None
    best_distance = radius_m
    for hazard in candidates:
        d = distance_metres(latitude, longitude, hazard.latitude, hazard.longitude)
        if d <= best_distance:
            best, best_distance = hazard, d
    return best


def find_hazards_near(
    db: Session,
    latitude: float,
    longitude: float,
    radius_m: float = DEDUP_RADIUS_METRES,
    hazard_type: str | None = None,
) -> list[Hazard]:
    """All hazards near a point, nearest first. Used by repair verification."""
    min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius_m)

    query = select(Hazard).where(
        Hazard.latitude.between(min_lat, max_lat),
        Hazard.longitude.between(min_lon, max_lon),
    )
    if hazard_type:
        query = query.where(Hazard.type == hazard_type)

    nearby = [
        (distance_metres(latitude, longitude, h.latitude, h.longitude), h)
        for h in db.scalars(query).all()
    ]
    return [h for d, h in sorted(nearby, key=lambda pair: pair[0]) if d <= radius_m]
