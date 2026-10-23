from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from experiment_metrics import parse_iperf_csv_measurement, parse_flow_counters
from policy_config import load_config
from traffic_policy import transport_match_fields
from scripts.run_experiments import run_clients, start_servers, parse_measurement, measurement_columns


TCP_ROW = "20261023000000,10.0.0.1,40000,10.0.0.3,5001,3,0.0-10.0,1250000,1000000\n"
UDP_ROW = TCP_ROW.strip() + ",0.125,10,1000,1.000,0\n"


class UdpExperimentTests(unittest.TestCase):
    def test_receiver_reports_jitter_loss_and_received_rate(self):
        value = parse_iperf_csv_measurement(UDP_ROW, protocol="udp")
        self.assertEqual(1, value.throughput_mbps)
        self.assertEqual(0.125, value.jitter_ms)
        self.assertEqual(10, value.lost_datagrams)
        self.assertEqual(1000, value.total_datagrams)
        self.assertEqual(1, value.loss_pct)

    def test_sender_ignores_returned_receiver_report(self):
        value = parse_iperf_csv_measurement(TCP_ROW + UDP_ROW, protocol="udp", role="sender")
        self.assertEqual(1, value.throughput_mbps)
        self.assertIsNone(value.jitter_ms)

    def test_incomplete_receiver_report_is_unavailable(self):
        value, error = parse_measurement(TCP_ROW, "", "10.0.0.1", "10.0.0.3",
                                         5001, 10, protocol="udp")
        self.assertIsNone(value)
        self.assertTrue(error)
        self.assertEqual("", measurement_columns("receiver", value, error)["receiver_throughput_mbps"])

    def test_rejects_invalid_udp_metrics(self):
        for suffix in (",nan,10,1000,1,0", ",1,1001,1000,100,0", ",1,10,1000,80,0"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                parse_iperf_csv_measurement(TCP_ROW.strip() + suffix, protocol="udp")

    def test_same_port_classes_do_not_cross_protocols(self):
        config = load_config()
        high = config.traffic_class("high_priority")
        best = replace(config.traffic_class("best_effort"), protocol="udp", destination_port=5001)
        config = replace(config, traffic_classes=(high, best))
        self.assertEqual(high, config.classify("tcp", 5001))
        self.assertEqual(best, config.classify("udp", 5001))
        self.assertEqual({"ip_proto": 17, "udp_src": 1234, "udp_dst": 5001},
                         transport_match_fields("udp", 1234, 5001))
        self.assertEqual(6, transport_match_fields("tcp", 1234, 5001)["ip_proto"])

    def test_flow_counters_separate_protocols(self):
        output = "n_packets=2,n_bytes=100,tcp,tp_dst=5001\nn_packets=3,n_bytes=200,udp,tp_dst=5001"
        values = parse_flow_counters(output, [("tcp", 5001), ("udp", 5001)])
        self.assertEqual(100, values[("tcp", 5001)]["bytes"])
        self.assertEqual(200, values[("udp", 5001)]["bytes"])

    @patch("scripts.run_experiments.time.sleep")
    def test_client_and_server_commands_support_mixed_protocols(self, sleep):
        classes = (("high_priority", "h1", 5001, 1, "tcp"),
                   ("best_effort", "h2", 5002, 0, "udp"))
        receiver = Mock()
        start_servers(receiver, classes)
        commands = [call.args[0] for call in receiver.popen.call_args_list]
        self.assertNotIn("-u", commands[0])
        self.assertIn("-u", commands[1])
        net = Mock()
        process = net.get.return_value.popen.return_value
        process.communicate.return_value = (TCP_ROW, "")
        process.returncode = 0
        run_clients(net, "1000000", 10, classes)
        commands = [call.args[0] for call in net.get.return_value.popen.call_args_list]
        self.assertNotIn("-u", commands[0])
        self.assertIn("-u", commands[1])
