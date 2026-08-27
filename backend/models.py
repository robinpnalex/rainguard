"""Database tables.

Two tables only:

  Hazard      -- one row per physical hazard in the world
  Observation -- one row per uploaded image/report that touched a hazard

A hazard accumulates observations. Repeat sightings raise the observation
count (and therefore severity/status); clean observations after a repair
raise the clean count until the hazard is VERIFIED.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# Hazard types the prototype understands.
HAZARD_TYPES = ("pothole", "manhole", "waterlogging")

# Lifecycle states. See README for the transition diagram.
STATUS_SUSPECTED = "SUSPECTED"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_REPAIR_PENDING = "REPAIR_PENDING"
STATUS_REPAIRED = "REPAIRED"
STATUS_VERIFIED = "VERIFIED"


def utcnow() -> datetime:
    """
    Current UTC time as a *naive* datetime.

    SQLite has no timezone type, so values read back from the database are
    always naive. Keeping everything naive-UTC avoids "can't compare
    offset-naive and offset-aware datetimes" the first time a hazard is
    updated. The dashboard renders these as UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Hazard(Base):
    __tablename__ = "hazards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default=STATUS_SUSPECTED)

    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # --- repair workflow state ---
    repair_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    # Consecutive re-inspections that did NOT find the hazard. Resets to 0
    # whenever a re-inspection still detects it.
    clean_observation_count: Mapped[int] = mapped_column(Integer, default=0)
    # True when the most recent re-inspection still found the hazard, so the
    # dashboard can flag "repair check failed".
    verification_failed: Mapped[bool] = mapped_column(Boolean, default=False)

    observations: Mapped[list["Observation"]] = relationship(
        back_populates="hazard",
        cascade="all, delete-orphan",
        order_by="Observation.timestamp",
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hazard_id: Mapped[int] = mapped_column(
        ForeignKey("hazards.id", ondelete="CASCADE"), index=True
    )

    type: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Where the coordinates came from: "manual" | "exif" | "browser" | "seed"
    location_source: Mapped[str] = mapped_column(String(16), default="manual")

    # A "clean" observation is a post-repair re-inspection in which the
    # detector did NOT find this hazard type at this location.
    is_clean: Mapped[bool] = mapped_column(Boolean, default=False)

    hazard: Mapped["Hazard"] = relationship(back_populates="observations")
