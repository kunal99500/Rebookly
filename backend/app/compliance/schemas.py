"""What the compliance API accepts and returns."""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

TAX_NOTE = ("Rebookly prints the tax details you confirm here. It doesn't give tax advice: "
            "check your registration status and rate with your accountant.")


class CountryOut(BaseModel):
    code: str
    name: str
    tax_label: str
    registration_label: str


class CountryFormOut(CountryOut):
    registration_example: str
    registered_question: str
    help_text: str
    registration_optional: bool
    prices_include_tax_default: bool
    note: str = TAX_NOTE


class NumberCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1, max_length=40)


class NumberCheckOut(BaseModel):
    valid: bool
    normalized: str
    message: str
    details: dict


class TaxProfileIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    country_code: str = Field(pattern=r"^[A-Za-z]{2}$")
    legal_name: str | None = Field(default=None, max_length=160)
    registered_address: str | None = Field(default=None, max_length=300)
    region_code: str | None = Field(default=None, max_length=10)
    tax_registered: bool = False
    registration_number: str | None = Field(default=None, max_length=40)
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    prices_include_tax: bool | None = Field(default=None, description="Leave empty to use the country's usual way")
    fees_taxable: bool | None = Field(default=None, description="Whether cancellation and no-show fees include tax")


class TaxProfileOut(BaseModel):
    country_code: str
    country_name: str
    legal_name: str | None
    registered_address: str | None
    region_code: str | None
    tax_registered: bool
    tax_label: str
    registration_label: str
    registration_number: str | None
    verification_status: str
    tax_rate: Decimal | None
    prices_include_tax: bool
    fees_taxable: bool | None
    warnings: list[str]
    note: str = TAX_NOTE