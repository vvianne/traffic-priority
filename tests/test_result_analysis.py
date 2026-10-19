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
