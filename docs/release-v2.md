# TrafficPriority v2 release evidence

This document records the environment and evidence used to assess the v2 package. It is not a claim that every Docker host will reproduce identical timing or throughput.

## Tested environment

| Component | Verified value |
| --- | --- |
| Host | Windows with Docker Desktop and WSL2 backend, x86-64 |
| Docker client and engine | `29.2.1` |
| Container kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Container base | Ubuntu 20.04, pinned by digest in `Dockerfile` |
| Python | `3.8.10` |
| Eventlet | `0.30.2` |
| Ryu | `4.34` |
| Mininet | `2.3.0.dev6` |
| Open vSwitch | `2.13.8` |
| iperf | `2.0.13` |
| OpenFlow | `1.3` |

PyPI package versions, including transitive dependencies, are pinned in `requirements.txt`. Python modules supplied by Ubuntu packages (including the matching OVS bindings) remain sourced from the Ubuntu 20.04 repositories available at image-build time.

## MVP evidence checklist

- [x] The four-host/two-switch topology has one documented 5 Mbps bottleneck.
- [x] Ryu installs contextual TCP/5001 and TCP/5002 OpenFlow 1.3 rules without learned-rule shadowing.
- [x] QoS mode creates two real OVS HTB queues on the verified `s1-eth3` egress.
- [x] The relevant `s1` actions select queue 1 or queue 0 before output.
- [x] Both traffic classes run concurrently in paired without-QoS and with-QoS scenarios.
- [x] The published raw CSV contains three repetitions at three offered-load levels in both modes.
- [x] Flow, queue, and interface counter deltas connect measurements to the active policy.
- [x] The generated report contains every run, aggregate means, sample standard deviations, capacity checks, limitations, and a raw-file hash.
- [x] The comparison SVG is generated entirely from the published raw CSV.
- [x] README claims are limited to the behavior and environment demonstrated here.

The non-privileged package audit is:

```bash
python -B scripts/verify_package.py
```

The privileged integration evidence was also regenerated through the documented Docker experiment command. A release tag is a maintainer action and is not created automatically by this repository.

## Published evidence

- Raw measurements: `results/raw/experiment-20261019T082718Z.csv`
- Controller logs: `results/raw/experiment-20261019T082718Z-*-controller.log`
- Per-run measurements: `results/analysis/experiment-20261019T082718Z/per-run.csv`
- Aggregate statistics: `results/analysis/experiment-20261019T082718Z/summary.csv`
- Interpretation: `results/analysis/experiment-20261019T082718Z/analysis.md`
- Plot: `results/plots/experiment-20261019T082718Z-throughput-comparison.svg`

The raw CSV hash is embedded in the generated interpretation so changes are detectable.

## Release claim boundary

The evidence shows queue selection and a throughput-allocation change in this controlled lab under measured congestion. It does not show that QoS creates bandwidth, guarantee application QoE, validate UDP behavior, or establish portability to untested kernels and container runtimes.
