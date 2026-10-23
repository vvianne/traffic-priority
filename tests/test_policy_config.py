import copy
from pathlib import Path
import tempfile
import unittest

import yaml

from policy_config import ConfigurationError, load_config


DEFAULT_DOCUMENT = {
    "network": {
        "access_link_mbps": 10,
        "bottleneck_mbps": 5,
        "qos_datapath": 1,
        "qos_egress_port": 3,
        "qos_egress_interface": "s1-eth3",
        "qos_bridge": "s1",
    },
    "traffic_classes": {
        "high_priority": {
            "protocol": "tcp",
            "destination_port": 5001,
            "flow_priority": 100,
            "queue_id": 1,
            "min_rate_mbps": 3,
            "max_rate_mbps": 5,
        },
        "best_effort": {
            "protocol": "tcp",
            "destination_port": 5002,
            "flow_priority": 90,
            "queue_id": 0,
            "min_rate_mbps": 1,
            "max_rate_mbps": 5,
        },
    },
    "adaptive_qos": {
        "enabled": False,
        "utilization_threshold": 0.8,
        "monitoring_interval_seconds": 2,
        "hysteresis_margin": 0.1,
        "minimum_dwell_seconds": 10,
    },
}


class PolicyConfigurationTests(unittest.TestCase):
    def load_document(self, document):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.yaml"
            path.write_text(yaml.safe_dump(document), encoding="utf-8")
            return load_config(path)

    def assert_invalid(self, mutate, expected):
        document = copy.deepcopy(DEFAULT_DOCUMENT)
        mutate(document)
        with self.assertRaisesRegex(ConfigurationError, expected):
            self.load_document(document)

    def test_repository_default_preserves_v2_policy(self):
        config = load_config()

        self.assertEqual(5, config.network.bottleneck_mbps)
        self.assertEqual(10, config.network.access_link_mbps)
        self.assertEqual("s1-eth3", config.network.qos_egress_interface)
        high = config.traffic_class("high_priority")
        best = config.traffic_class("best_effort")
        self.assertEqual(("tcp", 5001, 100, 1, 3, 5), (
            high.protocol,
            high.destination_port,
            high.flow_priority,
            high.queue_id,
            high.min_rate_mbps,
            high.max_rate_mbps,
        ))
        self.assertEqual(("tcp", 5002, 90, 0, 1, 5), (
            best.protocol,
            best.destination_port,
            best.flow_priority,
            best.queue_id,
            best.min_rate_mbps,
            best.max_rate_mbps,
        ))
        self.assertFalse(config.adaptive_qos.enabled)

    def test_valid_custom_policy_is_typed(self):
        document = copy.deepcopy(DEFAULT_DOCUMENT)
        document["network"]["bottleneck_mbps"] = 8
        document["traffic_classes"]["high_priority"]["destination_port"] = 6001
        document["traffic_classes"]["high_priority"]["min_rate_mbps"] = 4
        document["traffic_classes"]["high_priority"]["max_rate_mbps"] = 8
        document["traffic_classes"]["best_effort"]["min_rate_mbps"] = 2
        document["traffic_classes"]["best_effort"]["max_rate_mbps"] = 8
        document["adaptive_qos"]["enabled"] = True

        config = self.load_document(document)

        self.assertEqual(8_000_000, config.network.bottleneck_bps)
        self.assertEqual(6001, config.traffic_class("high_priority").destination_port)
        self.assertTrue(config.adaptive_qos.enabled)

    def test_rejects_unsupported_protocol(self):
        self.assert_invalid(
            lambda value: value["traffic_classes"]["high_priority"].update(
                protocol="icmp"
            ),
            "protocol must be one of",
        )

    def test_udp_protocol_loads_from_yaml(self):
        document = copy.deepcopy(DEFAULT_DOCUMENT)
        document["traffic_classes"]["high_priority"]["protocol"] = "udp"
        config = self.load_document(document)
        self.assertEqual("udp", config.traffic_class("high_priority").protocol)

    def test_rejects_invalid_port(self):
        self.assert_invalid(
            lambda value: value["traffic_classes"]["high_priority"].update(
                destination_port=70000
            ),
            "destination_port must be between",
        )

    def test_rejects_negative_queue_identifier(self):
        self.assert_invalid(
            lambda value: value["traffic_classes"]["high_priority"].update(
                queue_id=-1
            ),
            "queue_id must be between",
        )

    def test_rejects_duplicate_queue_identifier(self):
        self.assert_invalid(
            lambda value: value["traffic_classes"]["high_priority"].update(
                queue_id=0
            ),
            "queue IDs must be unique",
        )

    def test_rejects_duplicate_protocol_and_port_match(self):
        self.assert_invalid(
            lambda value: value["traffic_classes"]["high_priority"].update(
                destination_port=5002
            ),
            "protocol/port matches must be unique",
        )

    def test_rejects_negative_rate(self):
        self.assert_invalid(
            lambda value: value["traffic_classes"]["best_effort"].update(
                min_rate_mbps=-1
            ),
            "min_rate_mbps must be at least",
        )

    def test_rejects_bottleneck_faster_than_access_links(self):
        self.assert_invalid(
            lambda value: value["network"].update(bottleneck_mbps=11),
            "bottleneck_mbps cannot exceed access_link_mbps",
        )

    def test_rejects_minimum_allocations_above_capacity(self):
        self.assert_invalid(
            lambda value: value["traffic_classes"]["best_effort"].update(
                min_rate_mbps=3
            ),
            "minimum allocations cannot exceed",
        )

    def test_rejects_invalid_adaptive_threshold(self):
        self.assert_invalid(
            lambda value: value["adaptive_qos"].update(
                utilization_threshold=1.2
            ),
            "utilization_threshold must be at most",
        )

    def test_rejects_invalid_timing(self):
        self.assert_invalid(
            lambda value: value["adaptive_qos"].update(
                monitoring_interval_seconds=0
            ),
            "monitoring_interval_seconds must be greater than zero",
        )

    def test_rejects_unknown_keys(self):
        self.assert_invalid(
            lambda value: value["network"].update(bottelneck_mbps=5),
            "unknown keys",
        )


if __name__ == "__main__":
    unittest.main()
