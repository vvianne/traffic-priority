"""Validated, unit-aware v3 metrics, summaries, and dependency-free SVG plots."""

from collections import defaultdict
from html import escape
from math import isfinite
from pathlib import Path
from statistics import mean, stdev

from result_analysis import sha256_file


METRICS = {
    "sender_throughput_mbps": ("Mbps", "sender"),
    "receiver_throughput_mbps": ("Mbps", "receiver"),
    "egress_mbps": ("Mbps", "switch"),
    "rtt_min_ms": ("ms", "ICMP"),
    "rtt_avg_ms": ("ms", "ICMP"),
    "rtt_max_ms": ("ms", "ICMP"),
    "rtt_p95_ms": ("ms", "ICMP"),
    "probe_loss_pct": ("%", "ICMP"),
    "udp_jitter_ms": ("ms", "UDP receiver"),
    "udp_loss_pct": ("%", "UDP receiver"),
    "bottleneck_utilization_pct": ("%", "switch"),
}
SUMMARY_FIELDS = (
    "scenario", "load_level", "traffic_class", "protocol", "metric", "unit", "source",
    "expected_count", "sample_count", "unavailable_count", "unavailable_reasons",
    "mean", "sample_stddev", "minimum", "maximum", "raw_source", "raw_sha256",
)


def numeric(row, key, minimum=0, maximum=None):
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Missing or invalid metric: " + key) from error
    if not isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError("Out-of-range metric: " + key)
    return value


def metric_value(row, metric):
    if metric.startswith("udp_") and row["protocol"].upper() != "UDP":
        return None, "not applicable: TCP"
    if metric.startswith("rtt_") or metric == "probe_loss_pct":
        if row.get("probe_valid") == "false":
            return None, row["probe_error"]
        if metric.startswith("rtt_") and int(row["rtt_sample_count"]) == 0:
            return None, "no probe replies"
        if metric == "rtt_p95_ms" and int(row["rtt_sample_count"]) < 20:
            return None, "fewer than 20 probe replies"
    if metric == "sender_throughput_mbps" and row.get("sender_measurement_valid") == "false":
        return None, row["sender_measurement_error"]
    return numeric(row, metric, maximum=100 if metric.endswith("loss_pct") else None), ""


def validate_extended(rows):
    """Validate optionality, protocol identity, and shared switch measurements."""
    protocols = defaultdict(set)
    endpoints = defaultdict(set)
    shared = {}
    if len({row["experiment_id"] for row in rows}) != 1:
        raise ValueError("Analyze one experiment at a time")
    if len({row["link_capacity_mbps"] for row in rows}) != 1:
        raise ValueError("Inconsistent experiment capacity")
    for row in rows:
        protocol = row.get("protocol", "").upper()
        if protocol not in {"TCP", "UDP"}:
            raise ValueError("Unknown transport protocol")
        protocols[row["traffic_class"]].add(protocol)
        endpoints[row["traffic_class"]].add(row.get("destination_port"))
        numeric(row, "offered_mbps")
        numeric(row, "client_start_skew_ms")
        if row.get("sender_measurement_valid") == "true":
            if abs(numeric(row, "throughput_mbps") - numeric(row, "sender_throughput_mbps")) > 0.000001:
                raise ValueError("Legacy sender alias disagrees with sender measurement")
        for prefix in ("sender_measurement", "probe"):
            if row.get(prefix + "_valid") not in {"true", "false"}:
                raise ValueError("Missing validity field: " + prefix)
            if row[prefix + "_valid"] == "false" and not row.get(prefix + "_error"):
                raise ValueError("Unavailable measurement requires a diagnostic")
        capacity = numeric(row, "link_capacity_mbps", minimum=0.000001)
        egress = numeric(row, "egress_mbps")
        utilization = numeric(row, "bottleneck_utilization_pct")
        if abs(utilization - egress / capacity * 100) > 0.02:
            raise ValueError("Utilization disagrees with measured egress")
        context = (capacity, egress, utilization)
        if shared.setdefault(row["run_id"], context) != context:
            raise ValueError("Conflicting switch measurements within run")
        if row["probe_valid"] == "true":
            sent = numeric(row, "probe_sent", minimum=1)
            received = numeric(row, "probe_received", maximum=sent)
            samples = numeric(row, "rtt_sample_count", maximum=received)
            if any(value != int(value) for value in (sent, received, samples)) or samples != received:
                raise ValueError("Inconsistent probe counts")
            if abs(numeric(row, "probe_loss_pct", maximum=100) - 100 * (sent - received) / sent) > 1.01:
                raise ValueError("Probe loss disagrees with counts")
            start = numeric(row, "probe_start_offset_s")
            end = numeric(row, "probe_end_offset_s")
            if end < start or end > numeric(row, "wall_duration_s") + 0.01:
                raise ValueError("Probe observation bounds lie outside measurement window")
            if samples:
                low, avg, high = (numeric(row, key) for key in ("rtt_min_ms", "rtt_avg_ms", "rtt_max_ms"))
                if not low <= avg <= high:
                    raise ValueError("Inconsistent RTT statistics")
                if samples >= 20 and not low <= numeric(row, "rtt_p95_ms") <= high:
                    raise ValueError("Inconsistent RTT percentile")
        for metric in METRICS:
            value, reason = metric_value(row, metric)
            if value is None and row.get(metric) not in (None, ""):
                raise ValueError("Unavailable metric contains a value: " + metric)
    if any(len(values) != 1 for values in protocols.values()):
        raise ValueError("Mixed protocols for the same traffic class; analyze experiments separately")
    if any(len(values) != 1 for values in endpoints.values()):
        raise ValueError("Inconsistent destination ports for traffic class")


def summarize(rows, raw_path):
    groups = defaultdict(list)
    for row in rows:
        for metric, (unit, source) in METRICS.items():
            # Switch metrics occur on both class rows; count once per run.
            if source == "switch" and row["traffic_class"] != "high_priority":
                continue
            key = (row["scenario"], row["load_level"],
                   "all" if source == "switch" else row["traffic_class"],
                   "all" if source == "switch" else row["protocol"].upper(), metric)
            groups[key].append(metric_value(row, metric))
    result = []
    digest = sha256_file(raw_path)
    for key, observations in sorted(groups.items()):
        values = [value for value, _ in observations if value is not None]
        unit, source = METRICS[key[-1]]
        result.append(dict(zip(SUMMARY_FIELDS[:5], key), unit=unit, source=source,
                           expected_count=len(observations), sample_count=len(values),
                           unavailable_count=len(observations) - len(values),
                           unavailable_reasons="; ".join(sorted({reason for _, reason in observations if reason})),
                           mean=mean(values) if values else "",
                           sample_stddev=stdev(values) if len(values) > 1 else "",
                           minimum=min(values) if values else "", maximum=max(values) if values else "",
                           raw_source=Path(raw_path).name, raw_sha256=digest))
    return result


def render_metric_svg(summaries, metric, output_path):
    selected = [row for row in summaries if row["metric"] == metric]
    unit = METRICS[metric][0]
    source = selected[0]
    height = 150 + len(selected) * 32
    maximum = max([float(row["mean"]) + (row["sample_stddev"] or 0)
                   for row in selected if row["sample_count"]] + [1]) * 1.1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g font-family="sans-serif" font-size="12" fill="#222">',
             f'<text x="20" y="25">{escape(metric)} ({unit}); mean with sample SD; N = independent runs</text>',
             f'<text x="20" y="48">Source: {escape(source["raw_source"])}</text>',
             f'<text x="20" y="68">SHA-256: {source["raw_sha256"]}</text>']
    for index, row in enumerate(selected):
        y = 100 + index * 32
        label = " / ".join(str(row[key]) for key in ("scenario", "load_level", "traffic_class", "protocol"))
        parts.append(f'<text x="20" y="{y + 12}">{escape(label)}</text>')
        if not row["sample_count"]:
            parts.append(f'<text x="500" y="{y + 12}">Unavailable (N=0): {escape(row["unavailable_reasons"])}</text>')
            continue
        value = row["mean"]
        scale = 430 / maximum
        parts.append(f'<rect x="500" y="{y}" width="{value * scale:.2f}" height="16" fill="#2878a0"/>')
        sd = row["sample_stddev"]
        if sd != "":
            parts.append(f'<path d="M {500 + max(0, value-sd)*scale:.2f} {y+8} H {500+(value+sd)*scale:.2f}" stroke="black" stroke-width="2"/>')
        parts.append(f'<text x="950" y="{y+12}">{value:.4g} {unit}; N={row["sample_count"]}/{row["expected_count"]}; '
                     f'SD={format(sd, ".3g") if sd != "" else "unavailable"}</text>')
    parts.append('</g></svg>')
    Path(output_path).write_text("\n".join(parts), encoding="utf-8")


def report_section(summaries, plots):
    lines = ["", "## Extended v3 measurements", "",
             "Receiver throughput measures delivered application traffic; sender estimates and switch egress are separate metrics. "
             "ICMP RTT follows the fallback queue and is not one-way or class-specific application delay. "
             "Statistics summarize independent run values with equal weight; p95 is a per-run percentile, not a pooled percentile. "
             "Missing values are excluded with counts and reasons; SD requires two runs. Switch metrics are counted once per run.", "",
             "| Scenario | Load | Class | Protocol | Metric | Unit | N/expected | Mean | SD | Min | Max | Unavailable reason |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in summaries:
        def cell(key):
            value = row[key]
            return f"{value:.6g}" if isinstance(value, float) else str(value).replace("|", "\\|").replace("\n", " ")
        lines.append("| " + " | ".join(cell(key) for key in (
            "scenario", "load_level", "traffic_class", "protocol", "metric", "unit")) +
                     f' | {row["sample_count"]}/{row["expected_count"]} | ' +
                     " | ".join(cell(key) for key in ("mean", "sample_stddev", "minimum", "maximum", "unavailable_reasons")) + " |")
    for metric, filename in plots.items():
        lines += ["", f"![{metric}](../../plots/{filename})"]
    return "\n".join(lines) + "\n"
