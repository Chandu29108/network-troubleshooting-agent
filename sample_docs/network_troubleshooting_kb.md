# Internal Network Troubleshooting Runbook

## Interface Down / Flapping (LINK-3-UPDOWN)
A flapping interface (repeatedly changing between up and down) is most
commonly caused by:
1. A bad or loose cable/SFP — reseat or swap the cable first.
2. Duplex mismatch between the local port and the connected device.
3. A failing transceiver reporting high optical power variance.
Fix priority: reseat cable → check `show interface status` for
input/output errors → replace SFP if CRC errors persist after reseating.

## CRC Errors
High CRC error counts on an interface almost always point to a physical
layer problem: damaged cable, dirty fiber connector, or a mismatched
speed/duplex setting. CRC errors are not typically caused by software
configuration. Clear counters, wait 5 minutes, and re-check before
concluding the fix worked.

## Duplex Mismatch
Occurs when one side of a link is set to full duplex and the other to
half duplex (or auto-negotiation failed). Symptoms: late collisions,
FCS errors, and unusually slow throughput despite low utilization.
Fix: set both ends to `auto` or explicitly match duplex/speed on both
sides — never mix explicit and auto on either end of the same link.

## High Latency
Latency above 150ms on an intra-region link usually indicates either
route congestion or a suboptimal path (asymmetric routing). Use
traceroute to identify which hop introduces the delay. If the delay
appears at the last hop only, the issue is local to that device, not
the network path.

## Packet Loss
Sustained packet loss over 1% warrants checking interface error
counters first (before assuming congestion). If counters are clean but
loss persists, check for QoS policy drops or an oversubscribed uplink.

## BGP Neighbor Flapping
A BGP neighbor that repeatedly resets is commonly caused by:
1. An unstable underlying link (check interface errors first).
2. Hold-timer mismatches between peers.
3. Maximum-prefix limit being hit, causing the session to be torn down.
Always check the interface layer before touching BGP configuration —
BGP flaps are frequently a symptom, not the root cause.

## High CPU Utilization
Sustained CPU above 80% on a router can cause missed keepalives,
which in turn causes BGP/OSPF neighbor flaps that look unrelated to
CPU at first glance. Check `show processes cpu sorted` before assuming
a routing protocol issue.

## Authentication Failures
Repeated login/authentication failures from the same source in a short
window may indicate a misconfigured automation script (wrong
credentials in a monitoring tool) rather than a security incident —
but should still be cross-checked against expected source IPs.
