"""
Sentry error tracking.

Kept as a single init call, guarded by whether SENTRY_DSN is set, so local
dev and the test suite never need a Sentry account — sentry_sdk becomes a
harmless no-op client when init() is never called, so nothing elsewhere in
the app needs to check "is Sentry on" before using it (see
core/security.py's sentry_sdk.set_user call, for example).
"""
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import get_settings
from app.core.logging_config import logger


def init_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        logger.info("SENTRY_DSN not set — Sentry error tracking is disabled")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        # 10% of requests get full performance traces (latency breakdown per
        # endpoint/DB call) — enough to spot slow paths without paying to
        # trace every single request. Errors are always captured regardless
        # of this number; it only affects performance/tracing data.
        traces_sample_rate=0.1,
        # Sends the LLM prompt/response and other request bodies only if
        # explicitly enabled later — off by default so a Sentry event never
        # accidentally contains a user's network logs or symptoms text.
        send_default_pii=False,
    )
    logger.info("Sentry error tracking enabled (environment=%s)", settings.environment)
