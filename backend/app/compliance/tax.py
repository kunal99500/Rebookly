"""Tax on prices and receipts. Pure functions with exact decimal maths.

Prices that INCLUDE tax (common in India, UK, EU, Australia):  ₹450 incl. 18% -> tax ₹68.64 inside it
Prices that EXCLUDE tax (common in the US and Canada):          $40 + 8%      -> tax $3.20 added on top
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class TaxLine:
    net: Decimal      # before tax
    tax: Decimal
    gross: Decimal    # what the client pays


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def tax_for_price(price: Decimal, rate: Decimal, prices_include_tax: bool) -> TaxLine:
    if rate < 0 or rate > 100:
        raise ValueError("Tax rate must be between 0 and 100")
    price = Decimal(price)
    if prices_include_tax:
        tax = _round(price * rate / (HUNDRED + rate))
        return TaxLine(net=price - tax, tax=tax, gross=price)
    tax = _round(price * rate / HUNDRED)
    return TaxLine(net=price, tax=tax, gross=price + tax)


@dataclass(frozen=True)
class VisitTax:
    lines: tuple[TaxLine, ...]   # one per service, in order
    tax_total: Decimal
    gross_total: Decimal         # what the client pays for the whole visit


def tax_for_visit(prices: list[Decimal], rate: Decimal | None, prices_include_tax: bool) -> VisitTax:
    """Tax each service separately (as invoices list them), then add up. No rate = no tax."""
    if rate is None:
        lines = tuple(TaxLine(Decimal(p), Decimal("0.00"), Decimal(p)) for p in prices)
    else:
        lines = tuple(tax_for_price(p, rate, prices_include_tax) for p in prices)
    return VisitTax(lines=lines, tax_total=sum((l.tax for l in lines), Decimal("0.00")),
                    gross_total=sum((l.gross for l in lines), Decimal("0.00")))


# ---------- how tax appears on receipts ----------

def format_rate(rate: Decimal) -> str:
    """Decimal('18.00') -> '18', Decimal('8.50') -> '8.5'."""
    text = f"{Decimal(rate):f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def receipt_tax_section(
    *, label: str, rate: Decimal, prices_include_tax: bool, amount: Decimal, currency: str,
    registration_label: str | None, registration_number: str | None, legal_name: str | None,
    on_visit_total: bool = False,
) -> dict:
    """The frozen tax block printed on a receipt, e.g. "Includes GST 18%: ₹69.40".

    on_visit_total: the tax belongs to the whole visit's price (confirmations and payment receipts),
    not to the amount on this particular document (such as a deposit).
    """
    from app.rules.formatting import money

    rate_text = f"{label} {format_rate(rate)}%"
    if on_visit_total:
        line = f"{rate_text} {'included in' if prices_include_tax else 'added to'} the visit total"
    else:
        line = f"Includes {rate_text}" if prices_include_tax else rate_text
    return {
        "line": line,
        "amount": money(amount, currency),
        "registration_label": registration_label if registration_number else None,
        "registration_number": registration_number,
        "legal_name": legal_name,
    }