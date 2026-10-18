"""Ryu controller for contextual forwarding and traffic classification."""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ether_types, ethernet, ipv4, packet, tcp
from ryu.ofproto import ofproto_v1_3

from openflow_utils import has_usable_buffer_id
from traffic_policy import classify_tcp_destination_port


FORWARDING_PRIORITY = 10


class PriorityApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PriorityApp, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

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
        return parser.OFPMatch(**fields)

    @staticmethod
    def classified_tcp_match(parser, eth, ip_header, tcp_header, in_port):
        """Match one directed TCP flow with explicit forwarding context."""
        return parser.OFPMatch(
            in_port=in_port,
            eth_src=eth.src,
            eth_dst=eth.dst,
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=ip_header.src,
            ipv4_dst=ip_header.dst,
            ip_proto=6,
            tcp_src=tcp_header.src_port,
            tcp_dst=tcp_header.dst_port,
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
        actions = [parser.OFPActionOutput(out_port)]

        ip_header = pkt.get_protocol(ipv4.ipv4)
        tcp_header = pkt.get_protocol(tcp.tcp)
        policy = None
        if ip_header is not None and tcp_header is not None:
            policy = classify_tcp_destination_port(tcp_header.dst_port)

        if out_port != ofproto.OFPP_FLOOD:
            if policy is not None:
                match = self.classified_tcp_match(
                    parser,
                    eth,
                    ip_header,
                    tcp_header,
                    in_port,
                )
                priority = policy.flow_priority
                self.logger.info(
                    "Classified %s traffic: datapath=%s in_port=%s "
                    "out_port=%s match=%s",
                    policy.name,
                    dpid,
                    in_port,
                    out_port,
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
