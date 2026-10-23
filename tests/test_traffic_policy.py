import unittest
from dataclasses import replace

from traffic_policy import (
    BEST_EFFORT,
    DEFAULT_QUEUE_ID,
    HIGH_PRIORITY,
    classify_tcp_destination_port,
)
from policy_config import load_config


class TrafficPolicyTests(unittest.TestCase):
    def test_compatibility_constants_match_repository_configuration(self):
        config = load_config()

        self.assertEqual(HIGH_PRIORITY, config.traffic_class("high_priority"))
        self.assertEqual(BEST_EFFORT, config.traffic_class("best_effort"))

    def test_tcp_5001_is_high_priority(self):
        policy = classify_tcp_destination_port(5001)

        self.assertEqual(HIGH_PRIORITY, policy)
        self.assertEqual("high-priority", policy.name)
        self.assertEqual(100, policy.flow_priority)
        self.assertEqual(1, policy.queue_id)

    def test_tcp_5002_is_best_effort(self):
        policy = classify_tcp_destination_port(5002)

        self.assertEqual(BEST_EFFORT, policy)
        self.assertEqual("best-effort", policy.name)
        self.assertLess(policy.flow_priority, HIGH_PRIORITY.flow_priority)
        self.assertEqual(DEFAULT_QUEUE_ID, policy.queue_id)

    def test_unconfigured_destination_port_uses_fallback_forwarding(self):
        self.assertIsNone(classify_tcp_destination_port(8080))

    def test_explicit_configured_policies_override_default_ports(self):
        configured_high = replace(HIGH_PRIORITY, destination_port=6001)

        self.assertEqual(
            configured_high,
            classify_tcp_destination_port(6001, (configured_high, BEST_EFFORT)),
        )
        self.assertIsNone(
            classify_tcp_destination_port(5001, (configured_high, BEST_EFFORT))
        )


if __name__ == "__main__":
    unittest.main()
