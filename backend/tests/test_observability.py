"""
Sentry is deliberately never turned on in tests (SENTRY_DSN is unset in
conftest.py) — these tests just confirm init_sentry() itself behaves
correctly in both states, without ever needing a real DSN or network call.
"""
import sentry_sdk

from app.config import get_settings
from app.core.observability import init_sentry


def test_init_sentry_is_noop_without_dsn():
    """No SENTRY_DSN set (the test-suite default) -> no Sentry client."""
    init_sentry()
    assert sentry_sdk.get_client().is_active() is False


def test_init_sentry_activates_with_dsn(monkeypatch):
    """A valid-looking DSN actually initializes the client."""
    monkeypatch.setenv("SENTRY_DSN", "https://examplekey@o0.ingest.sentry.io/0")
    get_settings.cache_clear()
    try:
        init_sentry()
        assert sentry_sdk.get_client().is_active() is True
    finally:
        # Don't leak an active Sentry client into other tests.
        sentry_sdk.get_client().close()
        get_settings.cache_clear()
