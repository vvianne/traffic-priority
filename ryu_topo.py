"""Mininet topology for the TrafficPriority shared-bottleneck testbed."""

import os

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController


CONTROLLER_HOST = "127.0.0.1"
CONTROLLER_PORT = 6653
ACCESS_LINK_MBPS = 10
BOTTLENECK_LINK_MBPS = 5


def create_topology():
    """Create two traffic sources and one receiver behind a shared bottleneck."""
    print("Starting Open vSwitch service...")
    if os.system("service openvswitch-switch start") != 0:
        raise RuntimeError("Open vSwitch failed to start")

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

    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")
    s1 = net.addSwitch("s1", protocols="OpenFlow13", failMode="secure")
    s2 = net.addSwitch("s2", protocols="OpenFlow13", failMode="secure")

    print("Creating access links and the shared 5 Mbps bottleneck...")
    net.addLink(h1, s1, bw=ACCESS_LINK_MBPS, delay="1ms")
    net.addLink(h2, s1, bw=ACCESS_LINK_MBPS, delay="1ms")
    net.addLink(
        s1,
        s2,
        bw=BOTTLENECK_LINK_MBPS,
        delay="5ms",
        max_queue_size=100,
        use_htb=True,
    )
    net.addLink(h3, s2, bw=ACCESS_LINK_MBPS, delay="1ms")
    net.addLink(h4, s2, bw=ACCESS_LINK_MBPS, delay="1ms")

    try:
        print("Starting network...")
        net.start()
        if not net.waitConnected(timeout=10):
            raise RuntimeError(
                "Switches did not connect to Ryu at "
                f"{CONTROLLER_HOST}:{CONTROLLER_PORT}"
            )

        print("Network ready; no startup traffic has been generated.")
        print("Expected bottleneck: s1-eth3 <-> s2-eth1 at 5 Mbps.")
        print("Use 'links' and 'sh ovs-ofctl -O OpenFlow13 show s1' to verify ports.")
        print("Use 'h1 ping -c 1 h3' and 'h2 ping -c 1 h3' to verify paths.")
        CLI(net)
    finally:
        print("Stopping network...")
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    create_topology()
