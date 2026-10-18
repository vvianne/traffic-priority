import unittest

from traffic_policy import (
    BEST_EFFORT,
    HIGH_PRIORITY,
    classify_tcp_destination_port,
)


class TrafficPolicyTests(unittest.TestCase):
    def test_tcp_5001_is_high_priority(self):
        policy = classify_tcp_destination_port(5001)

        self.assertEqual(HIGH_PRIORITY, policy)
        self.assertEqual("high-priority", policy.name)
        self.assertEqual(100, policy.flow_priority)

    def test_tcp_5002_is_best_effort(self):
        policy = classify_tcp_destination_port(5002)

        self.assertEqual(BEST_EFFORT, policy)
        self.assertEqual("best-effort", policy.name)
        self.assertLess(policy.flow_priority, HIGH_PRIORITY.flow_priority)

    def test_unconfigured_destination_port_uses_fallback_forwarding(self):
        self.assertIsNone(classify_tcp_destination_port(8080))


if __name__ == "__main__":
    unittest.main()
