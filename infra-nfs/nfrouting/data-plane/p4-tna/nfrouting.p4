#include <core.p4>
#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#include <tna.p4>
#endif

#include "../../../common-p4/headers.p4"
#include "../../../common-p4/parsers.p4"

struct ingress_metadata_t {
}

struct egress_metadata_t {
}

struct header_t {
    ethernet_t ethernet;
    evlan_t evlan;
    d6gmain_t d6gmain;
    ipv6_t ipv6;
}

parser NFIngressParser(
        packet_in pkt,
        out header_t hdr,
        out ingress_metadata_t ig_md,
        out ingress_intrinsic_metadata_t ig_intr_md) {


    TofinoIngressParser() tofino_parser;

    state start {
        tofino_parser.apply(pkt, ig_intr_md);
        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            ETHERTYPE_VLAN: parse_evlan;
            ETHERTYPE_IPV6: parse_ipv6;
            ETHERTYPE_D6G:  parse_d6g;
            default: accept;
        }
    }

    state parse_evlan {
  	pkt.extract(hdr.evlan);
        transition select(hdr.evlan.etherType) {
            ETHERTYPE_IPV6: parse_ipv6;
            ETHERTYPE_D6G:  parse_d6g;
            default: accept;
        }
    }

    state parse_ipv6 {
        pkt.extract(hdr.ipv6);
        transition accept;
    }

    state parse_d6g {
        pkt.extract(hdr.d6gmain);

//        transition select(hdr.d6gmain.nextHeader) {
//           ETHERTYPE_IPV6: parse_ipv6;
//        }
        transition accept;
    }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control NFIngress(
        inout header_t hdr,
        inout ingress_metadata_t ig_md,
        in ingress_intrinsic_metadata_t ig_intr_md,
        in ingress_intrinsic_metadata_from_parser_t ig_prsr_md,
        inout ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md,
        inout ingress_intrinsic_metadata_for_tm_t ig_tm_md) {

    action drop() {
        ig_dprsr_md.drop_ctl = ig_dprsr_md.drop_ctl | 0b001;
        exit;
    }

    action PortForward(bit<9> port) {
	ig_tm_md.ucast_egress_port = port;
    }

    action PortForwardAddVLAN(bit<9> port, bit<12> vid) {
	ig_tm_md.ucast_egress_port = port;
	hdr.evlan.etherType = hdr.ethernet.etherType;
	hdr.evlan.vid = vid;
	hdr.ethernet.etherType = ETHERTYPE_VLAN;
	hdr.evlan.setValid();
    }	

    action PortForwardModVLAN(bit<9> port, bit<12> vid) {
	ig_tm_md.ucast_egress_port = port;
	hdr.evlan.vid = vid;
    }	

    action PortForwardAddD6G(bit<16> sid, bit<16> lid, bit<16> nfid) {
	hdr.d6gmain.serviceId = sid;
 	hdr.d6gmain.locationId = lid;
	hdr.d6gmain.nextNF = nfid;
	hdr.d6gmain.nextHeader = hdr.ethernet.etherType;
	hdr.ethernet.etherType = ETHERTYPE_D6G;
	hdr.d6gmain.setValid();
    }


    table PortBasedRouter {
	key = {
		ig_intr_md.ingress_port : exact;
		hdr.evlan.isValid()	: exact;
		hdr.evlan.vid		: exact;
	}
	actions = {
		PortForward;PortForwardAddVLAN;PortForwardModVLAN;PortForwardAddD6G;drop;
	}
	size = 1000;
	default_action = drop();

    }

    action UpdateNF(bit<16> nfid) {
        hdr.d6gmain.nextNF = nfid;
    }

    table FWDGExecute {
	key = {
            hdr.d6gmain.serviceId    : exact;
            hdr.d6gmain.nextNF       : exact;
	}
	actions = {
		NoAction; UpdateNF;
	}
	size = 10000;
	default_action = NoAction();
    }

    action NFForward(bit<9> port, bit<48> dstMAC) { // SRC-MAC?
	ig_tm_md.ucast_egress_port = port;
	hdr.ethernet.dstAddr = dstMAC;
    }

    action NFForwardToExternal(bit<9> port, bit<48> dstMAC) { // SRC-MAC?
	ig_tm_md.ucast_egress_port = port;
	hdr.ethernet.dstAddr = dstMAC;
	hdr.ethernet.etherType =hdr.d6gmain.nextHeader;
	hdr.d6gmain.setInvalid();
    }

    table NFRouter {
       key={
            hdr.d6gmain.serviceId    : exact;
            hdr.d6gmain.locationId   : exact;
            hdr.d6gmain.nextNF       : exact;
       }
       actions = {
           NFForward;NFForwardToExternal;drop;
       }
       size = 10000;
       default_action = drop();
    }


    apply {
	if (hdr.d6gmain.isValid()) {
		FWDGExecute.apply();
//	} else {
//		PortBasedRouter.apply();
//	}
//	if (hdr.d6gmain.isValid()) {
		NFRouter.apply();
	}
    }


}

control NFIngressDeparser(
        packet_out pkt,
        inout header_t hdr,
        in ingress_metadata_t ig_md,
        in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md) {



    apply {
        pkt.emit(hdr.ethernet);
	pkt.emit(hdr.evlan);
        pkt.emit(hdr.d6gmain);
        pkt.emit(hdr.ipv6);
    }
}


// EGRESS ************************************************************

parser NFEgressParser(
        packet_in pkt,
        out header_t hdr,
        out egress_metadata_t eg_md,
        out egress_intrinsic_metadata_t eg_intr_md) {

    TofinoEgressParser() tofino_parser;

    state start {
        tofino_parser.apply(pkt, eg_intr_md);
        transition accept;
    }

}


control NFEgress(
        inout header_t hdr,
        inout egress_metadata_t eg_md,
        in egress_intrinsic_metadata_t eg_intr_md,
        in egress_intrinsic_metadata_from_parser_t eg_intr_from_prsr,
        inout egress_intrinsic_metadata_for_deparser_t eg_intr_md_for_dprsr,
        inout egress_intrinsic_metadata_for_output_port_t eg_intr_md_for_oport) {

   apply {}

}

control NFEgressDeparser(
        packet_out pkt,
        inout header_t hdr,
        in egress_metadata_t eg_md,
        in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md) {

apply {}

}

Pipeline(NFIngressParser(),
         NFIngress(),
         NFIngressDeparser(),
         NFEgressParser(),
         NFEgress(),
         NFEgressDeparser()) pipe;

Switch(pipe) main;


