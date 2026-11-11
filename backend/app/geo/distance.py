"""Distances between two points on Earth. Pure functions."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line ("as the crow flies") distance, using the haversine formula."""
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def coarse(value: float, decimals: int = 2) -> float:
    """Round a coordinate (2 decimals is about 1 km) so precise locations are never kept or logged."""
    return round(value, decimals)