import json
import unittest
from unittest.mock import patch

from ovs_qos import cleanup, queue_policy, setup, verify_kernel, verify_flow_actions
from policy_config import load_config


class OvsQoSTests(unittest.TestCase):
    def test_flow_queue_selection(self):
        verify_flow_actions("tcp actions=set_queue:1,output:3", {0, 1}, 3, True)
        verify_flow_actions("tcp actions=output:3", {0}, 3, False)
        with self.assertRaisesRegex(RuntimeError, "missing or invalid"):
            verify_flow_actions("tcp actions=output:3", {0, 1}, 3, True)
        with self.assertRaisesRegex(RuntimeError, "unexpectedly"):
            verify_flow_actions("tcp actions=set_queue:1,output:3", {0}, 3, False)

    def test_modes_share_parent(self):
        config = load_config()
        self.assertEqual({0: (5000000, 5000000)}, queue_policy(config, False))
        self.assertEqual({0: (1000000, 5000000), 1: (3000000, 5000000)},
                         queue_policy(config, True))

    def test_kernel_rates(self):
        classes = json.dumps([
            {"handle": "1:fffe", "root": True,
             "options": {"rate": 625000, "ceil": 625000}},
            {"handle": "1:1", "options": {"rate": 625000, "ceil": 625000}},
        ])
        verify_kernel('[{"kind":"htb","root":true}]', classes,
                      5000000, {0: (5000000, 5000000)})
        with self.assertRaisesRegex(RuntimeError, "HTB root"):
            verify_kernel('[{"kind":"tbf","root":true}]', classes, 5000000, {})
        with self.assertRaisesRegex(RuntimeError, "parent rate"):
            verify_kernel('[{"kind":"htb","root":true}]', classes, 1000000, {})
        with self.assertRaisesRegex(RuntimeError, "queue rates"):
            verify_kernel('[{"kind":"htb","root":true}]', classes,
                          5000000, {0: (1000000, 5000000)})

    @patch("ovs_qos.scalar", side_effect=["foreign-qos", "another-project"])
    @patch("ovs_qos.ovs", return_value="s1-eth3")
    def test_cleanup_refuses_foreign_policy(self, ovs, scalar):
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            cleanup("s1-eth3")
        self.assertEqual(1, ovs.call_count)

    @patch("ovs_qos.time.sleep")
    @patch("ovs_qos.verify", side_effect=RuntimeError("kernel mismatch"))
    @patch("ovs_qos.command", return_value='[{"kind":"noqueue","root":true}]')
    @patch("ovs_qos.cleanup")
    @patch("ovs_qos.ovs", return_value="s1")
    def test_failed_realization_cleans_up(self, ovs, cleanup, command, verify, sleep):
        with self.assertRaisesRegex(RuntimeError, "kernel mismatch"):
            setup(load_config(), False)
        self.assertEqual(2, cleanup.call_count)
        self.assertIn("queues:0=@q0", ovs.call_args.args)
        self.assertNotIn("queues:1=@q1", ovs.call_args.args)
