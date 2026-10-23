# 06: Measure latency under controlled congestion

**What to build:** Each controlled load condition includes concurrent latency probes whose results show network responsiveness and probe loss without presenting round-trip time as one-way delay.

**Blocked by:** 04: Run reproducible and counterbalanced TCP experiments.

**Status:** implemented-awaiting-privileged-verification

- [ ] Probes run during the defined measurement window without replacing or serializing the competing class traffic.
- [ ] Raw results record sample count, minimum, average, maximum, p95 when enough samples exist, and packet loss.
- [ ] The workflow preserves raw probe output or sufficient provenance and explicitly marks missing, insufficient, or malformed samples.
- [ ] Parsing, percentile behavior, packet-loss handling, and measurement-window alignment are unit tested and the RTT limitation is documented.

## Implementation notes

Concurrent, deadline-bounded ICMP probes start after both class clients launch and stop when they complete. Each source records raw ping output, observation timestamps/offsets, sample count, RTT min/average/max, nearest-rank p95 with 20 or more replies, and probe loss. Complete loss leaves RTT unavailable; malformed output has explicit validity/error fields. Tests cover statistics, loss, missing output, raw-output preservation, and launch ordering. ICMP follows fallback queue policy and measures RTT rather than one-way or class-specific application delay. Privileged runtime verification remains outstanding.

