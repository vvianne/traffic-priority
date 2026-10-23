import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from extended_analysis import METRICS, validate_extended, summarize
from result_analysis import validate_rows, sha256_file


def fixture_rows():
    """Synthetic unit-test input only; never published as experiment evidence."""
    rows = []
    for scenario in ("without_qos", "with_qos"):
        for load in ("light", "near_capacity", "congested"):
            for repetition in (1, 2):
                for name, protocol, port in (("high_priority", "UDP", 5001),
                                              ("best_effort", "TCP", 5002)):
                    row = dict(
                        experiment_id="synthetic-test", run_id=f"{scenario}-{load}-{repetition}",
                        timestamp_utc="2026-10-23T00:00:00+00:00", scenario=scenario,
                        load_level=load, policy=scenario, traffic_class=name, protocol=protocol,
                        destination_port=str(port), offered_mbps="5", throughput_mbps="6",
                        sender_throughput_mbps="6", sender_measurement_valid="true",
                        sender_measurement_error="", receiver_throughput_mbps=str(repetition),
                        receiver_measurement_valid="true", receiver_measurement_error="",
                        receiver_interval_start_s="0", receiver_interval_end_s="10",
                        receiver_transferred_bytes="1250000", link_capacity_mbps="5",
                        egress_mbps="4.9", bottleneck_utilization_pct="98",
                        congestion_detected="true", client_start_skew_ms="1",
                        flow_packet_delta="20", queue_packet_delta="10",
                        probe_valid="true", probe_error="", rtt_sample_count="20",
                        probe_sent="20", probe_received="20", probe_loss_pct="0",
                        rtt_min_ms="1", rtt_avg_ms=str(repetition + 1), rtt_max_ms="5",
                        rtt_p95_ms="4", probe_start_offset_s="0.01",
                        probe_end_offset_s="10", wall_duration_s="11",
                        udp_metrics_valid="true" if protocol == "UDP" else "false",
                        udp_jitter_ms="0.5" if protocol == "UDP" else "",
                        udp_lost_datagrams="10" if protocol == "UDP" else "",
                        udp_total_datagrams="1000" if protocol == "UDP" else "",
                        udp_loss_pct="1" if protocol == "UDP" else "",
                    )
                    rows.append(row)
    return rows


class ExtendedAnalysisTests(unittest.TestCase):
    def test_aggregation_uses_independent_runs_and_separate_sources(self):
        rows = fixture_rows()
        validate_rows(rows, rows[0].keys())
        validate_extended(rows)
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "synthetic.csv"
            raw.write_text("synthetic fixture", encoding="utf-8")
            summary = summarize(rows, raw)
        receiver = next(row for row in summary if row["metric"] == "receiver_throughput_mbps")
        sender = next(row for row in summary if row["metric"] == "sender_throughput_mbps")
        switch = next(row for row in summary if row["metric"] == "egress_mbps")
        self.assertEqual(1.5, receiver["mean"])
        self.assertAlmostEqual(0.70710678, receiver["sample_stddev"])
        self.assertEqual(6, sender["mean"])
        self.assertEqual(2, switch["sample_count"])
        self.assertEqual("all", switch["traffic_class"])

    def test_absent_rtt_is_excluded_with_reason_not_zero(self):
        rows = fixture_rows()
        rows[0].update(probe_received="0", rtt_sample_count="0", probe_loss_pct="100",
                       rtt_min_ms="", rtt_avg_ms="", rtt_max_ms="", rtt_p95_ms="")
        validate_extended(rows)
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "synthetic.csv"
            raw.write_text("synthetic fixture")
            summary = summarize(rows, raw)
            result = next(row for row in summary if row["metric"] == "rtt_avg_ms"
                          and row["scenario"] == rows[0]["scenario"]
                          and row["load_level"] == rows[0]["load_level"]
                          and row["traffic_class"] == rows[0]["traffic_class"])
        self.assertEqual(1, result["sample_count"])
        self.assertEqual(3, result["mean"])
        self.assertEqual("", result["sample_stddev"])
        self.assertIn("no probe replies", result["unavailable_reasons"])

    def test_rejects_bad_values_and_protocol_mixing(self):
        for key, value in (("sender_throughput_mbps", "nan"), ("rtt_avg_ms", "-1"),
                           ("bottleneck_utilization_pct", "50"), ("protocol", "TCP")):
            rows = fixture_rows()
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_extended(rows)

    def test_missing_probe_requires_diagnostic_and_blank_values(self):
        rows = fixture_rows()
        rows[0]["probe_valid"] = "false"
        with self.assertRaisesRegex(ValueError, "diagnostic"):
            validate_extended(rows)
        rows[0]["probe_error"] = "probe failed"
        with self.assertRaisesRegex(ValueError, "Unavailable metric"):
            validate_extended(rows)

    def test_incomplete_matrix_is_rejected(self):
        rows = [row for row in fixture_rows() if row["load_level"] != "light"]
        with self.assertRaisesRegex(ValueError, "missing conditions"):
            validate_rows(rows, rows[0].keys())

    def test_cli_writes_traceable_tables_and_valid_svg_for_every_metric(self):
        rows = fixture_rows()
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            raw = directory / "synthetic-fixture.csv"
            with raw.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            subprocess.run([sys.executable, "-B", str(root / "scripts/analyze_results.py"),
                            str(raw), "--output-root", str(directory / "output")],
                           check=True, capture_output=True, text=True)
            summary_path = directory / "output/analysis/synthetic-fixture/extended-summary.csv"
            with summary_path.open(encoding="utf-8") as source:
                summaries = list(csv.DictReader(source))
            self.assertTrue(all(row["raw_sha256"] == sha256_file(raw) for row in summaries))
            for metric in METRICS:
                plot = directory / "output/plots" / f"synthetic-fixture-{metric}.svg"
                ET.parse(plot)
                self.assertIn(sha256_file(raw), plot.read_text(encoding="utf-8"))
            unavailable = directory / "output/plots/synthetic-fixture-udp_jitter_ms.svg"
            self.assertIn("Unavailable (N=0)", unavailable.read_text(encoding="utf-8"))
