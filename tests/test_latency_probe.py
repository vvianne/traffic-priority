from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from latency_probe import parse_ping, start_probes, collect_probes
from scripts.run_experiments import run_clients


def ping_output(samples, sent=None):
    sent = len(samples) if sent is None else sent
    replies = "\n".join(f"64 bytes from 10.0.0.3: icmp_seq={i} ttl=64 time={value} ms"
                        for i, value in enumerate(samples, 1))
    loss = 100 * (sent - len(samples)) / sent
    return replies + f"\n{sent} packets transmitted, {len(samples)} received, {loss}% packet loss\n"


class LatencyTests(unittest.TestCase):
    def test_rtt_statistics_and_nearest_rank_percentile(self):
        result = parse_ping(ping_output(list(range(1, 21))))
        self.assertEqual(1, result["rtt_min_ms"])
        self.assertEqual(10.5, result["rtt_avg_ms"])
        self.assertEqual(20, result["rtt_max_ms"])
        self.assertEqual(19, result["rtt_p95_ms"])

    def test_loss_and_insufficient_percentile(self):
        result = parse_ping(ping_output([2, 4], sent=4))
        self.assertEqual(50, result["probe_loss_pct"])
        self.assertEqual("", result["rtt_p95_ms"])
        self.assertEqual(2, result["rtt_sample_count"])

    def test_total_loss_is_valid_without_fabricated_rtt(self):
        result = parse_ping(ping_output([], sent=10))
        self.assertEqual(100, result["probe_loss_pct"])
        self.assertEqual("true", result["probe_valid"])
        self.assertEqual("", result["rtt_avg_ms"])

    def test_rejects_missing_summary_or_truncated_samples(self):
        for output in ("ping: network unavailable", ping_output([2]).replace("1 received", "2 received")):
            with self.subTest(output=output), self.assertRaises(ValueError):
                parse_ping(output)

    def test_probes_begin_after_clients_launch_and_before_wait(self):
        events = []
        net = Mock()
        process = Mock(returncode=0)
        def launch(*args, **kwargs):
            events.append("client")
            return process
        def wait(**kwargs):
            events.append("wait")
            return "", ""
        net.get.return_value.popen.side_effect = launch
        process.communicate.side_effect = wait
        run_clients(net, "1000000", 10,
                    (("high_priority", "h1", 5001, 1, "tcp"),
                     ("best_effort", "h2", 5002, 0, "tcp")),
                    on_started=lambda: events.append("probes"))
        self.assertEqual(["client", "client", "probes", "wait", "wait"], events)

    def test_probe_command_is_bounded_and_uses_numeric_c_locale(self):
        net = Mock()
        start_probes(net, (("high_priority", "h1", 5001, 1, "tcp"),), 10)
        call = net.get.return_value.popen.call_args
        self.assertIn("-D", call.args[0])
        self.assertEqual("10", call.args[0][call.args[0].index("-w") + 1])
        self.assertEqual("C", call.kwargs["env"]["LC_ALL"])

    def test_bad_probe_output_is_preserved_and_marked_invalid(self):
        process = Mock(returncode=2)
        process.poll.return_value = 2
        process.communicate.return_value = ("", "ping failed")
        with tempfile.TemporaryDirectory() as directory:
            rows = collect_probes({"high_priority": process}, Path(directory), "run-1")
            row = rows["high_priority"]
            self.assertEqual("false", row["probe_valid"])
            self.assertEqual("", row["rtt_avg_ms"])
            self.assertIn("ping failed", (Path(directory) / row["probe_output"]).read_text())
