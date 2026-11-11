"""What the location API accepts and returns."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.geo import places

# Countries where the state/province matters (e.g. for tax), so it must be chosen.
REGION_REQUIRED = {"IN", "US", "CA", "AU"}


class CountryOut(BaseModel):
    code: str
    name: str


class RegionOut(BaseModel):
    code: str
    name: str


class CoordinatesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PlaceOut(BaseModel):
    country_code: str | None
    region_code: str | None
    region_name: str | None
    city: str | None
    postal_code: str | None
    address_line: str | None
    latitude: float | None
    longitude: float | None
    label: str


class BusinessLocationIn(BaseModel):
    """Where the business is. Filled from live location, a search result, or typed by hand."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    country_code: str = Field(pattern=r"^[A-Za-z]{2}$")
    region_code: str | None = Field(default=None, max_length=10, description="ISO code, e.g. IN-MH or US-CA")
    city: str = Field(min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=300, description="Street and number")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    source: Literal["gps", "search", "manual"] = "manual"

    @model_validator(mode="after")
    def _check(self) -> "BusinessLocationIn":
        self.country_code = self.country_code.upper()
        if places.country(self.country_code) is None:
            raise ValueError("Unknown country")
        if self.region_code:
            region = places.region(self.country_code, self.region_code)
            if region is None:
                raise ValueError("That state/region doesn't belong to the chosen country")
            self.region_code = region.code
        elif self.country_code in REGION_REQUIRED:
            raise ValueError("Choose a state/region")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Send both latitude and longitude, or neither")
        return self


class BusinessLocationOut(BaseModel):
    country_code: str
    country_name: str
    region_code: str | None
    region_name: str | None
    city: str
    postal_code: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    source: str | None
    warnings: list[str]