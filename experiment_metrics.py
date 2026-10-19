"""Pure parsers for experiment throughput and switch counter output."""

import csv
import re


def parse_iperf_csv(output):
    """Return the final client throughput in decimal megabits per second."""
    for line in reversed(output.splitlines()):
        fields = next(csv.reader([line]))
        if len(fields) < 9:
            continue
        try:
            return float(fields[8]) / 1_000_000
        except ValueError:
            continue
    raise ValueError(f"Could not parse iperf CSV output: {output!r}")


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
        if port in totals:
            totals[port]["packets"] += int(packet_match.group(1))
            totals[port]["bytes"] += int(byte_match.group(1))
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
