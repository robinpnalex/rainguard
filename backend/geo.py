"""Tiny geo helpers. No PostGIS, no GeoPandas -- just trigonometry."""
import math

EARTH_RADIUS_M = 6_371_000.0


def distance_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bounding_box(lat: float, lon: float, radius_m: float):
    """Rough lat/lon box around a point, used to pre-filter DB rows cheaply."""
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon
