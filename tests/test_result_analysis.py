import tempfile
from pathlib import Path
import unittest

from result_analysis import (
    CLASS_ORDER,
    LOAD_ORDER,
    REQUIRED_COLUMNS,
    SCENARIO_ORDER,
    build_aggregate_summaries,
    build_run_summaries,
    observations,
    render_svg,
    validate_rows,
    validate_reproducibility,
)


def sample_rows():
    rows = []
    base_rates = {
        "light": {"high_priority": 1.0, "best_effort": 1.0},
        "near_capacity": {"high_priority": 2.5, "best_effort": 2.4},
        "congested": {"high_priority": 2.5, "best_effort": 2.4},
    }
    for scenario in SCENARIO_ORDER:
        for load_level in LOAD_ORDER:
            for repetition in (1, 2):
                run_id = f"{scenario}-{load_level}-r{repetition}"
                for traffic_class in CLASS_ORDER:
                    throughput = base_rates[load_level][traffic_class]
                    if scenario == "with_qos" and load_level == "congested":
                        throughput = 3.6 if traffic_class == "high_priority" else 1.3
                    throughput += 0.1 * (repetition - 1)
                    rows.append(
                        {
                            "experiment_id": "experiment-test",
                            "run_id": run_id,
                            "timestamp_utc": "2026-10-19T00:00:00+00:00",
                            "scenario": scenario,
                            "load_level": load_level,
                            "policy": scenario,
                            "traffic_class": traffic_class,
                            "offered_mbps": "5" if load_level == "congested" else "1",
                            "throughput_mbps": str(throughput),
                            "link_capacity_mbps": "5",
                            "egress_mbps": "4.9",
                            "congestion_detected": (
                                "true" if load_level == "congested" else "false"
                            ),
                            "client_start_skew_ms": "2.5",
                            "flow_packet_delta": "100",
                            "queue_packet_delta": (
                                "90" if scenario == "with_qos" else ""
                            ),
                        }
                    )
    return rows


class ResultAnalysisTests(unittest.TestCase):
    def reproducible_rows(self):
        rows = sample_rows()
        for row in rows:
            row.update({
                "expected_repetitions": "2", "repetition": row["run_id"][-1],
                "duration_s": "10", "warmup_s": "2", "scenario_order": "counterbalanced",
                "order_seed": "42", "session_index": "1", "warmup_wall_s": "3",
                "environment_json": "{}", "effective_config_json": "{}",
                "config_sha256": "abc", "measurement_end_utc": "2026-10-19T00:00:11+00:00",
                "wall_duration_s": "11", "egress_window_s": "11.1",
            })
        return rows

    def test_reproducible_dataset_is_complete(self):
        rows = self.reproducible_rows()
        validate_reproducibility(rows)
        validate_rows(rows, rows[0].keys())

    def test_rejects_truncated_repetitions(self):
        rows = [row for row in self.reproducible_rows() if not row["run_id"].endswith("r2")]
        with self.assertRaisesRegex(ValueError, "Incomplete repetition"):
            validate_reproducibility(rows)

    def test_rejects_conflicting_timing_within_run(self):
        rows = self.reproducible_rows()
        rows[0]["egress_window_s"] = "12"
        with self.assertRaisesRegex(ValueError, "per-run"):
            validate_reproducibility(rows)

    def test_rejects_nonfinite_timing(self):
        rows = self.reproducible_rows()
        rows[0]["wall_duration_s"] = "nan"
        with self.assertRaisesRegex(ValueError, "timing"):
            validate_reproducibility(rows)

    def test_rejects_udp_rows_without_loss_and_jitter(self):
        rows = sample_rows()
        for row in rows:
            row.update({
                "protocol": "UDP", "receiver_throughput_mbps": "1",
                "receiver_measurement_valid": "true", "receiver_measurement_error": "",
                "receiver_interval_start_s": "0", "receiver_interval_end_s": "10",
                "receiver_transferred_bytes": "1250000",
            })
        with self.assertRaisesRegex(ValueError, "UDP metrics"):
            validate_rows(rows, rows[0].keys())

    def test_builds_per_run_and_statistical_summaries(self):
        rows = sample_rows()
        validate_rows(rows, REQUIRED_COLUMNS)
        runs = build_run_summaries(rows)
        summaries = build_aggregate_summaries(rows, runs)

        self.assertEqual(12, len(runs))
        self.assertEqual(24, len(summaries))
        congested_high = next(
            row
            for row in summaries
            if row["scenario"] == "with_qos"
            and row["load_level"] == "congested"
            and row["metric"] == "high_priority"
        )
        self.assertAlmostEqual(3.65, congested_high["mean_mbps"])
        self.assertGreater(congested_high["stddev_mbps"], 0)

    def test_explains_congested_tradeoff(self):
        rows = sample_rows()
        runs = build_run_summaries(rows)
        summaries = build_aggregate_summaries(rows, runs)
        notes = observations(runs, summaries)
        self.assertTrue(any("shifted throughput" in note for note in notes))
        self.assertTrue(any("not additional physical bandwidth" in note for note in notes))

    def test_v3_analysis_prefers_valid_receiver_throughput(self):
        rows = sample_rows()
        for row in rows:
            row["sender_throughput_mbps"] = "99"
            row["throughput_mbps"] = "99"
            row["receiver_throughput_mbps"] = "1.25"
            row["receiver_measurement_valid"] = "true"
            row["receiver_measurement_error"] = ""
            row["receiver_interval_start_s"] = "0"
            row["receiver_interval_end_s"] = "10"
            row["receiver_transferred_bytes"] = "1000000"

        validate_rows(rows, rows[0].keys())
        runs = build_run_summaries(rows)

        self.assertEqual("receiver_reported", runs[0]["throughput_source"])
        self.assertEqual(1.25, runs[0]["high_priority_mbps"])
        self.assertEqual(1.25, runs[0]["best_effort_mbps"])

    def test_v3_analysis_rejects_missing_receiver_measurement(self):
        rows = sample_rows()
        for row in rows:
            row["receiver_throughput_mbps"] = "1.25"
            row["receiver_measurement_valid"] = "true"
            row["receiver_measurement_error"] = ""
            row["receiver_interval_start_s"] = "0"
            row["receiver_interval_end_s"] = "10"
            row["receiver_transferred_bytes"] = "1000000"
        rows[0]["receiver_throughput_mbps"] = ""
        rows[0]["receiver_measurement_valid"] = "false"
        rows[0]["receiver_measurement_error"] = "server output missing"

        with self.assertRaisesRegex(ValueError, "server output missing"):
            validate_rows(rows, rows[0].keys())

    def test_renders_labelled_svg_from_aggregates(self):
        rows = sample_rows()
        runs = build_run_summaries(rows)
        summaries = build_aggregate_summaries(rows, runs)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.svg"
            render_svg(summaries, output, "raw.csv")
            svg = output.read_text(encoding="utf-8")
        self.assertIn("Traffic-class throughput", svg)
        self.assertIn("High priority", svg)
        self.assertIn("Without QoS", svg)
        self.assertIn("configured 5 Mbps", svg)

    def test_rejects_incomplete_condition_matrix(self):
        rows = sample_rows()
        rows = [row for row in rows if row["load_level"] != "light"]
        with self.assertRaisesRegex(ValueError, "missing conditions"):
            validate_rows(rows, REQUIRED_COLUMNS)


if __name__ == "__main__":
    unittest.main()
