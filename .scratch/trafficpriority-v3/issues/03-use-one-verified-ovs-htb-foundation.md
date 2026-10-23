# 03: Use one verified OVS HTB bottleneck foundation

**What to build:** Baseline and static-QoS experiments share the same 5 Mbps OVS HTB parent bottleneck, differing only in whether traffic classes receive differentiated queue allocation.

**Blocked by:** 01: Load and validate backward-compatible QoS configuration.

**Status:** implemented-awaiting-privileged-verification

- [ ] Baseline mode installs one non-differentiated default queue or an equivalently controlled OVS HTB policy, while static mode installs the configured class queues on the same egress.
- [ ] Topology startup prevents a competing root qdisc and cleanup removes only TrafficPriority-owned QoS state.
- [ ] Startup verification checks the port attachment, OVSDB records, realized kernel HTB classes, parent capacity, queue rates, and applicable OpenFlow queue actions.
- [ ] Failures leave a clear diagnostic and safe cleanup path, and automated tests cover policy construction and verification parsing where privileged execution is unnecessary.

## Implementation notes

Both modes use an unshaped inter-switch link and the same OVS HTB parent. Baseline queue 0 shares the full capacity; static mode uses configured class queues. Startup validates OVSDB and kernel HTB rates, and the experiment runner checks installed queue actions after traffic. Cleanup is scoped to the attached owned policy and does not destroy shared queues. Unit tests cover policy construction, kernel validation, foreign ownership refusal, and failed realization cleanup. Privileged verification remains outstanding because Docker Desktop's Linux daemon is unavailable; no new experimental results are claimed.

