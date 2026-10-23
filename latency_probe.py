"""Concurrent ICMP RTT probes and strict Linux iputils ping parsing."""

from math import ceil, isfinite
import os
import re
import signal
import subprocess


LATENCY_FIELDS = (
    "rtt_sample_count", "rtt_min_ms", "rtt_avg_ms", "rtt_max_ms", "rtt_p95_ms",
    "probe_sent", "probe_received", "probe_loss_pct", "probe_valid", "probe_error",
    "probe_p95_status", "probe_output", "probe_interval_s", "probe_start_utc",
    "probe_end_utc", "probe_start_offset_s", "probe_end_offset_s",
)
PROBE_INTERVAL = 0.2


def parse_ping(output):
    """Use individual RTT samples; nearest-rank p95 requires 20 replies."""
    summary = re.findall(
        r"(\d+) packets transmitted, (\d+) (?:packets )?received,.*?([\d.]+)% packet loss",
        output,
    )
    if len(summary) != 1:
        raise ValueError("Missing or ambiguous ping packet summary")
    sent, received = map(int, summary[0][:2])
    loss = float(summary[0][2])
    samples = [float(value) for value in re.findall(r"\btime=([\d.]+) ms", output)]
    if (sent <= 0 or not 0 <= received <= sent or len(samples) != received
            or not isfinite(loss) or not 0 <= loss <= 100
            or abs(loss - 100 * (sent - received) / sent) > 1.01
            or any(not isfinite(value) or value < 0 for value in samples)
            or "DUP!" in output or re.search(r"\btime<", output)):
        raise ValueError("Inconsistent or unsupported ping measurements")
    return {
        "rtt_sample_count": len(samples),
        "rtt_min_ms": min(samples) if samples else "",
        "rtt_avg_ms": sum(samples) / len(samples) if samples else "",
        "rtt_max_ms": max(samples) if samples else "",
        "rtt_p95_ms": sorted(samples)[ceil(0.95 * len(samples)) - 1] if len(samples) >= 20 else "",
        "probe_sent": sent, "probe_received": received, "probe_loss_pct": loss,
        "probe_p95_status": "available" if len(samples) >= 20 else "insufficient samples (need 20)",
        "probe_valid": "true", "probe_error": "",
    }


def stop_probe(process, signal_sent=False):
    if not signal_sent and process.poll() is None:
        process.send_signal(signal.SIGINT)
    try:
        return process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return stdout, stderr + " probe exceeded shutdown timeout"


def start_probes(net, traffic_classes, duration):
    probes = {}
    environment = dict(os.environ, LC_ALL="C")
    try:
        for name, host, _, _, _ in traffic_classes:
            probes[name] = net.get(host).popen(
                ["ping", "-n", "-D", "-i", str(PROBE_INTERVAL), "-w", str(duration),
                 net.get("h3").IP()],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment,
            )
    except BaseException:
        for process in probes.values():
            stop_probe(process)
        raise
    return probes


def collect_probes(probes, output_directory, run_id):
    results = {}
    # Stop both probes before waiting for either process to flush its output.
    for process in probes.values():
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
    for name, process in probes.items():
        stdout, stderr = stop_probe(process, signal_sent=True)
        filename = f"{run_id}-{name}-ping.log"
        (output_directory / filename).write_text(stdout + "\nSTDERR:\n" + stderr, encoding="utf-8")
        try:
            if process.returncode not in (0, 1, -signal.SIGINT) or stderr.strip():
                raise ValueError("Ping process failed: " + stderr.strip())
            row = parse_ping(stdout)
        except ValueError as error:
            row = {key: "" for key in LATENCY_FIELDS}
            row.update(probe_valid="false", probe_error=str(error), probe_p95_status="unavailable")
        row.update(probe_output=filename, probe_interval_s=PROBE_INTERVAL)
        results[name] = row
    return results
