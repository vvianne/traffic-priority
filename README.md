# Traffic Prioritization with Ryu and Mininet

TrafficPriority is an SDN testbed built with Ryu, OpenFlow 1.3, Open vSwitch, and Mininet. Two traffic sources share one 5 Mbps inter-switch bottleneck on their path to a receiver.

> **Current status:** the shared-bottleneck topology, contextual TCP/5001 and TCP/5002 classification, optional Open vSwitch HTB queue policy, configurable A/B experiment runner, and distinct sender, receiver, and egress measurements are implemented. The included 18-run dataset predates receiver-side capture and remains labelled as v2 evidence.

See the [v1 baseline report](docs/baseline-v1.md) for the behavior before the topology correction and the [v2 release evidence](docs/release-v2.md) for the tested environment, MVP checklist, and claim boundaries.

## Topology

```text
h1 (10.0.0.1) --10 Mbps--\
                           s1 == 5 Mbps == s2 --10 Mbps-- h3 (10.0.0.3)
h2 (10.0.0.2) --10 Mbps--/                 \\--10 Mbps-- h4 (10.0.0.4)
```

`h1` and `h2` are the traffic sources, and `h3` is the primary receiver. Both source-to-receiver paths cross `s1-eth3 <-> s2-eth1`. Both modes now use OVS `linux-htb` on the forward bottleneck egress with the same 5 Mbps parent. Baseline uses a single queue 0 with a 5 Mbps minimum and maximum; static QoS uses the configured differentiated queues. Neither mode applies Mininet shaping to the inter-switch link. The reverse direction is unshaped in both modes; access links retain their shared 10 Mbps configuration.

Startup verifies the OVS attachment, parent and queue rates, and realized kernel HTB classes using `tc -j`. A conflicting root qdisc causes startup to fail. Experiment runs also check installed bottleneck flow queue actions after traffic. Baseline flows retain their classification rule priorities but do not select differentiated queues; OpenFlow matching priority does not allocate bandwidth. Cleanup deletes only the attached project-owned QoS policy and its unshared owned queues. These v3 changes await privileged runtime verification; historical v2 results used the former TCLink baseline.

Both switches:

- use OpenFlow 1.3;
- run in secure fail mode; and
- must connect to the Ryu controller at `127.0.0.1:6653` before the CLI opens.

Startup does not run `pingAll()` or generate other test traffic. This leaves only the table-miss rules in place so first-packet behavior can be inspected deliberately.

### Packet path

```text
h1 or h2 application
  -> source access link
  -> s1 OpenFlow lookup
  -> Ryu PacketIn for a new directed flow
  -> TCP destination-port classification
  -> queue 1 (TCP/5001) or queue 0 (TCP/5002/fallback)
  -> s1-eth3, the 5 Mbps controlled egress
  -> s2 forwarding
  -> h3 receiver
```

OpenFlow rule priority decides which rule matches. The OVS HTB policy on `s1-eth3`, when enabled, performs the actual bandwidth allocation.

## Prerequisites

- Docker Desktop or Docker Engine with Linux containers
- A Linux or WSL2 environment capable of running privileged containers
- Kernel and container permissions sufficient for Open vSwitch and Mininet network namespaces

The published v2 evidence was captured with:

| Component | Tested version |
| --- | --- |
| Docker client/engine | `29.2.1` |
| Container kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Python | `3.8.10` |
| Eventlet | `0.30.2` |
| Ryu | `4.34` |
| Mininet | `2.3.0.dev6` |
| Open vSwitch | `2.13.8` |
| iperf | `2.0.13` |

PyPI dependencies, including transitive packages, are pinned in [requirements.txt](requirements.txt). The Ubuntu 20.04 base image is pinned by digest, while `apt` packages resolve from the Ubuntu repositories available at build time. Other hosts and kernels may behave differently.

## Policy configuration

TrafficPriority loads its network and QoS policy from `config/traffic_priority.yaml`. The checked-in defaults preserve the v2 behavior: a 5 Mbps bottleneck, TCP/5001 in queue 1 with a 3 Mbps minimum, TCP/5002 in queue 0 with a 1 Mbps minimum, and adaptive QoS disabled.

The configuration controls:

- access-link and bottleneck capacity plus the OVS egress attachment;
- TCP destination ports, OpenFlow rule priorities, and queue identifiers;
- static queue minimum and maximum rates; and
- future adaptive-QoS thresholds and timing, with adaptation off by default.

The controller, topology, QoS lifecycle, and experiment runner use the same validated policy model. Invalid or unknown fields, unsupported protocols, invalid ports or queue IDs, negative or impossible rates, duplicate matches or queues, allocations above parent capacity, and invalid adaptive thresholds or timing values stop startup before network state is changed. Each class supports `protocol: tcp` or `protocol: udp`; defaults remain TCP.

To use another policy file, set its path for every process through the environment:

```bash
export TRAFFIC_PRIORITY_CONFIG=/app/config/my-policy.yaml
docker run --privileged --rm \
  -e TRAFFIC_PRIORITY_CONFIG=/app/config/my-policy.yaml \
  --mount "type=bind,source=$PWD/my-policy.yaml,target=/app/config/my-policy.yaml,readonly" \
  traffic-priority
```

The topology and experiment commands also accept `--config PATH`. The experiment runner records the selected configuration path and effective policy description in every output row.

## Build and run

```bash
docker build -t traffic-priority .
docker run --privileged --rm -it traffic-priority
```

Enable the OVS queue policy explicitly for a QoS run:

```bash
docker run --privileged --rm -it -e QOS_ENABLED=1 traffic-priority
```

`run_all.sh` passes `--qos` to the topology when `QOS_ENABLED=1`, so the topology and controller always enter QoS mode together. The topology verifies that `s1-eth3` belongs to bridge `s1`, creates the policy after the switches connect, and removes it during shutdown.

On Linux or WSL2, the helper provides the shortest interactive quick start:

```bash
chmod +x start_project.sh
./start_project.sh
```

The container starts Ryu, creates the topology, waits for both switches to connect, prints the expected bottleneck ports, and opens the Mininet CLI.

The same helper can run the complete experiment and analyzer while mounting `results/` automatically:

```bash
./start_project.sh experiment
./start_project.sh analyze /app/results/raw/experiment-20261019T082718Z.csv
```

## Verify the topology

Before generating traffic, inspect the links, switch ports, controller state, and initial flows:

```text
mininet> links
mininet> sh ovs-ofctl -O OpenFlow13 show s1
mininet> sh ovs-ofctl -O OpenFlow13 show s2
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2
```

The port inspection should show `s1-eth3` connected to `s2-eth1`. Before the first packet is sent, each flow table should contain only its priority-0 controller rule.

Verify both source-to-receiver paths and their reverse directions explicitly:

```text
mininet> h1 ping -c 1 h3
mininet> h2 ping -c 1 h3
mininet> h3 ping -c 1 h1
mininet> h3 ping -c 1 h2
```

In the default, queue-disabled mode, inspect the traffic-control class applied to the shared link:

```text
mininet> sh tc class show dev s1-eth3
```

It should report `rate 5Mbit ceil 5Mbit`. In QoS mode, use the inspection commands below instead. An indicative single-flow probe can then be run with:

```text
mininet> h3 iperf -s -p 5001 > /tmp/iperf-server.log 2>&1 &
mininet> h1 iperf -c 10.0.0.3 -p 5001 -t 5
```

Docker scheduling, short test duration, and Mininet resource-limit warnings can make a single `iperf` result noisy, so use the traffic-control state as the authoritative configured rate. This probe does not demonstrate QoS. A valid QoS experiment must run both traffic classes concurrently and compare queue-enabled and queue-disabled conditions.

## Verify traffic classification

The high-priority lab class is TCP/5001 and the best-effort lab class is TCP/5002. First generate ordinary ICMP traffic to prove learned forwarding does not hide later classification, then run both TCP flows:

```text
mininet> h1 ping -c 1 h3
mininet> h3 iperf -s -p 5001 > /tmp/iperf-server.log 2>&1 &
mininet> h3 iperf -s -p 5002 > /tmp/iperf-best-effort.log 2>&1 &
mininet> h1 iperf -c 10.0.0.3 -p 5001 -t 3
mininet> h2 iperf -c 10.0.0.3 -p 5002 -t 3
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2
```

Ryu should log each classification once per switch. The flow dumps should contain priority-100 TCP/5001 and priority-90 TCP/5002 rules matching the ingress port, source and destination MAC addresses, source and destination IPv4 addresses, TCP source port, and TCP destination port. Without QoS, forward actions are `output:3` on `s1` and `output:2` on `s2`. With QoS, the `s1` actions are `set_queue:1,output:3` for TCP/5001 and `set_queue:0,output:3` for TCP/5002; `s2` still only uses `output:2`. A flood action is never stored as a class-specific rule.

The classification policy has non-privileged unit tests:

```bash
python -m unittest discover -s tests -v
```

### Fallback behavior

- ARP and non-TCP packets use learned forwarding with an EtherType- or IP-protocol-specific match.
- TCP ports without a configured class use a priority-10 contextual rule containing their directed IP and transport endpoints.
- An unknown destination is flooded for the current packet only. No flood output is installed in the flow table.
- LLDP is ignored by the application.
- MAC learning is isolated by datapath, so the same MAC can map to different ports on different switches.
- OpenFlow buffer ID `0` is treated as valid. The `OFP_NO_BUFFER` sentinel causes the packet bytes to be included in `PacketOut`.

## OVS queue policy

QoS mode installs one `linux-htb` policy on the verified bottleneck egress:

| Traffic | TCP destination | Queue | Minimum | Maximum |
| --- | --- | --- | --- | --- |
| High-priority lab class | `5001` | `1` | 3 Mbps | 5 Mbps |
| Best effort and fallback | `5002` or unclassified | `0` | 1 Mbps | 5 Mbps |

The parent port maximum is 5 Mbps. HTB permits unused capacity to be borrowed, so the minimums are allocation guarantees during contention, not fixed per-flow rates or strict-priority scheduling.

From the Mininet CLI, inspect the attachment, database records, realized kernel policy, OpenFlow actions, and counters with:

```text
mininet> sh ovs-vsctl get Port s1-eth3 qos
mininet> sh ovs-vsctl --columns=_uuid,type,other_config,queues,external_ids list QoS
mininet> sh ovs-vsctl --columns=_uuid,other_config,external_ids list Queue
mininet> sh ovs-appctl qos/show s1-eth3
mininet> sh tc -s class show dev s1-eth3
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
mininet> sh ovs-ofctl -O OpenFlow13 queue-stats s1
mininet> sh ovs-ofctl -O OpenFlow13 dump-ports s1 3
```

`ovs-appctl qos/show` and `queue-stats` should expose queue 0 and queue 1 packet/byte counters after traffic crosses the link. The setup and cleanup operations are safe to repeat:

```text
mininet> sh /app/scripts/cleanup_qos.sh s1-eth3
mininet> sh /app/scripts/setup_qos.sh s1-eth3 s1
```

Setup first removes any policy attached to that port, then creates exactly one owned QoS record and two owned Queue records. Cleanup clears the port reference and destroys those records; running cleanup again is a no-op.

## Automated A/B experiments

The experiment command recreates the same four-host/two-switch topology for the without-QoS and with-QoS scenarios. It restarts Ryu with the matching policy mode, starts both receiver servers automatically, and launches the TCP/5001 and TCP/5002 clients back-to-back so they run concurrently.

Each class offers the following paced load:

| Load level | Per class | Combined | Expected condition |
| --- | ---: | ---: | --- |
| `light` | 1 Mbps | 2 Mbps | Below capacity |
| `near_capacity` | 2.5 Mbps | 5 Mbps | At capacity |
| `congested` | 5 Mbps | 10 Mbps | Above capacity |

The default is three repetitions of every load in both scenarios, with 10-second client pairs. This produces 18 run IDs and 36 CSV rows because each run records both traffic classes.

### UDP experiments

To run UDP, copy the default policy YAML and change `protocol: tcp` to `protocol: udp` for either or both classes. Pass the copy with `experiment --config PATH`; TCP and UDP classes can run together. The runner adds iperf's UDP option to both the receiver and client. Offered load remains configurable through the capacity-scaled light, near-capacity, and congested scenarios, and is explicitly recorded in `offered_mbps`. `received_mbps` aliases the receiver throughput; UDP receiver reports additionally populate `udp_jitter_ms`, `udp_lost_datagrams`, `udp_total_datagrams`, and `udp_loss_pct`.

UDP metrics come only from the receiving host's final CSV report. Client output may include a returned server report, which is excluded from the sender measurement. Missing or malformed UDP fields are blank with validity/error columns; TCP rows mark these fields as not applicable. Loss is iperf's receiver sequence-based estimate, and jitter is its reported interarrival jitter, not RTT. The parser targets the basic iperf 2 CSV layout; other report layouts must be validated before use. UDP loss and jitter plots are deferred to the extended analysis ticket.

For privileged verification, mount the edited YAML and results directory into the existing image, rebuild it, and run `experiment --config /app/config/udp.yaml --duration 10 --warmup 2 --repetitions 3 --seed 42`. Inspect each saved receiver CSV against its corresponding experiment row, and inspect `ovs-ofctl -O OpenFlow13 dump-flows s1` and `queue-stats s1` during a static session. Expect `udp`/protocol 17 with the configured destination ports and `set_queue` actions before output; verify received rates, datagram loss, and jitter against raw reports. This check still requires a working privileged Linux Docker/Mininet/OVS environment.

### Throughput measurement boundaries

Each measured run now launches ICMP probes from both traffic-source hosts to the receiver immediately after both class clients start. Probes run concurrently at a 0.2-second interval with a deadline equal to the configured duration, and are stopped when clients finish. Probe start and collection timestamps and offsets record the observation bounds within the run; startup skew and the short final collection delay prevent claiming perfectly identical application/probe windows. Warm-up runs do not launch recorded probes.

CSV rows record RTT sample count, minimum/average/maximum RTT, nearest-rank p95 only with at least 20 replies, transmitted/received probe counts, and probe loss percentage. All-loss runs retain valid loss measurements but leave RTT fields blank. Missing or malformed output is explicitly invalid. Raw timestamped ping output and stderr are retained per source and run. These are round-trip ICMP measurements, not one-way latency or latency specific to a TCP/UDP traffic class: ICMP uses fallback forwarding and the best-effort/default queue. Probes themselves add a small amount of traffic to the measured bottleneck. RTT plotting is part of the extended analysis ticket.

V3 defaults to a separate 2-second warm-up before every measured class pair. Use `--warmup 0` to disable it, `--duration 10` to select measured seconds, and `--repetitions 3` to select repetitions per condition. Warm-up connections finish and receiver processes restart before any measured counter snapshot. Consequently warm-up bytes are excluded, but the measured TCP connections still start with fresh congestion-control state; this is network/path warm-up, not a steady-state TCP measurement.

The default `--order counterbalanced` alternates the two scenarios across repetitions with a seeded initial order. `--order random --seed 42` reproducibly shuffles each repetition's scenario order. `--order legacy --warmup 0` retains the v2 scenario-grouped sequence. Each scenario session recreates the topology and controller; load order within a session remains light, near-capacity, then congested. Odd repetition counts leave a one-session order imbalance.

Every CSV row includes repetition count, ordering mode and seed, session position, actual warm-up time, measurement end timestamp, the separately timed switch-counter window, serialized effective policy, and available Python/kernel/hostname/container/Mininet/tc/Ryu/OVS/iperf metadata. Container detection records `/.dockerenv` presence, not a Docker image digest or host engine version. A uniquely named policy snapshot and SHA-256 preserve the exact configuration used by both controller and topology. Existing output files are refused. V3 validation rejects missing or duplicate repetitions, non-finite timing, and conflicting run metadata. Counter resets or missing counters abort with diagnostics instead of generating artificial zero deltas.

Every run creates a fresh CSV-reporting iperf server for each traffic class. The configured client duration defines the intended application measurement window. Sender and receiver summaries are accepted only when their endpoint pair, receiver address and port, interval start, and interval duration match that run. The raw summaries are saved beside the experiment CSV.

The three throughput views have different meanings:

- `sender_throughput_mbps` is the client-side iperf estimate and is retained for compatibility and diagnosis;
- `receiver_throughput_mbps` is the server-side iperf result and is the application-delivery value used by v3 analysis; and
- `egress_mbps` is calculated from the bottleneck switch's byte-counter delta over the measured wall interval and remains the capacity/utilization evidence.

The legacy `throughput_mbps` column mirrors the sender value so existing v2 tooling does not break. It must not be interpreted as received traffic. A missing, malformed, ambiguous, wrong-endpoint, or wrong-window result is written with an empty measurement, `*_measurement_valid=false`, and a diagnostic; no zero or estimated value is substituted. Analysis rejects an incomplete v3 receiver dataset rather than falling back silently to sender throughput. CSVs that entirely predate the receiver schema retain their explicitly labelled legacy behavior.

Build the image, create a host results directory, and run the complete experiment. In Bash:

```bash
mkdir -p results/raw
docker build -t traffic-priority .
docker run --privileged --rm \
  --mount "type=bind,source=$PWD/results,target=/app/results" \
  traffic-priority experiment
```

In PowerShell:

```powershell
New-Item -ItemType Directory -Force results\raw
docker build -t traffic-priority .
docker run --privileged --rm `
  --mount "type=bind,source=$((Get-Location).Path)\results,target=/app/results" `
  traffic-priority experiment
```

For a quick integration check rather than a publishable experiment, override the duration and repetition count:

```bash
docker run --privileged --rm traffic-priority experiment \
  --duration 2 --repetitions 1 --output /tmp/smoke.csv
```

The generated CSV includes the experiment and run IDs, UTC timestamp, scenario, load, active policy, traffic class, protocol/port/queue, offered rate, separately labelled sender/receiver/egress throughput, measurement validity and diagnostics, iperf interval and transferred-byte fields, raw-output filenames, configured duration, actual wall duration, client start skew, link capacity, utilization, congestion detection, flow and queue deltas, tool versions, and controller-log filename. Controller logs and raw iperf summaries are written beside the CSV.

`congestion_detected=true` means the combined offered load exceeded 5 Mbps and the measured bottleneck egress reached at least 80% utilization. This supplies measured congestion evidence instead of inferring congestion from offered load alone. Without-QoS rows use flow and interface counters; with-QoS rows additionally record the corresponding queue counter delta.

Analyze any complete ticket 6 CSV using the same mounted results directory:

```bash
docker run --rm \
  --mount "type=bind,source=$PWD/results,target=/app/results" \
  traffic-priority analyze \
  /app/results/raw/experiment-20261019T082718Z.csv
```

The analyzer validates that every scenario/load/class condition is present and produces:

- `results/analysis/<experiment>/per-run.csv` with every paired run;
- `results/analysis/<experiment>/summary.csv` with mean, sample standard deviation, minimum, and maximum for each class, its explicit measurement source, summed application throughput, and measured egress throughput;
- `results/analysis/<experiment>/analysis.md` with source hash, tables, conclusions, unexpected results, and limitations; and
- `results/plots/<experiment>-throughput-comparison.svg`, derived entirely from the saved raw CSV.

V3 datasets containing probe measurements also produce `extended-summary.csv` and one SVG per extended metric: separately labelled sender and receiver throughput, switch egress, RTT minimum/average/maximum/p95, probe loss, UDP jitter/loss, and bottleneck utilization. The analysis report embeds these plots and a unit-aware comparison table. Run the existing `analyze RAW.csv` command to generate them; CSVs from earlier versions retain their legacy analysis behavior.

Extended summaries group by scenario, load, class, protocol, and metric. They show expected/available sample counts, mean, sample SD, minimum/maximum, and reasons for unavailable observations. SD requires at least two independent runs. RTT statistics are aggregated per run with equal weight; the reported average p95 is not a percentile pooled across all ping replies. Switch metrics are counted once per run despite appearing in both source rows. TCP-only UDP metrics, failed probes with diagnostics, and p95 with fewer than 20 replies remain unavailable, with no plotted zero substitutions.

Validation rejects incomplete scenario/load/class or repetition matrices, changes to a class's protocol or destination port across conditions, non-finite/negative metrics, inconsistent switch utilization, invalid probe counts/timing, and missing diagnostics. Analyze experiments with different protocol configurations separately. Every newly generated CSV and plot identifies the raw source and SHA-256. No v3 dataset is bundled yet; generated unit-test fixtures exercise plotting only and are not experimental evidence.

## Captured results

![Measured traffic-class throughput comparison](results/plots/experiment-20261019T082718Z-throughput-comparison.svg)

The included [analysis report](results/analysis/experiment-20261019T082718Z/analysis.md) covers 18 complete legacy v2 runs with three repetitions per condition. It contains sender-side application estimates because it was captured before v3 receiver measurement was added. Its main observations are:

- Light and near-capacity class means were nearly identical between modes, so QoS made little measurable difference while bandwidth was not clearly scarce.
- Under the congested offered load, the high-priority client-side mean increased from 3.185 to 5.165 Mbps while the best-effort mean decreased from 2.729 to 1.939 Mbps. This indicates a class-allocation trade-off, not new capacity.
- Measured switch egress remained effectively fixed: 4.995 Mbps without QoS and 4.981 Mbps with QoS. Both are approximately 100% of the configured 5 Mbps bottleneck.
- Six congested runs had summed client-side TCP estimates above physical capacity. The report preserves this discrepancy and treats switch egress counters as authoritative for the capacity check; client figures can reflect buffering and measurement-boundary effects.

The [raw CSV](results/raw/experiment-20261019T082718Z.csv), controller logs, per-run summary, aggregate summary, report, and SVG are kept together so every claim can be traced back to recorded measurements.

## Cleanup

- Type `exit` or press Ctrl-D in the Mininet CLI. The topology removes its owned QoS and Queue records before stopping Mininet.
- The experiment runner tears down each network, controller, and QoS policy between scenarios and on handled failures.
- Containers use `--rm`, so Docker removes them after exit. If an interactive container is still running, locate it with `docker ps --filter ancestor=traffic-priority` and stop that exact container with `docker stop <container-id>`.
- If Mininet was run directly on Linux outside Docker and left stale interfaces, run `sudo mn -c` on that same host. This is normally unnecessary for the documented disposable-container workflow.
- Generated evidence is intentionally retained under `results/`; remove it only when you no longer need the audit trail.

## Repository structure

```text
.
|-- priority_ryu_controller.py   # Ryu learning/classification application
|-- ryu_topo.py                  # shared-bottleneck Mininet topology
|-- policy_config.py             # typed YAML loading and validation
|-- config/                      # default network and QoS policy
|-- traffic_policy.py            # pure class/queue policy
|-- experiment_metrics.py        # pure runtime counter parsers
|-- result_analysis.py           # statistics, interpretation, SVG generation
|-- scripts/                     # QoS lifecycle, experiment, analysis, verification
|-- tests/                       # non-privileged unit tests
|-- docs/                        # baseline and release evidence
|-- results/raw/                 # measured CSV and controller logs
|-- results/analysis/            # per-run, aggregate, and narrative outputs
`-- results/plots/               # generated comparison SVG
```

## Package verification

Run the non-privileged release audit from the repository root:

```bash
python -B scripts/verify_package.py
```

It runs the unit suite, validates the full experiment matrix and repetition counts, requires congestion evidence for every high-load run, verifies all published artifacts, checks the raw CSV hash recorded in the report, parses the SVG as XML, and ensures all local work packages are resolved. The Docker build also runs the unit suite.

The source is licensed under the [MIT License](LICENSE). A release tag is deliberately left to the maintainer; the repository does not create or push tags automatically.

## Troubleshooting

### Docker or privilege errors

- `Operation not permitted`, namespace failures, or missing virtual interfaces usually mean the container was not started with `--privileged` or the host cannot provide Linux network namespaces.
- Use Linux containers. Windows containers cannot run this Mininet/OVS topology.
- On Windows, use Docker Desktop's WSL2 backend and confirm `docker info` reports `OSType: linux`.
- If Docker Desktop reports missing BuildKit snapshots or daemon connection errors, restart Docker Desktop and rerun the build. Do not delete project data to repair a Docker cache failure.

### OVS, Mininet, or controller errors

- If switches do not connect, check that nothing else is using TCP port `6653` and inspect the scenario controller log under `results/raw/`.
- `ovs-vsctl` database errors indicate the Open vSwitch service did not initialize; rerun in a fresh container and inspect its startup output.
- If QoS records exist but `ovs-appctl qos/show s1-eth3` has no queues, another qdisc may own the egress. Use the documented QoS mode, which leaves the inter-switch link available for OVS to own.
- Mininet's resource-limit warning is common inside Docker Desktop. Treat failed host creation or connectivity as an error, but record the warning when comparing environments.
- Ryu 4.34 is paired with Eventlet 0.30.2 and Python 3.8 in this image. Changing these versions can reintroduce import/runtime incompatibilities.

### Unexpected measurements

- Confirm the congested rows have `congestion_detected=true` and egress utilization near 100%; offered load alone is not evidence of congestion.
- Short runs are noisy. Use the default 10-second duration and three repetitions for conclusions.
- Compare all three labelled values. Receiver throughput is the v3 delivered-traffic measure, while switch egress remains the physical-capacity check; sender totals can exceed both because of buffering and measurement boundaries.
- QoS should make little difference below congestion. A lack of separation at light load is expected, not a failure.

## Current forwarding behavior

The Ryu application provides table-miss handling, per-datapath MAC learning, protocol-specific learned forwarding, explicit TCP/5001 and TCP/5002 classes, contextual fallback forwarding, and optional queue selection on the single configured bottleneck egress. Learned ARP, ICMP, or unrelated TCP rules cannot capture either classified traffic flow.

## Known limitations

- Differentiated QoS is opt-in; the default run has one OVS HTB baseline queue.
- Flow rule priority is not packet scheduling priority; only the OVS HTB queues perform rate allocation.
- Python dependencies are pinned, but Ubuntu system packages can change if the upstream Ubuntu 20.04 repositories change.
- Privileged Mininet execution depends on the host kernel and Docker environment.
- Short smoke runs are useful for integration checks but are too noisy for conclusions; use the default duration and repetitions for collected results.
- Sender-side TCP throughput can temporarily exceed receiver or measured egress throughput because the measurement boundaries include buffering. V3 retains all three values, uses receiver throughput for delivered traffic, and uses switch egress counters for the capacity check.
- No v3 privileged experiment evidence has been published yet; the checked-in results remain historical v2 sender-side evidence.

## Release status

Every v2 MVP definition-of-done item is backed by code, tests, runtime counters, saved raw measurements, and generated analysis. TrafficPriority v2 is ready for a maintainer-created release tag on the tested platform. The evidence supports describing it as a controlled SDN QoS testbed, not as a production QoS system or a guarantee of application QoE.
