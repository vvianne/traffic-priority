# TrafficPriority v2 — Development Roadmap

> **Project:** Traffic Prioritization using Ryu, OpenFlow 1.3, Open vSwitch, and Mininet  
> **Repository:** [vvianne/TrafficPriority](https://github.com/vvianne/TrafficPriority)  
> **Status:** Planning / refactoring (v2 features are **not implemented yet**)  
> **Scope:** Upgrade the existing SDN demonstration into a reproducible QoS experiment with verifiable results.

## 1. Project Goal

Build a Software-Defined Networking (SDN) testbed that **classifies traffic by transport protocol and destination port**, maps traffic classes to **Open vSwitch QoS queues**, and measures how competing traffic behaves on a shared bottleneck link.

The goal is not just to show that OpenFlow rules have different priorities. It is to demonstrate, through experiments, that a defined QoS policy changes how available bandwidth is allocated during congestion.

### Minimum viable result (MVP)

- [ ] A reproducible Mininet topology with **one shared bottleneck link**.
- [ ] A working Ryu controller that correctly installs class-specific OpenFlow 1.3 rules.
- [ ] OVS QoS/queue configuration on the relevant **egress port**.
- [ ] Repeatable **without-QoS** and **with-QoS** experiments using simultaneous traffic flows.
- [ ] Automatically collected measurements and at least one comparison graph.
- [ ] Accurate README with setup, topology, commands, verification, limitations, and results.

### Out of scope for the first release

- Production deployment, automatic failover, multi-controller clustering, machine learning, and a full web dashboard.
- Claims of guaranteed end-to-end application Quality of Experience (QoE).
- Dynamic routing: this version focuses on traffic classification and QoS at a controlled bottleneck.

---

## 2. Current Repository Inventory (from `traffic-priority-main.zip`)

| File | Current purpose | Planned change |
| --- | --- | --- |
| `priority_ryu_controller.py` | MAC-learning switch; installs port-based TCP rules | Fix classification/forwarding interactions; add queue actions and counters |
| `ryu_topo.py` | Builds two independent host/switch segments | Replace with connected hosts and a shared bottleneck topology |
| `run_all.sh` | Starts Ryu then Mininet | Add startup checks, clear failures, and cleanup |
| `start_project.sh` | Builds and launches Docker container | Improve reproducibility, documentation, and cleanup options |
| `Dockerfile` | Installs Ubuntu, Mininet, Ryu, and utilities | Audit versions/dependencies; install test utilities needed for experiments |
| `README.md` | Overview and manual `iperf` test instructions | Correct claims; provide reproducible experiment guide and real evidence |

### Key findings (static code review; not yet tested at runtime)

- [ ] **Fix conceptual QoS issue:** `priority=20` vs. `priority=10` decides OpenFlow rule matching precedence; it does **not** itself schedule packets or reserve bandwidth.
- [ ] **Prevent premature general forwarding rules:** the controller installs an L2 rule matching `in_port` and `eth_dst`. After `net.pingAll()` populates learning rules, future TCP packets may bypass `PacketIn` and never reach application classification logic.
- [ ] **Make traffic matches sufficiently specific:** current TCP rules match `eth_type`, `ip_proto`, and `tcp_dst` but omit ingress/destination context; their stored output port may be wrong for other flows on the same switch.
- [ ] **Separate classification from forwarding:** determine class and egress port before installing the flow, then install class-specific rules or a deliberate forwarding pipeline so class policy cannot be shadowed by generic rules.
- [ ] **Handle `buffer_id` explicitly:** the existing `if buffer_id:` test mishandles valid value `0`; check against `None` and `OFP_NO_BUFFER` as appropriate.
- [ ] **Remove topology/README inconsistencies:** the code actually defines `h1—s1—h2` and `h3—s2—h4` with no link between switches. `s2` is described as unmanaged but is created as an `OVSSwitch` in a network with a controller.
- [ ] **Test congestion rather than isolated throughput:** the README runs port 5001 and port 5002 tests one at a time, which does not establish prioritization under contention.
- [ ] **Use OpenFlow 1.3 for verification:** check switch rules with `ovs-ofctl -O OpenFlow13 dump-flows <switch>` where applicable.
- [ ] **Verify runtime compatibility:** the Ubuntu/Python/Ryu/Eventlet versions are fragile if not pinned and tested; record the working host/kernel/Docker environment instead of assuming every Docker Desktop host works.

> **Important:** These are code-review findings, not proof of runtime failure. Confirm each behavior using logs, flow dumps, queue counters, and repeatable traffic tests.

---

## 3. Target Architecture

### Proposed topology

```text
 h1 (high-priority test traffic) ──┐
                                  ├── s1 (OVS) == 5 Mbps bottleneck == s2 (OVS) ── h3 (traffic receiver)
 h2 (best-effort test traffic) ────┘                                 └──────────── h4 (optional)
               │
         Ryu Controller
       (OpenFlow 1.3)

        QoS queues configured on s1's egress port towards s2
```

* `h1` sends traffic to `h3:5001` (high-priority class).
* `h2` sends traffic to `h3:5002` (best-effort class).
* The two flows run **at the same time** and compete for the same egress link.
* The Ryu controller classifies traffic and maps it to the appropriate queue.
* OVS/Linux queuing is responsible for bandwidth allocation, not flow-match priority.

**Port-based classification is a lab convention.** Port `5001` is not inherently video, and port `5002` is not inherently file transfer. Describe them as *video-like/high-priority test traffic* and *bulk/best-effort test traffic* unless actual applications are used.

### Proposed queue policy (starting configuration, subject to validation)

| Class | Destination port | Queue | Illustrative minimum | Maximum |
| --- | --- | --- | --- | --- |
| High priority | TCP/5001 | `1` | 3 Mbps | 5 Mbps |
| Best effort | TCP/5002 and other traffic | `0` | 1 Mbps | 5 Mbps |

The bottleneck capacity is 5 Mbps. These values are **configuration targets**, not guaranteed experimental outcomes. HTB supports rate allocation and borrowing; do not describe this as strict-priority packet scheduling without implementing and verifying such a discipline. The queue must be attached to the correct **OVS output port**.

### Intended request/packet path

```text
Host traffic
   ↓
OVS ingress / OpenFlow flow lookup
   ↓ (if no specific flow exists)
Ryu PacketIn → learn destination / choose output port
   ↓
Classify TCP destination port → choose queue ID
   ↓
Install matching OpenFlow rule
   ↓
OFPActionSetQueue(queue_id) + OFPActionOutput(egress_port)
   ↓
OVS egress QoS queue → shared bottleneck link
   ↓
Receiver + traffic measurements
```

A multi-table OpenFlow design is optional; a clean, explicit single-table implementation is sufficient for MVP.

---

## 4. Implementation Checklist

### Phase 0 — Establish the baseline

- [ ] Save existing project as a tagged baseline (for example `v1-baseline`).
- [ ] Document the host OS, kernel, Docker/WSL setup, Python, OVS, Mininet, and Ryu versions that actually work.
- [ ] Reproduce the current test and capture controller logs.
- [ ] Run `ovs-ofctl -O OpenFlow13 dump-flows s1` and note when the L2 and TCP-specific rules appear.
- [ ] Record any controller startup, `PacketIn`, Docker privileges, or OVS initialization issues.
- [ ] Update wording in the current README so OpenFlow rule priority is not presented as proven QoS.

**Exit criteria:** the old behavior is documented and its limitations can be reproduced.

### Phase 1 — Repair forwarding and topology

- [ ] Connect the traffic sources and receiver through **one shared bottleneck**.
- [ ] Ensure controller attachment and switch OpenFlow versions are intentional and consistent.
- [ ] Remove or isolate the `pingAll()` startup side effect when checking first-packet classification.
- [ ] Refactor forwarding to keep learned MAC/output-port state separate per datapath.
- [ ] Determine `out_port` before installing class-specific flows; do not store a flood port in a unicast flow.
- [ ] Install sufficiently specific matches (`in_port`, IP protocol, destination context, and transport port where appropriate).
- [ ] Ensure generic MAC-learning rules cannot bypass intended QoS policy.
- [ ] Handle ARP, non-TCP, unknown destinations, and unsupported traffic without breaking connectivity.
- [ ] Add bounded logging of classification, queue ID, match, and selected output port.
- [ ] Verify bidirectional connectivity and traffic arrival at the expected receiver.

**Exit criteria:** both traffic classes are correctly recognized; specific flow rules appear and forward to the right interface.

### Phase 2 — Implement QoS in Open vSwitch

- [ ] Identify the exact egress interface on `s1` leading to `s2` (`ovs-ofctl show s1`, interface/port inspection).
- [ ] Configure a consistent queueing discipline (e.g., OVS `linux-htb`) and `QoS`/`Queue` records.
- [ ] Create queue `0` (best effort) and queue `1` (high priority).
- [ ] Associate queues with the correct OVS interface, not an arbitrary port.
- [ ] Add `OFPActionSetQueue(queue_id)` **before** `OFPActionOutput(out_port)` for relevant flows.
- [ ] Define fallback behavior for unclassified packets.
- [ ] Verify QoS objects (`ovs-vsctl list QoS`, `ovs-vsctl list Queue`, interface configuration).
- [ ] Verify OpenFlow actions in flow dumps and inspect queue counters where supported (`ovs-ofctl -O OpenFlow13 queue-stats s1`, plus OVS interface stats).
- [ ] Ensure QoS setup/teardown is reproducible between runs.

**Exit criteria:** both classes use their intended queues; queue configuration and counters provide evidence of actual forwarding.

### Phase 3 — Build repeatable experiments

- [ ] Create a script to start the two `iperf`/`iperf3` servers on `h3` and concurrent clients on `h1`/`h2`.
- [ ] Ensure the chosen traffic-generation tool and argument syntax are consistent throughout the repository.
- [ ] Run **Scenario A: no QoS** (same topology and offered load).
- [ ] Run **Scenario B: QoS enabled** (only policy differs).
- [ ] Test at least three offered-load levels (below, near, and above bottleneck capacity).
- [ ] Repeat each condition multiple times (e.g., 5 runs) and use the same run duration, test order policy, and host environment.
- [ ] Save raw logs and per-flow throughput values into a machine-readable format.
- [ ] Record effective controller policy, configured link rate, queue rates, run ID, timestamp, tool versions, and test duration.
- [ ] Verify that the link is actually congested in the high-load scenario.
- [ ] Include evidence from flow counters and/or queue counters.

**Exit criteria:** one command or a small documented sequence reproduces A/B test runs and produces consistent, inspectable data.

### Phase 4 — Analyze and visualize

- [ ] Produce a **throughput comparison** by traffic class (without QoS vs. with QoS).
- [ ] Report per-run values plus a mean and variability measure (e.g., standard deviation).
- [ ] Report total throughput and whether the measured behavior respects the link capacity.
- [ ] Discuss trade-offs for best-effort traffic; do not claim QoS increases total physical bandwidth.
- [ ] If using UDP tests: include jitter/loss (and document offered rate); extend controller matching beyond TCP first.
- [ ] If measuring RTT/latency: describe how it was measured and its sampling frequency.
- [ ] Document unexpected results, test limitations, and conditions where QoS makes little difference.
- [ ] Save plots in `results/plots/` and link them from the README.

**Exit criteria:** a reader can trace each conclusion back to scripts, configuration, and raw data.

### Phase 5 — Make it GitHub-ready

- [ ] Add a concise project overview and **accurate** value proposition.
- [ ] Add an architecture diagram showing packet path and bottleneck.
- [ ] Include a short demo GIF or video if helpful; keep reproducible written steps primary.
- [ ] Provide Linux/WSL2/Docker prerequisites, kernel/OVS limitations, and tested versions.
- [ ] Add a quick-start command and troubleshooting section.
- [ ] Document baseline vs QoS experiment parameters and results.
- [ ] Add a `LICENSE`, `.gitignore`, dependency manifest, and clear file structure.
- [ ] Add basic tests for classification/policy mapping without requiring a full Mininet lab.
- [ ] Optionally add CI for unit tests and static checks (not for privileged Mininet integration tests unless a compatible runner is available).
- [ ] Tag a release, e.g., `v2.0.0`, **only after** passing the exit criteria.

**Exit criteria:** another developer on a supported system can recreate at least one experiment from your instructions.

---

## 5. Experiment Matrix

Keep variables controlled. The example below specifies a framework; load values and link rate should be calibrated against the actual test environment.

| Experiment | Traffic offered | QoS mode | Purpose |
| --- | --- | --- | --- |
| E1 | Light simultaneous load | Off / On | Show behavior without congestion |
| E2 | Near-capacity simultaneous load | Off / On | Observe competition onset |
| E3 | Above-capacity simultaneous load | Off / On | Evaluate class differentiation under congestion |
| E4 (optional) | Vary high-priority flow load | Off / On | Inspect fairness and best-effort trade-off |

**Controlled variables:** topology, bottleneck capacity, traffic tool, transport protocol, host placement, test duration, start offsets, and system resource limits. Start concurrent flows close together; use a warm-up period or record ramp-up so comparisons are meaningful.

### Suggested result schema

```csv
run_id,scenario,qos_enabled,load_level,class,protocol,dst_port,offered_mbps,throughput_mbps,loss_pct,jitter_ms,duration_s,link_mbps
```

`loss_pct` and `jitter_ms` should be left empty or marked not applicable when the corresponding transport/tool does not reliably provide them. Do not invent those metrics from TCP throughput.

### Expected evidence, not predetermined outcomes

- **Without QoS:** both classes contend on the bottleneck; actual sharing depends on traffic and system behavior.
- **With QoS:** if configured correctly and congestion exists, class-specific queue allocation should influence observed throughput allocation.
- **Light load:** both modes may perform similarly because queues are not competing for scarce capacity.
- **Valid conclusion:** explain *what changed*, *how much*, *under what conditions*, and *what trade-off was observed*.

---

## 6. Suggested Repository Structure (target, not current)

```text
TrafficPriority/
├── README.md
├── LICENSE
├── .gitignore
├── Dockerfile
├── start_project.sh
├── run_all.sh
├── priority_ryu_controller.py
├── ryu_topo.py
├── configs/
│   └── qos_policy.yaml             # optional: centralize ports/queues/rates
├── scripts/
│   ├── setup_qos.sh               # create queues and attach to OVS egress
│   ├── cleanup_qos.sh             # clean reproducibly
│   ├── run_experiments.py         # run paired A/B load tests
│   └── plot_results.py           # generate figures from saved results
├── tests/
│   └── test_traffic_policy.py     # pure policy/classification logic
├── docs/
│   ├── architecture.md
│   └── experiment-methodology.md
└── results/
    ├── sample-results.csv
    └── plots/
        └── throughput-comparison.png
```

Keep the project small: directories/scripts above are a **proposed organization** and should be created only as functionality is implemented. Avoid committing huge generated logs; include representative results and the method to regenerate them.

---

## 7. GitHub Issues / Work Packages

Create separate issues (or use these as your to-do headings):

1. **Fix SDN classification and forwarding pipeline** — ensure actual class matches survive MAC learning and all output ports are correct.
2. **Redesign Mininet topology with shared bottleneck** — remove disconnected test segments and define a reproducible traffic path.
3. **Add OVS QoS queues and Ryu queue actions** — configure the egress queue policy and verify queue/flow stats.
4. **Automate simultaneous congestion tests** — execute no-QoS vs QoS experiments with controlled workload.
5. **Generate results and plots** — parse raw metrics, summarize repetitions, create at least one well-labelled chart.
6. **Publish reproducible documentation** — clean README, limitations, architecture, troubleshooting, tests, and release.

**Recommended order:** `1 → 2 → 3 → 4 → 5 → 6`. The controller/topology tasks may be developed together, but **do not** jump into plotting before having a valid shared bottleneck and a verified queue policy.

---

## 8. Definition of Done (v2 MVP)

TrafficPriority v2 is done when all of the following can be demonstrated:

- [ ] The topology has a documented, measurable shared bottleneck.
- [ ] The Ryu controller installs correct, class-specific OpenFlow 1.3 rules.
- [ ] The output action actually references the intended QoS queue.
- [ ] OVS is configured to perform queueing on the actual bottleneck egress port.
- [ ] Both traffic classes run **concurrently** in the experiments.
- [ ] The repository contains raw measurements from both **without QoS** and **with QoS** conditions.
- [ ] At least one graph summarizes measured results without presenting illustrative data as real results.
- [ ] README claims are limited to what the implementation and evidence support.
- [ ] Test commands and prerequisites are clear enough for another person to reproduce the demonstration.

### Nice-to-have *after* MVP

- [ ] CLI flags to choose queue policy and traffic load.
- [ ] Separate YAML configuration instead of hard-coded policy.
- [ ] UDP real-time-like traffic scenario with jitter/loss evaluation.
- [ ] Flow/queue statistics exporter or a lightweight metrics report.
- [ ] CI for unit tests and linting.
- [ ] Experiment with different queue-rate allocations to discuss trade-offs.

---

## 9. Technical Notes / Pitfalls

1. **Rule priority ≠ packet queue priority.** Flow selection happens in the OpenFlow pipeline; actual QoS needs a queueing/shaping mechanism in the datapath.
2. **Install queue actions on the right output path.** `OFPActionSetQueue` by itself does not define an OVS queue or enforce its rate.
3. **Flows may never hit `PacketIn`.** Default L2 learning can hide the classification bug, especially when `pingAll()` runs first.
4. **A port number is not a true application detector.** For this MVP, the port is an explicit test label; do not market it as reliable production traffic identification.
5. **TCP and UDP measure different behavior.** TCP throughput is a useful MVP metric; jitter and packet-loss experiments generally require deliberately generated UDP traffic and corresponding protocol-aware rules.
6. **Mininet inside Docker depends on host networking capabilities.** Privileged mode and suitable Linux/OVS support are required; verify the exact environment, particularly when using Docker Desktop on Windows.
7. **Do not overstate results.** QoS changes resource allocation during contention; it does not create bandwidth, and an isolated `iperf` run does not validate prioritization.

## 10. Progress Tracker

| Milestone | Status |
| --- | --- |
| Existing code audited | **Done — static review only** |
| Baseline reproduced on a working host | Not started |
| Controller and topology corrected | Not started |
| OVS QoS queues integrated | Not started |
| Controlled A/B experiments completed | Not started |
| Measurements, charts, and analysis | Not started |
| README + reproducibility + v2 release | Not started |

> **Portfolio positioning:** “An SDN-based, reproducible QoS testbed using Ryu, OpenFlow 1.3, Mininet, and Open vSwitch, with controlled congestion experiments comparing traffic-class bandwidth allocation.” Use this description **only after** the corresponding features and experiments exist.
