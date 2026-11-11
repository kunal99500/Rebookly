"""Saving and reading a business's tax profile, and working out the tax on a visit."""
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.countries import get_pack
from app.compliance.schemas import TaxProfileIn, TaxProfileOut
from app.compliance.tax import VisitTax, tax_for_visit
from app.models import Business, BusinessTaxProfile
from app.services import audit
from app.geo.places import gst_state_code


async def get_profile(session: AsyncSession, business_id: uuid.UUID) -> BusinessTaxProfile | None:
    return await session.scalar(select(BusinessTaxProfile).where(BusinessTaxProfile.business_id == business_id))


def _warnings(profile: BusinessTaxProfile, business_region_code: str | None = None) -> list[str]:
    warnings = []
       # India: the GSTIN's first two digits are the state it's registered in.
    expected = gst_state_code(business_region_code) or profile.region_code
    if (profile.registration_type == "gstin" and profile.registration_number and expected
               and profile.registration_number[:2] != expected):
           warnings.append(f"This GSTIN is registered in state {profile.registration_number[:2]}, but your business "
                           f"is in state {expected}. That's fine if you have several registrations; "
                           "otherwise please check it.")
    if profile.tax_registered and profile.fees_taxable is None:
        warnings.append("You haven't said whether cancellation and no-show fees include tax. "
                        "Until you do, fee receipts won't show tax.")
    return warnings


def to_out(profile: BusinessTaxProfile, business_region_code: str | None = None) -> TaxProfileOut:
    pack = get_pack(profile.country_code)
    return TaxProfileOut(
        country_code=profile.country_code, country_name=pack.name if pack.code != "default" else profile.country_code,
        legal_name=profile.legal_name, registered_address=profile.registered_address, region_code=profile.region_code,
        tax_registered=profile.tax_registered, tax_label=profile.tax_label, registration_label=pack.registration_label,
        registration_number=profile.registration_number, verification_status=profile.verification_status,
        tax_rate=profile.tax_rate, prices_include_tax=profile.prices_include_tax, fees_taxable=profile.fees_taxable,
        warnings=_warnings(profile, business_region_code),
    )


async def save_profile(session: AsyncSession, business: Business, owner_id: uuid.UUID, data: TaxProfileIn) -> BusinessTaxProfile:
    country = data.country_code.upper()
    pack = get_pack(country)

    number, verification = None, "unverified"
    if data.registration_number:
        result = pack.check(data.registration_number)
        if not result.valid:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result.message)
        number, verification = result.normalized, "format_valid"

    if data.tax_registered:
        if data.tax_rate is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"Enter your {pack.tax_label} rate (the one your accountant confirmed)")
        if number is None and not pack.registration_optional:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Enter your {pack.registration_label}")

    profile = await get_profile(session, business.id)
    if profile is None:
        profile = BusinessTaxProfile(business_id=business.id)
        session.add(profile)
    profile.country_code = country
    profile.legal_name = data.legal_name
    profile.registered_address = data.registered_address
    profile.region_code = data.region_code.upper() if data.region_code else None
    profile.tax_registered = data.tax_registered
    profile.registration_type = pack.registration_type if number else None
    profile.registration_number = number
    profile.verification_status = verification
    profile.tax_label = pack.tax_label
    profile.tax_rate = data.tax_rate if data.tax_registered else None
    profile.prices_include_tax = (data.prices_include_tax if data.prices_include_tax is not None
                                  else pack.prices_include_tax_default)
    profile.fees_taxable = data.fees_taxable if data.tax_registered else None

    audit.record(session, actor_type="owner", actor_id=owner_id, action="tax_profile.saved", business_id=business.id,
                 details={"country": country, "tax_registered": data.tax_registered,
                          "tax_rate": str(profile.tax_rate) if profile.tax_rate is not None else None})
    await session.commit()
    await session.refresh(profile)
    return profile


async def visit_tax(session: AsyncSession, business_id: uuid.UUID, prices: list[Decimal]) -> tuple[VisitTax, BusinessTaxProfile | None]:
    """Tax for the services in a visit. No profile, or not registered, means no tax."""
    profile = await get_profile(session, business_id)
    if profile is None or not profile.tax_registered:
        return tax_for_visit(prices, None, True), profile
    return tax_for_visit(prices, profile.tax_rate, profile.prices_include_tax), profile