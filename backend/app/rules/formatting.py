"""How money and times are shown to people. Pure functions, shared by the checkout page and documents."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "AUD": "A$", "CAD": "C$"}


def money(amount: Decimal | int | str, currency: str) -> str:
    """Decimal('1234.5'), 'USD' -> '$1,234.50'. Unknown currencies show their code: '1,234.50 CHF'."""
    value = Decimal(str(amount))
    symbol = CURRENCY_SYMBOLS.get(currency)
    return f"{symbol}{value:,.2f}" if symbol else f"{value:,.2f} {currency}"


def local_time(moment: datetime, tz: str) -> str:
    """A UTC moment shown in the business's time zone: 'Tue 20 Oct, 7:00 AM'."""
    return moment.astimezone(ZoneInfo(tz)).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")