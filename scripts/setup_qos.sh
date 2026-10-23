#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/..${PYTHONPATH:+:${PYTHONPATH}}"
python3 -c '
import sys
from dataclasses import replace
from policy_config import load_config
from ovs_qos import setup
config = load_config()
network = replace(config.network, qos_egress_interface=sys.argv[1], qos_bridge=sys.argv[2])
setup(replace(config, network=network), differentiated=True)
' "${1:-s1-eth3}" "${2:-s1}"
