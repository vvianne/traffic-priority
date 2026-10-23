# 07: Analyze and plot the extended experiment matrix

**What to build:** A user can validate and analyze baseline and static-QoS experiments across light, near-capacity, and congested loads, producing traceable comparisons of delivered throughput, latency, jitter, loss, and bottleneck utilization.

**Blocked by:** 05: Run protocol-aware UDP class experiments; 06: Measure latency under controlled congestion.

**Status:** implemented-offline-validated-awaiting-v3-evidence

- [ ] Validation requires complete, internally consistent scenario/load/protocol/class repetitions while allowing explicitly unavailable metrics only where justified.
- [ ] Summaries distinguish sender, receiver, and egress throughput and use receiver measurements for delivered-traffic comparisons.
- [ ] Generated tables and plots cover per-class throughput, RTT, UDP jitter and loss, and bottleneck utilization with sample counts and variability.
- [ ] Every artifact identifies its raw-data source and contains only recorded measurements; tests cover incomplete matrices, invalid values, aggregation, and plot generation.

## Implementation notes

The analyzer now validates extended protocol/RTT/UDP/utilization data and emits a unit-aware extended summary, eleven metric plots, and embedded report tables. Receiver throughput remains the application-delivery metric while sender and switch metrics are separately labelled. Switch measurements count once per run; unavailable metrics retain reasons/counts and never become plotted zeroes. Summaries and plots identify the raw filename and SHA-256. Tests cover CLI artifact generation, SVG parsing, protocol consistency, missing/invalid metrics, matrix incompleteness, variability, and independent-run counting. Historical v2 package verification still passes. Offline behavior is validated with explicitly synthetic test fixtures; actual v3 experiment evidence remains pending the privileged environment required by Tickets 05 and 06.

