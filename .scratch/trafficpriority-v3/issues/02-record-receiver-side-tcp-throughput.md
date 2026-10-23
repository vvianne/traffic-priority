# 02: Record trustworthy receiver-side TCP throughput

**What to build:** A TCP experiment records separately named sender-reported, receiver-reported, and bottleneck-egress throughput values so users can judge delivered traffic without treating the sender estimate as received traffic.

**Blocked by:** None (can start immediately).

**Status:** implemented-awaiting-privileged-verification

- [ ] The receiver emits a parseable per-class result for the controlled measurement interval while the existing sender and switch-egress measurements remain available.
- [x] Raw output identifies the source, interval, units, and aggregation method for every throughput value.
- [x] Missing, malformed, incomplete, or mismatched receiver results produce an explicit invalid or unavailable value and diagnostic instead of zero or a fabricated estimate.
- [x] Unit tests cover valid output, multiple intervals, malformed output, missing results, and validation of sender/receiver identity and measurement windows.

## Implementation notes

- Every measured run starts fresh CSV-reporting iperf receivers for both traffic classes, captures the two sender summaries, and gracefully stops the receivers so their final summaries are flushed.
- Raw sender and receiver summaries are stored beside the experiment CSV. Each result records its interval, transferred bytes, throughput, validity, diagnostic, and raw-output filename; the legacy throughput column remains a sender alias.
- Validation accounts for iperf 2.0.13 reporting local and peer endpoints rather than consistently reporting traffic direction. It checks the unordered address pair, exact receiver address and listening port, a near-zero interval start, and duration tolerance.
- V3 analysis requires valid receiver results and uses them for application-delivery comparisons. Historical CSVs that entirely lack the receiver schema remain supported as explicitly labelled legacy sender evidence.
- Python compilation, 34 unit tests, package verification, and diff validation pass. The remaining acceptance item requires a privileged Mininet/OVS experiment; Docker Desktop's Linux daemon was unavailable during implementation.

