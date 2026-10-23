"""Ryu controller for contextual forwarding and traffic classification."""

import os

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ether_types, ethernet, ipv4, packet, tcp, udp
from ryu.ofproto import ofproto_v1_3

from openflow_utils import has_usable_buffer_id
from policy_config import load_config
from traffic_policy import transport_match_fields


FORWARDING_PRIORITY = 10


def environment_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class PriorityApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PriorityApp, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.policy_config = load_config()
        best_effort = self.policy_config.traffic_class("best_effort")
        self.default_queue_id = best_effort.queue_id
        self.qos_enabled = environment_flag("QOS_ENABLED")
        self.qos_datapath = int(
            os.getenv(
                "QOS_DATAPATH", str(self.policy_config.network.qos_datapath)
            ),
            0,
        )
        self.qos_egress_port = int(
            os.getenv(
                "QOS_EGRESS_PORT", str(self.policy_config.network.qos_egress_port)
            ),
            0,
        )
        self.logger.info(
            "QoS mode %s for datapath=%s out_port=%s config=%s adaptive=%s",
            "enabled" if self.qos_enabled else "disabled",
            self.qos_datapath,
            self.qos_egress_port,
            self.policy_config.source_path,
            "enabled" if self.policy_config.adaptive_qos.enabled else "disabled",
        )

    def output_actions(self, parser, datapath_id, out_port, queue_id):
        """Set a queue only on the configured bottleneck egress."""
        actions = []
        if self.uses_qos_output(datapath_id, out_port):
            actions.append(parser.OFPActionSetQueue(queue_id))
        actions.append(parser.OFPActionOutput(out_port))
        return actions

    def uses_qos_output(self, datapath_id, out_port):
        """Return whether this output is governed by the OVS queue policy."""
        return (
            self.qos_enabled
            and datapath_id == self.qos_datapath
            and out_port == self.qos_egress_port
        )

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("Default flow installed on datapath %s", datapath.id)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions,
            )
        ]
        flow = {
            "datapath": datapath,
            "priority": priority,
            "match": match,
            "instructions": instructions,
        }
        if has_usable_buffer_id(buffer_id, ofproto.OFP_NO_BUFFER):
            flow["buffer_id"] = buffer_id
        datapath.send_msg(parser.OFPFlowMod(**flow))

    @staticmethod
    def contextual_match(parser, pkt, eth, in_port):
        """Build a learned-flow match that cannot hide another IP protocol."""
        fields = {
            "in_port": in_port,
            "eth_src": eth.src,
            "eth_dst": eth.dst,
            "eth_type": eth.ethertype,
        }
        ip_header = pkt.get_protocol(ipv4.ipv4)
        if ip_header is not None:
            fields.update(
                {
                    "ipv4_src": ip_header.src,
                    "ipv4_dst": ip_header.dst,
                    "ip_proto": ip_header.proto,
                }
            )
            tcp_header = pkt.get_protocol(tcp.tcp)
            if tcp_header is not None:
                fields.update(
                    {
                        "tcp_src": tcp_header.src_port,
                        "tcp_dst": tcp_header.dst_port,
                    }
                )
            udp_header = pkt.get_protocol(udp.udp)
            if udp_header is not None:
                fields.update(transport_match_fields(
                    "udp", udp_header.src_port, udp_header.dst_port
                ))
        return parser.OFPMatch(**fields)

    @staticmethod
    def classified_transport_match(parser, eth, ip_header, header, in_port, protocol):
        """Match one directed TCP or UDP flow with explicit context."""
        return parser.OFPMatch(
            in_port=in_port,
            eth_src=eth.src,
            eth_dst=eth.dst,
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=ip_header.src,
            ipv4_dst=ip_header.dst,
            **transport_match_fields(protocol, header.src_port, header.dst_port),
        )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth.src] = in_port

        out_port = self.mac_to_port[dpid].get(
            eth.dst,
            ofproto.OFPP_FLOOD,
        )
        ip_header = pkt.get_protocol(ipv4.ipv4)
        tcp_header = pkt.get_protocol(tcp.tcp)
        udp_header = pkt.get_protocol(udp.udp)
        header = tcp_header or udp_header
        protocol = "tcp" if tcp_header is not None else "udp"
        policy = None
        if ip_header is not None and header is not None:
            policy = self.policy_config.classify(protocol, header.dst_port)

        queue_id = policy.queue_id if policy is not None else self.default_queue_id
        actions = self.output_actions(parser, dpid, out_port, queue_id)

        if out_port != ofproto.OFPP_FLOOD:
            if policy is not None:
                match = self.classified_transport_match(
                    parser,
                    eth,
                    ip_header,
                    header,
                    in_port,
                    protocol,
                )
                priority = policy.flow_priority
                self.logger.info(
                    "Classified %s traffic: datapath=%s in_port=%s "
                    "out_port=%s queue_id=%s match=%s",
                    policy.name,
                    dpid,
                    in_port,
                    out_port,
                    (
                        queue_id
                        if self.uses_qos_output(dpid, out_port)
                        else "not-applied"
                    ),
                    match,
                )
            else:
                match = self.contextual_match(parser, pkt, eth, in_port)
                priority = FORWARDING_PRIORITY

            self.add_flow(
                datapath,
                priority,
                match,
                actions,
                msg.buffer_id,
            )
            if has_usable_buffer_id(msg.buffer_id, ofproto.OFP_NO_BUFFER):
                return

        data = (
            None
            if has_usable_buffer_id(msg.buffer_id, ofproto.OFP_NO_BUFFER)
            else msg.data
        )
        packet_out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(packet_out)
