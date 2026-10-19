# 06: Run repeatable without-QoS and with-QoS experiments

**What to build:** A repeatable experiment command that runs both traffic classes concurrently under controlled light, near-capacity, and congested loads, comparing an unchanged topology with QoS disabled and enabled.

**Blocked by:** 05: Enforce and verify the OVS queue policy.

**Status:** resolved

- [x] The receiver servers and both source clients are started automatically with consistent traffic-tool syntax and closely aligned start times.
- [x] Paired without-QoS and with-QoS scenarios run at no fewer than three offered-load levels and repeat each condition multiple times.
- [x] Every run records per-class throughput plus scenario, load, policy, duration, link capacity, timestamp, run identifier, and relevant tool versions in machine-readable data.
- [x] The high-load scenario includes evidence that the shared link was actually congested.
- [x] Flow or queue counters are captured so experiment results can be tied to the active controller and queue policy.

## Implementation notes

- `docker run --privileged --rm traffic-priority experiment` runs three 10-second repetitions at combined offered loads of 2, 5, and 10 Mbps in both policy modes.
- Each client pair is launched back-to-back and its measured start skew is recorded. The receiver servers and Ryu controller lifecycle are automatic.
- Each per-class CSV row includes configuration, throughput, tool versions, flow deltas, egress deltas, and queue deltas when QoS is active. Scenario-specific controller logs are stored beside the CSV.
- Congestion is recorded only when offered load exceeds the 5 Mbps link and measured egress utilization reaches at least 80%.
- A shortened full-matrix smoke run completed all six conditions. Both congested conditions measured about 5.2 Mbps at the egress (roughly 104% including link-layer/accounting overhead), confirming saturation of the configured bottleneck.

