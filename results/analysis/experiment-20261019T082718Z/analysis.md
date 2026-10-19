# TrafficPriority experiment analysis

- Generated: `2026-10-19T08:33:24.316555+00:00`
- Raw source: `experiment-20261019T082718Z.csv`
- Raw SHA-256: `600cc34e0eca3587eca5d70e6c046316ef39115f366cf7a4f9840fd4433eccb6`
- Experiment IDs: `experiment-20261019T082718Z`
- Complete runs: `18`
- Plot: `experiment-20261019T082718Z-throughput-comparison.svg`

![Traffic-class throughput comparison](../../plots/experiment-20261019T082718Z-throughput-comparison.svg)

## Per-run measurements

| Run | Scenario | Load | High Mbps | Best-effort Mbps | Total Mbps | Capacity Mbps | Egress Mbps | Congested |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `without_qos-light-r01-6c0c57e3` | without_qos | light | 1.153 | 1.153 | 2.307 | 5.000 | 2.263 | false |
| `without_qos-light-r02-5d45c65e` | without_qos | light | 1.084 | 1.086 | 2.170 | 5.000 | 1.806 | false |
| `without_qos-light-r03-2bcbe584` | without_qos | light | 1.153 | 1.153 | 2.307 | 5.000 | 2.262 | false |
| `with_qos-light-r01-e0ef447f` | with_qos | light | 1.153 | 1.151 | 2.304 | 5.000 | 2.272 | false |
| `with_qos-light-r02-fa412c43` | with_qos | light | 1.153 | 1.153 | 2.307 | 5.000 | 2.310 | false |
| `with_qos-light-r03-a1eaea65` | with_qos | light | 1.090 | 1.093 | 2.182 | 5.000 | 1.722 | false |
| `without_qos-near_capacity-r01-c58f989a` | without_qos | near_capacity | 2.621 | 2.621 | 5.242 | 5.000 | 5.002 | false |
| `without_qos-near_capacity-r02-a66aff67` | without_qos | near_capacity | 2.584 | 2.584 | 5.167 | 5.000 | 4.261 | false |
| `without_qos-near_capacity-r03-d02e78d6` | without_qos | near_capacity | 2.619 | 2.621 | 5.240 | 5.000 | 4.983 | false |
| `with_qos-near_capacity-r01-844214a0` | with_qos | near_capacity | 2.621 | 2.621 | 5.242 | 5.000 | 4.976 | false |
| `with_qos-near_capacity-r02-5b4639bc` | with_qos | near_capacity | 2.621 | 2.615 | 5.236 | 5.000 | 4.969 | false |
| `with_qos-near_capacity-r03-5da7b67d` | with_qos | near_capacity | 2.592 | 2.592 | 5.185 | 5.000 | 3.935 | false |
| `without_qos-congested-r01-67c81a6f` | without_qos | congested | 2.824 | 2.751 | 5.575 | 5.000 | 4.986 | true |
| `without_qos-congested-r02-47730472` | without_qos | congested | 3.486 | 3.094 | 6.580 | 5.000 | 4.997 | true |
| `without_qos-congested-r03-4330a6bf` | without_qos | congested | 3.245 | 2.341 | 5.585 | 5.000 | 5.001 | true |
| `with_qos-congested-r01-b1748d20` | with_qos | congested | 5.063 | 2.489 | 7.552 | 5.000 | 4.985 | true |
| `with_qos-congested-r02-23a39ad5` | with_qos | congested | 5.325 | 1.147 | 6.472 | 5.000 | 4.972 | true |
| `with_qos-congested-r03-82020a78` | with_qos | congested | 5.106 | 2.180 | 7.286 | 5.000 | 4.986 | true |

## Aggregate comparison

| Scenario | Load | Metric | N | Mean Mbps | SD Mbps | Min | Max | Mean/capacity |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| without_qos | light | high_priority | 3 | 1.130 | 0.040 | 1.084 | 1.153 | 22.6% |
| without_qos | light | best_effort | 3 | 1.131 | 0.039 | 1.086 | 1.153 | 22.6% |
| without_qos | light | total | 3 | 2.261 | 0.079 | 2.170 | 2.307 | 45.2% |
| without_qos | light | egress_total | 3 | 2.110 | 0.263 | 1.806 | 2.263 | 42.2% |
| with_qos | light | high_priority | 3 | 1.132 | 0.037 | 1.090 | 1.153 | 22.6% |
| with_qos | light | best_effort | 3 | 1.132 | 0.034 | 1.093 | 1.153 | 22.6% |
| with_qos | light | total | 3 | 2.265 | 0.071 | 2.182 | 2.307 | 45.3% |
| with_qos | light | egress_total | 3 | 2.102 | 0.329 | 1.722 | 2.310 | 42.0% |
| without_qos | near_capacity | high_priority | 3 | 2.608 | 0.021 | 2.584 | 2.621 | 52.2% |
| without_qos | near_capacity | best_effort | 3 | 2.608 | 0.022 | 2.584 | 2.621 | 52.2% |
| without_qos | near_capacity | total | 3 | 5.216 | 0.043 | 5.167 | 5.242 | 104.3% |
| without_qos | near_capacity | egress_total | 3 | 4.749 | 0.422 | 4.261 | 5.002 | 95.0% |
| with_qos | near_capacity | high_priority | 3 | 2.612 | 0.017 | 2.592 | 2.621 | 52.2% |
| with_qos | near_capacity | best_effort | 3 | 2.609 | 0.015 | 2.592 | 2.621 | 52.2% |
| with_qos | near_capacity | total | 3 | 5.221 | 0.031 | 5.185 | 5.242 | 104.4% |
| with_qos | near_capacity | egress_total | 3 | 4.626 | 0.599 | 3.935 | 4.976 | 92.5% |
| without_qos | congested | high_priority | 3 | 3.185 | 0.335 | 2.824 | 3.486 | 63.7% |
| without_qos | congested | best_effort | 3 | 2.729 | 0.377 | 2.341 | 3.094 | 54.6% |
| without_qos | congested | total | 3 | 5.914 | 0.577 | 5.575 | 6.580 | 118.3% |
| without_qos | congested | egress_total | 3 | 4.995 | 0.008 | 4.986 | 5.001 | 99.9% |
| with_qos | congested | high_priority | 3 | 5.165 | 0.141 | 5.063 | 5.325 | 103.3% |
| with_qos | congested | best_effort | 3 | 1.939 | 0.703 | 1.147 | 2.489 | 38.8% |
| with_qos | congested | total | 3 | 7.103 | 0.562 | 6.472 | 7.552 | 142.1% |
| with_qos | congested | egress_total | 3 | 4.981 | 0.008 | 4.972 | 4.986 | 99.6% |

## Interpretation and limitations

- 6 run(s) reported summed client throughput more than 5% above link capacity. Treat client throughput as an application-side estimate and use egress counters for the capacity check.
- Under measured congestion, QoS shifted throughput toward the high-priority class (+1.980 Mbps) at the expense of best effort (-0.790 Mbps). This is allocation, not additional physical bandwidth.
- At light load, corresponding class means differed by no more than 10% of link capacity between modes; QoS made little measurable difference in that condition.
- At near capacity load, corresponding class means differed by no more than 10% of link capacity between modes; QoS made little measurable difference in that condition.
- Results apply to this controlled TCP/port-based lab and do not establish end-to-end application QoE or behavior on other hosts and kernels.

The plot and tables are derived entirely from the raw CSV named above. Regenerate them with `traffic-priority analyze` after collecting new data.
