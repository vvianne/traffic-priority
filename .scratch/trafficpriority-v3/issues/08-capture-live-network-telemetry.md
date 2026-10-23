# 08: Capture live bottleneck and traffic-class telemetry

**What to build:** A lightweight runtime monitor periodically records trustworthy bottleneck, queue, and flow observations that can support adaptive decisions and later explain what the network was doing.

**Blocked by:** 03: Use one verified OVS HTB bottleneck foundation; 04: Run reproducible and counterbalanced TCP experiments.

**Status:** ready-for-agent

- [ ] Monitoring samples port utilization and available queue and flow counters at a configurable interval without disrupting forwarding.
- [ ] Counter deltas handle first samples, resets, rollover or regression, missing queues, elapsed time, and malformed command or OpenFlow output explicitly.
- [ ] Telemetry identifies observed utilization separately from inferred traffic-class demand and records metric availability and provenance.
- [ ] Samples can be logged with experiment/run identity, and unit tests cover rate calculations, counter anomalies, and unavailable inputs.

