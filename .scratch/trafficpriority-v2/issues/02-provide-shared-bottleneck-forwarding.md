# 02: Provide forwarding through a shared bottleneck

**What to build:** A connected Mininet testbed in which both traffic sources can reach the receiver through the same measurable 5 Mbps bottleneck, with deliberate OpenFlow 1.3 controller attachment and reliable bidirectional connectivity.

**Blocked by:** 01: Capture a truthful, reproducible v1 baseline.

**Status:** resolved

- [x] High-priority and best-effort source hosts reach the intended receiver through the same inter-switch link.
- [x] The shared link is configured as a 5 Mbps bottleneck while access links have enough capacity not to become the limiting path.
- [x] Both switches intentionally use OpenFlow 1.3 and connect to the expected controller.
- [x] Startup does not pre-populate flows in a way that hides first-packet classification during verification.
- [x] Connectivity and the effective port layout can be verified with documented commands.

## Implementation notes

The topology now uses 10 Mbps access links and a bidirectional 5 Mbps `s1-eth3 <-> s2-eth1` inter-switch link. A privileged runtime verification showed both switches connected, only the table-miss flow before deliberate traffic, `0% dropped (12/12 received)` after an explicit `pingall`, and an HTB class on `s1-eth3` with `rate 5Mbit ceil 5Mbit`.
