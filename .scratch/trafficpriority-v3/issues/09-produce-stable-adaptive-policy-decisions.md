# 09: Produce stable adaptive policy decisions

**What to build:** Live telemetry produces understandable, logged recommendations for default or congestion allocations using a deterministic heuristic that protects best effort and does not oscillate on noisy measurements.

**Blocked by:** 01: Load and validate backward-compatible QoS configuration; 08: Capture live bottleneck and traffic-class telemetry.

**Status:** ready-for-agent

- [ ] A pure decision component applies configured EWMA smoothing, entry and exit thresholds, hysteresis, and minimum dwell time.
- [ ] Every recommendation preserves the configured best-effort minimum, uses non-negative rates, and keeps guaranteed allocations within parent capacity.
- [ ] Unchanged conditions do not generate redundant updates, while decisions and suppressed transitions record their input, state, reason, and time.
- [ ] Unit tests cover threshold boundaries, EWMA behavior, sustained and transient congestion, hysteresis, dwell time, clock behavior, invalid telemetry, and allocation constraints.

