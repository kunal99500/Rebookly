"""Tests for Supabase token verification, using locally generated keys (no network)."""
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.supabase_auth import AuthError, SupabaseTokenVerifier

SUPABASE_URL = "https://testproject.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
USER_ID = uuid.uuid4()
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())  # plays the role of Supabase's signing key
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())    # an attacker's key


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeJWKS:
    """Stands in for Supabase's public key endpoint."""
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey(self.public_key)


def make_verifier(public_key=None, legacy_secret=None) -> SupabaseTokenVerifier:
    verifier = SupabaseTokenVerifier(SUPABASE_URL, legacy_jwt_secret=legacy_secret)
    verifier._jwks = FakeJWKS(public_key or PRIVATE_KEY.public_key())
    return verifier


def make_token(key=PRIVATE_KEY, algorithm="ES256", **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER, "aud": "authenticated", "sub": str(USER_ID), "role": "authenticated",
        "iat": now, "exp": now + 3600, "phone": "15551234567", "session_id": "s1",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": "test-key"})


def test_valid_token_returns_user():
    user = make_verifier().verify(make_token())
    assert user.id == USER_ID
    assert user.phone == "15551234567"
    assert not user.is_anonymous


def test_expired_token_is_rejected_with_friendly_message():
    with pytest.raises(AuthError, match="expired"):
        make_verifier().verify(make_token(exp=int(time.time()) - 120))


def test_token_signed_by_another_key_is_rejected():
    with pytest.raises(AuthError):
        make_verifier().verify(make_token(key=OTHER_KEY))


@pytest.mark.parametrize("claim, value", [
    ("iss", "https://evil.example.com/auth/v1"),
    ("aud", "something-else"),
    ("role", "anon"),
    ("sub", "not-a-uuid"),
])
def test_wrong_claims_are_rejected(claim, value):
    with pytest.raises(AuthError):
        make_verifier().verify(make_token(**{claim: value}))


def test_missing_expiry_is_rejected():
    with pytest.raises(AuthError):
        make_verifier().verify(make_token(exp=None))


def test_unsigned_token_is_rejected():
    token = jwt.encode({"sub": str(USER_ID), "aud": "authenticated", "iss": ISSUER, "role": "authenticated"},
                       key=None, algorithm="none")
    with pytest.raises(AuthError):
        make_verifier().verify(token)


def test_hs256_rejected_without_legacy_secret():
    token = make_token(key="a-shared-secret-that-is-long-enough-1234", algorithm="HS256")
    with pytest.raises(AuthError):
        make_verifier().verify(token)


def test_hs256_accepted_with_matching_legacy_secret():
    secret = "a-shared-secret-that-is-long-enough-1234"
    user = make_verifier(legacy_secret=secret).verify(make_token(key=secret, algorithm="HS256"))
    assert user.id == USER_ID


def test_garbage_is_rejected():
    with pytest.raises(AuthError):
        make_verifier().verify("not.a.token")