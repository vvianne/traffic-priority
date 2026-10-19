# 07: Generate statistical comparisons and plots

**What to build:** An analysis workflow that turns captured experiment data into traceable per-run summaries and a clear comparison of traffic-class throughput with and without QoS.

**Blocked by:** 06: Run repeatable without-QoS and with-QoS experiments.

**Status:** resolved

- [x] Analysis reports every run as well as the mean and a variability measure for each class and condition.
- [x] Total measured throughput is reported and checked against the configured bottleneck capacity.
- [x] At least one well-labelled comparison plot is generated entirely from saved raw measurements.
- [x] The analysis explains the best-effort trade-off and does not imply that QoS creates additional physical bandwidth.
- [x] Unexpected results, experimental limitations, and conditions where QoS makes little difference are preserved alongside the conclusions.

## Implementation notes

- `traffic-priority analyze <raw.csv>` validates the complete condition matrix and writes per-run CSV, aggregate CSV, Markdown interpretation, and a dependency-free SVG comparison plot.
- The aggregate table reports mean, sample standard deviation, minimum, and maximum for both traffic classes, summed client throughput, and measured egress throughput.
- A complete 18-run dataset was captured in `results/raw/experiment-20261019T082718Z.csv`; its SHA-256 is recorded in the generated report.
- Congested egress averaged 4.995 Mbps without QoS and 4.981 Mbps with QoS on the configured 5 Mbps link. The class estimates showed more high-priority and less best-effort throughput with QoS, while total physical egress did not increase.
- The report explicitly preserves six client-total capacity exceedances, the client/egress measurement-boundary limitation, variability, and the negligible differences at light and near-capacity loads.

