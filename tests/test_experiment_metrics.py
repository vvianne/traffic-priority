import unittest

from experiment_metrics import (
    parse_egress_counters,
    parse_flow_counters,
    parse_iperf_csv,
    parse_queue_counters,
)


class ExperimentMetricTests(unittest.TestCase):
    def test_parses_final_iperf_csv_throughput(self):
        output = (
            "20261019120000,10.0.0.1,40000,10.0.0.3,5001,3,"
            "0.0-10.0,5000000,4000000\n"
        )
        self.assertEqual(4.0, parse_iperf_csv(output))

    def test_sums_matching_flow_counters(self):
        output = "\n".join(
            (
                "n_packets=3, n_bytes=300, tcp,tp_dst=5001 actions=output:3",
                "n_packets=2, n_bytes=250, tcp,tp_dst=5001 actions=output:3",
                "n_packets=4, n_bytes=500, tcp,tp_dst=5002 actions=output:3",
            )
        )
        counters = parse_flow_counters(output, [5001, 5002])
        self.assertEqual({"packets": 5, "bytes": 550}, counters[5001])
        self.assertEqual({"packets": 4, "bytes": 500}, counters[5002])

    def test_parses_queue_and_egress_counters(self):
        queue_output = (
            "port 3 queue 0: bytes=1200, pkts=12, errors=0\n"
            "port 3 queue 1: bytes=3400, pkts=34, errors=0"
        )
        self.assertEqual(
            {"bytes": 3400, "packets": 34},
            parse_queue_counters(queue_output)[1],
        )
        self.assertEqual(
            {"packets": 46, "bytes": 4600},
            parse_egress_counters("tx pkts=46, bytes=4600, drop=0"),
        )


if __name__ == "__main__":
    unittest.main()
