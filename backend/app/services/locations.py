"""Where a business is: country, state/region, city, address and map position."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance import profiles as tax_profiles
from app.geo import places
from app.geo.schemas import BusinessLocationIn, BusinessLocationOut
from app.models import Business
from app.services import audit


async def location_out(session: AsyncSession, business: Business) -> BusinessLocationOut:
    country = places.country(business.country_code or "")
    region = places.region(business.country_code or "", business.region_code)
    warnings = []
    if business.latitude is None:
        warnings.append("Add your map position so nearby clients can find you.")
    profile = await tax_profiles.get_profile(session, business.id)
    if profile is not None and profile.country_code != business.country_code:
        warnings.append("Your tax details are for a different country. Please update them.")
    elif profile is not None:
        warnings.extend(w for w in tax_profiles.to_out(profile, business.region_code).warnings if "GSTIN" in w)
    return BusinessLocationOut(
        country_code=business.country_code, country_name=country.name if country else business.country_code,
        region_code=business.region_code, region_name=region.name if region else None,
        city=business.city, postal_code=business.postal_code, address=business.address,
        latitude=float(business.latitude) if business.latitude is not None else None,
        longitude=float(business.longitude) if business.longitude is not None else None,
        source=business.location_source, warnings=warnings,
    )


async def set_location(session: AsyncSession, business: Business, owner_id: uuid.UUID,
                       data: BusinessLocationIn) -> BusinessLocationOut:
    business.country_code = data.country_code
    business.region_code = data.region_code
    business.city = data.city
    business.postal_code = data.postal_code
    business.address = data.address
    business.latitude = round(data.latitude, 6) if data.latitude is not None else None
    business.longitude = round(data.longitude, 6) if data.longitude is not None else None
    business.location_source = data.source
    # The exact position isn't written to the audit log, only that it changed.
    audit.record(session, actor_type="owner", actor_id=owner_id, action="business.location_updated",
                 business_id=business.id, details={"country": data.country_code, "region": data.region_code,
                                                   "city": data.city, "source": data.source})
    await session.commit()
    await session.refresh(business)
    return await location_out(session, business)