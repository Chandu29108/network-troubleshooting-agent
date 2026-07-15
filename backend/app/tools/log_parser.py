"""
Router log parser tool.

Why a dedicated regex-based tool instead of just handing raw logs to the LLM:
raw router/syslog output is noisy and repetitive (thousands of lines), which
burns context and tokens fast, and LLMs are unreliable at precise pattern
counting (e.g. "how many CRC errors in the last hour?"). This tool does the
deterministic extraction first; the LLM then reasons over a compact, labeled
summary instead of the raw log dump.

Patterns cover common Cisco/Juniper-style syslog messages. Extend
`PATTERNS` to support more vendors/formats as needed.
"""
import re
from langchain_core.tools import tool

PATTERNS = {
    "interface_down": re.compile(r"(?i)interface\s+(\S+).*?(down|changed state to down)"),
    "interface_up": re.compile(r"(?i)interface\s+(\S+).*?(up|changed state to up)"),
    "crc_error": re.compile(r"(?i)CRC error"),
    "packet_loss": re.compile(r"(?i)packet loss|input errors|output errors"),
    "high_latency": re.compile(r"(?i)latency.*?(\d{3,})\s*ms"),
    "bgp_flap": re.compile(r"(?i)BGP.*?(Down|Up|neighbor.*?(reset|flapped))"),
    "duplex_mismatch": re.compile(r"(?i)duplex mismatch"),
    "high_cpu": re.compile(r"(?i)CPU utilization.*?(\d{2,3})%"),
    "auth_failure": re.compile(r"(?i)authentication failure|login failed"),
}


@tool
def parse_router_log(log_text: str) -> str:
    """
    Parse raw router/syslog text and extract a structured summary of
    findings: interface state changes, CRC errors, packet loss, latency
    spikes, BGP flaps, duplex mismatches, high CPU, and auth failures.
    Use this whenever the user pastes raw log lines instead of describing
    the problem in plain language.
    `log_text` is the raw multi-line log content.
    """
    if not log_text or not log_text.strip():
        return "No log text provided."

    findings: dict[str, list[str]] = {key: [] for key in PATTERNS}
    lines = log_text.splitlines()

    for line in lines:
        for key, pattern in PATTERNS.items():
            if pattern.search(line):
                findings[key].append(line.strip())

    summary_lines = [f"Parsed {len(lines)} log lines."]
    any_hits = False
    for key, matches in findings.items():
        if matches:
            any_hits = True
            summary_lines.append(f"- {key} ({len(matches)}): e.g. \"{matches[0][:160]}\"")

    if not any_hits:
        summary_lines.append("No known issue patterns matched. Logs may be clean, "
                              "or use an unrecognized log format.")

    return "\n".join(summary_lines)
