"""Country and state/region lists, from the ISO 3166 standard (via pycountry). Works offline.

Cities aren't listed here (there are hundreds of thousands); they're typed or found by the geocoder.
"""
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import pycountry

# India: clean English names and the GST state code for each ISO region.
INDIA_REGIONS = {
    "IN-AN": ("Andaman and Nicobar Islands", "35"), "IN-AP": ("Andhra Pradesh", "37"),
    "IN-AR": ("Arunachal Pradesh", "12"), "IN-AS": ("Assam", "18"), "IN-BR": ("Bihar", "10"),
    "IN-CG": ("Chhattisgarh", "22"), "IN-CH": ("Chandigarh", "04"),
    "IN-DH": ("Dadra and Nagar Haveli and Daman and Diu", "26"), "IN-DL": ("Delhi", "07"),
    "IN-GA": ("Goa", "30"), "IN-GJ": ("Gujarat", "24"), "IN-HP": ("Himachal Pradesh", "02"),
    "IN-HR": ("Haryana", "06"), "IN-JH": ("Jharkhand", "20"), "IN-JK": ("Jammu and Kashmir", "01"),
    "IN-KA": ("Karnataka", "29"), "IN-KL": ("Kerala", "32"), "IN-LA": ("Ladakh", "38"),
    "IN-LD": ("Lakshadweep", "31"), "IN-MH": ("Maharashtra", "27"), "IN-ML": ("Meghalaya", "17"),
    "IN-MN": ("Manipur", "14"), "IN-MP": ("Madhya Pradesh", "23"), "IN-MZ": ("Mizoram", "15"),
    "IN-NL": ("Nagaland", "13"), "IN-OD": ("Odisha", "21"), "IN-PB": ("Punjab", "03"),
    "IN-PY": ("Puducherry", "34"), "IN-RJ": ("Rajasthan", "08"), "IN-SK": ("Sikkim", "11"),
    "IN-TN": ("Tamil Nadu", "33"), "IN-TR": ("Tripura", "16"), "IN-TS": ("Telangana", "36"),
    "IN-UK": ("Uttarakhand", "05"), "IN-UP": ("Uttar Pradesh", "09"), "IN-WB": ("West Bengal", "19"),
}
# Older ISO codes some geocoders still return.
_ALIASES = {"IN-CT": "IN-CG", "IN-OR": "IN-OD", "IN-TG": "IN-TS", "IN-UT": "IN-UK"}


@dataclass(frozen=True)
class Country:
    code: str     # "IN"
    name: str


@dataclass(frozen=True)
class Region:
    code: str     # ISO 3166-2, e.g. "IN-MH", "US-CA", "GB-SCT"
    name: str


def _plain(text: str) -> str:
    """Lowercase without accents, for matching: 'Mahārāshtra' -> 'maharashtra'."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold().strip()


@lru_cache
def countries() -> tuple[Country, ...]:
    return tuple(sorted((Country(c.alpha_2, getattr(c, "common_name", c.name)) for c in pycountry.countries),
                        key=lambda c: c.name))


def country(code: str) -> Country | None:
    return next((c for c in countries() if c.code == (code or "").upper()), None)


@lru_cache
def regions(country_code: str) -> tuple[Region, ...]:
    """Top-level regions only (states, provinces, the UK's four nations), sorted by name."""
    code = (country_code or "").upper()
    if code == "IN":
        return tuple(sorted((Region(c, name) for c, (name, _) in INDIA_REGIONS.items()), key=lambda r: r.name))
    subs = pycountry.subdivisions.get(country_code=code) or []
    top = [s for s in subs if not getattr(s, "parent_code", None)]
    clean = (Region(s.code, re.sub(r"\s*\[.*?\]", "", s.name).strip()) for s in top)
    return tuple(sorted(clean, key=lambda r: r.name))


def normalize_region_code(code: str | None) -> str | None:
    if not code:
        return None
    upper = code.upper()
    return _ALIASES.get(upper, upper)


def region(country_code: str, region_code: str | None) -> Region | None:
    code = normalize_region_code(region_code)
    return next((r for r in regions(country_code) if r.code == code), None)


def find_region(country_code: str, name: str | None) -> Region | None:
    """Match a geocoder's state name ('Mahārāshtra', 'maharashtra') to a region."""
    if not name:
        return None
    wanted = _plain(name)
    return next((r for r in regions(country_code) if _plain(r.name) == wanted), None)


def gst_state_code(region_code: str | None) -> str | None:
    """India only: 'IN-MH' -> '27' (the first two digits of a Maharashtra GSTIN)."""
    entry = INDIA_REGIONS.get(normalize_region_code(region_code) or "")
    return entry[1] if entry else None