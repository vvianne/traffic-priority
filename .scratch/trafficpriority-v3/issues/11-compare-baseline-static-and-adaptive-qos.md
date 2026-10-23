# 11: Compare baseline, static, and adaptive QoS

**What to build:** A user can run baseline, static, and adaptive QoS under controlled equivalent traffic and determine from saved evidence whether adaptive allocation offers a measurable advantage or disadvantage.

**Blocked by:** 07: Analyze and plot the extended experiment matrix; 10: Apply adaptive queue allocations safely at runtime.

**Status:** ready-for-agent

- [ ] All three modes use the same topology, parent bottleneck, traffic definitions, measurement windows, load levels, repetition policy, and recorded scenario ordering except for the allocation behavior under test.
- [ ] Results include receiver throughput, per-class metrics, RTT, applicable UDP jitter and loss, port and queue utilization, policy-update count, congestion time, and policy transitions.
- [ ] Analysis compares modes with sample counts and variability and reports neutral or negative adaptive results as faithfully as positive results.
- [ ] Adaptive runs are not accepted as verified unless logs and runtime inspection show actual queue changes and corresponding measurements; unsupported privileged execution is reported as unverified.

