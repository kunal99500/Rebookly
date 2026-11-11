"""What the public search returns."""
from decimal import Decimal

from pydantic import BaseModel


class SearchResult(BaseModel):
    slug: str
    name: str
    category: str
    city: str | None
    distance_km: float | None        # None when the client's location isn't known
    rating_average: Decimal | None
    rating_count: int
    price_from: Decimal | None       # cheapest main service
    currency: str
    cover_thumb_url: str | None


class SearchOut(BaseModel):
    category: str | None             # what we understood, e.g. "barber"
    near_me: bool
    results: list[SearchResult]