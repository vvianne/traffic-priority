# 01: Load and validate backward-compatible QoS configuration

**What to build:** A user can define the bottleneck, traffic classes, queue allocations, and adaptive settings in YAML, while the unchanged default configuration preserves TCP/5001 high priority, TCP/5002 best effort, the 5 Mbps bottleneck, and disabled adaptive QoS.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The default configuration reproduces the current classification, queue selection, bottleneck capacity, and static allocation without requiring user changes.
- [x] Configuration is loaded once into a typed policy model shared by the controller, topology, QoS lifecycle, and experiment workflow.
- [x] Invalid protocols, ports, queue identifiers, rates, thresholds, timing values, duplicate matches, and allocations exceeding parent capacity are rejected before network state is changed.
- [x] Adaptive QoS remains disabled unless explicitly enabled, and configuration behavior and validation errors are documented and unit tested.

## Implementation notes

- The checked-in YAML preserves the v2 10 Mbps access links, 5 Mbps bottleneck, TCP/5001 and TCP/5002 classes, queue 1 at a 3 Mbps minimum, queue 0 at a 1 Mbps minimum, and disabled adaptation.
- One immutable policy model validates and supplies the controller, topology, OVS lifecycle arguments, experiment traffic definitions, counter targets, load scaling, and CSV policy provenance.
- Validation rejects unknown schema keys, unsupported protocols, missing current classes, invalid ports, flow priorities and queue IDs, duplicate matches or queues, non-finite or impossible rates, an ineffective bottleneck, and invalid adaptive thresholds or timing.
- The controller and experiment runner pass configured queue IDs and rates through to OVS while retaining the original defaults for direct script compatibility.
- Documentation describes custom configuration and the intentional TCP-only boundary before the later UDP ticket.
- Python compilation, 28 unit tests, shell syntax validation, and the non-privileged package verifier passed. Mininet/OVS execution was not rerun because the Docker Linux daemon was unavailable; runtime queue verification remains part of the later OVS foundation ticket.

