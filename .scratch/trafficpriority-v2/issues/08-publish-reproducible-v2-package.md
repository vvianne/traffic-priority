# 08: Publish the reproducible v2 package

**What to build:** A repository that another developer on a supported system can use to understand the architecture, reproduce at least one paired experiment, verify the active policy, and trace every published conclusion back to real evidence.

**Blocked by:** 07: Generate statistical comparisons and plots.

**Status:** resolved

- [x] Documentation includes an accurate project overview, packet path and bottleneck architecture, prerequisites, tested versions, quick start, and cleanup instructions.
- [x] The baseline and QoS experiment parameters, verification commands, representative raw data, plots, and conclusions are linked coherently.
- [x] Troubleshooting covers relevant Docker, Linux or WSL2, kernel, privileges, OVS, Mininet, and controller compatibility limitations.
- [x] The repository includes licensing, ignore rules, dependency information, a clear structure, and basic non-privileged classification tests.
- [x] Release claims are limited to demonstrated behavior, and a v2 release is considered ready only after every MVP definition-of-done item passes.

## Implementation notes

- The README now covers architecture, packet path, quick starts, exact tested versions, verification, cleanup, repository structure, troubleshooting, evidence links, claim boundaries, and release status.
- Python dependencies are pinned in `requirements.txt`; the Docker build installs that manifest and runs all non-privileged tests.
- The package includes an MIT license, focused ignore rules, baseline and v2 release evidence, raw measurements, controller logs, statistical tables, narrative analysis, and the generated SVG.
- `scripts/verify_package.py` checks required files, unit tests, the complete 18-run/three-repetition evidence matrix, congestion evidence, generated artifacts, the raw-data hash, SVG validity, and local issue resolution.
- The verified release environment and every MVP definition-of-done item are recorded in `docs/release-v2.md`. No Git tag or remote publication was performed.
