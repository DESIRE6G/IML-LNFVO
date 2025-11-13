#include <core.p4>
#if __TARGET_TOFINO__ == 2
#include <t2na.p4>
#else
#ifdef __TARGET_TOFINO__
#include <tna.p4>
#else
#include <v1model.p4>
#endif
#endif

#include "../../common-p4/headers.p4"

#ifdef __TARGET_TOFINO__
#include "../../common-p4/parsers.p4"
#endif

#ifdef __TARGET_TOFINO__
#define RXPORT ig_intr_md.ingress_port
#define TXPORT ig_tm_md.ucast_egress_port
#else
#define RXPORT standard_metadata.ingress_port
#define TXPORT standard_metadata.egress_spec
#endif

struct ingress_metadata_t {
    bit<16> instId;
}

struct header_t {
    ethernet_t ethernet;
    ipv4_t ipv4;
}

parser NFIngressParser(
        packet_in pkt,
        out header_t hdr,
#ifdef __TARGET_TOFINO__
        out ingress_metadata_t meta,
        out ingress_intrinsic_metadata_t ig_intr_md
#else
        inout ingress_metadata_t meta,
        inout standard_metadata_t standard_metadata
#endif
) {

#ifdef __TARGET_TOFINO__
    TofinoIngressParser() tofino_parser;
#endif

    state start {
#ifdef __TARGET_TOFINO__
        tofino_parser.apply(pkt, ig_intr_md);
#endif
        meta.instId = 0;
        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            ETHERTYPE_IPV4:  parse_ipv4;
            //default: reject;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition accept;
    }
}

/*************************************************************************
 **************  I N G R E S S   P R O C E S S I N G   *******************
 *************************************************************************/

#include "af-selector-control.p4"

control NFIngressDeparser(
        packet_out pkt,
#ifdef __TARGET_TOFINO__
        inout header_t hdr,
        in ingress_metadata_t ig_md,
        in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md
#else
        in header_t hdr
#endif
) {

    apply {
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.ipv4);
    }
}

// EGRESS ************************************************************
#ifdef __TARGET_TOFINO__
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

   apply { }
}

control NFEgressDeparser(
        packet_out pkt,
        inout header_t hdr,
        in egress_metadata_t eg_md,
        in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md) {

    apply { }
}

Pipeline(
        NFIngressParser(),
        AFLB(),
        NFIngressDeparser(),
        NFEgressParser(),
        NFEgress(),
        NFEgressDeparser()) pipe;
        Switch(pipe) main;
#else

control MyVerifyChecksum(inout header_t hdr, inout ingress_metadata_t ig_md) {

    apply { }
}

control MyEgress(inout header_t hdr,
                 inout ingress_metadata_t ig_md,
                 inout standard_metadata_t standard_metadata) {

    apply { }
}


control MyComputeChecksum(inout header_t hdr, inout ingress_metadata_t ig_md) {

    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            {
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserv,
                hdr.ipv4.ecn,
                hdr.ipv4.totalLen,
                hdr.ipv4.identification,
                hdr.ipv4._reserved,
                hdr.ipv4.dont_fragment,
                hdr.ipv4.more_fragments,
                hdr.ipv4.fragOffset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                16w0,
                hdr.ipv4.srcAddr,
                hdr.ipv4.dstAddr
            },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16
        );

    }
}

V1Switch(
        NFIngressParser(),
        MyVerifyChecksum(),
        AFLB(),
        MyEgress(),
        MyComputeChecksum(),
        NFIngressDeparser()) main;
#endif
