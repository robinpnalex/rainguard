"""
Demo data and the scripted demo story.

Why this module exists: a live demo that depends on real uploads, real GPS and
venue wifi is a demo that fails on stage. `/demo/seed` fills the map with
plausible Manipal hazards in a second, and `/demo/story` replays the entire
lifecycle -- detect, repeat sighting, confirm, repair, verify -- deterministically.
"""
import random
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

import demo_images
import hazard_service
from config import (
    CLEAN_OBSERVATIONS_FOR_VERIFIED,
    DEDUP_RADIUS_METRES,
    OBSERVATIONS_FOR_CONFIRMED,
)
from database import get_db
from models import STATUS_VERIFIED, Hazard, Observation, utcnow

router = APIRouter(prefix="/demo", tags=["demo"])

# Real places around Manipal, so the seeded map looks like somewhere.
SEED_SITES = [
    ("Tiger Circle",            13.34670, 74.78690, "pothole",      6, 4),
    ("End Point Road",          13.35120, 74.77880, "waterlogging", 4, 2),
    ("MIT Main Gate",           13.35250, 74.79300, "manhole",      3, 6),
    ("Syndicate Circle",        13.34960, 74.78620, "pothole",      1, 1),
    ("Manipal Lake Road",       13.34210, 74.78560, "waterlogging", 2, 3),
    ("Eshwar Nagar",            13.35620, 74.78970, "pothole",      5, 9),
    ("Kunjibettu Junction",     13.33890, 74.77910, "manhole",      1, 2),
    ("Alevoor Road",            13.35830, 74.78120, "pothole",      2, 5),
]
# Sites that get walked further along the lifecycle after seeding.
REPAIR_PENDING_SITE = ("Perampalli Road", 13.36110, 74.77340, "pothole", 4, 7)
VERIFIED_SITE = ("Udupi-Manipal Road", 13.34480, 74.77490, "waterlogging", 4, 12)

# A quiet spot with no seeded hazard, reserved for the scripted story.
STORY_SITE = ("Vidyaratna Road", 13.35410, 74.78430, "pothole")


def wipe(db: Session) -> dict:
    """Delete every hazard, observation and stored image."""
    db.execute(delete(Observation))
    db.execute(delete(Hazard))
    db.commit()
    return {"images_removed": demo_images.cleanup()}


def seed(db: Session) -> list[Hazard]:
    """Populate the map with a realistic spread of Manipal hazards."""
    rng = random.Random(20260827)  # fixed seed: the demo looks the same every time
    now = utcnow()
    created: list[Hazard] = []

    def observe(name, lat, lon, hazard_type, count, days_ago, clean_run=0):
        hazard = None
        for i in range(count):
            # Scatter repeat sightings by a few metres, as real GPS would.
            jitter_lat = lat + rng.uniform(-0.00008, 0.00008)
            jitter_lon = lon + rng.uniform(-0.00008, 0.00008)
            seen_at = now - timedelta(days=days_ago, hours=-6 * i)
            image = demo_images.make_image(
                hazard_type,
                f"{name} - {hazard_type} - sighting {i + 1}",
                f"seed_{hazard_type}_{name.replace(' ', '_').replace('-', '_')}_{i}.jpg",
            )
            hazard, _ = hazard_service.record_detection(
                db,
                hazard_type=hazard_type,
                confidence=round(rng.uniform(0.62, 0.96), 2),
                latitude=jitter_lat,
                longitude=jitter_lon,
                image_path=image,
                location_source="seed",
                timestamp=seen_at,
            )
        return hazard

    for name, lat, lon, hazard_type, count, days_ago in SEED_SITES:
        created.append(observe(name, lat, lon, hazard_type, count, days_ago))

    # One hazard already waiting on a repair check.
    name, lat, lon, hazard_type, count, days_ago = REPAIR_PENDING_SITE
    pending = observe(name, lat, lon, hazard_type, count, days_ago)
    hazard_service.mark_repaired(db, pending)
    created.append(pending)

    # One hazard fully closed out, so the map shows a resolved marker.
    name, lat, lon, hazard_type, count, days_ago = VERIFIED_SITE
    done = observe(name, lat, lon, hazard_type, count, days_ago)
    hazard_service.mark_repaired(db, done)
    for i in range(CLEAN_OBSERVATIONS_FOR_VERIFIED):
        image = demo_images.make_image(
            "clean", f"{name} - re-inspection {i + 1} - clear", f"seed_clean_{i}.jpg"
        )
        hazard_service.record_clean_observation(
            db, done,
            latitude=lat, longitude=lon,
            image_path=image, location_source="seed",
            timestamp=now - timedelta(days=1, hours=-4 * i),
        )
    created.append(done)

    return created


@router.post("/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Wipe everything. Use before a rehearsal."""
    return {"message": "Database cleared.", **wipe(db)}


@router.post("/seed")
def demo_seed(reset: bool = True, db: Session = Depends(get_db)):
    """Fill the map with sample Manipal hazards."""
    result = wipe(db) if reset else {}
    hazards = seed(db)
    return {
        "message": f"Seeded {len(hazards)} hazards around Manipal.",
        "hazard_ids": [h.id for h in hazards],
        **result,
    }


@router.post("/story")
def demo_story(fail_first_repair: bool = False, db: Session = Depends(get_db)):
    """
    Replay the full hazard lifecycle on a fresh hazard and return every step.

    This is the sequence to show judges:
        detect -> repeat sighting strengthens it -> CONFIRMED
        -> municipality marks repaired -> clean re-inspections -> VERIFIED

    With `fail_first_repair=true` the first re-inspection still finds the
    hazard, demonstrating that a repair claim alone does not close a hazard.
    """
    name, lat, lon, hazard_type = STORY_SITE
    now = utcnow()
    steps: list[dict] = []
    hazard = None

    def snapshot(title: str, detail: str):
        steps.append({
            "step": len(steps) + 1,
            "title": title,
            "detail": detail,
            "hazard_id": hazard.id,
            "status": hazard.status,
            "severity": hazard.severity,
            "observation_count": hazard.observation_count,
            "clean_observation_count": hazard.clean_observation_count,
            "verification_failed": hazard.verification_failed,
        })

    # 1-3: repeated sightings drive SUSPECTED -> CONFIRMED
    for i in range(OBSERVATIONS_FOR_CONFIRMED):
        image = demo_images.make_image(
            hazard_type,
            f"{name} - citizen report {i + 1}",
            f"story_{hazard_type}_{i}_{now.timestamp():.0f}.jpg",
        )
        hazard, is_new = hazard_service.record_detection(
            db,
            hazard_type=hazard_type,
            confidence=[0.71, 0.84, 0.93][i],
            latitude=lat + (i * 0.00005),
            longitude=lon + (i * 0.00004),
            image_path=image,
            location_source="seed",
            timestamp=now + timedelta(minutes=i),
        )
        if is_new:
            snapshot(
                f"New {hazard_type} detected at {name}",
                f"First sighting. One observation, so it is only SUSPECTED "
                f"(severity {hazard.severity}/10).",
            )
        else:
            snapshot(
                f"Repeat sighting #{hazard.observation_count}",
                f"Within {DEDUP_RADIUS_METRES:.0f} m of hazard "
                f"#{hazard.id}, so it merges instead of creating a duplicate. "
                f"Severity is now {hazard.severity}/10, status {hazard.status}.",
            )

    # 4: municipality claims the repair
    hazard = hazard_service.mark_repaired(db, hazard)
    snapshot(
        "Municipality marks it repaired",
        "Status is REPAIR_PENDING, not REPAIRED. A repair claim alone does not "
        "close a hazard -- it has to be proven by later observations.",
    )

    # 5 (optional): the repair did not hold
    if fail_first_repair:
        image = demo_images.make_image(
            hazard_type, f"{name} - re-inspection - still damaged",
            f"story_fail_{now.timestamp():.0f}.jpg",
        )
        hazard, _ = hazard_service.record_detection(
            db,
            hazard_type=hazard_type, confidence=0.89,
            latitude=lat, longitude=lon,
            image_path=image, location_source="seed",
        )
        snapshot(
            "Repair check FAILED",
            "The re-inspection photo still shows the hazard, so it reopens as "
            "CONFIRMED and the clean-observation counter resets to zero.",
        )
        hazard = hazard_service.mark_repaired(db, hazard)
        snapshot("Marked repaired again", "Second repair attempt, awaiting proof.")

    # 6-8: clean re-inspections close it out
    for i in range(CLEAN_OBSERVATIONS_FOR_VERIFIED):
        image = demo_images.make_image(
            "clean", f"{name} - re-inspection {i + 1} - clear",
            f"story_clean_{i}_{now.timestamp():.0f}.jpg",
        )
        hazard = hazard_service.record_clean_observation(
            db, hazard,
            latitude=lat, longitude=lon,
            image_path=image, location_source="seed",
            timestamp=now + timedelta(hours=i + 1),
        )
        if hazard.status == STATUS_VERIFIED:
            snapshot(
                "Repair VERIFIED",
                f"{CLEAN_OBSERVATIONS_FOR_VERIFIED} independent re-inspections "
                "found nothing. The hazard is closed and drops off the active map.",
            )
        else:
            snapshot(
                f"Clean re-inspection {hazard.clean_observation_count}/"
                f"{CLEAN_OBSERVATIONS_FOR_VERIFIED}",
                "No hazard detected at this location. Status REPAIRED, "
                "still awaiting further confirmation.",
            )

    return {"hazard_id": hazard.id, "steps": steps}
