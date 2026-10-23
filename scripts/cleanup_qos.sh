#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/..${PYTHONPATH:+:${PYTHONPATH}}"
python3 -c 'import sys; from ovs_qos import cleanup; cleanup(sys.argv[1])' "${1:-s1-eth3}"
