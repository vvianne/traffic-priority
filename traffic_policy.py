"""Pure traffic classification backed by the validated policy configuration."""

from typing import Iterable, Optional

from policy_config import TrafficClassConfig


TrafficPolicy = TrafficClassConfig


HIGH_PRIORITY = TrafficPolicy(
    key="high_priority",
    protocol="tcp",
    destination_port=5001,
    flow_priority=100,
    queue_id=1,
    min_rate_mbps=3,
    max_rate_mbps=5,
)
BEST_EFFORT = TrafficPolicy(
    key="best_effort",
    protocol="tcp",
    destination_port=5002,
    flow_priority=90,
    queue_id=0,
    min_rate_mbps=1,
    max_rate_mbps=5,
)
DEFAULT_QUEUE_ID = BEST_EFFORT.queue_id
POLICIES_BY_DESTINATION_PORT = {
    policy.destination_port: policy for policy in (HIGH_PRIORITY, BEST_EFFORT)
}


def classify_tcp_destination_port(
    destination_port: int,
    policies: Optional[Iterable[TrafficPolicy]] = None,
) -> Optional[TrafficPolicy]:
    """Return the configured policy for a TCP destination port, if any."""
    if policies is None:
        return POLICIES_BY_DESTINATION_PORT.get(destination_port)
    for policy in policies:
        if policy.protocol == "tcp" and policy.destination_port == destination_port:
            return policy
    return None


def transport_match_fields(protocol, source_port, destination_port):
    """OpenFlow 1.3 transport fields with explicit IP protocol prerequisites."""
    if protocol not in {"tcp", "udp"}:
        raise ValueError("Unsupported transport protocol: " + protocol)
    return {
        "ip_proto": 6 if protocol == "tcp" else 17,
        protocol + "_src": source_port,
        protocol + "_dst": destination_port,
    }
