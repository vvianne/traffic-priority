#!/usr/bin/env bash

set -euo pipefail

echo "Starting Ryu controller on 0.0.0.0:6653..."
ryu-manager --ofp-tcp-listen 6653 /app/priority_ryu_controller.py &
RYU_PID=$!

cleanup() {
    kill "${RYU_PID}" 2>/dev/null || true
    wait "${RYU_PID}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Ryu PID=${RYU_PID}"
python3 /app/ryu_topo.py
