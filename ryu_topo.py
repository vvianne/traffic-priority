"""Mininet topology for the TrafficPriority shared-bottleneck testbed."""

import argparse
import os
from pathlib import Path
import subprocess

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from policy_config import load_config
from ovs_qos import setup as setup_ovs_qos, cleanup as cleanup_ovs_qos


CONTROLLER_HOST = "127.0.0.1"
CONTROLLER_PORT = 6653
ACCESS_LINK_MBPS = 10
BOTTLENECK_LINK_MBPS = 5
QOS_EGRESS_PORT = "s1-eth3"
SCRIPT_DIRECTORY = Path(__file__).resolve().parent / "scripts"


def qos_script(name, policy_config, check=True):
    """Run a repository-owned QoS lifecycle script for the bottleneck port."""
    network = policy_config.network
    command = [
        str(SCRIPT_DIRECTORY / name),
        network.qos_egress_interface,
        network.qos_bridge,
    ]
    if name == "setup_qos.sh":
        best_effort = policy_config.traffic_class("best_effort")
        high_priority = policy_config.traffic_class("high_priority")
        command.extend(
            str(value)
            for value in (
                network.bottleneck_bps,
                best_effort.queue_id,
                best_effort.min_rate_bps,
                best_effort.max_rate_bps,
                high_priority.queue_id,
                high_priority.min_rate_bps,
                high_priority.max_rate_bps,
            )
        )
    return subprocess.run(
        command,
        check=check,
    )


def ensure_openvswitch():
    """Start the Open vSwitch service required by Mininet."""
    print("Starting Open vSwitch service...")
    if os.system("service openvswitch-switch start") != 0:
        raise RuntimeError("Open vSwitch failed to start")


def build_network(qos_enabled=False, policy_config=None):
    """Build, but do not start, the shared-bottleneck network."""
    policy_config = policy_config or load_config()
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
    )

    print("Adding controller, hosts, and OpenFlow 1.3 switches...")
    net.addController(
        "c1",
        controller=RemoteController,
        ip=CONTROLLER_HOST,
        port=CONTROLLER_PORT,
    )

    access_link_mbps = policy_config.network.access_link_mbps
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")
    s1 = net.addSwitch("s1", protocols="OpenFlow13", failMode="secure")
    s2 = net.addSwitch("s2", protocols="OpenFlow13", failMode="secure")

    print("Creating access links and the shared 5 Mbps bottleneck...")
    net.addLink(h1, s1, bw=access_link_mbps, delay="1ms")
    net.addLink(h2, s1, bw=access_link_mbps, delay="1ms")
    # Both modes leave the root qdisc to OVS; only queue allocation differs.
    net.addLink(s1, s2)
    net.addLink(h3, s2, bw=access_link_mbps, delay="1ms")
    net.addLink(h4, s2, bw=access_link_mbps, delay="1ms")
    return net


def start_network(net, qos_enabled=False, policy_config=None):
    """Start the network, wait for Ryu, and apply the selected policy."""
    policy_config = policy_config or load_config()
    print("Starting network...")
    net.start()
    if not net.waitConnected(timeout=10):
        raise RuntimeError(
            "Switches did not connect to Ryu at "
            f"{CONTROLLER_HOST}:{CONTROLLER_PORT}"
        )

    setup_ovs_qos(policy_config, differentiated=qos_enabled)


def stop_network(net, qos_enabled=False, policy_config=None):
    """Remove repository-owned QoS state and stop the network."""
    policy_config = policy_config or load_config()
    try:
        cleanup_ovs_qos(policy_config.network.qos_egress_interface)
    finally:
        print("Stopping network...")
        net.stop()


def create_topology(qos_enabled=False, policy_config=None):
    """Create two traffic sources and one receiver behind a shared bottleneck."""
    policy_config = policy_config or load_config()
    ensure_openvswitch()
    net = build_network(qos_enabled=qos_enabled, policy_config=policy_config)

    try:
        start_network(net, qos_enabled=qos_enabled, policy_config=policy_config)

        print("Network ready; no startup traffic has been generated.")
        print(
            "Expected bottleneck: {} <-> s2-eth1 at {} Mbps.".format(
                policy_config.network.qos_egress_interface,
                policy_config.network.bottleneck_mbps,
            )
        )
        print("Policy configuration: {}.".format(policy_config.source_path))
        print("QoS mode: {}.".format("enabled" if qos_enabled else "disabled"))
        print("Use 'links' and 'sh ovs-ofctl -O OpenFlow13 show s1' to verify ports.")
        print("Use 'h1 ping -c 1 h3' and 'h2 ping -c 1 h3' to verify paths.")
        CLI(net)
    finally:
        stop_network(net, qos_enabled=qos_enabled, policy_config=policy_config)


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument(
        "--qos",
        action="store_true",
        help="Attach the OVS HTB queue policy to the bottleneck egress.",
    )
    argument_parser.add_argument(
        "--config",
        type=Path,
        help="Policy YAML (default: config/traffic_priority.yaml).",
    )
    arguments = argument_parser.parse_args()
    setLogLevel("info")
    create_topology(
        qos_enabled=arguments.qos,
        policy_config=load_config(arguments.config),
    )
