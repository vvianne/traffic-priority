# 05: Enforce and verify the OVS queue policy

**What to build:** A reproducible QoS mode that attaches best-effort and high-priority queues to the actual bottleneck egress interface and makes the controller select the appropriate queue before forwarding each classified flow.

**Blocked by:** 04: Handle best-effort and fallback traffic without bypassing policy.

**Status:** ready-for-agent

- [ ] QoS setup discovers or verifies the exact egress interface from the first switch toward the second switch.
- [ ] Queue 0 and queue 1 are created with the documented rate policy and attached to that interface using a consistent queueing discipline.
- [ ] Classified flows set their intended queue before the output action, with documented fallback behavior for unclassified packets.
- [ ] QoS records, queue records, OpenFlow actions, and available queue or interface counters can be inspected with documented commands.
- [ ] Repeated setup and teardown leave no stale QoS state and produce the same effective configuration.

