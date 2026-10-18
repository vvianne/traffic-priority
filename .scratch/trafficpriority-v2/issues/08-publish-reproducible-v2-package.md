# 08: Publish the reproducible v2 package

**What to build:** A repository that another developer on a supported system can use to understand the architecture, reproduce at least one paired experiment, verify the active policy, and trace every published conclusion back to real evidence.

**Blocked by:** 07: Generate statistical comparisons and plots.

**Status:** ready-for-agent

- [ ] Documentation includes an accurate project overview, packet path and bottleneck architecture, prerequisites, tested versions, quick start, and cleanup instructions.
- [ ] The baseline and QoS experiment parameters, verification commands, representative raw data, plots, and conclusions are linked coherently.
- [ ] Troubleshooting covers relevant Docker, Linux or WSL2, kernel, privileges, OVS, Mininet, and controller compatibility limitations.
- [ ] The repository includes licensing, ignore rules, dependency information, a clear structure, and basic non-privileged classification tests.
- [ ] Release claims are limited to demonstrated behavior, and a v2 release is considered ready only after every MVP definition-of-done item passes.
