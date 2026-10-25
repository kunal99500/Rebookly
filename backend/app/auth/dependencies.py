"""FastAPI dependencies that identify the caller.

Use in any route that needs a signed-in user:
    async def handler(user: AuthUser = Depends(get_current_user)): ...
"""
import asyncio

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.supabase_auth import AuthError, AuthUser, SupabaseTokenVerifier

_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def _verifier(request: Request) -> SupabaseTokenVerifier:
    verifier = getattr(request.app.state, "auth", None)
    if verifier is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Sign-in is not configured on the server")
    return verifier


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue", headers=_CHALLENGE)
    verifier = _verifier(request)
    try:
        # Runs in a worker thread, because fetching keys (rarely) waits on the network.
        return await asyncio.to_thread(verifier.verify, credentials.credentials)
    except AuthError as err:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(err), headers=_CHALLENGE)