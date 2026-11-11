"""Location API: country and state lists (public), and address lookups (signed-in users only)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.auth.dependencies import get_current_user
from app.auth.supabase_auth import AuthUser
from app.geo import places
from app.geo.geocoding import Geocoder, GeocoderError, Place
from app.geo.schemas import CoordinatesIn, CountryOut, PlaceOut, RegionOut

router = APIRouter(prefix="/api/geo", tags=["location"])


def _geocoder(request: Request) -> Geocoder:
    geocoder = getattr(request.app.state, "geocoder", None)
    if geocoder is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Address lookup isn't available. Choose your country, state and city instead.")
    return geocoder


def _out(place: Place) -> PlaceOut:
    return PlaceOut(**place.__dict__)


@router.get("/countries", response_model=list[CountryOut])
async def countries():
    return [CountryOut(code=c.code, name=c.name) for c in places.countries()]


@router.get("/countries/{country_code}/regions", response_model=list[RegionOut])
async def regions(country_code: str):
    """States, provinces or regions of a country (may be empty for small countries)."""
    if places.country(country_code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown country")
    return [RegionOut(code=r.code, name=r.name) for r in places.regions(country_code)]


@router.post("/reverse", response_model=PlaceOut)
async def from_coordinates(data: CoordinatesIn, request: Request, user: AuthUser = Depends(get_current_user)):
    """Live location -> country, state, city and address. The coordinates are not stored."""
    try:
        place = await _geocoder(request).reverse(data.latitude, data.longitude)
    except GeocoderError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't look up that location. Please choose it by hand.")
    if place is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No address found here. Please choose it by hand.")
    return _out(place)


@router.get("/search", response_model=list[PlaceOut])
async def search(
    request: Request,
    q: str = Query(min_length=2, max_length=200, description="An address, area or city"),
    country: str | None = Query(default=None, pattern=r"^[A-Za-z]{2}$"),
    cities_only: bool = False,
    user: AuthUser = Depends(get_current_user),
):
    """Find an address or city as the user types. Pick a result to fill in the form."""
    try:
        results = await _geocoder(request).search(q, country_code=country, cities_only=cities_only)
    except GeocoderError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Address search isn't working right now. Please type it in.")
    return [_out(p) for p in results]