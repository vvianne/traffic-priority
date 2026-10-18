# 04: Handle best-effort and fallback traffic without bypassing policy

**What to build:** Predictable forwarding for TCP/5002 and unclassified traffic while preserving ARP and general connectivity, ensuring learned forwarding rules cannot shadow the traffic-class policy.

**Blocked by:** 03: Classify and forward high-priority traffic correctly.

**Status:** resolved

- [x] TCP traffic to destination port 5002 is recognized as best-effort test traffic and reaches the intended receiver.
- [x] Learned MAC state is isolated per datapath and generic forwarding rules cannot bypass class-specific handling.
- [x] ARP, non-TCP packets, unknown destinations, and unsupported traffic retain documented fallback behavior.
- [x] Valid buffer identifier zero and the no-buffer case are handled correctly.
- [x] Automated policy tests cover best-effort and fallback decisions, and flow dumps show the intended rules for both traffic classes.

## Implementation notes

TCP/5002 now maps to the best-effort policy at priority 90, below TCP/5001 at priority 100. Runtime verification produced 0% loss for ARP/ICMP connectivity, installed both class rules on both switches, forwarded unclassified TCP/8080 with a priority-10 contextual rule, and stored no flood action after probing an unknown destination. Pure unit tests cover both traffic classes, unconfigured-port fallback, valid buffer ID zero, the no-buffer sentinel, and a missing buffer ID.
