"""
Basic structured logging.

Why this matters for a "professional" project: when the agent misdiagnoses
something in production, you need to see which node ran, what tools fired,
and what the LLM was asked — not just a stack trace. Every agent node and
tool call logs through this logger so you get a readable trace per request.
"""
import logging
import sys


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("netagent")
    if logger.handlers:  # avoid duplicate handlers on reload
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = setup_logging()
