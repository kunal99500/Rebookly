"""Tests for phone number protection."""
import pytest
from cryptography.fernet import Fernet

from app.security.phone import PhoneError, PhoneProtector, mask_phone, normalize_phone

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()
HASH_KEY = "x" * 40


def make_protector(keys=KEY_A, hash_key=HASH_KEY) -> PhoneProtector:
    return PhoneProtector(keys, hash_key)


@pytest.mark.parametrize("raw, region, expected", [
    ("+44 7911 123456", None, "+447911123456"),
    ("447911123456", None, "+447911123456"),
    ("07911 123456", "GB", "+447911123456"),
    ("+1 (202) 555-0143", None, "+12025550143"),
    ("98765 43210", "IN", "+919876543210"),
])
def test_numbers_are_normalized_to_international_format(raw, region, expected):
    assert normalize_phone(raw, region) == expected


@pytest.mark.parametrize("raw", ["", "abc", "+1 123", "12345", "+44 0000 000000"])
def test_invalid_numbers_are_rejected(raw):
    with pytest.raises(PhoneError):
        normalize_phone(raw)


def test_mask_shows_country_code_and_last_four():
    assert mask_phone("+447911123456") == "+44 •••• ••3456"


def test_same_number_always_gives_same_hash_whatever_the_format():
    protector = make_protector()
    assert protector.protect("+44 7911 123456").hash == protector.protect("07911123456", "GB").hash


def test_hash_depends_on_secret_key():
    number = "+447911123456"
    assert make_protector().hash(number) != make_protector(hash_key="y" * 40).hash(number)


def test_encrypted_number_round_trips_and_is_not_readable():
    protector = make_protector()
    protected = protector.protect("+44 7911 123456")
    assert b"7911123456" not in protected.encrypted
    assert protector.reveal(protected.encrypted) == "+447911123456"
    assert protected.last4 == "3456"


def test_encrypting_twice_gives_different_ciphertext():
    protector = make_protector()
    assert protector.protect("+447911123456").encrypted != protector.protect("+447911123456").encrypted


def test_key_rotation_keeps_old_numbers_readable():
    old = make_protector(KEY_A).protect("+447911123456")
    rotated = make_protector(f"{KEY_B},{KEY_A}")
    assert rotated.reveal(old.encrypted) == "+447911123456"


def test_wrong_key_cannot_decrypt():
    encrypted = make_protector(KEY_A).protect("+447911123456").encrypted
    with pytest.raises(RuntimeError):
        make_protector(KEY_B).reveal(encrypted)


@pytest.mark.parametrize("keys, hash_key", [("", HASH_KEY), ("not-a-key", HASH_KEY), (KEY_A, "short")])
def test_bad_keys_are_refused_at_startup(keys, hash_key):
    with pytest.raises(ValueError):
        PhoneProtector(keys, hash_key)