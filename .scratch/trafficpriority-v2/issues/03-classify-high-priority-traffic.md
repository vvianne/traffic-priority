# 03: Classify and forward high-priority traffic correctly

**What to build:** An end-to-end TCP/5001 path that the controller recognizes as high-priority test traffic and forwards through the correct interface using a specific, inspectable rule that cannot accidentally capture unrelated flows.

**Blocked by:** 02: Provide forwarding through a shared bottleneck.

**Status:** resolved

- [x] TCP traffic to destination port 5001 reaches the intended receiver across the shared bottleneck.
- [x] The installed match includes enough ingress, destination, protocol, and transport context to select the correct egress port.
- [x] A flood output is never stored as a unicast class-specific flow.
- [x] Classification logs identify the class, selected match, and output port without flooding normal runs with repeated messages.
- [x] Automated policy tests cover the TCP/5001 classification decision without requiring a privileged Mininet environment.

## Implementation notes

The controller now installs protocol-specific learned rules and a priority-100 high-priority rule for TCP/5001 only after the destination port is known. Runtime verification deliberately sent ICMP first, then confirmed the TCP rule on both switches with `output:3` on `s1` and `output:2` on `s2`. The match included ingress port, both MAC addresses, both IPv4 addresses, IP protocol, TCP source port, and TCP destination port.
