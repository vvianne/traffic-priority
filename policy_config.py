"""Typed, validated configuration for TrafficPriority policies."""

from dataclasses import dataclass
from math import isfinite
import os
from pathlib import Path
from typing import Mapping, Optional, Tuple

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "traffic_priority.yaml"
CONFIG_ENVIRONMENT_VARIABLE = "TRAFFIC_PRIORITY_CONFIG"
SUPPORTED_TRAFFIC_CLASS_NAMES = {"high_priority", "best_effort"}
SUPPORTED_PROTOCOLS = {"tcp", "udp"}
MAX_QUEUE_ID = 0xFFFFFFFF
MAX_FLOW_PRIORITY = 0xFFFF


class ConfigurationError(ValueError):
    """Raised before runtime state changes when policy configuration is invalid."""


@dataclass(frozen=True)
class NetworkConfig:
    access_link_mbps: float
    bottleneck_mbps: float
    qos_datapath: int
    qos_egress_port: int
    qos_egress_interface: str
    qos_bridge: str

    @property
    def bottleneck_bps(self):
        return int(round(self.bottleneck_mbps * 1_000_000))


@dataclass(frozen=True)
class TrafficClassConfig:
    key: str
    protocol: str
    destination_port: int
    flow_priority: int
    queue_id: int
    min_rate_mbps: float
    max_rate_mbps: float

    @property
    def name(self):
        return self.key.replace("_", "-")

    @property
    def min_rate_bps(self):
        return int(round(self.min_rate_mbps * 1_000_000))

    @property
    def max_rate_bps(self):
        return int(round(self.max_rate_mbps * 1_000_000))


@dataclass(frozen=True)
class AdaptiveQoSConfig:
    enabled: bool
    utilization_threshold: float
    monitoring_interval_seconds: float
    hysteresis_margin: float
    minimum_dwell_seconds: float


@dataclass(frozen=True)
class PolicyConfig:
    network: NetworkConfig
    traffic_classes: Tuple[TrafficClassConfig, ...]
    adaptive_qos: AdaptiveQoSConfig
    source_path: Path

    def traffic_class(self, key):
        for traffic_class in self.traffic_classes:
            if traffic_class.key == key:
                return traffic_class
        raise KeyError(key)

    def classify(self, protocol, destination_port):
        normalized_protocol = protocol.lower()
        for traffic_class in self.traffic_classes:
            if (
                traffic_class.protocol == normalized_protocol
                and traffic_class.destination_port == destination_port
            ):
                return traffic_class
        return None


def _mapping(value, location):
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{location} must be a mapping")
    return value


def _require_keys(mapping, required, location):
    missing = sorted(set(required).difference(mapping))
    unknown = sorted(set(mapping).difference(required))
    if missing:
        raise ConfigurationError(f"{location} is missing: {', '.join(missing)}")
    if unknown:
        raise ConfigurationError(f"{location} has unknown keys: {', '.join(unknown)}")


def _integer(value, location, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{location} must be an integer")
    if not minimum <= value <= maximum:
        raise ConfigurationError(
            f"{location} must be between {minimum} and {maximum}"
        )
    return value


def _number(value, location, minimum=None, maximum=None, strictly_positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{location} must be a number")
    result = float(value)
    if not isfinite(result):
        raise ConfigurationError(f"{location} must be finite")
    if strictly_positive and result <= 0:
        raise ConfigurationError(f"{location} must be greater than zero")
    if minimum is not None and result < minimum:
        raise ConfigurationError(f"{location} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise ConfigurationError(f"{location} must be at most {maximum}")
    return result


def _text(value, location):
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{location} must be a non-empty string")
    return value.strip()


def _boolean(value, location):
    if not isinstance(value, bool):
        raise ConfigurationError(f"{location} must be true or false")
    return value


def _parse_network(raw):
    location = "network"
    values = _mapping(raw, location)
    required = {
        "access_link_mbps",
        "bottleneck_mbps",
        "qos_datapath",
        "qos_egress_port",
        "qos_egress_interface",
        "qos_bridge",
    }
    _require_keys(values, required, location)
    access_link_mbps = _number(
        values["access_link_mbps"],
        "network.access_link_mbps",
        strictly_positive=True,
    )
    bottleneck_mbps = _number(
        values["bottleneck_mbps"],
        "network.bottleneck_mbps",
        strictly_positive=True,
    )
    if bottleneck_mbps > access_link_mbps:
        raise ConfigurationError(
            "network.bottleneck_mbps cannot exceed access_link_mbps"
        )
    return NetworkConfig(
        access_link_mbps=access_link_mbps,
        bottleneck_mbps=bottleneck_mbps,
        qos_datapath=_integer(
            values["qos_datapath"], "network.qos_datapath", 1, 0xFFFFFFFFFFFFFFFF
        ),
        qos_egress_port=_integer(
            values["qos_egress_port"], "network.qos_egress_port", 1, 0xFFFFFFFF
        ),
        qos_egress_interface=_text(
            values["qos_egress_interface"], "network.qos_egress_interface"
        ),
        qos_bridge=_text(values["qos_bridge"], "network.qos_bridge"),
    )


def _parse_traffic_classes(raw, capacity):
    values = _mapping(raw, "traffic_classes")
    names = set(values)
    if names != SUPPORTED_TRAFFIC_CLASS_NAMES:
        missing = sorted(SUPPORTED_TRAFFIC_CLASS_NAMES.difference(names))
        unknown = sorted(names.difference(SUPPORTED_TRAFFIC_CLASS_NAMES))
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if unknown:
            details.append(f"unsupported {', '.join(unknown)}")
        raise ConfigurationError(
            "traffic_classes must define the current high_priority and best_effort "
            f"classes ({'; '.join(details)})"
        )

    required = {
        "protocol",
        "destination_port",
        "flow_priority",
        "queue_id",
        "min_rate_mbps",
        "max_rate_mbps",
    }
    parsed = []
    for key in ("high_priority", "best_effort"):
        location = f"traffic_classes.{key}"
        traffic_class = _mapping(values[key], location)
        _require_keys(traffic_class, required, location)
        protocol = _text(traffic_class["protocol"], f"{location}.protocol").lower()
        if protocol not in SUPPORTED_PROTOCOLS:
            raise ConfigurationError(
                f"{location}.protocol must be one of: "
                f"{', '.join(sorted(SUPPORTED_PROTOCOLS))}"
            )
        min_rate = _number(
            traffic_class["min_rate_mbps"],
            f"{location}.min_rate_mbps",
            minimum=0,
            maximum=capacity,
        )
        max_rate = _number(
            traffic_class["max_rate_mbps"],
            f"{location}.max_rate_mbps",
            strictly_positive=True,
            maximum=capacity,
        )
        if min_rate > max_rate:
            raise ConfigurationError(
                f"{location}.min_rate_mbps cannot exceed max_rate_mbps"
            )
        parsed.append(
            TrafficClassConfig(
                key=key,
                protocol=protocol,
                destination_port=_integer(
                    traffic_class["destination_port"],
                    f"{location}.destination_port",
                    1,
                    65535,
                ),
                flow_priority=_integer(
                    traffic_class["flow_priority"],
                    f"{location}.flow_priority",
                    1,
                    MAX_FLOW_PRIORITY,
                ),
                queue_id=_integer(
                    traffic_class["queue_id"],
                    f"{location}.queue_id",
                    0,
                    MAX_QUEUE_ID,
                ),
                min_rate_mbps=min_rate,
                max_rate_mbps=max_rate,
            )
        )

    matches = [(item.protocol, item.destination_port) for item in parsed]
    if len(set(matches)) != len(matches):
        raise ConfigurationError("traffic class protocol/port matches must be unique")
    queue_ids = [item.queue_id for item in parsed]
    if len(set(queue_ids)) != len(queue_ids):
        raise ConfigurationError("traffic class queue IDs must be unique")
    if sum(item.min_rate_mbps for item in parsed) > capacity:
        raise ConfigurationError(
            "traffic class minimum allocations cannot exceed bottleneck capacity"
        )
    return tuple(parsed)


def _parse_adaptive_qos(raw):
    location = "adaptive_qos"
    values = _mapping(raw, location)
    required = {
        "enabled",
        "utilization_threshold",
        "monitoring_interval_seconds",
        "hysteresis_margin",
        "minimum_dwell_seconds",
    }
    _require_keys(values, required, location)
    threshold = _number(
        values["utilization_threshold"],
        "adaptive_qos.utilization_threshold",
        strictly_positive=True,
        maximum=1,
    )
    margin = _number(
        values["hysteresis_margin"],
        "adaptive_qos.hysteresis_margin",
        minimum=0,
        maximum=1,
    )
    if margin >= threshold:
        raise ConfigurationError(
            "adaptive_qos.hysteresis_margin must be less than utilization_threshold"
        )
    return AdaptiveQoSConfig(
        enabled=_boolean(values["enabled"], "adaptive_qos.enabled"),
        utilization_threshold=threshold,
        monitoring_interval_seconds=_number(
            values["monitoring_interval_seconds"],
            "adaptive_qos.monitoring_interval_seconds",
            strictly_positive=True,
        ),
        hysteresis_margin=margin,
        minimum_dwell_seconds=_number(
            values["minimum_dwell_seconds"],
            "adaptive_qos.minimum_dwell_seconds",
            strictly_positive=True,
        ),
    )


def load_config(path: Optional[Path] = None) -> PolicyConfig:
    """Load and validate one policy file before callers mutate network state."""
    selected_path = Path(
        path or os.getenv(CONFIG_ENVIRONMENT_VARIABLE) or DEFAULT_CONFIG_PATH
    ).expanduser().resolve()
    try:
        with selected_path.open(encoding="utf-8") as source:
            raw = yaml.safe_load(source)
    except OSError as error:
        raise ConfigurationError(
            f"Could not read configuration {selected_path}: {error}"
        ) from error
    except yaml.YAMLError as error:
        raise ConfigurationError(
            f"Could not parse configuration {selected_path}: {error}"
        ) from error

    document = _mapping(raw, "configuration")
    _require_keys(document, {"network", "traffic_classes", "adaptive_qos"}, "configuration")
    network = _parse_network(document["network"])
    traffic_classes = _parse_traffic_classes(
        document["traffic_classes"], network.bottleneck_mbps
    )
    adaptive_qos = _parse_adaptive_qos(document["adaptive_qos"])
    return PolicyConfig(
        network=network,
        traffic_classes=traffic_classes,
        adaptive_qos=adaptive_qos,
        source_path=selected_path,
    )
