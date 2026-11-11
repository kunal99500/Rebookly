"""Country packs: what each country calls its tax, its registration number, and how to check it.

Adding a country = adding one entry here (and its tests). Nothing else in the app changes.
Tax RATES are never hard-coded: the owner enters the rate their accountant confirms.
"""
from collections.abc import Callable
from dataclasses import dataclass

from app.compliance import validators
from app.compliance.validators import CheckResult

EU_COUNTRIES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany",
    "DK": "Denmark", "EE": "Estonia", "ES": "Spain", "FI": "Finland", "FR": "France", "GR": "Greece",
    "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg",
    "LV": "Latvia", "MT": "Malta", "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
}


@dataclass(frozen=True)
class CountryPack:
    code: str                         # ISO country code, or "default"
    name: str
    tax_label: str                    # what the tax is called on receipts: GST, VAT, Sales tax
    registration_type: str            # stored with the number: gstin, vat, abn, gst_hst, ein, tax_id
    registration_label: str           # form label: "GSTIN", "VAT number"
    registration_example: str
    registered_question: str          # "Are you registered for GST?"
    help_text: str
    check: Callable[[str], CheckResult]
    prices_include_tax_default: bool  # how prices are usually shown in this country
    registration_optional: bool = False


_DEFAULT = CountryPack(
    code="default", name="Other countries", tax_label="Tax", registration_type="tax_id",
    registration_label="Tax ID", registration_example="", registered_question="Do you charge tax on your services?",
    help_text="If your business is registered for a sales tax, enter its registration number as it should appear on receipts.",
    check=validators.check_generic_tax_id, prices_include_tax_default=True, registration_optional=True,
)

_PACKS = {
    "IN": CountryPack(
        code="IN", name="India", tax_label="GST", registration_type="gstin", registration_label="GSTIN",
        registration_example="27AAPFU0939F1ZV", registered_question="Are you registered for GST?",
        help_text="Your GSTIN is the 15-character number on your GST registration certificate. "
                  "If your turnover is below the GST threshold you may not be registered; answer No.",
        check=validators.check_gstin, prices_include_tax_default=True,
    ),
    "GB": CountryPack(
        code="GB", name="United Kingdom", tax_label="VAT", registration_type="vat", registration_label="VAT number",
        registration_example="GB980780684", registered_question="Are you registered for VAT?",
        help_text="Your VAT registration number starts with GB and is on your VAT certificate from HMRC.",
        check=validators.check_uk_vat, prices_include_tax_default=True,
    ),
    "AU": CountryPack(
        code="AU", name="Australia", tax_label="GST", registration_type="abn", registration_label="ABN",
        registration_example="51824753556", registered_question="Are you registered for GST?",
        help_text="Your Australian Business Number (ABN) has 11 digits. Show it on receipts if you're registered for GST.",
        check=validators.check_abn, prices_include_tax_default=True,
    ),
    "CA": CountryPack(
        code="CA", name="Canada", tax_label="GST/HST", registration_type="gst_hst",
        registration_label="GST/HST number", registration_example="123456789RT0001",
        registered_question="Are you registered for GST/HST?",
        help_text="Your GST/HST number is your 9-digit business number followed by RT and 4 digits.",
        check=validators.check_canada_gst, prices_include_tax_default=False,
    ),
    "US": CountryPack(
        code="US", name="United States", tax_label="Sales tax", registration_type="ein", registration_label="EIN",
        registration_example="12-3456789", registered_question="Do you charge sales tax on your services?",
        help_text="Many personal services aren't subject to sales tax, but this depends on your state. "
                  "Your EIN is optional on receipts.",
        check=validators.check_ein, prices_include_tax_default=False, registration_optional=True,
    ),
}
for _code, _name in EU_COUNTRIES.items():
    _PACKS[_code] = CountryPack(
        code=_code, name=_name, tax_label="VAT", registration_type="vat", registration_label="VAT number",
        registration_example="DE123456789" if _code == "DE" else f"{'EL' if _code == 'GR' else _code}…",
        registered_question="Are you registered for VAT?",
        help_text="Your VAT number starts with your country code. It's on your VAT registration document.",
        check=validators.check_eu_vat, prices_include_tax_default=True,
    )


def get_pack(country_code: str) -> CountryPack:
    """The pack for a country, or the default pack for countries we haven't specialised yet."""
    return _PACKS.get((country_code or "").upper(), _DEFAULT)


def supported_countries() -> list[CountryPack]:
    return sorted(_PACKS.values(), key=lambda p: p.name)