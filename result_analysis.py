"""Analysis and SVG plotting for TrafficPriority experiment CSV files."""

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from html import escape
from math import ceil
from pathlib import Path
from statistics import mean, stdev


LOAD_ORDER = ("light", "near_capacity", "congested")
SCENARIO_ORDER = ("without_qos", "with_qos")
CLASS_ORDER = ("high_priority", "best_effort")
REQUIRED_COLUMNS = {
    "experiment_id",
    "run_id",
    "timestamp_utc",
    "scenario",
    "load_level",
    "policy",
    "traffic_class",
    "offered_mbps",
    "throughput_mbps",
    "link_capacity_mbps",
    "egress_mbps",
    "congestion_detected",
    "client_start_skew_ms",
    "flow_packet_delta",
    "queue_packet_delta",
}
RUN_FIELDS = (
    "experiment_id",
    "run_id",
    "timestamp_utc",
    "scenario",
    "load_level",
    "policy",
    "offered_total_mbps",
    "high_priority_mbps",
    "best_effort_mbps",
    "total_throughput_mbps",
    "link_capacity_mbps",
    "total_capacity_pct",
    "total_within_capacity",
    "egress_mbps",
    "egress_capacity_pct",
    "congestion_detected",
    "client_start_skew_ms",
    "high_flow_packets",
    "best_effort_flow_packets",
    "high_queue_packets",
    "best_effort_queue_packets",
)
SUMMARY_FIELDS = (
    "scenario",
    "load_level",
    "metric",
    "sample_count",
    "mean_mbps",
    "stddev_mbps",
    "min_mbps",
    "max_mbps",
    "link_capacity_mbps",
    "mean_capacity_pct",
)


def number(row, field):
    value = row.get(field, "")
    return float(value) if value not in (None, "") else None


def integer_or_blank(row, field):
    value = row.get(field, "")
    return int(value) if value not in (None, "") else ""


def validate_rows(rows, fieldnames):
    missing = sorted(REQUIRED_COLUMNS.difference(fieldnames or ()))
    if missing:
        raise ValueError(f"Raw CSV is missing columns: {', '.join(missing)}")
    if not rows:
        raise ValueError("Raw CSV contains no measurements")

    grouped = defaultdict(list)
    for row in rows:
        if row["scenario"] not in SCENARIO_ORDER:
            raise ValueError(f"Unknown scenario: {row['scenario']}")
        if row["load_level"] not in LOAD_ORDER:
            raise ValueError(f"Unknown load level: {row['load_level']}")
        if row["traffic_class"] not in CLASS_ORDER:
            raise ValueError(f"Unknown traffic class: {row['traffic_class']}")
        grouped[row["run_id"]].append(row)

    for run_id, run_rows in grouped.items():
        classes = [row["traffic_class"] for row in run_rows]
        if sorted(classes) != sorted(CLASS_ORDER):
            raise ValueError(
                f"Run {run_id} must contain exactly one row for each traffic class"
            )
        contexts = {
            (row["experiment_id"], row["scenario"], row["load_level"])
            for row in run_rows
        }
        if len(contexts) != 1:
            raise ValueError(f"Run {run_id} contains inconsistent scenario metadata")

    observed = {
        (row["scenario"], row["load_level"], row["traffic_class"])
        for row in rows
    }
    expected = {
        (scenario, load_level, traffic_class)
        for scenario in SCENARIO_ORDER
        for load_level in LOAD_ORDER
        for traffic_class in CLASS_ORDER
    }
    missing_conditions = sorted(expected.difference(observed))
    if missing_conditions:
        raise ValueError(f"Raw CSV is missing conditions: {missing_conditions}")


def build_run_summaries(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["run_id"]].append(row)

    summaries = []
    for run_id, run_rows in grouped.items():
        by_class = {row["traffic_class"]: row for row in run_rows}
        first = run_rows[0]
        high = number(by_class["high_priority"], "throughput_mbps")
        best = number(by_class["best_effort"], "throughput_mbps")
        total = high + best
        capacity = number(first, "link_capacity_mbps")
        egress = number(first, "egress_mbps")
        summaries.append(
            {
                "experiment_id": first["experiment_id"],
                "run_id": run_id,
                "timestamp_utc": first["timestamp_utc"],
                "scenario": first["scenario"],
                "load_level": first["load_level"],
                "policy": first["policy"],
                "offered_total_mbps": sum(
                    number(row, "offered_mbps") for row in run_rows
                ),
                "high_priority_mbps": high,
                "best_effort_mbps": best,
                "total_throughput_mbps": total,
                "link_capacity_mbps": capacity,
                "total_capacity_pct": total / capacity * 100,
                "total_within_capacity": total <= capacity * 1.05,
                "egress_mbps": egress,
                "egress_capacity_pct": egress / capacity * 100,
                "congestion_detected": first["congestion_detected"].lower()
                == "true",
                "client_start_skew_ms": number(first, "client_start_skew_ms"),
                "high_flow_packets": integer_or_blank(
                    by_class["high_priority"], "flow_packet_delta"
                ),
                "best_effort_flow_packets": integer_or_blank(
                    by_class["best_effort"], "flow_packet_delta"
                ),
                "high_queue_packets": integer_or_blank(
                    by_class["high_priority"], "queue_packet_delta"
                ),
                "best_effort_queue_packets": integer_or_blank(
                    by_class["best_effort"], "queue_packet_delta"
                ),
            }
        )

    scenario_index = {name: index for index, name in enumerate(SCENARIO_ORDER)}
    load_index = {name: index for index, name in enumerate(LOAD_ORDER)}
    return sorted(
        summaries,
        key=lambda row: (
            load_index[row["load_level"]],
            scenario_index[row["scenario"]],
            row["run_id"],
        ),
    )


def metric_summary(scenario, load_level, metric, values, capacity):
    return {
        "scenario": scenario,
        "load_level": load_level,
        "metric": metric,
        "sample_count": len(values),
        "mean_mbps": mean(values),
        "stddev_mbps": stdev(values) if len(values) > 1 else 0.0,
        "min_mbps": min(values),
        "max_mbps": max(values),
        "link_capacity_mbps": capacity,
        "mean_capacity_pct": mean(values) / capacity * 100,
    }


def build_aggregate_summaries(rows, run_summaries):
    aggregates = []
    for load_level in LOAD_ORDER:
        for scenario in SCENARIO_ORDER:
            selected_rows = [
                row
                for row in rows
                if row["load_level"] == load_level and row["scenario"] == scenario
            ]
            selected_runs = [
                row
                for row in run_summaries
                if row["load_level"] == load_level and row["scenario"] == scenario
            ]
            if not selected_rows or not selected_runs:
                continue
            capacity = number(selected_rows[0], "link_capacity_mbps")
            for traffic_class in CLASS_ORDER:
                values = [
                    number(row, "throughput_mbps")
                    for row in selected_rows
                    if row["traffic_class"] == traffic_class
                ]
                aggregates.append(
                    metric_summary(
                        scenario,
                        load_level,
                        traffic_class,
                        values,
                        capacity,
                    )
                )
            aggregates.append(
                metric_summary(
                    scenario,
                    load_level,
                    "total",
                    [row["total_throughput_mbps"] for row in selected_runs],
                    capacity,
                )
            )
            aggregates.append(
                metric_summary(
                    scenario,
                    load_level,
                    "egress_total",
                    [row["egress_mbps"] for row in selected_runs],
                    capacity,
                )
            )
    return aggregates


def observations(run_summaries, aggregates):
    notes = []
    samples = {row["sample_count"] for row in aggregates}
    if min(samples) < 2:
        notes.append(
            "At least one condition has only one sample, so its variability "
            "estimate is not meaningful."
        )

    excessive_totals = [
        row for row in run_summaries if not row["total_within_capacity"]
    ]
    if excessive_totals:
        notes.append(
            f"{len(excessive_totals)} run(s) reported summed client throughput "
            "more than 5% above link capacity. Treat client throughput as an "
            "application-side estimate and use egress counters for the capacity check."
        )

    unsaturated = [
        row
        for row in run_summaries
        if row["load_level"] == "congested" and not row["congestion_detected"]
    ]
    if unsaturated:
        notes.append(
            f"{len(unsaturated)} congested-load run(s) did not reach the measured "
            "80% egress-utilization threshold; conclusions for those runs are weak."
        )

    skewed = [row for row in run_summaries if row["client_start_skew_ms"] > 100]
    if skewed:
        notes.append(
            f"{len(skewed)} run(s) launched clients more than 100 ms apart."
        )

    lookup = {
        (row["scenario"], row["load_level"], row["metric"]): row
        for row in aggregates
    }
    required = [
        (scenario, "congested", traffic_class)
        for scenario in SCENARIO_ORDER
        for traffic_class in CLASS_ORDER
    ]
    if all(key in lookup for key in required):
        high_delta = (
            lookup[("with_qos", "congested", "high_priority")]["mean_mbps"]
            - lookup[("without_qos", "congested", "high_priority")]["mean_mbps"]
        )
        best_delta = (
            lookup[("with_qos", "congested", "best_effort")]["mean_mbps"]
            - lookup[("without_qos", "congested", "best_effort")]["mean_mbps"]
        )
        if high_delta > 0 and best_delta < 0:
            notes.append(
                "Under measured congestion, QoS shifted throughput toward the "
                f"high-priority class ({high_delta:+.3f} Mbps) at the expense of "
                f"best effort ({best_delta:+.3f} Mbps). This is allocation, not "
                "additional physical bandwidth."
            )
        else:
            notes.append(
                "The congested-load means did not show the expected combination "
                "of higher high-priority throughput and lower best-effort throughput; "
                "inspect run variability and queue counters before claiming a QoS benefit."
            )

    for load_level in ("light", "near_capacity"):
        load_keys = [
            (scenario, load_level, traffic_class)
            for scenario in SCENARIO_ORDER
            for traffic_class in CLASS_ORDER
        ]
        if not all(key in lookup for key in load_keys):
            continue
        class_change = max(
            abs(
                lookup[("with_qos", load_level, traffic_class)]["mean_mbps"]
                - lookup[("without_qos", load_level, traffic_class)]["mean_mbps"]
            )
            for traffic_class in CLASS_ORDER
        )
        capacity = lookup[("with_qos", load_level, "high_priority")][
            "link_capacity_mbps"
        ]
        if class_change <= capacity * 0.1:
            notes.append(
                f"At {load_level.replace('_', ' ')} load, corresponding class "
                "means differed by no more than 10% of link capacity between "
                "modes; QoS made little measurable difference in that condition."
            )

    notes.append(
        "Results apply to this controlled TCP/port-based lab and do not establish "
        "end-to-end application QoE or behavior on other hosts and kernels."
    )
    return notes


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def format_number(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6f}"
    return value


def render_svg(aggregates, output_path, source_name):
    """Render a three-panel grouped bar chart with one-standard-deviation bars."""
    lookup = {
        (row["load_level"], row["scenario"], row["metric"]): row
        for row in aggregates
    }
    values = [
        row["mean_mbps"] + row["stddev_mbps"]
        for row in aggregates
        if row["metric"] in CLASS_ORDER
    ]
    capacities = [row["link_capacity_mbps"] for row in aggregates]
    y_max = float(ceil(max(values + capacities + [1.0]) * 1.15))
    width, height = 1200, 650
    top, bottom = 105, 520
    panel_width = 350
    panel_gap = 35
    left = 75
    plot_height = bottom - top
    colors = {"high_priority": "#d95f02", "best_effort": "#1b9e77"}

    def y(value):
        return bottom - value / y_max * plot_height

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" '
        'viewBox="0 0 1200 650">',
        '<rect width="1200" height="650" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#222}.axis{stroke:#333;'
        'stroke-width:1}.grid{stroke:#ddd;stroke-width:1}.error{stroke:#222;'
        'stroke-width:2}.capacity{stroke:#666;stroke-width:1.5;stroke-dasharray:6 4}</style>',
        '<text x="600" y="32" text-anchor="middle" font-size="22" '
        'font-weight="bold">Traffic-class throughput by load and QoS mode</text>',
        '<text x="600" y="58" text-anchor="middle" font-size="13">'
        f'Mean throughput; error bars show ±1 SD. Source: {escape(source_name)}</text>',
        '<rect x="420" y="70" width="16" height="16" fill="#d95f02"/>',
        '<text x="443" y="83" font-size="13">High priority</text>',
        '<rect x="555" y="70" width="16" height="16" fill="#1b9e77"/>',
        '<text x="578" y="83" font-size="13">Best effort</text>',
        '<text x="20" y="315" transform="rotate(-90 20 315)" '
        'text-anchor="middle" font-size="14">Throughput (Mbps)</text>',
    ]

    tick_max = int(y_max)
    for panel_index, load_level in enumerate(LOAD_ORDER):
        panel_left = left + panel_index * (panel_width + panel_gap)
        panel_right = panel_left + panel_width
        parts.append(
            f'<text x="{(panel_left + panel_right) / 2}" y="100" '
            f'text-anchor="middle" font-size="16" font-weight="bold">'
            f'{escape(load_level.replace("_", " ").title())}</text>'
        )
        for tick in range(tick_max + 1):
            tick_y = y(tick)
            parts.append(
                f'<line class="grid" x1="{panel_left}" y1="{tick_y:.2f}" '
                f'x2="{panel_right}" y2="{tick_y:.2f}"/>'
            )
            if panel_index == 0:
                parts.append(
                    f'<text x="{panel_left - 8}" y="{tick_y + 4:.2f}" '
                    f'text-anchor="end" font-size="11">{tick}</text>'
                )
        parts.append(
            f'<line class="axis" x1="{panel_left}" y1="{bottom}" '
            f'x2="{panel_right}" y2="{bottom}"/>'
        )
        capacity = next(
            row["link_capacity_mbps"]
            for row in aggregates
            if row["load_level"] == load_level
        )
        parts.append(
            f'<line class="capacity" x1="{panel_left}" y1="{y(capacity):.2f}" '
            f'x2="{panel_right}" y2="{y(capacity):.2f}"/>'
        )

        for scenario_index, scenario in enumerate(SCENARIO_ORDER):
            group_center = panel_left + 95 + scenario_index * 165
            for class_index, traffic_class in enumerate(CLASS_ORDER):
                row = lookup.get((load_level, scenario, traffic_class))
                if row is None:
                    continue
                bar_x = group_center - 38 + class_index * 42
                bar_width = 36
                bar_y = y(row["mean_mbps"])
                bar_height = bottom - bar_y
                parts.append(
                    f'<rect x="{bar_x}" y="{bar_y:.2f}" width="{bar_width}" '
                    f'height="{bar_height:.2f}" fill="{colors[traffic_class]}"/>'
                )
                error_top = y(row["mean_mbps"] + row["stddev_mbps"])
                error_bottom = y(max(0, row["mean_mbps"] - row["stddev_mbps"]))
                center = bar_x + bar_width / 2
                parts.extend(
                    (
                        f'<line class="error" x1="{center}" y1="{error_top:.2f}" '
                        f'x2="{center}" y2="{error_bottom:.2f}"/>',
                        f'<line class="error" x1="{center - 5}" y1="{error_top:.2f}" '
                        f'x2="{center + 5}" y2="{error_top:.2f}"/>',
                        f'<line class="error" x1="{center - 5}" y1="{error_bottom:.2f}" '
                        f'x2="{center + 5}" y2="{error_bottom:.2f}"/>',
                        f'<text x="{center}" y="{bar_y - 7:.2f}" text-anchor="middle" '
                        f'font-size="10">{row["mean_mbps"]:.2f}</text>',
                    )
                )
            label = "Without QoS" if scenario == "without_qos" else "With QoS"
            parts.append(
                f'<text x="{group_center}" y="545" text-anchor="middle" '
                f'font-size="12">{label}</text>'
            )

    parts.extend(
        (
            '<text x="600" y="590" text-anchor="middle" font-size="12">'
            'Dashed line: configured 5 Mbps bottleneck capacity</text>',
            '<text x="600" y="615" text-anchor="middle" font-size="11">'
            'QoS reallocates constrained capacity; it does not increase link capacity.'
            '</text>',
            '</svg>',
        )
    )
    Path(output_path).write_text("\n".join(parts) + "\n", encoding="utf-8")


def render_markdown(raw_path, run_summaries, aggregates, notes, plot_path):
    generated = datetime.now(timezone.utc).isoformat()
    experiment_ids = sorted({row["experiment_id"] for row in run_summaries})
    lines = [
        "# TrafficPriority experiment analysis",
        "",
        f"- Generated: `{generated}`",
        f"- Raw source: `{Path(raw_path).name}`",
        f"- Raw SHA-256: `{sha256_file(raw_path)}`",
        f"- Experiment IDs: `{', '.join(experiment_ids)}`",
        f"- Complete runs: `{len(run_summaries)}`",
        f"- Plot: `{Path(plot_path).name}`",
        "",
        f"![Traffic-class throughput comparison](../../plots/{Path(plot_path).name})",
        "",
        "## Per-run measurements",
        "",
        "| Run | Scenario | Load | High Mbps | Best-effort Mbps | Total Mbps | "
        "Capacity Mbps | Egress Mbps | Congested |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in run_summaries:
        lines.append(
            f"| `{row['run_id']}` | {row['scenario']} | {row['load_level']} | "
            f"{row['high_priority_mbps']:.3f} | {row['best_effort_mbps']:.3f} | "
            f"{row['total_throughput_mbps']:.3f} | "
            f"{row['link_capacity_mbps']:.3f} | {row['egress_mbps']:.3f} | "
            f"{str(row['congestion_detected']).lower()} |"
        )

    lines.extend(
        (
            "",
            "## Aggregate comparison",
            "",
            "| Scenario | Load | Metric | N | Mean Mbps | SD Mbps | Min | Max | "
            "Mean/capacity |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        )
    )
    for row in aggregates:
        lines.append(
            f"| {row['scenario']} | {row['load_level']} | {row['metric']} | "
            f"{row['sample_count']} | {row['mean_mbps']:.3f} | "
            f"{row['stddev_mbps']:.3f} | {row['min_mbps']:.3f} | "
            f"{row['max_mbps']:.3f} | {row['mean_capacity_pct']:.1f}% |"
        )

    lines.extend(("", "## Interpretation and limitations", ""))
    lines.extend(f"- {note}" for note in notes)
    lines.extend(
        (
            "",
            "The plot and tables are derived entirely from the raw CSV named above. "
            "Regenerate them with `traffic-priority analyze` after collecting new data.",
            "",
        )
    )
    return "\n".join(lines)
