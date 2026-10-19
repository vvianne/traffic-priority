"""Pure traffic-classification policy shared by the controller and tests."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TrafficPolicy:
    name: str
    destination_port: int
    flow_priority: int
    queue_id: int


DEFAULT_QUEUE_ID = 0


HIGH_PRIORITY = TrafficPolicy(
    name="high-priority",
    destination_port=5001,
    flow_priority=100,
    queue_id=1,
)

BEST_EFFORT = TrafficPolicy(
    name="best-effort",
    destination_port=5002,
    flow_priority=90,
    queue_id=0,
)

POLICIES_BY_DESTINATION_PORT = {
    HIGH_PRIORITY.destination_port: HIGH_PRIORITY,
    BEST_EFFORT.destination_port: BEST_EFFORT,
}


def classify_tcp_destination_port(destination_port: int) -> Optional[TrafficPolicy]:
    """Return the configured policy for a TCP destination port, if any."""
    return POLICIES_BY_DESTINATION_PORT.get(destination_port)
