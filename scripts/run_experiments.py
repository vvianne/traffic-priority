#!/usr/bin/env python3
"""Run repeatable paired TrafficPriority experiments and write raw CSV data."""

import argparse
import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ryu_topo import (  # noqa: E402
    BOTTLENECK_LINK_MBPS,
    build_network,
    ensure_openvswitch,
    start_network,
    stop_network,
)
from experiment_metrics import (  # noqa: E402
    parse_egress_counters,
    parse_flow_counters,
    parse_iperf_csv,
    parse_queue_counters,
)


LOAD_LEVELS = (
    ("light", "1M", 1.0),
    ("near_capacity", "2500K", 2.5),
    ("congested", "5M", 5.0),
)
TRAFFIC_CLASSES = (
    ("high_priority", "h1", 5001, 1),
    ("best_effort", "h2", 5002, 0),
)
SCENARIOS = (
    ("without_qos", False, "single_5mbps_bottleneck"),
    ("with_qos", True, "htb_queue0_1mbps_queue1_3mbps"),
)
CSV_FIELDS = (
    "experiment_id",
    "run_id",
    "timestamp_utc",
    "scenario",
    "qos_enabled",
    "load_level",
    "policy",
    "traffic_class",
    "protocol",
    "destination_port",
    "queue_id",
    "offered_mbps",
    "throughput_mbps",
    "duration_s",
    "wall_duration_s",
    "client_start_skew_ms",
    "link_capacity_mbps",
    "egress_mbps",
    "bottleneck_utilization_pct",
    "congestion_detected",
    "flow_packet_delta",
    "flow_byte_delta",
    "queue_packet_delta",
    "queue_byte_delta",
    "egress_packet_delta",
    "egress_byte_delta",
    "iperf_version",
    "ovs_version",
    "ryu_version",
    "controller_log",
)


def command_output(command, check=True):
    """Run a command and return combined, stripped output."""
    completed = subprocess.run(
        command,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.stdout.strip()


def first_line(command):
    output = command_output(command, check=False)
    return output.splitlines()[0] if output else "unknown"


def flow_counters(destination_ports):
    """Sum installed s1 flow counters by TCP destination port."""
    output = command_output(
        ["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"]
    )
    return parse_flow_counters(output, destination_ports)


def queue_counters(qos_enabled):
    """Read OpenFlow queue counters when the queue policy is active."""
    if not qos_enabled:
        return {}
    output = command_output(
        ["ovs-ofctl", "-O", "OpenFlow13", "queue-stats", "s1"]
    )
    return parse_queue_counters(output)


def egress_counters():
    """Read aggregate transmit counters for s1's bottleneck port."""
    output = command_output(
        ["ovs-ofctl", "-O", "OpenFlow13", "dump-ports", "s1", "3"]
    )
    return parse_egress_counters(output)


def counter_delta(after, before, key):
    return max(0, after.get(key, 0) - before.get(key, 0))


def start_servers(receiver):
    servers = []
    for _, _, port, _ in TRAFFIC_CLASSES:
        servers.append(
            receiver.popen(
                ["iperf", "-s", "-p", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    time.sleep(0.5)
    return servers


def stop_processes(processes):
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run_clients(net, bandwidth, duration):
    """Start both clients back-to-back and wait for concurrent completion."""
    clients = []
    launch_times = []
    for _, host_name, port, _ in TRAFFIC_CLASSES:
        launch_times.append(time.monotonic())
        clients.append(
            net.get(host_name).popen(
                [
                    "iperf",
                    "-c",
                    "10.0.0.3",
                    "-p",
                    str(port),
                    "-t",
                    str(duration),
                    "-b",
                    bandwidth,
                    "-y",
                    "C",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    outputs = []
    try:
        for process in clients:
            stdout, stderr = process.communicate(timeout=duration + 15)
            if process.returncode != 0:
                raise RuntimeError(
                    f"iperf client failed with {process.returncode}: {stderr.strip()}"
                )
            outputs.append(stdout)
    except Exception:
        stop_processes(clients)
        raise

    skew_ms = (max(launch_times) - min(launch_times)) * 1000
    return [parse_iperf_csv(output) for output in outputs], skew_ms


def start_controller(qos_enabled, log_path):
    environment = os.environ.copy()
    environment["QOS_ENABLED"] = "1" if qos_enabled else "0"
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            "ryu-manager",
            "--ofp-tcp-listen",
            "6653",
            str(PROJECT_ROOT / "priority_ryu_controller.py"),
        ],
        cwd=str(PROJECT_ROOT),
        env=environment,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(1)
    if process.poll() is not None:
        log_file.close()
        raise RuntimeError(f"Ryu failed to start; inspect {log_path}")
    return process, log_file


def stop_controller(process, log_file):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    log_file.close()


def run_scenario(
    writer,
    csv_file,
    experiment_id,
    scenario,
    qos_enabled,
    policy,
    repetitions,
    duration,
    versions,
    output_directory,
):
    controller_log = output_directory / f"{experiment_id}-{scenario}-controller.log"
    controller, controller_file = start_controller(qos_enabled, controller_log)
    net = None
    servers = []
    try:
        net = build_network(qos_enabled=qos_enabled)
        start_network(net, qos_enabled=qos_enabled)
        receiver = net.get("h3")
        servers = start_servers(receiver)

        # Resolve ARP and establish learned paths before counter snapshots.
        net.get("h1").cmd("ping -c 1 -W 1 10.0.0.3")
        net.get("h2").cmd("ping -c 1 -W 1 10.0.0.3")

        ports = [traffic[2] for traffic in TRAFFIC_CLASSES]
        for load_name, bandwidth, offered_mbps in LOAD_LEVELS:
            for repetition in range(1, repetitions + 1):
                run_id = (
                    f"{scenario}-{load_name}-r{repetition:02d}-"
                    f"{uuid.uuid4().hex[:8]}"
                )
                before_flow = flow_counters(ports)
                before_queue = queue_counters(qos_enabled)
                before_egress = egress_counters()

                started_at = datetime.now(timezone.utc)
                wall_started = time.monotonic()
                throughputs, start_skew_ms = run_clients(
                    net,
                    bandwidth,
                    duration,
                )
                wall_duration = time.monotonic() - wall_started
                time.sleep(0.2)

                after_flow = flow_counters(ports)
                after_queue = queue_counters(qos_enabled)
                after_egress = egress_counters()
                egress_packets = counter_delta(after_egress, before_egress, "packets")
                egress_bytes = counter_delta(after_egress, before_egress, "bytes")
                egress_mbps = (egress_bytes * 8) / wall_duration / 1_000_000
                utilization = egress_mbps / BOTTLENECK_LINK_MBPS * 100
                offered_total = offered_mbps * len(TRAFFIC_CLASSES)
                congestion_detected = (
                    offered_total > BOTTLENECK_LINK_MBPS and utilization >= 80
                )

                for index, (class_name, _, port, queue_id) in enumerate(
                    TRAFFIC_CLASSES
                ):
                    flow_packets = counter_delta(
                        after_flow[port], before_flow[port], "packets"
                    )
                    flow_bytes = counter_delta(
                        after_flow[port], before_flow[port], "bytes"
                    )
                    queue_before = before_queue.get(queue_id, {})
                    queue_after = after_queue.get(queue_id, {})
                    writer.writerow(
                        {
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                            "timestamp_utc": started_at.isoformat(),
                            "scenario": scenario,
                            "qos_enabled": str(qos_enabled).lower(),
                            "load_level": load_name,
                            "policy": policy,
                            "traffic_class": class_name,
                            "protocol": "TCP",
                            "destination_port": port,
                            "queue_id": queue_id if qos_enabled else "",
                            "offered_mbps": offered_mbps,
                            "throughput_mbps": f"{throughputs[index]:.6f}",
                            "duration_s": duration,
                            "wall_duration_s": f"{wall_duration:.6f}",
                            "client_start_skew_ms": f"{start_skew_ms:.3f}",
                            "link_capacity_mbps": BOTTLENECK_LINK_MBPS,
                            "egress_mbps": f"{egress_mbps:.6f}",
                            "bottleneck_utilization_pct": f"{utilization:.3f}",
                            "congestion_detected": str(congestion_detected).lower(),
                            "flow_packet_delta": flow_packets,
                            "flow_byte_delta": flow_bytes,
                            "queue_packet_delta": (
                                counter_delta(
                                    queue_after, queue_before, "packets"
                                )
                                if qos_enabled
                                else ""
                            ),
                            "queue_byte_delta": (
                                counter_delta(queue_after, queue_before, "bytes")
                                if qos_enabled
                                else ""
                            ),
                            "egress_packet_delta": egress_packets,
                            "egress_byte_delta": egress_bytes,
                            "iperf_version": versions["iperf"],
                            "ovs_version": versions["ovs"],
                            "ryu_version": versions["ryu"],
                            "controller_log": controller_log.name,
                        }
                    )
                csv_file.flush()
                print(
                    f"{run_id}: throughput={sum(throughputs):.3f} Mbps, "
                    f"egress={egress_mbps:.3f} Mbps, "
                    f"utilization={utilization:.1f}%"
                )
    finally:
        stop_processes(servers)
        if net is not None:
            stop_network(net, qos_enabled=qos_enabled)
        stop_controller(controller, controller_file)
        time.sleep(0.5)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Seconds per concurrent client pair (default: 10).",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=3,
        help="Repetitions per scenario and load level (default: 3).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path (default: results/raw/<experiment-id>.csv).",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    if arguments.duration < 1:
        raise SystemExit("--duration must be at least 1 second")
    if arguments.repetitions < 1:
        raise SystemExit("--repetitions must be at least 1")

    experiment_id = datetime.now(timezone.utc).strftime("experiment-%Y%m%dT%H%M%SZ")
    output_path = arguments.output or (
        PROJECT_ROOT / "results" / "raw" / f"{experiment_id}.csv"
    )
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    versions = {
        "iperf": first_line(["iperf", "--version"]),
        "ovs": first_line(["ovs-vsctl", "--version"]),
        "ryu": first_line(["ryu-manager", "--version"]),
    }
    ensure_openvswitch()

    print(f"Writing experiment data to {output_path}")
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        csv_file.flush()
        for scenario, qos_enabled, policy in SCENARIOS:
            print(f"Starting scenario: {scenario}")
            run_scenario(
                writer,
                csv_file,
                experiment_id,
                scenario,
                qos_enabled,
                policy,
                arguments.repetitions,
                arguments.duration,
                versions,
                output_path.parent,
            )

    print(f"Experiment complete: {output_path}")


if __name__ == "__main__":
    main()
