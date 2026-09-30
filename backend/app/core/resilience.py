"""
Resilience helpers for calling the LLM provider.

Why this exists: Gemini periodically returns 503 "high demand" or 429 "rate
limit" errors. These are temporary — the same request usually succeeds a
few seconds later — so giving up on the first one turns a brief provider
blip into a user-facing failure. We retry those (and only those) a few
times with a short, growing pause, and translate whatever finally fails
into a plain-language message instead of showing users a raw API error dump.

Why not LangChain's `.with_retry()`: wrapping a model in RunnableRetry
replaces token-by-token `astream` with a single buffered response, which
would silently break the live streaming the UI depends on. Hand-rolled
helpers let us retry the *connection* while keeping streaming intact.
"""
import asyncio
import random
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.core.logging_config import logger

MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 1.0  # waits ~1s, then ~2s (plus jitter) between attempts

# Temporary conditions worth retrying: rate limit + provider-side outages.
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

FRIENDLY_BUSY_MESSAGE = (
    "The AI service is busy right now. Please wait a moment and try again."
)
FRIENDLY_GENERIC_MESSAGE = (
    "Something went wrong while generating a response. Please try again."
)


def is_transient_error(exc: BaseException) -> bool:
    """True for temporary provider errors (503 overload, 429 rate limit, ...)."""
    return getattr(exc, "code", None) in TRANSIENT_STATUS_CODES


def friendly_error_message(exc: BaseException) -> str:
    """Plain-language text for users. The full error still goes to the logs."""
    return FRIENDLY_BUSY_MESSAGE if is_transient_error(exc) else FRIENDLY_GENERIC_MESSAGE


def _delay_for(attempt: int) -> float:
    # attempt is 1-based: 1s, 2s, ... with up to 25% jitter so simultaneous
    # users who all failed together don't all retry at the same instant.
    base = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
    return base + random.uniform(0, base * 0.25)  # noqa: S311


def invoke_with_retry(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a blocking LLM function, retrying transient errors. Runs in a
    worker thread under LangGraph, so time.sleep here doesn't block the loop."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not is_transient_error(exc) or attempt == MAX_ATTEMPTS:
                raise
            delay = _delay_for(attempt)
            logger.warning(
                "LLM transient error (code=%s), retry %d/%d in %.1fs",
                getattr(exc, "code", "?"), attempt, MAX_ATTEMPTS - 1, delay,
            )
            time.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover


async def astream_with_retry(
    stream_factory: Callable[[], AsyncIterator[Any]],
) -> AsyncIterator[Any]:
    """
    Stream chunks from the LLM, retrying transient failures — but only if
    the failure happens BEFORE the first chunk has been yielded. Once the
    user has already seen partial text, restarting would duplicate or
    garble the answer, so a mid-stream failure is raised instead.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        yielded_any = False
        try:
            async for chunk in stream_factory():
                yielded_any = True
                yield chunk
            return
        except Exception as exc:
            if yielded_any or not is_transient_error(exc) or attempt == MAX_ATTEMPTS:
                raise
            delay = _delay_for(attempt)
            logger.warning(
                "LLM stream transient error (code=%s), retry %d/%d in %.1fs",
                getattr(exc, "code", "?"), attempt, MAX_ATTEMPTS - 1, delay,
            )
            await asyncio.sleep(delay)
