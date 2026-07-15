"""
Network diagnostic tools, exposed to the LLM via LangChain's @tool decorator.

Why real subprocess calls instead of hardcoded fakes: ping/traceroute are
read-only, non-destructive diagnostic commands (same as a network engineer
would run) — this is what makes the "tool calling" feature genuinely useful
rather than decorative. Both are wrapped with a strict timeout and a
hostname allow-pattern so the LLM can't be tricked into shelling out
arbitrary commands.
"""
import re
import subprocess

from langchain_core.tools import tool

# Only allow sane hostnames/IPs — blocks flag-injection like "-e; rm -rf /"
_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9.\-:]+$")


def _validate_host(host: str) -> str | None:
    if not host or len(host) > 255 or not _HOST_PATTERN.match(host):
        return "Invalid host format. Provide a plain hostname or IP address."
    return None


@tool
def ping_host(host: str) -> str:
    """
    Ping a host to check reachability and latency. Use this when diagnosing
    connectivity issues, packet loss, or high latency reported in logs.
    `host` must be a plain hostname or IP address, e.g. '8.8.8.8' or 'router1.local'.
    """
    error = _validate_host(host)
    if error:
        return error
    try:
        result = subprocess.run(
            ["ping", "-c", "4", "-W", "2", host],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout or result.stderr
        return output.strip() or "No output returned from ping."
    except FileNotFoundError:
        return "ping binary not available in this environment."
    except subprocess.TimeoutExpired:
        return f"Ping to {host} timed out."


@tool
def traceroute_host(host: str) -> str:
    """
    Trace the network path to a host to identify where packet loss or
    latency spikes occur. Use this for routing / hop-level diagnosis.
    `host` must be a plain hostname or IP address.
    """
    error = _validate_host(host)
    if error:
        return error
    try:
        result = subprocess.run(
            ["tracert", "-h", "12", "-w", "2000", host],
            capture_output=True,
            text=True,
            timeout=25,
        )
        output = result.stdout or result.stderr
        return output.strip() or "No output returned from tracert."
    except FileNotFoundError:
        return "tracert command not available in this environment."
    except subprocess.TimeoutExpired:
        return f"Traceroute to {host} timed out."


NETWORK_TOOLS = [ping_host, traceroute_host]
