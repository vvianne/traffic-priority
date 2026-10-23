# 10: Apply adaptive queue allocations safely at runtime

**What to build:** An accepted adaptive recommendation safely changes TrafficPriority-owned OVS queue allocations while traffic continues to flow, and a failed change preserves or restores a known valid policy.

**Blocked by:** 03: Use one verified OVS HTB bottleneck foundation; 09: Produce stable adaptive policy decisions.

**Status:** ready-for-agent

- [ ] Queue updates modify only the intended TrafficPriority-owned policy and do not restart the topology, controller, or existing forwarding flows.
- [ ] Requested allocations are validated before mutation and the realized OVSDB and kernel HTB state is verified after mutation.
- [ ] Failed or partially verified updates retain the last known valid allocation or apply a documented safe fallback, with clear attempted and successful transition logs.
- [ ] Unit tests cover command construction, ownership checks, no-op updates, failures, verification mismatches, and fallback behavior; a privileged check demonstrates a real runtime allocation change when supported.

