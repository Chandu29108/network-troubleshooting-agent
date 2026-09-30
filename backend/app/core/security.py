"""
Clerk session-token verification.

Why hand-rolled JWKS verification instead of the full `clerk-backend-api`
SDK: this app only needs to answer one question per request — "is this a
valid, unexpired session token, and whose user id is it?" — which is
exactly what JWKS + PyJWT does directly, without pulling in a heavier
dependency whose other features (organizations, webhooks, user
management API) this app doesn't use.

How it works: Clerk signs session tokens with RS256, and publishes the
public verification keys at a well-known JWKS URL under your Clerk
instance's issuer domain. We fetch and cache that key set, find the key
matching the token's `kid` header, and verify the signature + expiry +
issuer. The token's `sub` claim is the Clerk user id — that's what every
auth-gated endpoint uses to scope data to the right user.
"""
from __future__ import annotations

import time

import httpx
import jwt
import sentry_sdk
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)

# Simple time-based cache: Clerk's signing keys rotate rarely, so
# re-fetching on every single request would be a wasteful, avoidable
# network call in the hot path of every authenticated endpoint.
_JWKS_CACHE_TTL_SECONDS = 3600
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}


def _jwks_url() -> str:
    return f"{get_settings().clerk_issuer.rstrip('/')}/.well-known/jwks.json"


def _get_jwks() -> dict:
    now = time.time()
    is_stale = (now - _jwks_cache["fetched_at"]) > _JWKS_CACHE_TTL_SECONDS
    if _jwks_cache["keys"] is None or is_stale:
        response = httpx.get(_jwks_url(), timeout=5)
        response.raise_for_status()
        _jwks_cache["keys"] = response.json()
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


def _find_signing_key(jwks: dict, kid: str | None):
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    return None


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency: verifies the request's `Authorization: Bearer <token>`
    header as a Clerk session token and returns the Clerk user id (the `sub`
    claim). Raises 401 for anything missing/invalid/expired — this is the
    single gate every auth-required endpoint depends on.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = credentials.credentials
    try:
        unverified_header = jwt.get_unverified_header(token)
        signing_key = _find_signing_key(_get_jwks(), unverified_header.get("kid"))
        if signing_key is None:
            raise HTTPException(status_code=401, detail="Unknown signing key")

        payload = jwt.decode(
            token,
            key=signing_key,
            algorithms=["RS256"],
            issuer=get_settings().clerk_issuer,
            # Clerk session tokens don't set a single fixed `aud` this app
            # needs to check; issuer + signature are the real trust boundary.
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    # Tags this request's Sentry events (if any) with who hit the error —
    # a no-op when Sentry isn't initialized (SENTRY_DSN unset), so this is
    # safe to leave in for local dev and the test suite too.
    sentry_sdk.set_user({"id": user_id})

    return user_id
