"""Owned OVS HTB lifecycle and verification, independent of Mininet."""

import argparse
import json
import re
import subprocess
import time

from policy_config import load_config


OWNER = "traffic-priority"


def verify_flow_actions(output, queues, egress_port, differentiated):
    """Validate queue actions on installed bottleneck flows after traffic."""
    selected = [line for line in output.splitlines()
                if re.search(r"output:{}(?:,|$)".format(egress_port), line)]
    if not selected:
        raise RuntimeError("No installed bottleneck forwarding flows to verify")
    for line in selected:
        actions = line.split("actions=", 1)[-1]
        ids = [int(value) for value in re.findall(r"set_queue:(\d+)", actions)]
        if differentiated and (len(ids) != 1 or ids[0] not in queues):
            raise RuntimeError("Static flow has missing or invalid queue selection")
        if not differentiated and ids:
            raise RuntimeError("Baseline flow unexpectedly selects a differentiated queue")


def command(arguments):
    return subprocess.check_output(arguments, text=True).strip()


def ovs(*arguments):
    return command(["ovs-vsctl"] + list(arguments))


def scalar(table, record, column):
    return ovs("get", table, record, column).strip('[]"')


def queue_policy(config, differentiated):
    if not differentiated:
        return {0: (config.network.bottleneck_bps, config.network.bottleneck_bps)}
    return {
        item.queue_id: (item.min_rate_bps, item.max_rate_bps)
        for item in config.traffic_classes
    }


def cleanup(port):
    """Delete only the attached owned policy and its unshared owned queues."""
    if not ovs("--if-exists", "get", "Port", port, "name"):
        return
    qos_id = scalar("Port", port, "qos")
    if not qos_id:
        return
    if scalar("QoS", qos_id, "external_ids:owner") != OWNER:
        raise RuntimeError("Refusing to remove an unrelated QoS policy on " + port)
    # OVSDB JSON preserves map values without relying on display formatting.
    document = json.loads(ovs("--format=json", "--columns=queues", "list", "QoS", qos_id))
    queues = [value[1] for _, value in document["data"][0][0][1]]
    ports = ovs("--data=bare", "--no-heading", "--columns=name", "find", "Port", "qos=" + qos_id)
    if ports.splitlines() != [port]:
        raise RuntimeError("Refusing to delete a shared QoS policy")
    ovs("--", "clear", "Port", port, "qos", "--", "destroy", "QoS", qos_id)
    for queue_id in queues:
        if scalar("Queue", queue_id, "external_ids:owner") != OWNER:
            continue
        # A referenced queue must never be destroyed. Inspect maps explicitly.
        maps = json.loads(ovs("--format=json", "--columns=queues", "list", "QoS"))
        referenced = any(
            value[1] == queue_id
            for row in maps["data"] for _, value in row[0][1]
        )
        if not referenced:
            ovs("--if-exists", "destroy", "Queue", queue_id)


def verify_kernel(qdisc_output, class_output, capacity, queues):
    """Check Linux HTB rates (tc JSON reports rates in bytes per second)."""
    roots = [item for item in json.loads(qdisc_output) if item.get("root")]
    if len(roots) != 1 or roots[0]["kind"] != "htb":
        raise RuntimeError("Expected exactly one HTB root qdisc")
    classes = json.loads(class_output)
    root = next((item for item in classes if item.get("root")), None)
    if root is None:
        # tc versions may describe the root class using parent=1:.
        root = next((item for item in classes if item.get("handle") == "1:fffe"), None)
    if root is None or root["options"].get("rate", -1) * 8 != capacity or root["options"].get("ceil", -1) * 8 != capacity:
        raise RuntimeError("Kernel parent rate differs from configured capacity")
    for queue_id, (minimum, maximum) in queues.items():
        handle = "1:{:x}".format(queue_id + 1)
        item = next((item for item in classes if item.get("handle") == handle), None)
        if item is None:
            raise RuntimeError("Kernel queue class missing: " + handle)
        options = item["options"]
        if options.get("rate", -1) * 8 != minimum or options.get("ceil", -1) * 8 != maximum:
            raise RuntimeError("Kernel queue rates differ for " + handle)


def verify(config, differentiated):
    network = config.network
    qos_id = scalar("Port", network.qos_egress_interface, "qos")
    if not qos_id or scalar("QoS", qos_id, "type") != "linux-htb":
        raise RuntimeError("Missing linux-htb port attachment")
    if scalar("QoS", qos_id, "other_config:max-rate") != str(network.bottleneck_bps):
        raise RuntimeError("OVS parent capacity mismatch")
    expected = queue_policy(config, differentiated)
    document = json.loads(ovs("--format=json", "--columns=queues", "list", "QoS", qos_id))
    actual = dict(document["data"][0][0][1])
    if set(actual) != set(expected):
        raise RuntimeError("OVS queue IDs differ from policy")
    for queue_id, (minimum, maximum) in expected.items():
        record = actual[queue_id][1]
        if (
            scalar("Queue", record, "other_config:min-rate") != str(minimum)
            or scalar("Queue", record, "other_config:max-rate") != str(maximum)
        ):
            raise RuntimeError("OVS queue rate mismatch")
    verify_kernel(
        command(["tc", "-j", "qdisc", "show", "dev", network.qos_egress_interface]),
        command(["tc", "-j", "class", "show", "dev", network.qos_egress_interface]),
        network.bottleneck_bps, expected,
    )


def setup(config, differentiated):
    network = config.network
    port = network.qos_egress_interface
    if ovs("port-to-br", port) != network.qos_bridge:
        raise RuntimeError("Configured egress belongs to another bridge")
    queues = queue_policy(config, differentiated)
    if any(queue_id > 61439 for queue_id in queues):
        raise ValueError("linux-htb queue IDs must be between 0 and 61439")
    cleanup(port)
    roots = json.loads(command(["tc", "-j", "qdisc", "show", "dev", port]))
    if any(item.get("root") and item["kind"] != "noqueue" for item in roots):
        raise RuntimeError("Competing root qdisc on " + port)
    arguments = ["--", "set", "Port", port, "qos=@qos", "--", "--id=@qos", "create", "QoS",
                 "type=linux-htb", "other-config:max-rate=" + str(network.bottleneck_bps),
                 "external_ids:owner=" + OWNER]
    arguments += ["queues:{}=@q{}".format(key, key) for key in queues]
    for key, (minimum, maximum) in queues.items():
        arguments += ["--", "--id=@q" + str(key), "create", "Queue",
                      "external_ids:owner=" + OWNER,
                      "other-config:min-rate=" + str(minimum),
                      "other-config:max-rate=" + str(maximum)]
    ovs(*arguments)
    try:
        for attempt in range(20):
            try:
                verify(config, differentiated)
                print("Verified OVS and kernel HTB policy on " + port)
                return
            except RuntimeError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
    except Exception:
        cleanup(port)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "cleanup", "verify"))
    parser.add_argument("--config")
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.action == "cleanup":
        cleanup(config.network.qos_egress_interface)
    else:
        globals()[args.action](config, args.static)
