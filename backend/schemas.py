"""Pydantic response models -- the shape the dashboard consumes."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

import severity as severity_module


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    confidence: float
    latitude: float
    longitude: float
    timestamp: datetime
    image_path: str | None
    image_url: str | None = None
    location_source: str
    is_clean: bool


class HazardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    latitude: float
    longitude: float
    observation_count: int
    avg_confidence: float
    severity: float
    risk_band: str
    status: str
    first_seen: datetime
    last_seen: datetime
    repair_requested_at: datetime | None
    clean_observation_count: int
    clean_observations_required: int
    verification_failed: bool
    before_image_url: str | None = None
    after_image_url: str | None = None


class HazardDetailOut(HazardOut):
    observations: list[ObservationOut] = []


class DetectionResultOut(BaseModel):
    """What POST /detections returns."""

    detector: str
    detections_found: int
    location_source: str
    latitude: float
    longitude: float
    image_url: str | None
    hazards: list[HazardOut]
    created_hazard_ids: list[int]
    updated_hazard_ids: list[int]
    message: str


class VerificationResultOut(BaseModel):
    """What POST /hazards/{id}/verify returns."""

    hazard: HazardDetailOut
    still_detected: bool
    clean_observations: int
    clean_observations_required: int
    verified: bool
    message: str


def risk_band(value: float) -> str:
    return severity_module.band(value)
