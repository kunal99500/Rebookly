"""Checks for business tax registration numbers. Pure functions, fully tested.

These check the FORMAT and built-in check characters, which catches most typos instantly.
They don't prove a number is registered; official lookups can be added per country later.
"""
import re
from dataclasses import dataclass, field

_ALNUM36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class CheckResult:
    valid: bool
    normalized: str
    message: str
    details: dict = field(default_factory=dict)


def normalize(value: str) -> str:
    """Uppercase, without spaces, dots or dashes: ' 27aapfu-0939f1zv ' -> '27AAPFU0939F1ZV'."""
    return re.sub(r"[\s.\-]", "", (value or "")).upper()


def _bad(normalized: str, message: str) -> CheckResult:
    return CheckResult(False, normalized, message)


# ---------- India: GSTIN ----------

INDIAN_STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory",
}
_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def gstin_check_character(first14: str) -> str:
    total = 0
    for i, char in enumerate(first14):
        product = _ALNUM36.index(char) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _ALNUM36[(36 - total % 36) % 36]


def check_gstin(value: str) -> CheckResult:
    number = normalize(value)
    if len(number) != 15:
        return _bad(number, "A GSTIN has 15 characters")
    if not _GSTIN.match(number):
        return _bad(number, "This doesn't look like a GSTIN. Check it against your GST certificate.")
    state = INDIAN_STATES.get(number[:2])
    if state is None:
        return _bad(number, f"'{number[:2]}' isn't a valid GST state code")
    if gstin_check_character(number[:14]) != number[14]:
        return _bad(number, "This GSTIN's last character doesn't match. Please check for a typo.")
    return CheckResult(True, number, f"Valid format · State: {state} ({number[:2]})",
                       {"state_code": number[:2], "state": state})


# ---------- United Kingdom: VAT number ----------

def check_uk_vat(value: str) -> CheckResult:
    number = normalize(value)
    digits = number[2:] if number.startswith("GB") else number
    if not re.fullmatch(r"[0-9]{9}([0-9]{3})?", digits):
        return _bad(number, "A UK VAT number is GB followed by 9 digits")
    nine = digits[:9]
    total = sum(int(d) * w for d, w in zip(nine[:7], range(8, 1, -1))) + int(nine[7:])
    if total % 97 != 0 and (total + 55) % 97 != 0:
        return _bad(number, "This VAT number's check digits don't match. Please check it.")
    return CheckResult(True, "GB" + digits, "Valid format")


# ---------- Australia: ABN ----------

_ABN_WEIGHTS = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)


def check_abn(value: str) -> CheckResult:
    number = normalize(value)
    if not re.fullmatch(r"[0-9]{11}", number):
        return _bad(number, "An ABN has 11 digits")
    digits = [int(d) for d in number]
    digits[0] -= 1
    if sum(d * w for d, w in zip(digits, _ABN_WEIGHTS)) % 89 != 0:
        return _bad(number, "This ABN's check digits don't match. Please check it.")
    return CheckResult(True, number, "Valid format")


# ---------- Canada: GST/HST number ----------

def check_canada_gst(value: str) -> CheckResult:
    number = normalize(value)
    if not re.fullmatch(r"[0-9]{9}RT[0-9]{4}", number):
        return _bad(number, "A GST/HST number is 9 digits, then RT, then 4 digits (e.g. 123456789RT0001)")
    return CheckResult(True, number, "Valid format")


# ---------- European Union: VAT number (format by country) ----------

EU_VAT_FORMATS = {
    "AT": r"U[0-9]{8}", "BE": r"[01][0-9]{9}", "BG": r"[0-9]{9,10}", "CY": r"[0-9]{8}[A-Z]",
    "CZ": r"[0-9]{8,10}", "DE": r"[0-9]{9}", "DK": r"[0-9]{8}", "EE": r"[0-9]{9}", "EL": r"[0-9]{9}",
    "ES": r"[A-Z0-9][0-9]{7}[A-Z0-9]", "FI": r"[0-9]{8}", "FR": r"[A-Z0-9]{2}[0-9]{9}",
    "HR": r"[0-9]{11}", "HU": r"[0-9]{8}", "IE": r"[0-9][A-Z0-9+*][0-9]{5}[A-Z]{1,2}", "IT": r"[0-9]{11}",
    "LT": r"([0-9]{9}|[0-9]{12})", "LU": r"[0-9]{8}", "LV": r"[0-9]{11}", "MT": r"[0-9]{8}",
    "NL": r"[0-9]{9}B[0-9]{2}", "PL": r"[0-9]{10}", "PT": r"[0-9]{9}", "RO": r"[0-9]{2,10}",
    "SE": r"[0-9]{12}", "SI": r"[0-9]{8}", "SK": r"[0-9]{10}",
}


def check_eu_vat(value: str) -> CheckResult:
    number = normalize(value)
    prefix, rest = number[:2], number[2:]
    if prefix == "GR":
        prefix = "EL"  # Greece uses EL for VAT numbers
    pattern = EU_VAT_FORMATS.get(prefix)
    if pattern is None:
        return _bad(number, "Start with your country code, e.g. DE123456789")
    if not re.fullmatch(pattern, rest):
        return _bad(number, f"This doesn't match the VAT number format for {prefix}")
    return CheckResult(True, prefix + rest, "Valid format", {"country_prefix": prefix})


# ---------- United States: EIN (optional) ----------

def check_ein(value: str) -> CheckResult:
    number = normalize(value)
    if not re.fullmatch(r"[0-9]{9}", number):
        return _bad(number, "An EIN has 9 digits (e.g. 12-3456789)")
    return CheckResult(True, f"{number[:2]}-{number[2:]}", "Valid format")


# ---------- Anywhere else ----------

def check_generic_tax_id(value: str) -> CheckResult:
    number = normalize(value)
    if not re.fullmatch(r"[A-Z0-9]{3,30}", number):
        return _bad(number, "Use 3 to 30 letters and numbers")
    return CheckResult(True, number, "Saved as entered")