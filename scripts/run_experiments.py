#!/usr/bin/env python3
"""Run repeatable paired TrafficPriority experiments and write raw CSV data."""

import argparse
import csv
from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
import json
import os
import platform
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import random


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from policy_config import load_config  # noqa: E402
from experiment_plan import scenario_schedule  # noqa: E402
from latency_probe import LATENCY_FIELDS, start_probes, collect_probes, stop_probe  # noqa: E402
from ovs_qos import verify_flow_actions, queue_policy  # noqa: E402
from experiment_metrics import (  # noqa: E402
    parse_egress_counters,
    parse_flow_counters,
    parse_iperf_csv_measurement,
    parse_queue_counters,
)


CSV_FIELDS = LATENCY_FIELDS + (
    "experiment_id",
    "run_id",
    "repetition",
    "expected_repetitions",
    "warmup_s",
    "warmup_wall_s",
    "scenario_order",
    "order_seed",
    "session_index",
    "environment_json",
    "effective_config_json",
    "config_sha256",
    "measurement_end_utc",
    "egress_window_s",
    "timestamp_utc",
    "scenario",
    "qos_enabled",
    "load_level",
    "policy",
    "configuration_file",
    "traffic_class",
    "protocol",
    "destination_port",
    "queue_id",
    "offered_mbps",
    "throughput_mbps",
    "measurement_method",
    "sender_throughput_mbps",
    "sender_measurement_valid",
    "sender_measurement_error",
    "sender_interval_start_s",
    "sender_interval_end_s",
    "sender_transferred_bytes",
    "sender_output",
    "receiver_throughput_mbps",
    "receiver_measurement_valid",
    "receiver_measurement_error",
    "receiver_interval_start_s",
    "receiver_interval_end_s",
    "receiver_transferred_bytes",
    "receiver_output",
    "received_mbps",
    "udp_jitter_ms",
    "udp_lost_datagrams",
    "udp_total_datagrams",
    "udp_loss_pct",
    "udp_metrics_valid",
    "udp_metrics_error",
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


def configured_traffic_classes(policy_config):
    """Return the current two experiment classes with their source hosts."""
    sources = {"high_priority": "h1", "best_effort": "h2"}
    return tuple(
        (
            traffic_class.key,
            sources[traffic_class.key],
            traffic_class.destination_port,
            traffic_class.queue_id,
            traffic_class.protocol,
        )
        for traffic_class in policy_config.traffic_classes
    )


def configured_scenarios(policy_config):
    best_effort = policy_config.traffic_class("best_effort")
    high_priority = policy_config.traffic_class("high_priority")
    capacity = policy_config.network.bottleneck_mbps
    return (
        ("without_qos", False, f"ovs_htb_single_queue_{capacity:g}mbps"),
        (
            "with_qos",
            True,
            "htb_queue{}_{:g}mbps_queue{}_{:g}mbps".format(
                best_effort.queue_id,
                best_effort.min_rate_mbps,
                high_priority.queue_id,
                high_priority.min_rate_mbps,
            ),
        ),
    )


def configured_load_levels(policy_config):
    """Scale the v2 load ratios with the configured bottleneck capacity."""
    capacity = policy_config.network.bottleneck_mbps
    return tuple(
        (name, str(int(round(offered_mbps * 1_000_000))), offered_mbps)
        for name, offered_mbps in (
            ("light", capacity * 0.2),
            ("near_capacity", capacity * 0.5),
            ("congested", capacity),
        )
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
    try:
        output = command_output(command, check=False)
    except OSError as error:
        return "unavailable: " + str(error)
    return output.splitlines()[0] if output else "unknown"


def flow_counters(destination_ports, policy_config):
    """Sum installed s1 flow counters by TCP destination port."""
    output = command_output(
        [
            "ovs-ofctl",
            "-O",
            "OpenFlow13",
            "dump-flows",
            policy_config.network.qos_bridge,
        ]
    )
    return parse_flow_counters(output, destination_ports)


def queue_counters(qos_enabled, policy_config):
    """Read OpenFlow queue counters when the queue policy is active."""
    output = command_output(
        [
            "ovs-ofctl",
            "-O",
            "OpenFlow13",
            "queue-stats",
            policy_config.network.qos_bridge,
        ]
    )
    return parse_queue_counters(output)


def egress_counters(policy_config):
    """Read aggregate transmit counters for s1's bottleneck port."""
    output = command_output(
        [
            "ovs-ofctl",
            "-O",
            "OpenFlow13",
            "dump-ports",
            policy_config.network.qos_bridge,
            str(policy_config.network.qos_egress_port),
        ]
    )
    return parse_egress_counters(output)


def counter_delta(after, before, key):
    if key not in after or key not in before or after[key] < before[key]:
        raise ValueError("Missing or reset counter: " + key)
    return after[key] - before[key]


def start_servers(receiver, traffic_classes):
    """Start fresh CSV-reporting receivers for one measurement run."""
    servers = {}
    for class_name, _, port, _, protocol in traffic_classes:
        servers[class_name] = safe_popen(receiver, list(servers.values()),
            ["iperf", "-s", "-p", str(port), "-y", "C"] + (["-u"] if protocol == "udp" else []),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    time.sleep(0.5)
    return servers


def safe_popen(host, active, *args, **kwargs):
    try:
        return host.popen(*args, **kwargs)
    except BaseException:
        stop_processes(active)
        raise


def collect_server_outputs(servers):
    """Gracefully stop receivers so iperf flushes each final CSV report."""
    for process in servers.values():
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
    outputs = {}
    for class_name, process in servers.items():
        try:
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        outputs[class_name] = (stdout, stderr)
    return outputs


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


def run_clients(net, bandwidth, duration, traffic_classes, on_started=None):
    """Start both clients back-to-back and wait for concurrent completion."""
    clients = []
    launch_times = []
    for _, host_name, port, _, protocol in traffic_classes:
        launch_times.append(time.monotonic())
        clients.append(
            safe_popen(net.get(host_name), clients,
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
                ] + (["-u"] if protocol == "udp" else []),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    outputs = []
    try:
        if on_started is not None:
            on_started()
        for process in clients:
            stdout, stderr = process.communicate(timeout=duration + 15)
            if process.returncode != 0:
                raise RuntimeError(
                    f"iperf client failed with {process.returncode}: {stderr.strip()}"
                )
            outputs.append(stdout)
    except BaseException:
        stop_processes(clients)
        raise

    skew_ms = (max(launch_times) - min(launch_times)) * 1000
    return outputs, skew_ms


def parse_measurement(output, stderr, sender_address, receiver_address, port, duration,
                      protocol="tcp", role="receiver"):
    """Return a validated measurement or an explicit diagnostic."""
    try:
        return (
            parse_iperf_csv_measurement(
                output,
                expected_addresses=(sender_address, receiver_address),
                expected_server_address=receiver_address,
                expected_server_port=port,
                expected_duration_s=duration,
                protocol=protocol,
                role=role,
            ),
            "",
        )
    except ValueError as error:
        diagnostic = str(error)
        stderr_summary = " ".join(stderr.split())
        if stderr_summary:
            diagnostic = f"{diagnostic}; stderr: {stderr_summary[:300]}"
        return None, diagnostic


def measurement_columns(prefix, measurement, error):
    if measurement is None:
        return {
            f"{prefix}_throughput_mbps": "",
            f"{prefix}_measurement_valid": "false",
            f"{prefix}_measurement_error": error,
            f"{prefix}_interval_start_s": "",
            f"{prefix}_interval_end_s": "",
            f"{prefix}_transferred_bytes": "",
        }
    return {
        f"{prefix}_throughput_mbps": f"{measurement.throughput_mbps:.6f}",
        f"{prefix}_measurement_valid": "true",
        f"{prefix}_measurement_error": "",
        f"{prefix}_interval_start_s": f"{measurement.interval_start_s:.6f}",
        f"{prefix}_interval_end_s": f"{measurement.interval_end_s:.6f}",
        f"{prefix}_transferred_bytes": measurement.transferred_bytes,
    }


def save_measurement_output(output_directory, run_id, class_name, role, output):
    filename = f"{run_id}-{class_name}-{role}-iperf.csv"
    (output_directory / filename).write_text(output, encoding="utf-8")
    return filename


def start_controller(qos_enabled, log_path, policy_config):
    environment = os.environ.copy()
    environment["QOS_ENABLED"] = "1" if qos_enabled else "0"
    environment["TRAFFIC_PRIORITY_CONFIG"] = str(policy_config.source_path)
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
    policy_config,
    repetition_numbers=None,
    warmup=2,
    run_metadata=None,
):
    from ryu_topo import build_network, start_network, stop_network

    run_metadata = run_metadata or {}
    session = run_metadata.get("session_index", 1)
    controller_log = output_directory / f"{experiment_id}-{scenario}-s{session}-controller.log"
    controller, controller_file = start_controller(
        qos_enabled, controller_log, policy_config
    )
    net = None
    servers = {}
    probes = {}
    traffic_classes = configured_traffic_classes(policy_config)
    capacity_mbps = policy_config.network.bottleneck_mbps
    try:
        net = build_network(qos_enabled=qos_enabled, policy_config=policy_config)
        start_network(
            net,
            qos_enabled=qos_enabled,
            policy_config=policy_config,
        )
        receiver = net.get("h3")

        # Resolve ARP and establish learned paths before counter snapshots.
        net.get("h1").cmd("ping -c 1 -W 1 10.0.0.3")
        net.get("h2").cmd("ping -c 1 -W 1 10.0.0.3")

        ports = [(traffic[4], traffic[2]) for traffic in traffic_classes]
        for load_name, bandwidth, offered_mbps in configured_load_levels(
            policy_config
        ):
            for repetition in (repetition_numbers or range(1, repetitions + 1)):
                run_id = (
                    f"{scenario}-{load_name}-r{repetition:02d}-"
                    f"{uuid.uuid4().hex[:8]}"
                )
                warmup_started = time.monotonic()
                if warmup:
                    servers = start_servers(receiver, traffic_classes)
                    try:
                        run_clients(net, bandwidth, warmup, traffic_classes)
                    finally:
                        collect_server_outputs(servers)
                        servers = {}
                warmup_wall = time.monotonic() - warmup_started
                # Fresh connections keep warm-up bytes out of iperf summaries.
                servers = start_servers(receiver, traffic_classes)
                before_flow = flow_counters(ports, policy_config)
                before_queue = queue_counters(qos_enabled, policy_config)
                counter_started = time.monotonic()
                before_egress = egress_counters(policy_config)

                started_at = datetime.now(timezone.utc)
                wall_started = time.monotonic()
                probe_timing = {}
                def launch_probes():
                    nonlocal probes
                    probe_timing["probe_start_utc"] = datetime.now(timezone.utc).isoformat()
                    probe_timing["probe_start_offset_s"] = time.monotonic() - wall_started
                    probes = start_probes(net, traffic_classes, duration)
                try:
                    sender_outputs, start_skew_ms = run_clients(
                        net,
                        bandwidth,
                        duration,
                        traffic_classes,
                        on_started=launch_probes,
                    )
                    probe_timing["probe_end_utc"] = datetime.now(timezone.utc).isoformat()
                    probe_timing["probe_end_offset_s"] = time.monotonic() - wall_started
                    probe_rows = collect_probes(probes, output_directory, run_id)
                    probes = {}
                    wall_duration = time.monotonic() - wall_started
                    measurement_end = datetime.now(timezone.utc).isoformat()
                    after_egress = egress_counters(policy_config)
                    egress_window = time.monotonic() - counter_started
                finally:
                    receiver_outputs = collect_server_outputs(servers)
                    servers = {}

                after_flow = flow_counters(ports, policy_config)
                after_queue = queue_counters(qos_enabled, policy_config)
                verify_flow_actions(
                    command_output([
                        "ovs-ofctl", "-O", "OpenFlow13", "dump-flows",
                        policy_config.network.qos_bridge,
                    ]),
                    queue_policy(policy_config, qos_enabled),
                    policy_config.network.qos_egress_port,
                    qos_enabled,
                )
                egress_packets = counter_delta(after_egress, before_egress, "packets")
                egress_bytes = counter_delta(after_egress, before_egress, "bytes")
                egress_mbps = (egress_bytes * 8) / egress_window / 1_000_000
                utilization = egress_mbps / capacity_mbps * 100
                offered_total = offered_mbps * len(traffic_classes)
                congestion_detected = (
                    offered_total > capacity_mbps and utilization >= 80
                )

                sender_measurements = []
                receiver_measurements = []
                for index, (
                    class_name,
                    host_name,
                    port,
                    queue_id,
                    protocol,
                ) in enumerate(
                    traffic_classes
                ):
                    sender_address = net.get(host_name).IP()
                    receiver_address = receiver.IP()
                    sender_output = sender_outputs[index]
                    receiver_output, receiver_stderr = receiver_outputs[class_name]
                    sender_measurement, sender_error = parse_measurement(
                        sender_output,
                        "",
                        sender_address,
                        receiver_address,
                        port,
                        duration,
                        protocol=protocol,
                        role="sender",
                    )
                    receiver_measurement, receiver_error = parse_measurement(
                        receiver_output,
                        receiver_stderr,
                        sender_address,
                        receiver_address,
                        port,
                        duration,
                        protocol=protocol,
                        role="receiver",
                    )
                    sender_measurements.append(sender_measurement)
                    receiver_measurements.append(receiver_measurement)
                    sender_output_name = save_measurement_output(
                        output_directory,
                        run_id,
                        class_name,
                        "sender",
                        sender_output,
                    )
                    receiver_output_name = save_measurement_output(
                        output_directory,
                        run_id,
                        class_name,
                        "receiver",
                        receiver_output,
                    )
                    flow_packets = counter_delta(
                        after_flow[(protocol, port)], before_flow[(protocol, port)], "packets"
                    )
                    flow_bytes = counter_delta(
                        after_flow[(protocol, port)], before_flow[(protocol, port)], "bytes"
                    )
                    measured_queue_id = queue_id if qos_enabled else 0
                    queue_before = before_queue.get(measured_queue_id, {})
                    queue_after = after_queue.get(measured_queue_id, {})
                    row = {
                            **probe_rows[class_name],
                            **probe_timing,
                            **run_metadata,
                            "repetition": repetition,
                            "expected_repetitions": repetitions,
                            "warmup_s": warmup,
                            "warmup_wall_s": f"{warmup_wall:.6f}",
                            "measurement_end_utc": measurement_end,
                            "egress_window_s": f"{egress_window:.6f}",
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                            "timestamp_utc": started_at.isoformat(),
                            "scenario": scenario,
                            "qos_enabled": str(qos_enabled).lower(),
                            "load_level": load_name,
                            "policy": policy,
                            "configuration_file": str(policy_config.source_path),
                            "traffic_class": class_name,
                            "protocol": protocol.upper(),
                            "destination_port": port,
                            "queue_id": queue_id if qos_enabled else "",
                            "offered_mbps": offered_mbps,
                            "throughput_mbps": (
                                f"{sender_measurement.throughput_mbps:.6f}"
                                if sender_measurement is not None
                                else ""
                            ),
                            "measurement_method": "iperf2_csv_final_summary",
                            "sender_output": sender_output_name,
                            "receiver_output": receiver_output_name,
                            "duration_s": duration,
                            "wall_duration_s": f"{wall_duration:.6f}",
                            "client_start_skew_ms": f"{start_skew_ms:.3f}",
                            "link_capacity_mbps": capacity_mbps,
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
                    row.update(
                        measurement_columns(
                            "sender", sender_measurement, sender_error
                        )
                    )
                    row.update(
                        measurement_columns(
                            "receiver", receiver_measurement, receiver_error
                        )
                    )
                    row["received_mbps"] = row["receiver_throughput_mbps"]
                    udp_valid = protocol == "udp" and receiver_measurement is not None
                    row.update({
                        "udp_metrics_valid": str(udp_valid).lower(),
                        "udp_metrics_error": (
                            receiver_error if protocol == "udp" else "not applicable: TCP"
                        ),
                        "udp_jitter_ms": receiver_measurement.jitter_ms if udp_valid else "",
                        "udp_lost_datagrams": receiver_measurement.lost_datagrams if udp_valid else "",
                        "udp_total_datagrams": receiver_measurement.total_datagrams if udp_valid else "",
                        "udp_loss_pct": receiver_measurement.loss_pct if udp_valid else "",
                    })
                    writer.writerow(row)
                csv_file.flush()
                valid_sender = [
                    item.throughput_mbps
                    for item in sender_measurements
                    if item is not None
                ]
                valid_receiver = [
                    item.throughput_mbps
                    for item in receiver_measurements
                    if item is not None
                ]
                print(
                    f"{run_id}: sender="
                    f"{sum(valid_sender):.3f} Mbps ({len(valid_sender)}/2 valid), "
                    f"receiver={sum(valid_receiver):.3f} Mbps "
                    f"({len(valid_receiver)}/2 valid), "
                    f"egress={egress_mbps:.3f} Mbps, "
                    f"utilization={utilization:.1f}%"
                )
    finally:
        try:
            for process in probes.values():
                stop_probe(process)
            stop_processes(list(servers.values()))
        finally:
            try:
                if net is not None:
                    stop_network(net, qos_enabled=qos_enabled, policy_config=policy_config)
            finally:
                stop_controller(controller, controller_file)
        time.sleep(0.5)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--order", choices=("counterbalanced", "random", "legacy"),
                        default="counterbalanced")
    parser.add_argument("--seed", type=int, help="Recorded scenario ordering seed.")
    parser.add_argument(
        "--config",
        type=Path,
        help="Policy YAML (default: config/traffic_priority.yaml).",
    )
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
    from ryu_topo import ensure_openvswitch

    arguments = parse_arguments()
    policy_config = load_config(arguments.config)
    if arguments.duration < 1:
        raise SystemExit("--duration must be at least 1 second")
    if arguments.repetitions < 1:
        raise SystemExit("--repetitions must be at least 1")
    if arguments.warmup < 0:
        raise SystemExit("--warmup must be non-negative")

    experiment_id = datetime.now(timezone.utc).strftime("experiment-%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
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
    seed = arguments.seed if arguments.seed is not None else random.SystemRandom().randrange(2**32)
    environment = dict(versions, python=sys.version, kernel=platform.release(),
                       platform=platform.platform(), hostname=platform.node(),
                       container=Path("/.dockerenv").exists(),
                       mininet=first_line(["mn", "--version"]),
                       ping=first_line(["ping", "-V"]),
                       tc=first_line(["tc", "-V"]))
    config_bytes = policy_config.source_path.read_bytes()
    snapshot = output_path.with_suffix(".policy.yaml")
    with snapshot.open("xb") as destination:
        destination.write(config_bytes)
    policy_config = load_config(snapshot)
    metadata = {
        "scenario_order": arguments.order, "order_seed": seed,
        "environment_json": json.dumps(environment, sort_keys=True),
        "effective_config_json": json.dumps(asdict(policy_config), default=str, sort_keys=True),
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
    }
    ensure_openvswitch()

    print(f"Writing experiment data to {output_path}")
    with output_path.open("x", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        csv_file.flush()
        schedule = scenario_schedule(configured_scenarios(policy_config),
                                     arguments.repetitions, arguments.order, seed)
        for session_index, (scenario_spec, repetition_numbers) in enumerate(schedule, 1):
            scenario, qos_enabled, policy = scenario_spec
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
                policy_config,
                repetition_numbers=repetition_numbers,
                warmup=arguments.warmup,
                run_metadata=dict(metadata, session_index=session_index),
            )

    print(f"Experiment complete: {output_path}")


if __name__ == "__main__":
    main()
