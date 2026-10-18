# Traffic Prioritization with Ryu and Mininet

TrafficPriority is an SDN testbed built with Ryu, OpenFlow 1.3, Open vSwitch, and Mininet. Two traffic sources share one 5 Mbps inter-switch bottleneck on their path to a receiver.

> **Current status:** the shared-bottleneck topology, controller connectivity, and contextual TCP/5001 and TCP/5002 classification are implemented. Bandwidth prioritization is not implemented yet: OpenFlow rule priority selects which matching rule wins; it does not schedule packets or reserve bandwidth. Actual QoS requires Open vSwitch queues, which are planned in later tickets.

See the [v1 baseline report](docs/baseline-v1.md) for the behavior before the topology correction. The remaining work is described in [the v2 roadmap](TRAFFICPRIORITY_V2_ROADMAP.md).

## Topology

```text
h1 (10.0.0.1) --10 Mbps--\
                           s1 == 5 Mbps == s2 --10 Mbps-- h3 (10.0.0.3)
h2 (10.0.0.2) --10 Mbps--/                 \\--10 Mbps-- h4 (10.0.0.4)
```

`h1` and `h2` are the traffic sources, and `h3` is the primary receiver. Both source-to-receiver paths cross `s1-eth3 <-> s2-eth1`, the shared 5 Mbps bottleneck. The 10 Mbps access links are intentionally faster so they do not become the limiting path.

Both switches:

- use OpenFlow 1.3;
- run in secure fail mode; and
- must connect to the Ryu controller at `127.0.0.1:6653` before the CLI opens.

Startup does not run `pingAll()` or generate other test traffic. This leaves only the table-miss rules in place so first-packet behavior can be inspected deliberately.

## Prerequisites

- Docker Desktop or Docker Engine with Linux containers
- A Linux or WSL2 environment capable of running privileged containers
- Kernel and container permissions sufficient for Open vSwitch and Mininet network namespaces

The captured environment uses Docker Desktop with its WSL2 backend on Windows. Other hosts may behave differently; consult the baseline report for the versions tested so far.

## Build and run

```bash
docker build -t traffic-priority .
docker run --privileged --rm -it traffic-priority
```

On Linux or WSL2, the helper performs the same steps:

```bash
chmod +x start_project.sh
./start_project.sh
```

The container starts Ryu, creates the topology, waits for both switches to connect, prints the expected bottleneck ports, and opens the Mininet CLI.

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

Inspect the traffic-control class applied to the shared link:

```text
mininet> sh tc class show dev s1-eth3
```

It should report `rate 5Mbit ceil 5Mbit`. An indicative single-flow probe can then be run with:

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

Ryu should log each classification once per switch. The flow dumps should contain priority-100 TCP/5001 and priority-90 TCP/5002 rules matching the ingress port, source and destination MAC addresses, source and destination IPv4 addresses, TCP source port, and TCP destination port. On the documented topology, forward actions are `output:3` on `s1` and `output:2` on `s2`; a flood action is never stored as a class-specific rule.

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

## Current forwarding behavior

The Ryu application provides table-miss handling, per-datapath MAC learning, protocol-specific learned forwarding, explicit TCP/5001 and TCP/5002 classes, and contextual fallback forwarding. Learned ARP, ICMP, or unrelated TCP rules cannot capture either classified traffic flow.

## Known limitations

- No OVS QoS or Queue records are configured yet.
- Flow rule priority is not packet scheduling priority.
- Docker dependencies are not fully pinned, so a future rebuild may resolve different package versions.
- Privileged Mininet execution depends on the host kernel and Docker environment.

## v2 objective

TrafficPriority v2 will map traffic classes to real OVS queues, run simultaneous without-QoS and with-QoS experiments, and publish raw measurements plus reproducible plots. Until those stages are complete, this repository should be described as an SDN shared-bottleneck testbed rather than a working QoS system.
