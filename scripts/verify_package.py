#!/usr/bin/env python3
"""Verify the non-privileged release package and its published evidence."""

import csv
import hashlib
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as element_tree


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from result_analysis import (  # noqa: E402
    build_aggregate_summaries,
    build_run_summaries,
    validate_rows,
)


REQUIRED_PATHS = (
    ".gitattributes",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "requirements.txt",
    "docs/baseline-v1.md",
    "docs/release-v2.md",
    "scripts/analyze_results.py",
    "scripts/cleanup_qos.sh",
    "scripts/run_experiments.py",
    "scripts/setup_qos.sh",
)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def fail(message):
    raise RuntimeError(message)


def verify():
    missing = [path for path in REQUIRED_PATHS if not (PROJECT_ROOT / path).exists()]
    if missing:
        fail(f"Missing required package paths: {missing}")

    subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=PROJECT_ROOT,
        check=True,
    )

    raw_files = sorted((PROJECT_ROOT / "results" / "raw").glob("experiment-*.csv"))
    if not raw_files:
        fail("No published experiment CSV exists")
    raw_path = raw_files[-1]
    with raw_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        validate_rows(rows, reader.fieldnames)

    run_summaries = build_run_summaries(rows)
    aggregates = build_aggregate_summaries(rows, run_summaries)
    if len(run_summaries) < 18:
        fail("Published evidence has fewer than 18 complete runs")
    if any(row["sample_count"] < 3 for row in aggregates):
        fail("Published evidence has fewer than three repetitions in a condition")
    congested_runs = [
        row for row in run_summaries if row["load_level"] == "congested"
    ]
    if not congested_runs or not all(
        row["congestion_detected"] for row in congested_runs
    ):
        fail("Not every published congested run contains measured congestion evidence")

    analysis_directory = PROJECT_ROOT / "results" / "analysis" / raw_path.stem
    report_path = analysis_directory / "analysis.md"
    summary_path = analysis_directory / "summary.csv"
    per_run_path = analysis_directory / "per-run.csv"
    plot_path = (
        PROJECT_ROOT
        / "results"
        / "plots"
        / f"{raw_path.stem}-throughput-comparison.svg"
    )
    for artifact in (report_path, summary_path, per_run_path, plot_path):
        if not artifact.is_file():
            fail(f"Missing generated evidence: {artifact.relative_to(PROJECT_ROOT)}")

    report = report_path.read_text(encoding="utf-8")
    if sha256_file(raw_path) not in report:
        fail("Analysis report does not contain the current raw CSV SHA-256")
    element_tree.parse(plot_path)

    unresolved = []
    for issue in sorted((PROJECT_ROOT / ".scratch" / "trafficpriority-v2" / "issues").glob("*.md")):
        if "**Status:** resolved" not in issue.read_text(encoding="utf-8"):
            unresolved.append(issue.name)
    if unresolved:
        fail(f"Unresolved work packages: {unresolved}")

    print("Package verification passed")
    print(f"Published raw data: {raw_path.relative_to(PROJECT_ROOT)}")
    print(f"Complete runs: {len(run_summaries)}")
    print(f"Aggregate rows: {len(aggregates)}")
    print(f"Raw SHA-256: {sha256_file(raw_path)}")


if __name__ == "__main__":
    verify()
