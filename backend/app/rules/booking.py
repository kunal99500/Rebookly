"""Small, pure booking rules shared by the booking service and its tests."""
import secrets
from decimal import Decimal

CONFIRMATION_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L: easy to read aloud
PAYMENT_WINDOW_MINUTES = 15          # how long a seat is held while the client pays
MAX_ACTIVE_BOOKINGS_PER_BUSINESS = 3  # stops one person blocking a business's calendar


def hold_amount(price: Decimal, deposit: Decimal, payment_option: str) -> Decimal:
    """How much PayPal should hold for this payment option."""
    if payment_option == "deposit_held":
        return deposit
    if payment_option == "full_held":
        return price
    raise ValueError(f"Unknown payment option: {payment_option}")


def new_confirmation_number() -> str:
    """e.g. RB-7K2M-9QXD: short, readable, and practically impossible to guess."""
    chars = "".join(secrets.choice(CONFIRMATION_ALPHABET) for _ in range(8))
    return f"RB-{chars[:4]}-{chars[4:]}"


def new_check_in_token() -> str:
    return secrets.token_urlsafe(32)