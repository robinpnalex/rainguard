"""
Where did this report happen?

Three sources, tried in priority order. This chain exists because live phone
GPS is the single most likely thing to fail during a demo:

  * browser geolocation is blocked on plain http:// origins, so a phone
    hitting the laptop over LAN gets nothing;
  * demo halls are indoors, where the fix degrades to wifi/cell
    triangulation with tens or hundreds of metres of error;
  * uploaded photos usually have their EXIF GPS stripped.

So the API accepts explicit coordinates (the dashboard sets them by clicking
the map), falls back to EXIF, and treats browser geolocation as a bonus.
A real field app needs manual correction for poor signal anyway.
"""
from pathlib import Path

SOURCE_MANUAL = "manual"
SOURCE_EXIF = "exif"
SOURCE_BROWSER = "browser"
SOURCE_SEED = "seed"


def resolve(
    latitude: float | None,
    longitude: float | None,
    image_path: Path | None,
    declared_source: str | None = None,
) -> tuple[float, float, str] | None:
    """Return (lat, lon, source), or None if no location could be determined."""
    if latitude is not None and longitude is not None:
        source = declared_source if declared_source in (
            SOURCE_MANUAL, SOURCE_BROWSER, SOURCE_SEED
        ) else SOURCE_MANUAL
        return latitude, longitude, source

    if image_path is not None:
        exif = read_exif_location(image_path)
        if exif is not None:
            return exif[0], exif[1], SOURCE_EXIF

    return None


def read_exif_location(image_path: Path) -> tuple[float, float] | None:
    """Pull GPS coordinates out of a photo's EXIF, if they survived upload."""
    try:
        from PIL import Image, ExifTags
    except ImportError:  # Pillow is optional
        return None

    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            if not exif:
                return None
            gps_tag = next(
                (k for k, v in ExifTags.TAGS.items() if v == "GPSInfo"), None
            )
            gps = exif.get_ifd(gps_tag) if gps_tag else None
            if not gps:
                return None

            lat = _to_degrees(gps.get(2), gps.get(1))
            lon = _to_degrees(gps.get(4), gps.get(3))
            if lat is None or lon is None:
                return None
            return lat, lon
    except Exception:
        return None


def _to_degrees(dms, ref) -> float | None:
    """EXIF stores coordinates as degrees/minutes/seconds plus a N/S/E/W ref."""
    if not dms or len(dms) != 3:
        return None
    degrees, minutes, seconds = (float(v) for v in dms)
    value = degrees + minutes / 60.0 + seconds / 3600.0
    if str(ref).upper() in ("S", "W"):
        value = -value
    return round(value, 7)
