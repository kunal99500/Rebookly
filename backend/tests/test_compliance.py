"""Tests for country packs, tax registration number checks, and tax maths (no database needed)."""
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from app.compliance import validators as v
from app.compliance.countries import get_pack, supported_countries
from app.compliance.schemas import TaxProfileIn
from app.compliance.tax import format_rate, receipt_tax_section, tax_for_price, tax_for_visit


# ---------- India: GSTIN ----------

@pytest.mark.parametrize("number, state", [("27AAPFU0939F1ZV", "Maharashtra"), ("29AAGCB7383J1Z4", "Karnataka")])
def test_valid_gstins(number, state):
    result = v.check_gstin(number)
    assert result.valid and result.details["state"] == state


def test_gstin_is_normalized():
    assert v.check_gstin(" 27aapfu-0939f1zv ").normalized == "27AAPFU0939F1ZV"


@pytest.mark.parametrize("number, message", [
    ("27AAPFU0939F1ZW", "last character"),     # one typo in the check character
    ("27AAPFU0939F1Z", "15 characters"),
    ("99AAPFU0939F1ZV", "state code"),
    ("27AAPF10939F1ZV", "doesn't look like"),  # digit where a letter belongs
])
def test_invalid_gstins(number, message):
    result = v.check_gstin(number)
    assert not result.valid and message in result.message


# ---------- other countries ----------

def test_uk_vat():
    assert v.check_uk_vat("GB 980 7806 84").valid
    assert v.check_uk_vat("980780684").normalized == "GB980780684"
    assert not v.check_uk_vat("GB123456788").valid


def test_australian_abn():
    assert v.check_abn("51 824 753 556").valid
    assert not v.check_abn("51 824 753 557").valid


def test_canadian_gst_hst_number():
    assert v.check_canada_gst("123456789 RT 0001").valid
    assert not v.check_canada_gst("123456789").valid


@pytest.mark.parametrize("number, valid", [
    ("DE123456789", True), ("NL123456789B01", True), ("FR12345678901", True),
    ("GR123456789", True),                    # Greece's VAT prefix is EL; GR is accepted and converted
    ("DE12345678", False), ("XX123", False),
])
def test_eu_vat_formats(number, valid):
    assert v.check_eu_vat(number).valid is valid


def test_us_ein_is_formatted():
    assert v.check_ein("123456789").normalized == "12-3456789"


# ---------- country packs ----------

def test_known_and_unknown_countries():
    assert get_pack("in").registration_label == "GSTIN"
    assert get_pack("DE").tax_label == "VAT"
    assert get_pack("ZZ").code == "default" and get_pack("ZZ").registration_optional


def test_usual_price_display_by_country():
    assert get_pack("IN").prices_include_tax_default and get_pack("GB").prices_include_tax_default
    assert not get_pack("US").prices_include_tax_default and not get_pack("CA").prices_include_tax_default


def test_every_pack_shows_a_valid_example():
    for pack in supported_countries():
        if pack.registration_example and "…" not in pack.registration_example:
            assert pack.check(pack.registration_example).valid, pack.code


# ---------- tax maths ----------

def test_tax_included_in_price():
    line = tax_for_price(D("450"), D("18"), prices_include_tax=True)
    assert (line.net, line.tax, line.gross) == (D("381.36"), D("68.64"), D("450"))


def test_tax_added_on_top():
    line = tax_for_price(D("40"), D("8"), prices_include_tax=False)
    assert (line.tax, line.gross) == (D("3.20"), D("43.20"))


def test_visit_tax_adds_up_per_service():
    visit = tax_for_visit([D("40"), D("5")], D("8"), prices_include_tax=False)
    assert visit.tax_total == D("3.60") and visit.gross_total == D("48.60")


def test_no_rate_means_no_tax():
    visit = tax_for_visit([D("450"), D("5")], None, prices_include_tax=True)
    assert visit.tax_total == D("0") and visit.gross_total == D("455")


@pytest.mark.parametrize("rate", [D("-1"), D("101")])
def test_impossible_rates_are_refused(rate):
    with pytest.raises(ValueError):
        tax_for_price(D("10"), rate, True)


def test_receipt_tax_section():
    section = receipt_tax_section(label="GST", rate=D("18.00"), prices_include_tax=True, amount=D("69.40"),
                                  currency="INR", registration_label="GSTIN",
                                  registration_number="27AAPFU0939F1ZV", legal_name="Lumen Salon Pvt Ltd")
    assert section["line"] == "Includes GST 18%" and section["amount"] == "₹69.40"
    assert format_rate(D("8.50")) == "8.5"


def test_visit_total_wording():
    inclusive = receipt_tax_section(label="GST", rate=D("18"), prices_include_tax=True, amount=D("69.40"),
                                    currency="INR", registration_label=None, registration_number=None,
                                    legal_name=None, on_visit_total=True)
    exclusive = receipt_tax_section(label="Sales tax", rate=D("8"), prices_include_tax=False, amount=D("3.60"),
                                    currency="USD", registration_label="EIN", registration_number=None,
                                    legal_name=None, on_visit_total=True)
    assert inclusive["line"] == "GST 18% included in the visit total"
    assert exclusive["line"] == "Sales tax 8% added to the visit total"
    assert exclusive["registration_label"] is None   # no number, so no label either


# ---------- input ----------

def test_profile_input_rules():
    assert TaxProfileIn(country_code="in", tax_registered=False).country_code == "in"
    with pytest.raises(ValidationError):
        TaxProfileIn(country_code="IND")
    with pytest.raises(ValidationError):
        TaxProfileIn(country_code="IN", tax_rate=D("150"))