# 05: Run protocol-aware UDP class experiments

**What to build:** A user can run configured UDP high-priority and best-effort traffic through classification, forwarding, queueing, measurement, and result capture while the existing TCP classes continue to work unchanged.

**Blocked by:** 01: Load and validate backward-compatible QoS configuration; 04: Run reproducible and counterbalanced TCP experiments.

**Status:** implemented-awaiting-privileged-verification

- [ ] Traffic classes match both protocol and destination port, and generated OpenFlow matches prevent TCP and UDP rules from capturing one another.
- [ ] UDP experiments record offered rate, receiver rate, throughput, jitter, lost and total datagrams, and loss percentage for each class.
- [ ] Missing or unsupported UDP metrics remain explicitly unavailable and never become fabricated zeroes.
- [ ] Unit tests cover protocol-aware classification and parsing, and a documented privileged check verifies queue selection and end-to-end UDP forwarding when the environment supports it.

## Implementation notes

YAML classes accept TCP or UDP. Controller matches and fallback flows include the appropriate transport endpoints and IP protocol; counters distinguish identical TCP/UDP destination ports. Experiment servers and clients select the configured transport. Receiver output supplies UDP throughput, received rate, jitter, lost/total datagrams, and loss percentage, with explicit validity diagnostics for incomplete reports. Tests cover parser validation, mixed-protocol command construction, YAML loading, and protocol isolation. README includes a privileged verification procedure; runtime verification remains outstanding until the Linux Docker daemon is available.

