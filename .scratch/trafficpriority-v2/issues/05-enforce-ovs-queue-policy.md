# 05: Enforce and verify the OVS queue policy

**What to build:** A reproducible QoS mode that attaches best-effort and high-priority queues to the actual bottleneck egress interface and makes the controller select the appropriate queue before forwarding each classified flow.

**Blocked by:** 04: Handle best-effort and fallback traffic without bypassing policy.

**Status:** resolved

- [x] QoS setup discovers or verifies the exact egress interface from the first switch toward the second switch.
- [x] Queue 0 and queue 1 are created with the documented rate policy and attached to that interface using a consistent queueing discipline.
- [x] Classified flows set their intended queue before the output action, with documented fallback behavior for unclassified packets.
- [x] QoS records, queue records, OpenFlow actions, and available queue or interface counters can be inspected with documented commands.
- [x] Repeated setup and teardown leave no stale QoS state and produce the same effective configuration.

## Implementation notes

- `scripts/setup_qos.sh` verifies `s1-eth3` belongs to `s1`, then attaches one `linux-htb` policy with a 5 Mbps parent, queue 0 at 1/5 Mbps, and queue 1 at 3/5 Mbps.
- QoS mode leaves the inter-switch link unshaped during Mininet creation so OVS owns the root qdisc; the default mode retains the 5 Mbps `TCLink` baseline.
- Ryu selects queue 1 for TCP/5001 and queue 0 for TCP/5002 and fallback traffic, only on datapath 1 output port 3. Queue selection precedes output.
- Runtime verification showed both queues as kernel HTB classes, class-specific `set_queue` actions on `s1`, forwarding-only actions on `s2`, and nonzero OpenFlow queue counters for both queues.
- Cleanup removed the port attachment plus all owned QoS/Queue records. A second cleanup was a no-op, and setup recreated exactly one QoS record and two Queue records.

