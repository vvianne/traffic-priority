#!/usr/bin/env python3
"""Generate summaries, interpretation, and an SVG plot from experiment CSV."""

import argparse
import csv
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from result_analysis import (  # noqa: E402
    RUN_FIELDS,
    SUMMARY_FIELDS,
    build_aggregate_summaries,
    build_run_summaries,
    format_number,
    observations,
    render_markdown,
    render_svg,
    validate_rows,
)


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: format_number(row.get(field, "")) for field in fieldnames}
            )


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_csv", type=Path, help="Ticket 6 raw experiment CSV.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "results",
        help="Results root containing analysis/ and plots/ (default: /app/results).",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    raw_path = arguments.raw_csv.resolve()
    if not raw_path.is_file():
        raise SystemExit(f"Raw CSV not found: {raw_path}")

    with raw_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        validate_rows(rows, reader.fieldnames)

    run_summaries = build_run_summaries(rows)
    aggregates = build_aggregate_summaries(rows, run_summaries)
    notes = observations(run_summaries, aggregates)

    output_root = arguments.output_root.resolve()
    analysis_directory = output_root / "analysis" / raw_path.stem
    plot_directory = output_root / "plots"
    analysis_directory.mkdir(parents=True, exist_ok=True)
    plot_directory.mkdir(parents=True, exist_ok=True)

    per_run_path = analysis_directory / "per-run.csv"
    summary_path = analysis_directory / "summary.csv"
    report_path = analysis_directory / "analysis.md"
    plot_path = plot_directory / f"{raw_path.stem}-throughput-comparison.svg"

    write_csv(per_run_path, RUN_FIELDS, run_summaries)
    write_csv(summary_path, SUMMARY_FIELDS, aggregates)
    render_svg(aggregates, plot_path, raw_path.name)
    report_path.write_text(
        render_markdown(raw_path, run_summaries, aggregates, notes, plot_path),
        encoding="utf-8",
    )

    print(f"Analyzed {len(run_summaries)} runs from {raw_path}")
    print(f"Per-run summary: {per_run_path}")
    print(f"Aggregate summary: {summary_path}")
    print(f"Interpretation: {report_path}")
    print(f"Comparison plot: {plot_path}")


if __name__ == "__main__":
    main()
