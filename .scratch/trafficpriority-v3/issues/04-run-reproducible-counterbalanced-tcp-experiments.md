# 04: Run reproducible and counterbalanced TCP experiments

**What to build:** A user can run a controlled TCP comparison with explicit warm-up and measurement periods, configurable repetitions, recorded configuration, counterbalanced scenario order, and dependable cleanup between runs.

**Blocked by:** 02: Record trustworthy receiver-side TCP throughput; 03: Use one verified OVS HTB bottleneck foundation.

**Status:** implemented-awaiting-privileged-verification

- [ ] Warm-up traffic is excluded from the documented measurement window, and configured duration, actual timing, launch skew, repetition, and scenario order are recorded.
- [ ] Scenario order can be reproducibly randomized or counterbalanced using a recorded seed, while a compatibility option retains the familiar v2 workflow.
- [ ] Every run records the effective policy, environment, kernel, container, Python, Ryu, OVS, Mininet, and traffic-tool metadata available in the environment.
- [ ] Networks, processes, counters, and owned QoS state are cleaned between scenarios and after failures, and incomplete or internally inconsistent CSV data is rejected by tests and analysis.

## Implementation notes

Added separate warm-up connections, seeded counterbalanced/random ordering, a legacy ordering option, repetition/session metadata, actual measurement and egress-counter windows, effective policy snapshots and hashes, and environment metadata. Scenario sessions recreate the network/controller. Failure cleanup now stops the controller even when network cleanup raises, and partial client/server launches stop already launched processes. CSV validation checks repetition completeness, duplicates, timing validity, and metadata consistency. Separate warm-up does not preserve TCP congestion-control state in measured connections; the methodology documents that limitation. Privileged execution remains pending alongside Tickets 02 and 03.

