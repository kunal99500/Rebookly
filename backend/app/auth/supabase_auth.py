"""Verifies Supabase login tokens (JWTs) so the backend knows exactly who is calling.

Flutter signs the user in with Supabase and sends the access token with each request:
    Authorization: Bearer <access token>
We verify the token's signature, expiry, issuer and audience before trusting anything in it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

ASYMMETRIC_ALGORITHMS = ("ES256", "RS256", "EdDSA")


class AuthError(Exception):
    """The token can't be trusted. The message is safe to show to the user."""


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    phone: str | None
    email: str | None
    session_id: str | None
    is_anonymous: bool


class SupabaseTokenVerifier:
    def __init__(self, supabase_url: str, legacy_jwt_secret: str | None = None, leeway_seconds: int = 30):
        if not supabase_url:
            raise ValueError("SUPABASE_URL is required to verify logins")
        self.issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self._legacy_secret = legacy_jwt_secret or None
        self._leeway = leeway_seconds
        # Downloads Supabase's public keys once and caches them for 10 minutes.
        self._jwks = PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=600, timeout=10)

    def verify(self, token: str) -> AuthUser:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise AuthError("Invalid login token")

        # Choose the key by the algorithm the token claims, but only from an allowed list.
        algorithm = header.get("alg")
        if algorithm in ASYMMETRIC_ALGORITHMS:
            try:
                key = self._jwks.get_signing_key_from_jwt(token).key
            except jwt.PyJWKClientError:
                raise AuthError("Invalid login token")
        elif algorithm == "HS256" and self._legacy_secret:
            key = self._legacy_secret
        else:
            raise AuthError("Invalid login token")

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience="authenticated",
                issuer=self.issuer,
                leeway=self._leeway,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Your session has expired. Sign in again.")
        except jwt.PyJWTError:
            raise AuthError("Invalid login token")

        if claims.get("role") != "authenticated":
            raise AuthError("Invalid login token")
        try:
            user_id = uuid.UUID(claims["sub"])
        except (ValueError, TypeError):
            raise AuthError("Invalid login token")

        return AuthUser(
            id=user_id,
            phone=claims.get("phone") or None,
            email=claims.get("email") or None,
            session_id=claims.get("session_id"),
            is_anonymous=bool(claims.get("is_anonymous", False)),
        )