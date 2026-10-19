#!/usr/bin/env bash

set -euo pipefail

QOS_PORT="${1:-s1-eth3}"
EXPECTED_BRIDGE="${2:-s1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ACTUAL_BRIDGE="$(ovs-vsctl port-to-br "${QOS_PORT}" 2>/dev/null || true)"
if [[ "${ACTUAL_BRIDGE}" != "${EXPECTED_BRIDGE}" ]]; then
    echo "QoS setup failed: ${QOS_PORT} belongs to '${ACTUAL_BRIDGE}', expected '${EXPECTED_BRIDGE}'." >&2
    exit 1
fi

"${SCRIPT_DIR}/cleanup_qos.sh" "${QOS_PORT}"

ovs-vsctl \
    -- set Port "${QOS_PORT}" qos=@qos \
    -- --id=@qos create QoS \
        type=linux-htb \
        other-config:max-rate=5000000 \
        external_ids:owner=traffic-priority \
        queues:0=@best_effort \
        queues:1=@high_priority \
    -- --id=@best_effort create Queue \
        other-config:min-rate=1000000 \
        other-config:max-rate=5000000 \
        external_ids:owner=traffic-priority \
    -- --id=@high_priority create Queue \
        other-config:min-rate=3000000 \
        other-config:max-rate=5000000 \
        external_ids:owner=traffic-priority \
    >/dev/null

QOS_UUID="$(ovs-vsctl get Port "${QOS_PORT}" qos | tr -d '[]\"')"
if [[ -z "${QOS_UUID}" ]]; then
    echo "QoS setup failed: no QoS record is attached to ${QOS_PORT}." >&2
    exit 1
fi

echo "QoS enabled on ${QOS_PORT}: queue 0 min 1 Mbps, queue 1 min 3 Mbps, port max 5 Mbps."
