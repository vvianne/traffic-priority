# 01: Capture a truthful, reproducible v1 baseline

**What to build:** A reproducible record of the current system that shows what actually works, which environment it works in, when controller rules appear, and why the existing rule-priority demonstration is not yet proof of QoS.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The tested host, container, Python, Ryu, Mininet, Open vSwitch, and OpenFlow versions are recorded.
- [x] The current demonstration is run and its controller logs, connectivity result, and OpenFlow 1.3 flow dump are captured.
- [x] Startup, privilege, PacketIn, or OVS failures encountered during reproduction are documented.
- [x] User-facing documentation no longer claims that OpenFlow match priority alone schedules or reserves bandwidth.

## Implementation notes

The verified environment, reproduction commands, runtime evidence, and limitations are recorded in `docs/baseline-v1.md`. The README now presents the current project as a baseline SDN classification experiment and links to that evidence instead of claiming proven QoS.
