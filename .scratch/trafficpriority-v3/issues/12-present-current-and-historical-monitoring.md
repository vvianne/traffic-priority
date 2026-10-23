# 12: Present current and historical experiment monitoring

**What to build:** A lightweight interface lets a user inspect current network state and browse historical verified experiments without deploying a large observability stack.

**Blocked by:** 11: Compare baseline, static, and adaptive QoS.

**Status:** ready-for-agent

- [ ] The interface presents utilization, traffic-class throughput, active QoS mode, queue minimums, congestion state, and recent adaptive decisions from recorded or live data.
- [ ] Historical views identify experiments and compare their scenarios, loads, metrics, and provenance without mixing incompatible runs.
- [ ] Missing, stale, invalid, and unverified information is visibly distinguished from measured zero values.
- [ ] The interface is documented, testable without privileged networking, lightweight enough for the existing Python project, and contains no fabricated demonstration data.

