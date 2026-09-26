"""
Unit tests for host-input validation in network_tools.py.

This is the security boundary between LLM-controlled tool-call arguments
and a real subprocess.run() call, so it's the highest-value place to have
regression coverage — a broken regex here is a shell-injection risk.
"""
import pytest

from app.tools.network_tools import _validate_host


@pytest.mark.parametrize(
    "host",
    [
        "8.8.8.8",
        "router1.local",
        "10.0.0.1",
        "example.com",
        "2001:db8::1",
        "a" * 255,  # exactly at the length limit
    ],
)
def test_validate_host_accepts_plain_hosts(host):
    assert _validate_host(host) is None


@pytest.mark.parametrize(
    "host",
    [
        "",
        None,
        "8.8.8.8; rm -rf /",
        "-e evil",
        "--flag=x",
        "host && whoami",
        "host`whoami`",
        "host$(whoami)",
        "a" * 256,  # one over the length limit
        "host with spaces",
    ],
)
def test_validate_host_rejects_unsafe_input(host):
    assert _validate_host(host) is not None
