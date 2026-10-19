#!/usr/bin/env bash

set -euo pipefail

if [[ "${1:-}" == "experiment" ]]; then
    shift
    exec python3 /app/scripts/run_experiments.py "$@"
fi

if [[ "${1:-}" == "analyze" ]]; then
    shift
    exec python3 /app/scripts/analyze_results.py "$@"
fi

echo "Starting Ryu controller on 0.0.0.0:6653..."
ryu-manager --ofp-tcp-listen 6653 /app/priority_ryu_controller.py &
RYU_PID=$!

cleanup() {
    kill "${RYU_PID}" 2>/dev/null || true
    wait "${RYU_PID}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Ryu PID=${RYU_PID}"

TOPOLOGY_ARGS=()
case "${QOS_ENABLED:-0}" in
    1|true|TRUE|yes|YES|on|ON) TOPOLOGY_ARGS+=(--qos) ;;
esac

python3 /app/ryu_topo.py "${TOPOLOGY_ARGS[@]}"
