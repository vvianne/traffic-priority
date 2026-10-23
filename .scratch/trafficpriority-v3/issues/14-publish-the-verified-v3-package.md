# 14: Publish the verified TrafficPriority v3 package

**What to build:** Maintainers receive a reproducible v3 package and implementation report whose architecture, instructions, results, and limitations are backed by the repository's actual tests and experiment evidence.

**Blocked by:** 11: Compare baseline, static, and adaptive QoS; 12: Present current and historical experiment monitoring; 13: Add non-privileged CI and test boundaries.

**Status:** ready-for-agent

- [ ] The README presents a useful architecture diagram, traffic and adaptive-policy flow, configuration examples, methodology, reproduction commands, and verified results near the beginning.
- [ ] v1 and v2 historical documentation and evidence remain intact, while v3 documentation clearly separates implemented, unit-validated, privileged-validated, and unverified behavior.
- [ ] A final report lists implemented behavior, modified areas, tests and experiments actually executed, results verified, unresolved limitations, and recommended next steps.
- [ ] Package verification checks required v3 artifacts and traceability without claiming success from fabricated data, missing privileged runs, or stale evidence.
