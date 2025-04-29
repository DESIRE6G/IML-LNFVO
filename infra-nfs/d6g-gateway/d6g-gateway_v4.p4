#include <core.p4>
#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#include <tna.p4>
#endif

#include "common/headers.p4"
#include "common/parsers.p4"

#define RXPORT ig_intr_md.ingress_port

struct ingress_metadata_t {
    bit<128> ueid;
    bit<1>   direction; // 0-upstream, 1-downstream
    bit<1>   nffwd;
    bit<16>  icmp_cs_tmp;
}

struct egress_metadata_t {
}

struct header_t {
    ethernet_t ethernet;
    d6gmain_t d6gmain;
    ipv4_t ipv4;
    icmp_t icmp;
    arp_generic_h  arp;
    arp_ipv4_h     arp_ipv4;
}


parser NFIngressParser(
        packet_in pkt,
        out header_t hdr,
        out ingress_metadata_t ig_md,
        out ingress_intrinsic_metadata_t ig_intr_md) {


    TofinoIngressParser() tofino_parser;
    Checksum() csicmp;

    state start {
        tofino_parser.apply(pkt, ig_intr_md);
        ig_md.ueid = 0;
        ig_md.direction = 0;
        ig_md.nffwd = 0;
        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            ETHERTYPE_IPV4: parse_ipv4;
            ETHERTYPE_ARP:  parse_arp;
            ETHERTYPE_D6G:  parse_d6g;
            default: accept;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
        	IPPROTO_ICMP: parse_icmp;
	        default: accept;
        }
    }

    state parse_icmp {
      pkt.extract(hdr.icmp);
      csicmp.subtract(hdr.icmp.checksum);
      csicmp.subtract(hdr.icmp.icmp_type);
      ig_md.icmp_cs_tmp = csicmp.get();
      transition accept;
    }

    state parse_arp {
        pkt.extract(hdr.arp);
        transition select(hdr.arp.htype, hdr.arp.ptype) { //, hdr.arp.hlen, hdr.arp.plen) {
            (ARP_HTYPE_ETHERNET, ARP_PTYPE_IPV4) : parse_arp_ipv4; //, ARP_HLEN_ETHERNET,  ARP_PLEN_IPV4) : parse_arp_ipv4;
            default : accept;
        }
    }

    state parse_arp_ipv4 {
        pkt.extract(hdr.arp_ipv4);
        transition accept;
    }


    state parse_d6g {
        pkt.extract(hdr.d6gmain);
        ig_md.nffwd = 0;
        transition accept;
    }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control NFR(inout header_t hdr,
        inout ingress_metadata_t ig_md,
        inout ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md,
        inout ingress_intrinsic_metadata_for_tm_t ig_tm_md) {

    action drop2() {
        ig_dprsr_md.drop_ctl = ig_dprsr_md.drop_ctl | 0b001;
        exit;
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

    action NFForward(bit<9> port) { // SRC-MAC?
        ig_tm_md.ucast_egress_port = port;
    }

    action NFForwardMAC(bit<9> port, bit<48> dstMAC) { // SRC-MAC?
        ig_tm_md.ucast_egress_port = port;
        hdr.ethernet.dstAddr = dstMAC;
    }

    action NFForwardToExternal(bit<9> port, bit<48> dstMAC) { // SRC-MAC?
        ig_tm_md.ucast_egress_port = port;
        hdr.ethernet.dstAddr = dstMAC;
        hdr.ethernet.etherType = hdr.d6gmain.nextHeader;
        hdr.d6gmain.setInvalid();
    }

    table NFRouter {
       key={
            hdr.d6gmain.serviceId    : exact;
            hdr.d6gmain.locationId   : exact;
            hdr.d6gmain.nextNF       : exact;
       }
       actions = {
           NFForward;NFForwardMAC;NFForwardToExternal;drop2;
       }
       size = 10000;
       default_action = drop2();
    }


    apply {
	if (ig_md.nffwd==1) {
                FWDGExecute.apply();
	}
                NFRouter.apply();
    }
}



control NFIngress(
        inout header_t hdr,
        inout ingress_metadata_t ig_md,
        in ingress_intrinsic_metadata_t ig_intr_md,
        in ingress_intrinsic_metadata_from_parser_t ig_prsr_md,
        inout ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md,
        inout ingress_intrinsic_metadata_for_tm_t ig_tm_md) {

    NFR() nfrouter;

    action drop() {
        ig_dprsr_md.drop_ctl = ig_dprsr_md.drop_ctl | 0b001;
        exit;
    }

/*    action send(bit<9> p) {
        ig_tm_md.ucast_egress_port = p;
        exit;
    }
*/

    action setUpstreamMode4(bit<9> port) {
	ig_md.ueid = (bit<128>) hdr.ipv4.srcAddr;
        ig_md.direction = 0;
        ig_tm_md.ucast_egress_port = port;
    }

    action setDownstreamMode4(bit<9> port) {
	ig_md.ueid = (bit<128>) hdr.ipv4.dstAddr;
        ig_md.direction = 1;
        ig_tm_md.ucast_egress_port = port;
    }

/*    action setUpstreamMode(bit<9> port) {
        ig_md.ueid = hdr.ipv6.srcAddr;
        ig_md.direction = 0;
        ig_tm_md.ucast_egress_port = port;
    }


    action setDownstreamMode(bit<9> port) {
	ig_md.ueid = hdr.ipv6.dstAddr;
        ig_md.direction = 1;
        ig_tm_md.ucast_egress_port = port;
    }
*/
    action setD6GService(bit<16> serviceId, bit<16> nextNF) {
        hdr.d6gmain.serviceId = serviceId;
        hdr.d6gmain.nextNF = nextNF;
        hdr.d6gmain.nextHeader = hdr.ethernet.etherType;
        hdr.ethernet.etherType = ETHERTYPE_D6G;
        hdr.d6gmain.setValid(); 
    }

    action UEMapping(bit<16> locationId) {
        hdr.d6gmain.locationId = locationId;
        hdr.d6gmain.hhFlag = 0;
    }

    action setHH() {
        hdr.d6gmain.hhFlag = 1;
    }

    table ModeSelector {
        key={
            ig_intr_md.ingress_port : exact; 
            hdr.ipv4.isValid()      : exact;
        }
        actions = {
  //          setDownstreamMode;
  //          setUpstreamMode;
            setDownstreamMode4;
            setUpstreamMode4;
            drop;
        }
        size = 1;
        default_action = drop();
    }

    table ServiceMapper {
        key={
            ig_md.direction : exact;
            ig_md.ueid      : lpm;
        }
        actions = {
            setD6GService;
            drop;
        }
        size = 256; 
        default_action = drop();
    }

    table UEMapper {
       key={
            ig_md.ueid: exact; // -> may be reduced by splitting the ip to UE id and using the service id together
       }
       actions = {
            UEMapping;
            drop;
       }
       size = 10000; // table size may be different for upstream and downstream cases - TODO
       default_action = drop();
    }

    action arp_reply(bit<48> my_mac) {
        hdr.ethernet.dstAddr = hdr.arp_ipv4.sha;
        hdr.ethernet.srcAddr = my_mac;
        hdr.arp.oper     = ARP_OPER_REPLY;
        hdr.arp_ipv4.tha = hdr.arp_ipv4.sha;
        bit<32> tmp = hdr.arp_ipv4.tpa;
        hdr.arp_ipv4.tpa = hdr.arp_ipv4.spa;
        hdr.arp_ipv4.sha = my_mac;
        hdr.arp_ipv4.spa = tmp;
	ig_tm_md.ucast_egress_port = RXPORT;
    }

    table arp_responder_v4 {
        key = {
                hdr.arp.oper : exact;
                hdr.arp_ipv4.tpa : exact;
        }
        actions = { drop; arp_reply; }
        size = 1024;
        default_action = drop();
        const entries = {
           (ARP_OPER_REQUEST, 0x0a0a0a0a) : arp_reply(0x0000aaaaaaaa);
        }
    }

    action icmp_reply() {
        //set ICMP type to Echo reply
        hdr.icmp.icmp_type = 0;

        //for checksum calculation this field should be zero
        //hdr.icmp.checksum = 0;

        //swap the source and destination IP addresses
	bit<32> tmp_ip = hdr.ipv4.srcAddr;
        hdr.ipv4.srcAddr = hdr.ipv4.dstAddr;
        hdr.ipv4.dstAddr = tmp_ip;

        //swap the source and destination MAC addresses
        bit<48> tmp_mac = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = hdr.ethernet.srcAddr;
        hdr.ethernet.srcAddr = tmp_mac;

        //send it back to the same port
        ig_tm_md.ucast_egress_port = RXPORT;
        //standard_metadata.egress_spec = standard_metadata.ingress_port;
    }


    // replies to ICMP echo requests if the destination IP matches
    table icmp_responder_v4 {
        key = {
            hdr.ethernet.dstAddr: exact;
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            icmp_reply;
            drop;
        }
        size = 1024;
        default_action = drop();
        const entries = {
          (0x0000aaaaaaaa, 0x0a0a0a0a) : icmp_reply();
        }
    }


    apply {
        if (hdr.arp.isValid()) {
                  arp_responder_v4.apply();
        } else if (hdr.icmp.isValid()) {
		  icmp_responder_v4.apply();
        } else if (!hdr.d6gmain.isValid()) {
           ModeSelector.apply();
           ServiceMapper.apply();
           UEMapper.apply();
	   ig_md.nffwd=1;
	} else {
	   nfrouter.apply(hdr, ig_md, ig_dprsr_md, ig_tm_md);
	}
    }


}

control NFIngressDeparser(
        packet_out pkt,
        inout header_t hdr,
        in ingress_metadata_t ig_md,
        in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md) {

    Checksum() cs;

    apply {
        if (hdr.icmp.isValid()) {
	    hdr.icmp.checksum = cs.update({ hdr.icmp.icmp_type, ig_md.icmp_cs_tmp});
        }
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.arp);
        pkt.emit(hdr.arp_ipv4);
        pkt.emit(hdr.d6gmain);
        pkt.emit(hdr.ipv4);
        pkt.emit(hdr.icmp);
        
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

