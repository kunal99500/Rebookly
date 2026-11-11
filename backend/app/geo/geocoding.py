"""Coordinates <-> addresses, through a Nominatim-compatible geocoder.

Works with OpenStreetMap's Nominatim (fine for development, strict usage limits) and
Nominatim-compatible paid services such as LocationIQ (set GEOCODER_BASE_URL and GEOCODER_API_KEY).

Privacy: a client's coordinates are used for one lookup and never stored. Lookups are cached by
coarse (about 100 m) coordinates, so the cache never holds anyone's exact position.
"""
import asyncio
import time
from dataclasses import dataclass

import httpx

from app.geo import places


class GeocoderError(Exception):
    pass


@dataclass(frozen=True)
class Place:
    country_code: str | None
    region_code: str | None
    region_name: str | None
    city: str | None
    postal_code: str | None
    address_line: str | None
    latitude: float | None
    longitude: float | None
    label: str                     # a readable one-line description


def parse_place(item: dict) -> Place:
    """Turn one Nominatim-style result into a Place. Pure, so it's easy to test."""
    address = item.get("address") or {}
    country_code = (address.get("country_code") or "").upper() or None
    region = None
    if country_code:
        region = (places.region(country_code, address.get("ISO3166-2-lvl4"))
                  or places.find_region(country_code, address.get("state")))
    city = next((address[k] for k in ("city", "town", "village", "municipality", "suburb", "county") if address.get(k)), None)
    street = " ".join(p for p in (address.get("house_number"), address.get("road")) if p) or None
    line = ", ".join(p for p in (street, address.get("neighbourhood") or address.get("suburb")) if p) or None
    try:
        lat, lon = float(item["lat"]), float(item["lon"])
    except (KeyError, TypeError, ValueError):
        lat = lon = None
    return Place(
        country_code=country_code, region_code=region.code if region else None,
        region_name=region.name if region else address.get("state"), city=city,
        postal_code=address.get("postcode"), address_line=line, latitude=lat, longitude=lon,
        label=item.get("display_name") or ", ".join(p for p in (city, address.get("state"), address.get("country")) if p),
    )


class Geocoder:
    def __init__(self, base_url: str, user_agent: str, api_key: str = "", min_interval_seconds: float = 1.0,
                 cache_size: int = 2000, timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._http = httpx.AsyncClient(headers={"User-Agent": user_agent}, timeout=timeout)
        self._min_interval = min_interval_seconds   # Nominatim's public server allows about 1 request per second
        self._last_call = 0.0
        self._lock = asyncio.Lock()
        self._cache: dict[tuple, object] = {}
        self._cache_size = cache_size

    async def close(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict) -> object:
        key = (path, tuple(sorted(params.items())))
        if key in self._cache:
            return self._cache[key]
        if self._key:
            params = {**params, "key": self._key}
        async with self._lock:  # space out requests to respect the provider's rate limit
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                response = await self._http.get(f"{self._base}{path}", params={**params, "format": "json"})
            finally:
                self._last_call = time.monotonic()
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise GeocoderError(f"Geocoder returned {response.status_code}")
        data = response.json()
        if len(self._cache) >= self._cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = data
        return data

    async def reverse(self, latitude: float, longitude: float) -> Place | None:
        """Coordinates -> address. Cached by ~100 m rounding, so exact positions are never kept."""
        data = await self._get("/reverse", {"lat": round(latitude, 3), "lon": round(longitude, 3),
                                            "addressdetails": 1, "zoom": 18})
        if not data or not isinstance(data, dict) or "error" in data:
            return None
        return parse_place(data)

    async def search(self, query: str, country_code: str | None = None, limit: int = 5,
                     cities_only: bool = False) -> list[Place]:
        """Address or city text -> matching places."""
        params = {"q": query.strip()[:200], "addressdetails": 1, "limit": max(1, min(limit, 10))}
        if country_code:
            params["countrycodes"] = country_code.lower()
        if cities_only:
            params["featureType"] = "city"
        data = await self._get("/search", params)
        return [parse_place(item) for item in (data or []) if isinstance(item, dict)]