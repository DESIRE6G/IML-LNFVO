#include <core.p4>
#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#include <tna.p4>
#endif

#include "../../../common-p4/headers.p4"
#include "../../../common-p4/parsers.p4"

struct ingress_metadata_t {
    bit<128> ueid;
    bit<1>   direction; // 0-upstream, 1-downstream
}

struct egress_metadata_t {
}

struct header_t {
    ethernet_t ethernet;
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

    action setUpstreamMode(bit<9> port) {
	ig_md.ueid = hdr.ipv6.srcAddr;
        ig_md.direction = 0;
        ig_tm_md.ucast_egress_port = port;
    }

    action setDownstreamMode(bit<9> port) {
	ig_md.ueid = hdr.ipv6.dstAddr;
        ig_md.direction = 1;
        ig_tm_md.ucast_egress_port = port;
    }

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
            hdr.ipv6.isValid()      : exact; // TODO: L2 traffic? ARP?
        }
        actions = {
            setDownstreamMode;
            setUpstreamMode;
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

    table IsHH {
       key={
            ig_md.ueid: exact;
       }
       actions = {
            setHH;
            NoAction;
       }
       size = 2000;
       default_action = NoAction;

    }

    apply {
        ModeSelector.apply();
        ServiceMapper.apply();
        if (ig_md.direction==1) { //Downstream
                     if (IsHH.apply().hit) {
                        UEMapper.apply();
                     }
                     else {
                        // TODO: Forwarding to a sw implementation with more memory for UEMapping
                     }
        } else {
                     UEMapper.apply();
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

