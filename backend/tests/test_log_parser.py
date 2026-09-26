"""
Unit tests for parse_router_log's pattern matching. This tool's output is
fed directly to the LLM as evidence for a diagnosis, so a silently-broken
pattern here degrades diagnosis quality without raising any error.
"""
from app.tools.log_parser import parse_router_log


def _invoke(log_text: str) -> str:
    # parse_router_log is a LangChain @tool; .invoke() runs the underlying fn.
    return parse_router_log.invoke({"log_text": log_text})


def test_empty_log_returns_message():
    assert "No log text provided" in _invoke("")
    assert "No log text provided" in _invoke("   ")


def test_interface_down_detected():
    log = "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down"
    result = _invoke(log)
    assert "interface_down" in result


def test_crc_error_detected():
    log = "Nov 12 04:00:01 sw1: CRC error on interface Gi0/2"
    result = _invoke(log)
    assert "crc_error" in result


def test_bgp_flap_detected():
    log = "BGP-5-ADJCHANGE: neighbor 10.0.0.2 Down BGP Notification sent"
    result = _invoke(log)
    assert "bgp_flap" in result


def test_high_cpu_detected():
    log = "CPU utilization for five seconds: 97%/0%"
    result = _invoke(log)
    assert "high_cpu" in result


def test_clean_log_reports_no_known_patterns():
    log = "Nov 12 04:00:01 sw1: routine keepalive sent"
    result = _invoke(log)
    assert "No known issue patterns matched" in result


def test_line_count_reported():
    log = "line one\nline two\nline three"
    result = _invoke(log)
    assert "Parsed 3 log lines." in result
