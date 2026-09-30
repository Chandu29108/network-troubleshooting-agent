"""
Rate limiting.

Why per-user rather than per-IP: this app now has real auth (Phase 4), and
a per-IP limit is the wrong unit here — several people behind the same
office/college NAT would share one limit, while one person switching
networks would get a fresh one. Keying by the Clerk user id is both more
accurate and harder to dodge.

Why the key function re-reads the token itself instead of depending on
get_current_user_id: slowapi's key_func runs on every request BEFORE
FastAPI resolves route dependencies, so it can't consume the result of
another dependency. It also must never raise — an unparseable token here
just falls back to IP-based limiting; the *actual* auth check still
happens in get_current_user_id as normal, so a forged or missing token
gains nothing beyond which throttling bucket it lands in.
"""
import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :]
        try:
            # Signature is NOT verified here — this is only ever used to
            # pick a rate-limit bucket, never to authorize anything. Real
            # verification happens in get_current_user_id.
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_limit_key)
