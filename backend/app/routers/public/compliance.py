"""Public API: country tax forms and instant number checks (used while an owner fills in the form)."""
from fastapi import APIRouter

from app.compliance.countries import get_pack, supported_countries
from app.compliance.schemas import CountryFormOut, CountryOut, NumberCheckIn, NumberCheckOut

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("/countries", response_model=list[CountryOut])
async def countries():
    """Countries with a dedicated tax form. Any other country uses a simple optional tax ID."""
    return [CountryOut(code=p.code, name=p.name, tax_label=p.tax_label, registration_label=p.registration_label)
            for p in supported_countries()]


@router.get("/countries/{country_code}/form", response_model=CountryFormOut)
async def country_form(country_code: str):
    """Labels, example and help text for one country's tax form."""
    pack = get_pack(country_code)
    return CountryFormOut(
        code=country_code.upper(), name=pack.name, tax_label=pack.tax_label,
        registration_label=pack.registration_label, registration_example=pack.registration_example,
        registered_question=pack.registered_question, help_text=pack.help_text,
        registration_optional=pack.registration_optional, prices_include_tax_default=pack.prices_include_tax_default,
    )


@router.post("/countries/{country_code}/check", response_model=NumberCheckOut)
async def check_number(country_code: str, data: NumberCheckIn):
    """Check a registration number's format as the owner types. Nothing is saved."""
    result = get_pack(country_code).check(data.number)
    return NumberCheckOut(valid=result.valid, normalized=result.normalized, message=result.message, details=result.details)