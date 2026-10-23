"""Pure parsers for experiment throughput and switch counter output."""

import csv
from dataclasses import dataclass
from math import isfinite
import re


@dataclass(frozen=True)
class IperfCsvMeasurement:
    """One iperf 2 CSV summary, preserving its two reported endpoints."""

    timestamp: str
    endpoint_a_address: str
    endpoint_a_port: int
    endpoint_b_address: str
    endpoint_b_port: int
    stream_id: int
    interval_start_s: float
    interval_end_s: float
    transferred_bytes: int
    bits_per_second: float
    jitter_ms: float = None
    lost_datagrams: int = None
    total_datagrams: int = None
    loss_pct: float = None

    @property
    def throughput_mbps(self):
        return self.bits_per_second / 1_000_000


def _parse_iperf_csv_line(line):
    fields = next(csv.reader([line]))
    if len(fields) < 9:
        return None
    interval_match = re.fullmatch(
        r"\s*([0-9]+(?:\.[0-9]+)?)-([0-9]+(?:\.[0-9]+)?)\s*",
        fields[6],
    )
    if interval_match is None:
        return None
    try:
        measurement = IperfCsvMeasurement(
            timestamp=fields[0].strip(),
            endpoint_a_address=fields[1].strip(),
            endpoint_a_port=int(fields[2]),
            endpoint_b_address=fields[3].strip(),
            endpoint_b_port=int(fields[4]),
            stream_id=int(fields[5]),
            interval_start_s=float(interval_match.group(1)),
            interval_end_s=float(interval_match.group(2)),
            transferred_bytes=int(fields[7]),
            bits_per_second=float(fields[8]),
            jitter_ms=float(fields[9]) if len(fields) >= 14 else None,
            lost_datagrams=int(fields[10]) if len(fields) >= 14 else None,
            total_datagrams=int(fields[11]) if len(fields) >= 14 else None,
            loss_pct=float(fields[12]) if len(fields) >= 14 else None,
        )
    except ValueError:
        return None
    numeric_values = (
        measurement.interval_start_s,
        measurement.interval_end_s,
        measurement.bits_per_second,
    )
    if not all(isfinite(value) for value in numeric_values):
        return None
    if measurement.jitter_ms is not None:
        if (
            not isfinite(measurement.jitter_ms) or measurement.jitter_ms < 0
            or not isfinite(measurement.loss_pct) or not 0 <= measurement.loss_pct <= 100
            or not 0 <= measurement.lost_datagrams <= measurement.total_datagrams
        ):
            return None
        if measurement.total_datagrams <= 0:
            return None
        expected_loss = 100 * measurement.lost_datagrams / measurement.total_datagrams
        if abs(expected_loss - measurement.loss_pct) > 0.11:
            return None
    if (
        not measurement.timestamp
        or not measurement.endpoint_a_address
        or not measurement.endpoint_b_address
        or not 1 <= measurement.endpoint_a_port <= 65535
        or not 1 <= measurement.endpoint_b_port <= 65535
        or measurement.interval_start_s < 0
        or measurement.interval_end_s <= measurement.interval_start_s
        or measurement.transferred_bytes < 0
        or measurement.bits_per_second < 0
    ):
        return None
    return measurement


def parse_iperf_csv_measurement(
    output,
    expected_addresses=None,
    expected_server_address=None,
    expected_server_port=None,
    expected_duration_s=None,
    protocol="tcp",
    role="receiver",
):
    """Parse and validate one final iperf 2 CSV summary.

    Iperf 2.0.13 reports local/peer endpoints rather than consistently reporting
    traffic direction, so validation treats the address pair as unordered and
    separately identifies the receiver's listening endpoint.
    """
    measurements = []
    for line in output.splitlines():
        measurement = _parse_iperf_csv_line(line)
        if measurement is not None:
            # UDP clients may also print the receiver's returned report.
            if protocol == "udp" and role == "sender" and measurement.jitter_ms is not None:
                continue
            if protocol == "udp" and role == "receiver" and measurement.jitter_ms is None:
                continue
            measurements.append(measurement)
    if not measurements:
        raise ValueError("No valid iperf CSV measurement was found")
    if len(measurements) != 1:
        raise ValueError(
            f"Expected one iperf CSV measurement, found {len(measurements)}"
        )

    measurement = measurements[0]
    if expected_addresses is not None:
        actual_addresses = {
            measurement.endpoint_a_address,
            measurement.endpoint_b_address,
        }
        if actual_addresses != set(expected_addresses):
            raise ValueError(
                "Iperf endpoints do not match the expected sender and receiver"
            )
    if expected_server_address is not None or expected_server_port is not None:
        server_endpoints = {
            (measurement.endpoint_a_address, measurement.endpoint_a_port),
            (measurement.endpoint_b_address, measurement.endpoint_b_port),
        }
        expected_server = (expected_server_address, expected_server_port)
        if expected_server not in server_endpoints:
            raise ValueError(
                "Iperf measurement does not contain the expected receiver endpoint"
            )
    if expected_duration_s is not None:
        tolerance = max(1.0, expected_duration_s * 0.2)
        measured_duration = (
            measurement.interval_end_s - measurement.interval_start_s
        )
        if measurement.interval_start_s > 0.25 or abs(
            measured_duration - expected_duration_s
        ) > tolerance:
            raise ValueError(
                "Iperf measurement interval does not match the configured window"
            )
    return measurement


def parse_iperf_csv(output):
    """Return the final client throughput in decimal megabits per second."""
    return parse_iperf_csv_measurement(output).throughput_mbps


def parse_flow_counters(output, destination_ports):
    """Sum flow packet and byte counters by TCP destination port."""
    totals = {port: {"packets": 0, "bytes": 0} for port in destination_ports}
    for line in output.splitlines():
        port_match = re.search(r"tp_dst=(\d+)", line)
        packet_match = re.search(r"n_packets=(\d+)", line)
        byte_match = re.search(r"n_bytes=(\d+)", line)
        if not (port_match and packet_match and byte_match):
            continue
        port = int(port_match.group(1))
        protocol = "udp" if re.search(r"\budp\b", line) else "tcp"
        key = (protocol, port) if (protocol, port) in totals else port
        if key in totals:
            totals[key]["packets"] += int(packet_match.group(1))
            totals[key]["bytes"] += int(byte_match.group(1))
    return totals


def parse_queue_counters(output):
    """Parse OpenFlow queue packet and byte counters by queue ID."""
    totals = {}
    pattern = re.compile(r"queue (\d+): bytes=(\d+), pkts=(\d+)")
    for match in pattern.finditer(output):
        totals[int(match.group(1))] = {
            "bytes": int(match.group(2)),
            "packets": int(match.group(3)),
        }
    return totals


def parse_egress_counters(output):
    """Parse transmit counters from an ovs-ofctl port dump."""
    match = re.search(r"tx pkts=(\d+), bytes=(\d+)", output)
    if match is None:
        raise ValueError("Could not parse transmit counters")
    return {"packets": int(match.group(1)), "bytes": int(match.group(2))}
