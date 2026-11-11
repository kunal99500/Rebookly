"""Finding live businesses by what the client typed and where they are."""
from math import cos, radians

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.distance import distance_km
from app.models import Business, BusinessPhoto, Service
from app.rules.search_terms import understand
from app.schemas.search import SearchOut, SearchResult

MAX_RESULTS = 20


async def search(
    session: AsyncSession, query: str, latitude: float | None, longitude: float | None,
    radius_km: float, category: str | None = None, photo_url=None,
) -> SearchOut:
    intent = understand(query)
    wanted_category = category or intent.category

    q = select(Business).where(Business.status == "live", Business.listed_publicly.is_(True))
    matches = []
    if wanted_category:
        matches.append(Business.category == wanted_category)
    for word in intent.words[:5]:
        like = f"%{word}%"
        matches.append(Business.name.ilike(like))
        matches.append(Business.id.in_(select(Service.business_id).where(
            Service.is_active.is_(True), Service.name.ilike(like))))
    if matches:
        q = q.where(or_(*matches))
    elif not query.strip() and latitude is None:
        return SearchOut(category=None, near_me=False, results=[])

    if latitude is not None and longitude is not None:
        # Quick box around the client first; the exact distance is calculated below.
        dlat = radius_km / 111.0
        dlon = radius_km / max(111.0 * cos(radians(latitude)), 1e-6)
        q = q.where(Business.latitude.between(latitude - dlat, latitude + dlat),
                    Business.longitude.between(longitude - dlon, longitude + dlon))
    businesses = list(await session.scalars(q.limit(200)))

    results = []
    for b in businesses:
        dist = None
        if latitude is not None and b.latitude is not None:
            dist = round(distance_km(latitude, longitude, float(b.latitude), float(b.longitude)), 1)
            if dist > radius_km:
                continue
        results.append((b, dist))

    # Nearest first when we know where the client is; otherwise best rated.
    if latitude is not None:
        results.sort(key=lambda r: (r[1] is None, r[1] or 0))
    else:
        results.sort(key=lambda r: (-(float(r[0].rating_average or 0)), -r[0].rating_count))
    results = results[:MAX_RESULTS]

    ids = [b.id for b, _ in results]
    prices = dict((await session.execute(
        select(Service.business_id, func.min(Service.price)).where(
            Service.business_id.in_(ids), Service.is_active.is_(True), Service.kind == "main")
        .group_by(Service.business_id))).all()) if ids else {}
    covers = dict((await session.execute(
        select(BusinessPhoto.business_id, BusinessPhoto.thumb_path).where(
            BusinessPhoto.business_id.in_(ids), BusinessPhoto.kind == "cover",
            BusinessPhoto.moderation_status == "approved"))).all()) if ids else {}

    return SearchOut(
        category=wanted_category, near_me=intent.near_me,
        results=[SearchResult(
            slug=b.slug, name=b.name, category=b.category, city=b.city, distance_km=dist,
            rating_average=b.rating_average, rating_count=b.rating_count,
            price_from=prices.get(b.id), currency=b.currency,
            cover_thumb_url=photo_url(covers[b.id]) if photo_url and b.id in covers else None,
        ) for b, dist in results],
    )