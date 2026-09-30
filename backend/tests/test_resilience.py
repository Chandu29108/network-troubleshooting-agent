"""
Tests for transient-LLM-error handling. Uses a fake exception carrying a
`.code` attribute (same shape as google.genai's real ServerError) so no
network or real API key is involved, and zeroes the retry delay so the
suite stays fast.
"""
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


def test_invoke_does_not_retry_non_transient():
    calls = {"n": 0}

    def bad_request():
        calls["n"] += 1
        raise FakeAPIError(400)

    with pytest.raises(FakeAPIError):
        resilience.invoke_with_retry(bad_request)
    assert calls["n"] == 1


async def _collect(factory):
    return [c async for c in resilience.astream_with_retry(factory)]


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
