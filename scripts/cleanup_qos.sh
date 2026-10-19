#!/usr/bin/env bash

set -euo pipefail

QOS_PORT="${1:-s1-eth3}"
QOS_OWNER="traffic-priority"

if ! ovs-vsctl get Port "${QOS_PORT}" name >/dev/null 2>&1; then
    echo "QoS cleanup: port ${QOS_PORT} does not exist; nothing to remove."
    exit 0
fi

QOS_UUID="$(ovs-vsctl get Port "${QOS_PORT}" qos | tr -d '[]\"')"
if [[ -n "${QOS_UUID}" ]]; then
    ATTACHED_OWNER="$(
        ovs-vsctl get QoS "${QOS_UUID}" external_ids:owner | tr -d '[]\"'
    )"
    if [[ "${ATTACHED_OWNER}" != "${QOS_OWNER}" ]]; then
        echo "QoS cleanup refused: ${QOS_PORT} has a policy not owned by ${QOS_OWNER}." >&2
        exit 1
    fi

    ovs-vsctl clear Port "${QOS_PORT}" qos
fi

mapfile -t QOS_UUIDS < <(
    ovs-vsctl --data=bare --no-heading --columns=_uuid \
        find QoS "external_ids:owner=${QOS_OWNER}"
)
mapfile -t QUEUE_UUIDS < <(
    ovs-vsctl --data=bare --no-heading --columns=_uuid \
        find Queue "external_ids:owner=${QOS_OWNER}"
)

for qos_uuid in "${QOS_UUIDS[@]}"; do
    ovs-vsctl --if-exists destroy QoS "${qos_uuid}"
done
for queue_uuid in "${QUEUE_UUIDS[@]}"; do
    ovs-vsctl --if-exists destroy Queue "${queue_uuid}"
done

if [[ -n "${QOS_UUID}" || ${#QOS_UUIDS[@]} -gt 0 || ${#QUEUE_UUIDS[@]} -gt 0 ]]; then
    echo "QoS cleanup: removed ${QOS_OWNER} policy state from ${QOS_PORT}."
else
    echo "QoS cleanup: no ${QOS_OWNER} policy state exists."
fi
