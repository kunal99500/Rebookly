"""Tests for places, distances and reading geocoder results (no network)."""
import httpx
import pytest
from pydantic import ValidationError

from app.geo import places
from app.geo.distance import coarse, distance_km
from app.geo.geocoding import Geocoder, GeocoderError, parse_place
from app.geo.schemas import BusinessLocationIn


# ---------- countries and regions ----------

def test_countries_include_the_world():
    assert len(places.countries()) > 240
    assert places.country("in").name == "India"
    assert places.country("ZZ") is None


def test_india_has_clean_names_and_gst_codes():
    names = [r.name for r in places.regions("IN")]
    assert "Maharashtra" in names and "Telangana" in names and len(names) == 36
    assert places.gst_state_code("IN-MH") == "27"
    assert places.gst_state_code("in-ka") == "29"
    assert places.gst_state_code("IN-TG") == "36"     # older code for Telangana still works


def test_uk_lists_its_four_nations_not_every_council():
    assert {r.name for r in places.regions("GB")} == {"England", "Northern Ireland", "Scotland", "Wales"}


@pytest.mark.parametrize("country, count", [("US", 57), ("AU", 8), ("CA", 13), ("DE", 16)])
def test_top_level_regions(country, count):
    assert len(places.regions(country)) == count


def test_region_matching_ignores_accents_and_case():
    assert places.find_region("IN", "Mahārāshtra").code == "IN-MH"
    assert places.find_region("DE", "baden-wurttemberg").code == "DE-BW"
    assert places.find_region("IN", "Atlantis") is None


def test_region_must_belong_to_the_country():
    assert places.region("IN", "IN-MH") is not None
    assert places.region("US", "IN-MH") is None


# ---------- distances ----------

def test_distance_between_cities():
    mumbai_to_pune = distance_km(19.0760, 72.8777, 18.5204, 73.8567)
    assert 115 < mumbai_to_pune < 125
    assert distance_km(51.5, -0.12, 51.5, -0.12) == 0


def test_coarse_coordinates_hide_exact_positions():
    assert coarse(19.076012) == 19.08


# ---------- reading geocoder results ----------

NOMINATIM_REVERSE = {
    "lat": "19.0760", "lon": "72.8777", "display_name": "12, Linking Road, Bandra West, Mumbai, Maharashtra, 400050, India",
    "address": {"house_number": "12", "road": "Linking Road", "suburb": "Bandra West", "city": "Mumbai",
                "state": "Maharashtra", "ISO3166-2-lvl4": "IN-MH", "postcode": "400050",
                "country": "India", "country_code": "in"},
}


def test_parse_reverse_result():
    place = parse_place(NOMINATIM_REVERSE)
    assert (place.country_code, place.region_code, place.region_name) == ("IN", "IN-MH", "Maharashtra")
    assert place.city == "Mumbai" and place.postal_code == "400050"
    assert place.address_line == "12 Linking Road, Bandra West"
    assert place.latitude == pytest.approx(19.076)


def test_parse_uses_state_name_when_iso_code_missing():
    item = {"lat": "12.97", "lon": "77.59", "address": {"town": "Whitefield", "state": "Karnātaka", "country_code": "in"}}
    place = parse_place(item)
    assert place.region_code == "IN-KA" and place.city == "Whitefield"


def test_parse_tolerates_missing_fields():
    place = parse_place({"address": {}})
    assert place.country_code is None and place.latitude is None


# ---------- the geocoder client (fake server, no network) ----------

def make_geocoder(handler, api_key=""):
    geo = Geocoder("https://geo.example", user_agent="Rebookly-test", api_key=api_key, min_interval_seconds=0)
    geo._http = httpx.AsyncClient(headers={"User-Agent": "Rebookly-test"}, transport=httpx.MockTransport(handler))
    return geo


@pytest.mark.asyncio
async def test_reverse_sends_rounded_coordinates_and_caches():
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=NOMINATIM_REVERSE)

    geo = make_geocoder(handler)
    first = await geo.reverse(19.076012, 72.877655)
    second = await geo.reverse(19.07604, 72.87771)     # within ~100 m: served from the cache
    assert first.city == "Mumbai" and second.city == "Mumbai"
    assert len(calls) == 1
    assert calls[0]["lat"] == "19.076" and calls[0]["lon"] == "72.878" and calls[0]["format"] == "json"


@pytest.mark.asyncio
async def test_api_key_is_sent_when_configured():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=[])

    await make_geocoder(handler, api_key="pk.test").search("Bandra", country_code="IN")
    assert seen["key"] == "pk.test" and seen["countrycodes"] == "in"


@pytest.mark.asyncio
async def test_geocoder_errors_are_raised():
    geo = make_geocoder(lambda request: httpx.Response(429, json={"error": "rate limited"}))
    with pytest.raises(GeocoderError):
        await geo.reverse(1.0, 2.0)


# ---------- business location input ----------

def test_location_codes_are_normalized():
    loc = BusinessLocationIn(country_code="in", region_code="in-tg", city="Hyderabad")
    assert (loc.country_code, loc.region_code) == ("IN", "IN-TS")   # old Telangana code converted


def test_region_is_optional_where_it_does_not_matter():
    assert BusinessLocationIn(country_code="SG", city="Singapore").region_code is None


@pytest.mark.parametrize("fields", [
    {"country_code": "IN", "city": "Mumbai"},                                   # India needs a state
    {"country_code": "IN", "region_code": "US-CA", "city": "Mumbai"},          # state from another country
    {"country_code": "ZZ", "city": "Nowhere"},                                  # unknown country
    {"country_code": "IN", "region_code": "IN-MH", "city": "Mumbai", "latitude": 19.07},   # half a position
    {"country_code": "IN", "region_code": "IN-MH", "city": ""},                 # no city
])
def test_invalid_locations_are_rejected(fields):
    with pytest.raises(ValidationError):
        BusinessLocationIn(**fields)