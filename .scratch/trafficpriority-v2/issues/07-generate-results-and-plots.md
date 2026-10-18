# 07: Generate statistical comparisons and plots

**What to build:** An analysis workflow that turns captured experiment data into traceable per-run summaries and a clear comparison of traffic-class throughput with and without QoS.

**Blocked by:** 06: Run repeatable without-QoS and with-QoS experiments.

**Status:** ready-for-agent

- [ ] Analysis reports every run as well as the mean and a variability measure for each class and condition.
- [ ] Total measured throughput is reported and checked against the configured bottleneck capacity.
- [ ] At least one well-labelled comparison plot is generated entirely from saved raw measurements.
- [ ] The analysis explains the best-effort trade-off and does not imply that QoS creates additional physical bandwidth.
- [ ] Unexpected results, experimental limitations, and conditions where QoS makes little difference are preserved alongside the conclusions.

