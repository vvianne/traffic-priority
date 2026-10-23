# 13: Add non-privileged CI and privileged-test boundaries

**What to build:** Every change receives fast automated feedback for unit, lint, and package correctness, while tests requiring Mininet, OVS, Docker privileges, or kernel networking remain clearly separated and reproducible.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] GitHub Actions run the supported Python unit suite, lint or static checks, configuration validation, and package verification without requiring privileged networking.
- [ ] Privileged integration and experiment checks use distinct markers or commands and are not presented as having run on standard hosted runners.
- [ ] The workflow uses versions compatible with Python 3.8 and Ryu 4.34 and reports actionable failures.
- [ ] Contributor documentation states which checks CI executes, which require a privileged local or container environment, and how to run both groups.

