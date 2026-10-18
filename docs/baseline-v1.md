# TrafficPriority v1 baseline

This report records the current repository behavior before the v2 QoS work. It is a runtime observation of commit `837cc4739d7ad819d7c3c013937f3f74c693d10d`, captured on 2026-10-18. It does not claim that the environment is portable to every Docker host.

## Tested environment

| Component | Observed value |
| --- | --- |
| Host OS | Microsoft Windows `10.0.26200.9711`, x86-64 |
| Host shell | Windows PowerShell `5.1.26100.9711` |
| WSL | WSL `2.6.3.0`, default version 2 |
| Container kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Docker Desktop | `4.63.0 (220185)` |
| Docker Engine | `29.2.1`, API `1.53`, Linux/amd64 |
| Baseline image | `sha256:53604cd607aa723051438d074a20ccbd05f3b507f268a055df9935e3f90dd63e` |
| Container base | Ubuntu 20.04 image resolved during the build |
| Python | `3.8.10` |
| Ryu | `4.34` |
| Open vSwitch | `2.13.8`, DB schema `8.2.0` |
| Mininet Python package | `2.3.0.dev6` |
| iperf | `2.0.13` |
| OpenFlow | `1.3`, requested by both switches and used for flow inspection |

The image also installs Mininet from Ubuntu packages before installing the `2.3.0.dev6` Python package from PyPI. Several transitive Python dependencies are not pinned. These observations describe this image build, not a permanent lockfile.

## Reproduction

Build the image:

```bash
docker build -t traffic-priority-baseline .
```

The build completed successfully. The unmodified default launch then failed immediately:

```text
exec /app/run_all.sh: no such file or directory
```

Inspection showed that the copied shell scripts use CRLF line endings. Linux therefore reads a carriage return as part of the shebang interpreter path. To continue observing the unmodified Python applications without changing the repository, the run used an entrypoint override:

```bash
docker run --privileged --rm -it \
  --entrypoint /bin/bash \
  traffic-priority-baseline \
  -lc 'ryu-manager --ofp-tcp-listen 6653 /app/priority_ryu_controller.py & python3 /app/ryu_topo.py'
```

The override changes only the disposable container process invocation; it does not repair the launcher or alter controller/topology behavior.

## Controller and topology startup

Ryu loaded the application and OpenFlow handler, both datapaths connected, and the controller reported a default flow on datapaths 1 and 2:

```text
loading app /app/priority_ryu_controller.py
loading app ryu.controller.ofp_handler
instantiating app /app/priority_ryu_controller.py of PriorityApp
instantiating app ryu.controller.ofp_handler of OFPHandler
Default flow installed on datapath 1
Default flow installed on datapath 2
```

Mininet also reported a non-fatal container limitation:

```text
*** Error setting resource limits. Mininet's performance may be affected.
```

This warning matters for later performance experiments: throughput measurements should not be treated as controlled evidence until resource-limit behavior is understood.

## Connectivity result

The topology creates `h1--s1--h2` and `h3--s2--h4` without an `s1--s2` link. The automatic full-mesh ping produced:

```text
*** Results: 66% dropped (4/12 received)
```

The four successful directed pings are the two directions within each disconnected segment. Cross-segment traffic cannot arrive.

## Flow behavior before the TCP test

After startup `pingAll()`, an OpenFlow 1.3 dump of `s1` contained:

- the priority-0 table-miss rule sending packets to the controller;
- a priority-1 learned rule from `s1` port 1 to port 2; and
- a priority-1 learned rule from `s1` port 2 to port 1.

The learned rules match `in_port` and destination MAC address. They are protocol-agnostic, so matching later TCP packets are forwarded in the switch without producing a new `PacketIn`.

## TCP/5001 probe

The probe used the only connected source/receiver pair on `s1`:

```text
mininet> h1 iperf -s -p 5001 > /tmp/iperf-5001.log 2>&1 &
mininet> h2 iperf -c 10.0.0.1 -p 5001 -t 3
```

Observed client result:

```text
[  3] local 10.0.0.2 port 59862 connected with 10.0.0.1 port 5001
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0- 3.3 sec  5.12 MBytes  13.1 Mbits/sec
```

This is an isolated flow on a nominal 10 Mbps emulated link, not a controlled benchmark. The short run, Mininet resource-limit warning, and observed value above the configured link rate make it unsuitable as QoS evidence.

The flow dump after the transfer still contained only the two priority-1 learned-MAC rules and the priority-0 controller rule. Their counters increased to thousands of packets, but there was no priority-20 TCP/5001 rule. No `Video Traffic detected!` controller log appeared during the transfer.

## Findings

1. The checked-in image builds on the tested Docker/WSL2 environment.
2. The checked-in default launcher does not start because of CRLF shell-script line endings.
3. With an entrypoint workaround, Ryu, OVS, and Mininet start and negotiate OpenFlow 1.3.
4. The two topology segments are disconnected, yielding 66% loss in the automatic all-host ping.
5. The automatic ping installs generic learned-MAC rules before the experiment.
6. Those rules forward subsequent TCP/5001 traffic without another `PacketIn`, so the class-specific rule is not installed.
7. No OVS queues are configured. Even if priority-10 and priority-20 rules appeared, their OpenFlow priorities would select matches rather than allocate bandwidth.

## Known startup and portability risks

- The default launcher requires Linux-compatible line endings.
- The container requires privileged networking and functioning OVS/kernel support.
- Mininet could not set all requested resource limits in this Docker Desktop environment.
- Docker Desktop initially had to be started before its Linux engine API became available.
- Direct Windows installations of Ryu, OVS, and Mininet were not present; the supported path tested here is the Linux container.
- The dependency graph is only partly pinned and may change on rebuild.

## Baseline conclusion

The current repository demonstrates that Ryu can connect to two OVS datapaths and that MAC-learning forwarding works within each isolated segment. It does not currently demonstrate successful TCP class-rule installation after startup, contention on a shared bottleneck, queue selection, or bandwidth prioritization. Those are v2 acceptance targets, not v1 results.
