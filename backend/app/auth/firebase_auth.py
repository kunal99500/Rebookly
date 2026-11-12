"""Client sign-in with Firebase phone codes.

Clients sign in on the app with Firebase (a code by SMS); business owners keep signing in with Supabase.
The backend accepts both: AuthVerifier looks at who issued a token and checks it with the right keys.

A Firebase user ID is text, while Rebookly stores user IDs as UUIDs, so each Firebase user is given a
fixed UUID derived from their Firebase ID (the same person always gets the same UUID).
"""
import uuid

import jwt
from jwt import PyJWKClient

from app.auth.supabase_auth import AuthError, AuthUser

FIREBASE_KEYS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
FIREBASE_NAMESPACE = uuid.UUID("6f2c1a52-1d3e-4c55-9b5e-2b2f6a8f9e41")   # never change: user IDs depend on it


def firebase_user_uuid(firebase_uid: str) -> uuid.UUID:
    return uuid.uuid5(FIREBASE_NAMESPACE, f"firebase:{firebase_uid}")


class FirebaseTokenVerifier:
    def __init__(self, project_id: str, leeway_seconds: int = 30, keys: PyJWKClient | None = None):
        if not project_id:
            raise ValueError("FIREBASE_PROJECT_ID is required to verify Firebase sign-ins")
        self.project_id = project_id
        self.issuer = f"https://securetoken.google.com/{project_id}"
        self._leeway = leeway_seconds
        # Google's public keys, downloaded once and cached.
        self._keys = keys or PyJWKClient(FIREBASE_KEYS_URL, cache_keys=True, lifespan=3600, timeout=10)

    def verify(self, token: str) -> AuthUser:
        try:
            if jwt.get_unverified_header(token).get("alg") != "RS256":
                raise AuthError("Invalid login token")
            key = self._keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"], audience=self.project_id, issuer=self.issuer,
                leeway=self._leeway, options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Your session has expired. Please sign in again.")
        except (jwt.PyJWTError, jwt.PyJWKClientError):
            raise AuthError("Invalid login token")
        if not claims.get("sub"):
            raise AuthError("Invalid login token")
        return AuthUser(
            id=firebase_user_uuid(claims["sub"]),
            phone=claims.get("phone_number"),
            email=claims.get("email"),
            session_id=None,
            is_anonymous=False,
        )


class AuthVerifier:
    """Checks a sign-in token from either Supabase (owners) or Firebase (clients)."""

    def __init__(self, supabase=None, firebase: FirebaseTokenVerifier | None = None):
        self.supabase = supabase
        self.firebase = firebase

    def verify(self, token: str) -> AuthUser:
        try:
            issuer = jwt.decode(token, options={"verify_signature": False}).get("iss", "")
        except jwt.PyJWTError:
            raise AuthError("Invalid login token")
        if issuer.startswith("https://securetoken.google.com/"):
            if self.firebase is None:
                raise AuthError("Phone sign-in isn't set up on this server")
            return self.firebase.verify(token)
        if self.supabase is None:
            raise AuthError("Sign-in isn't set up on this server")
        return self.supabase.verify(token)
