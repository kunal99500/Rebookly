"""Tests for adding a client email with a code (no database needed)."""
import uuid

import pytest

from app.services.client_email import code_hash, code_matches, new_code, normalize_email

SECRET = "test-secret"
CLIENT = uuid.uuid4()


@pytest.mark.parametrize("raw, clean", [("Priya@Example.com ", "priya@example.com"), ("a.b+c@mail.co.in", "a.b+c@mail.co.in")])
def test_emails_are_normalized(raw, clean):
    assert normalize_email(raw) == clean


@pytest.mark.parametrize("bad", ["", "priya", "priya@", "@example.com", "pri ya@example.com", "x@y"])
def test_invalid_emails_are_refused(bad):
    with pytest.raises(ValueError):
        normalize_email(bad)


def test_codes_are_six_digits():
    codes = {new_code() for _ in range(50)}
    assert all(len(c) == 6 and c.isdigit() for c in codes) and len(codes) > 40


def test_code_is_checked_against_its_hash_only():
    stored = code_hash(SECRET, CLIENT, "123456")
    assert "123456" not in stored
    assert code_matches(SECRET, CLIENT, " 123456 ", stored)
    assert not code_matches(SECRET, CLIENT, "123457", stored)
    assert not code_matches(SECRET, uuid.uuid4(), "123456", stored)     # tied to this client
    assert not code_matches("other-secret", CLIENT, "123456", stored)    # and to the server's key
    assert not code_matches(SECRET, CLIENT, "123456", None)