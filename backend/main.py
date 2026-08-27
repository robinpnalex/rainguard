"""
RainGuard API.

Thin HTTP layer. The interesting logic lives in hazard_service.py,
dedup.py, severity.py and detector/.
"""
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import demo
import hazard_service
import location as location_module
import schemas
from config import (
    CLEAN_OBSERVATIONS_FOR_VERIFIED,
    DEDUP_RADIUS_METRES,
    IMAGE_DIR,
    MANIPAL_CENTRE,
    OBSERVATIONS_FOR_CONFIRMED,
)
from database import get_db, init_db
from dedup import find_hazards_near
from detector import get_detector
from models import HAZARD_TYPES, STATUS_VERIFIED, Hazard

app = FastAPI(
    title="RainGuard",
    description="AI-assisted road hazard monitoring for Manipal.",
    version="0.1.0",
)

# The dashboard runs on a different port in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(demo.router)
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------------------------------------------------------
# Serialisation helpers
# --------------------------------------------------------------------------

def _image_url(path: str | None) -> str | None:
    return f"/images/{path}" if path else None


def _hazard_out(hazard: Hazard, detail: bool = False):
    images = hazard_service.latest_images(hazard)
    payload = {
        "id": hazard.id,
        "type": hazard.type,
        "latitude": round(hazard.latitude, 7),
        "longitude": round(hazard.longitude, 7),
        "observation_count": hazard.observation_count,
        "avg_confidence": hazard.avg_confidence,
        "severity": hazard.severity,
        "risk_band": schemas.risk_band(hazard.severity),
        "status": hazard.status,
        "first_seen": hazard.first_seen,
        "last_seen": hazard.last_seen,
        "repair_requested_at": hazard.repair_requested_at,
        "clean_observation_count": hazard.clean_observation_count,
        "clean_observations_required": CLEAN_OBSERVATIONS_FOR_VERIFIED,
        "verification_failed": hazard.verification_failed,
        "before_image_url": _image_url(images["before"]),
        "after_image_url": _image_url(images["after"]),
    }
    if not detail:
        return schemas.HazardOut(**payload)

    payload["observations"] = [
        schemas.ObservationOut(
            id=o.id,
            type=o.type,
            confidence=o.confidence,
            latitude=round(o.latitude, 7),
            longitude=round(o.longitude, 7),
            timestamp=o.timestamp,
            image_path=o.image_path,
            image_url=_image_url(o.image_path),
            location_source=o.location_source,
            is_clean=o.is_clean,
        )
        for o in hazard.observations
    ]
    return schemas.HazardDetailOut(**payload)


def _save_upload(image: UploadFile | None) -> Path | None:
    if image is None or not image.filename:
        return None
    # Keep the original name in the stored filename: the mock detector reads
    # filename hints, and it makes the storage folder readable during a demo.
    safe_name = Path(image.filename).name.replace(" ", "_")
    stored = IMAGE_DIR / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    with stored.open("wb") as fh:
        shutil.copyfileobj(image.file, fh)
    return stored


def _get_hazard_or_404(db: Session, hazard_id: int) -> Hazard:
    hazard = db.get(Hazard, hazard_id)
    if hazard is None:
        raise HTTPException(status_code=404, detail=f"Hazard {hazard_id} not found")
    return hazard


# --------------------------------------------------------------------------
# Meta
# --------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "detector": get_detector().name,
        "dedup_radius_metres": DEDUP_RADIUS_METRES,
        "observations_for_confirmed": OBSERVATIONS_FOR_CONFIRMED,
        "clean_observations_for_verified": CLEAN_OBSERVATIONS_FOR_VERIFIED,
        "map_centre": {"latitude": MANIPAL_CENTRE[0], "longitude": MANIPAL_CENTRE[1]},
        "hazard_types": list(HAZARD_TYPES),
    }


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Hazard.status, func.count(Hazard.id)).group_by(Hazard.status)
    ).all()
    by_status = {status: count for status, count in rows}

    type_rows = db.execute(
        select(Hazard.type, func.count(Hazard.id)).group_by(Hazard.type)
    ).all()

    total = sum(by_status.values())
    high_risk = db.scalar(
        select(func.count(Hazard.id)).where(
            Hazard.severity >= 7.0, Hazard.status != STATUS_VERIFIED
        )
    )
    return {
        "total_hazards": total,
        "open_hazards": total - by_status.get(STATUS_VERIFIED, 0),
        "high_risk_open": high_risk or 0,
        "by_status": by_status,
        "by_type": {t: c for t, c in type_rows},
        "total_observations": db.scalar(
            select(func.coalesce(func.sum(Hazard.observation_count), 0))
        ),
    }


# --------------------------------------------------------------------------
# Detections
# --------------------------------------------------------------------------

@app.post("/detections", response_model=schemas.DetectionResultOut)
def create_detection(
    image: UploadFile | None = File(default=None),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    location_source: str | None = Form(default=None),
    hazard_type: str | None = Form(default=None),
    confidence: float | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Ingest one road image.

    Location comes from (in priority order) the posted latitude/longitude,
    the image's EXIF GPS, or nothing -- in which case the request is rejected
    rather than guessed at.

    `hazard_type` + `confidence` bypass the detector entirely. That is how the
    seed script and the demo replay stay deterministic.
    """
    stored_path = _save_upload(image)

    resolved = location_module.resolve(latitude, longitude, stored_path, location_source)
    if resolved is None:
        if stored_path:
            stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=(
                "No location. Post latitude/longitude, or upload a photo that "
                "still carries EXIF GPS."
            ),
        )
    lat, lon, source = resolved

    detector = get_detector()
    if hazard_type:
        if hazard_type not in HAZARD_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"hazard_type must be one of {list(HAZARD_TYPES)}",
            )
        found = [(hazard_type, confidence if confidence is not None else 0.9)]
        detector_name = "manual"
    else:
        if stored_path is None:
            raise HTTPException(
                status_code=422,
                detail="Provide an image to run detection on, or an explicit hazard_type.",
            )
        found = [(d.type, d.confidence) for d in detector.detect(stored_path)]
        detector_name = detector.name

    image_name = stored_path.name if stored_path else None
    created, updated, hazards = [], [], []

    for found_type, found_conf in found:
        hazard, is_new = hazard_service.record_detection(
            db,
            hazard_type=found_type,
            confidence=float(found_conf),
            latitude=lat,
            longitude=lon,
            image_path=image_name,
            location_source=source,
        )
        (created if is_new else updated).append(hazard.id)
        hazards.append(_hazard_out(hazard))

    if not found:
        message = "No hazard detected in this image."
    elif created and updated:
        message = f"{len(created)} new hazard(s), {len(updated)} repeat sighting(s)."
    elif created:
        message = f"New hazard(s) recorded: {', '.join(f'#{i}' for i in created)}."
    else:
        message = f"Repeat sighting of hazard(s) {', '.join(f'#{i}' for i in updated)}."

    return schemas.DetectionResultOut(
        detector=detector_name,
        detections_found=len(found),
        location_source=source,
        latitude=round(lat, 7),
        longitude=round(lon, 7),
        image_url=_image_url(image_name),
        hazards=hazards,
        created_hazard_ids=created,
        updated_hazard_ids=updated,
        message=message,
    )


# --------------------------------------------------------------------------
# Hazards
# --------------------------------------------------------------------------

@app.get("/hazards", response_model=list[schemas.HazardOut])
def list_hazards(
    status: str | None = None,
    type: str | None = None,
    min_severity: float | None = None,
    include_verified: bool = True,
    db: Session = Depends(get_db),
):
    query = select(Hazard)
    if status:
        query = query.where(Hazard.status == status.upper())
    if type:
        query = query.where(Hazard.type == type)
    if min_severity is not None:
        query = query.where(Hazard.severity >= min_severity)
    if not include_verified:
        query = query.where(Hazard.status != STATUS_VERIFIED)

    hazards = db.scalars(query.order_by(Hazard.severity.desc(), Hazard.id)).all()
    return [_hazard_out(h) for h in hazards]


@app.get("/hazards/{hazard_id}", response_model=schemas.HazardDetailOut)
def get_hazard(hazard_id: int, db: Session = Depends(get_db)):
    return _hazard_out(_get_hazard_or_404(db, hazard_id), detail=True)


@app.post("/hazards/{hazard_id}/repair", response_model=schemas.HazardDetailOut)
def mark_repaired(hazard_id: int, db: Session = Depends(get_db)):
    """Municipality claims this is fixed -> REPAIR_PENDING, awaiting proof."""
    hazard = _get_hazard_or_404(db, hazard_id)
    if hazard.status == STATUS_VERIFIED:
        raise HTTPException(status_code=409, detail="Hazard is already verified.")
    return _hazard_out(hazard_service.mark_repaired(db, hazard), detail=True)


@app.post("/hazards/{hazard_id}/reopen", response_model=schemas.HazardDetailOut)
def reopen_hazard(hazard_id: int, db: Session = Depends(get_db)):
    """Undo a repair claim."""
    hazard = _get_hazard_or_404(db, hazard_id)
    return _hazard_out(hazard_service.reopen(db, hazard), detail=True)


@app.post("/hazards/{hazard_id}/verify", response_model=schemas.VerificationResultOut)
def verify_repair(
    hazard_id: int,
    image: UploadFile | None = File(default=None),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    location_source: str | None = Form(default=None),
    simulate: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Re-inspect a hazard that was marked repaired.

    Upload a photo from roughly the same spot. If the detector still finds the
    hazard the repair check fails and the hazard goes back to CONFIRMED. If it
    does not, that counts as one clean observation; three clean observations
    mark the hazard VERIFIED.

    `simulate=clean|still_there` skips the detector. It exists so the demo
    replay is deterministic -- do not present it as the real mechanism.
    """
    hazard = _get_hazard_or_404(db, hazard_id)
    if hazard.status == STATUS_VERIFIED:
        raise HTTPException(status_code=409, detail="Hazard is already verified.")

    stored_path = _save_upload(image)

    # Fall back to the hazard's own coordinates: the inspector is standing at
    # a known hazard, so we do not need a fresh fix to proceed.
    resolved = location_module.resolve(latitude, longitude, stored_path, location_source)
    lat, lon, source = resolved or (hazard.latitude, hazard.longitude, "manual")

    if simulate in ("clean", "still_there"):
        still_detected = simulate == "still_there"
        confidence = 0.88
    elif stored_path is not None:
        detections = get_detector().detect(stored_path)
        match = next((d for d in detections if d.type == hazard.type), None)
        still_detected = match is not None
        confidence = match.confidence if match else 0.0
    else:
        raise HTTPException(
            status_code=422,
            detail="Upload a re-inspection photo, or pass simulate=clean|still_there.",
        )

    image_name = stored_path.name if stored_path else None

    if still_detected:
        hazard, _ = hazard_service.record_detection(
            db,
            hazard_type=hazard.type,
            confidence=float(confidence),
            latitude=lat,
            longitude=lon,
            image_path=image_name,
            location_source=source,
        )
        message = (
            f"Repair check FAILED - {hazard.type} still detected. "
            f"Hazard #{hazard.id} reopened as {hazard.status}."
        )
    else:
        hazard = hazard_service.record_clean_observation(
            db,
            hazard,
            latitude=lat,
            longitude=lon,
            image_path=image_name,
            location_source=source,
        )
        if hazard.status == STATUS_VERIFIED:
            message = f"Repair VERIFIED after {hazard.clean_observation_count} clean checks."
        else:
            remaining = CLEAN_OBSERVATIONS_FOR_VERIFIED - hazard.clean_observation_count
            message = (
                f"Clean check {hazard.clean_observation_count}/"
                f"{CLEAN_OBSERVATIONS_FOR_VERIFIED}. "
                f"{remaining} more to verify."
            )

    return schemas.VerificationResultOut(
        hazard=_hazard_out(hazard, detail=True),
        still_detected=still_detected,
        clean_observations=hazard.clean_observation_count,
        clean_observations_required=CLEAN_OBSERVATIONS_FOR_VERIFIED,
        verified=hazard.status == STATUS_VERIFIED,
        message=message,
    )


@app.get("/hazards/{hazard_id}/observations", response_model=list[schemas.ObservationOut])
def hazard_observations(hazard_id: int, db: Session = Depends(get_db)):
    hazard = _get_hazard_or_404(db, hazard_id)
    return _hazard_out(hazard, detail=True).observations


@app.get("/hazards/near/{latitude}/{longitude}", response_model=list[schemas.HazardOut])
def hazards_near(
    latitude: float,
    longitude: float,
    radius_m: float = DEDUP_RADIUS_METRES,
    db: Session = Depends(get_db),
):
    return [_hazard_out(h) for h in find_hazards_near(db, latitude, longitude, radius_m)]


# --------------------------------------------------------------------------
# Safe routing (optional module -- see routing.py)
# --------------------------------------------------------------------------

@app.get("/route/status")
def route_status():
    """Whether the routing demo is usable, and whether the graph is cached."""
    import routing

    return {
        "available": routing.available(),
        "graph_cached": routing.GRAPH_PATH.exists(),
        "graph_path": str(routing.GRAPH_PATH),
        "hint": (
            "pip install osmnx networkx, then run python download_graph.py"
            if not (routing.available() and routing.GRAPH_PATH.exists())
            else "ready"
        ),
    }


@app.post("/route")
def safe_route(
    start_latitude: float = Form(...),
    start_longitude: float = Form(...),
    end_latitude: float = Form(...),
    end_longitude: float = Form(...),
    min_severity: float = Form(default=5.0),
    db: Session = Depends(get_db),
):
    """
    Shortest route vs hazard-avoiding route between two points in Manipal.

    Only open hazards at or above `min_severity` are penalised -- a low-risk
    pothole is not worth a detour.
    """
    import routing

    if not routing.available():
        raise HTTPException(
            status_code=503,
            detail="Routing needs osmnx and networkx: pip install osmnx networkx",
        )

    hazards = db.scalars(
        select(Hazard).where(
            Hazard.status != STATUS_VERIFIED, Hazard.severity >= min_severity
        )
    ).all()

    try:
        result = routing.route(
            (start_latitude, start_longitude), (end_latitude, end_longitude), hazards
        )
    except routing.RoutingUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not route: {exc}")

    result["hazards_considered"] = len(hazards)
    result["min_severity"] = min_severity
    return result
