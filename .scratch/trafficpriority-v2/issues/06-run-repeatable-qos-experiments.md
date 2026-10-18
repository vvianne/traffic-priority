# 06: Run repeatable without-QoS and with-QoS experiments

**What to build:** A repeatable experiment command that runs both traffic classes concurrently under controlled light, near-capacity, and congested loads, comparing an unchanged topology with QoS disabled and enabled.

**Blocked by:** 05: Enforce and verify the OVS queue policy.

**Status:** ready-for-agent

- [ ] The receiver servers and both source clients are started automatically with consistent traffic-tool syntax and closely aligned start times.
- [ ] Paired without-QoS and with-QoS scenarios run at no fewer than three offered-load levels and repeat each condition multiple times.
- [ ] Every run records per-class throughput plus scenario, load, policy, duration, link capacity, timestamp, run identifier, and relevant tool versions in machine-readable data.
- [ ] The high-load scenario includes evidence that the shared link was actually congested.
- [ ] Flow or queue counters are captured so experiment results can be tied to the active controller and queue policy.

