"""
Tests for transient-LLM-error handling. Uses a fake exception carrying a
`.code` attribute (same shape as google.genai's real ServerError) so no
network or real API key is involved, and zeroes the retry delay so the
suite stays fast.
"""
import httpx
import pytest

from app.core import resilience


class FakeAPIError(Exception):
    def __init__(self, code: int):
        super().__init__(f"fake {code}")
        self.code = code


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(resilience, "BASE_DELAY_SECONDS", 0.0)


def test_transient_classification():
    assert resilience.is_transient_error(FakeAPIError(503))
    assert resilience.is_transient_error(FakeAPIError(429))
    assert not resilience.is_transient_error(FakeAPIError(400))
    assert not resilience.is_transient_error(ValueError("no code attr"))


def test_friendly_messages_hide_raw_error():
    busy = resilience.friendly_error_message(FakeAPIError(503))
    other = resilience.friendly_error_message(FakeAPIError(400))
    assert "busy" in busy.lower()
    assert "503" not in busy and "UNAVAILABLE" not in busy
    assert "went wrong" in other.lower()


def test_invoke_retries_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise FakeAPIError(503)
        return "ok"

    assert resilience.invoke_with_retry(flaky) == "ok"
    assert calls["n"] == 3


def test_invoke_gives_up_after_max_attempts():
    calls = {"n": 0}

    def always_down():
        calls["n"] += 1
        raise FakeAPIError(503)

    with pytest.raises(FakeAPIError):
        resilience.invoke_with_retry(always_down)
    assert calls["n"] == resilience.MAX_ATTEMPTS


def test_network_timeout_is_transient():
    """Regression test: a real production traceback showed httpx.ReadTimeout
    (Gemini's streaming API taking too long) was NOT being retried, because
    it has no `.code` attribute -- the original check was code-only. Any
    httpx transport-level failure (timeouts, connection errors) must count
    as transient, same as a provider 503."""
    assert resilience.is_transient_error(httpx.ReadTimeout("timed out"))
    assert resilience.is_transient_error(httpx.ConnectTimeout("timed out"))
    assert resilience.is_transient_error(httpx.ConnectError("connection refused"))


def test_invoke_retries_network_timeout_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ReadTimeout("timed out")
        return "ok"

    assert resilience.invoke_with_retry(flaky) == "ok"
    assert calls["n"] == 2


def test_invoke_does_not_retry_non_transient():
    calls = {"n": 0}

    def bad_request():
        calls["n"] += 1
        raise FakeAPIError(400)

    with pytest.raises(FakeAPIError):
        resilience.invoke_with_retry(bad_request)
    assert calls["n"] == 1


def test_invoke_falls_back_after_primary_exhausted():
    """Primary always 503s; fallback should be tried and succeed."""
    primary_calls = {"n": 0}
    fallback_calls = {"n": 0}

    def primary():
        primary_calls["n"] += 1
        raise FakeAPIError(503)

    def fallback():
        fallback_calls["n"] += 1
        return "ok from fallback"

    result = resilience.invoke_with_retry_and_fallback(primary, fallback)
    assert result == "ok from fallback"
    assert primary_calls["n"] == resilience.MAX_ATTEMPTS
    assert fallback_calls["n"] == 1


def test_invoke_does_not_fall_back_for_non_transient_error():
    fallback_calls = {"n": 0}

    def primary():
        raise FakeAPIError(400)

    def fallback():
        fallback_calls["n"] += 1
        return "should not be called"

    with pytest.raises(FakeAPIError):
        resilience.invoke_with_retry_and_fallback(primary, fallback)
    assert fallback_calls["n"] == 0


def test_invoke_raises_if_both_primary_and_fallback_exhausted():
    def primary():
        raise FakeAPIError(503)

    def fallback():
        raise FakeAPIError(503)

    with pytest.raises(FakeAPIError):
        resilience.invoke_with_retry_and_fallback(primary, fallback)


async def _collect(factory):
    return [c async for c in resilience.astream_with_retry(factory)]


async def _collect_with_fallback(primary_factory, fallback_factory):
    return [
        c
        async for c in resilience.astream_with_retry_and_fallback(
            primary_factory, fallback_factory
        )
    ]


@pytest.mark.asyncio
async def test_stream_falls_back_after_primary_exhausted():
    async def primary_factory():
        raise FakeAPIError(503)
        yield  # pragma: no cover -- makes this an async generator function

    async def fallback_factory():
        yield "from fallback"

    result = await _collect_with_fallback(primary_factory, fallback_factory)
    assert result == ["from fallback"]


@pytest.mark.asyncio
async def test_stream_does_not_fall_back_after_partial_primary_output():
    """Once the primary has already streamed visible text, a transient
    failure should raise rather than switch models mid-answer."""

    async def primary_factory():
        yield "partial"
        raise FakeAPIError(503)

    async def fallback_factory():
        yield "should not appear"  # pragma: no cover

    with pytest.raises(FakeAPIError):
        await _collect_with_fallback(primary_factory, fallback_factory)


@pytest.mark.asyncio
async def test_stream_retries_when_failure_before_first_chunk():
    attempts = {"n": 0}

    async def factory_gen():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise FakeAPIError(503)
        yield "a"
        yield "b"

    assert await _collect(factory_gen) == ["a", "b"]
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_partial_output():
    attempts = {"n": 0}

    async def factory_gen():
        attempts["n"] += 1
        yield "partial"
        raise FakeAPIError(503)

    with pytest.raises(FakeAPIError):
        await _collect(factory_gen)
    assert attempts["n"] == 1  # restarting would duplicate visible text
