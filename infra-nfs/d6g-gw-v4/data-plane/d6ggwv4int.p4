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
/*
const bit<16> ETHERTYPE_TPID   = 0x8100;
const bit<16> ETHERTYPE_IPV4   = 0x0800;
const bit<16> ETHERTYPE_IPV6   = 0x86DD;
const bit<16> ETHERTYPE_TO_CPU = 0xBF01;
const bit<16> ETHERTYPE_D6GINT = 0xDF01;
const bit<16> ETHERTYPE_D6GMAIN = 0xD6D6;
*/
/*
 * Portable Types for PortId and MirrorID that do not depend on the target
 */
typedef bit<16> P_PortId_t;
typedef bit<16> P_MirrorId_t;
typedef bit<8>  P_QueueId_t;

#if __TARGET_TOFINO__ == 1
typedef bit<7> PortId_Pad_t;
typedef bit<6> MirrorId_Pad_t;
typedef bit<3> QueueId_Pad_t;
#define MIRROR_DEST_TABLE_SIZE 256
#elif __TARGET_TOFINO__ == 2
typedef bit<7> PortId_Pad_t;
typedef bit<8> MirrorId_Pad_t;
typedef bit<1> QueueId_Pad_t;
#define MIRROR_DEST_TABLE_SIZE 256
#else
#error Unsupported Tofino target
#endif

typedef bit<48> D6G_Timestamp_t;


/*** Internal Headers Used with Mirroring ***/
typedef bit<4> header_type_t;
typedef bit<4> header_info_t;

const header_type_t HEADER_TYPE_BRIDGE         = 0xB;
const header_type_t HEADER_TYPE_MIRROR_INGRESS = 0xC;
const header_type_t HEADER_TYPE_MIRROR_EGRESS  = 0xD;
const header_type_t HEADER_TYPE_RESUBMIT       = 0xA;

#define INTERNAL_HEADER         \
    header_type_t header_type;  \
    header_info_t header_info


header clock_sync_h {
    bit<8> count;
    D6G_Timestamp_t t0;
    D6G_Timestamp_t t1;
    D6G_Timestamp_t t2;
    D6G_Timestamp_t t3;
}

header inthdr_h {
    INTERNAL_HEADER;
}

/* Bridged metadata */
header bridge_h {
    INTERNAL_HEADER;
#ifdef FLEXIBLE_HEADERS
    @flexible bit<4>    d6gint_count;
#else
    @padding bit<4> pad0;   bit<4>  d6gint_count;
#endif
}

/* mirroring types */
const MirrorType_t ING_PORT_MIRROR = 3;
const MirrorType_t EGR_PORT_MIRROR = 5;


/* Bridged metadata for ingress mirrored packets */
header ing_port_mirror_h {
    INTERNAL_HEADER;

#ifdef FLEXIBLE_HEADERS
    @flexible  MirrorId_t  mirror_session;
    @flexible  D6G_Timestamp_t     t3;

#else
    @padding MirrorId_Pad_t  pad0;  MirrorId_t  mirror_session;        /*  2 */
                                    D6G_Timestamp_t     t3;
#endif
}

/* Bridged metadata for egress mirrored packets */
header egr_port_mirror_h {
    INTERNAL_HEADER;                                                  /* 1 */

#ifdef FLEXIBLE_HEADERS
    @flexible  MirrorId_t  mirror_session;
    @flexible bit<48> t1;
    @flexible bit<48> t2;
#else
    @padding MirrorId_Pad_t  pad0;  MirrorId_t  mirror_session;        /*  2 */
                                    bit<48>     t1;
                                    bit<48>     t2;

#endif
}


struct ingress_metadata_t {
    bit<32> ueid;
    bit<1>  direction; // 0-upstream, 1-downstream
#ifdef __TARGET_TOFINO__
    bit<16> icmp_cs_tmp;
    header_type_t  mirror_header_type;
    header_info_t  mirror_header_info;
    MirrorId_t     mirror_session;
#endif
    D6G_Timestamp_t        t3;
    bit<8>                 tstamp_slot;
}


struct header_t {
//  bridge_h            bridge;
    ethernet_t          ethernet;
    clock_sync_h        clock_sync;
    d6gmain_t           d6gmain;
    d6gint_t            d6gint;
    ipv4_t              ipv4;
    icmp_t              icmp;
    arp_generic_h       arp;
    arp_ipv4_h          arp_ipv4;
}

#include "../../nfrouter/data-plane/nfr-control.p4"
#include "../../ue2servicemapper/data-plane/ue2sm-control.p4"
#include "./clock_sync.p4"

parser NFIngressParser(
        packet_in pkt,
        out header_t hdr,
#ifdef __TARGET_TOFINO__
        out ingress_metadata_t ig_md,
        out ingress_intrinsic_metadata_t ig_intr_md
#else
        inout ingress_metadata_t ig_md,
        inout standard_metadata_t standard_metadata
#endif
) {

#ifdef __TARGET_TOFINO__
    TofinoIngressParser() tofino_parser;
    Checksum() csicmp;
#endif

    state start {
#ifdef __TARGET_TOFINO__
        tofino_parser.apply(pkt, ig_intr_md);
#endif
        ig_md.ueid = 0;
        ig_md.direction = 0;
        transition init_bridge_and_meta;
    }

    state init_bridge_and_meta {
        ig_md.mirror_header_type = 0;
        ig_md.mirror_header_info = 0;
        ig_md.mirror_session = 0;
        ig_md.tstamp_slot = 0;
        ig_md.t3 = 0;

//        hdr.bridge.setValid();
//        hdr.bridge.header_type  = HEADER_TYPE_BRIDGE;
//        hdr.bridge.header_info  = 0;

        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            ETHERTYPE_IPV4:             parse_ipv4;
            ETHERTYPE_ARP:              parse_arp;
            ETHERTYPE_D6G:              parse_d6g;
            ETHERTYPE_CLOCK_SYNC:       parse_clock_sync;
            default:                    accept;
        }
    }

    state parse_clock_sync{
        pkt.extract(hdr.clock_sync);
        transition accept;
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
#ifdef __TARGET_TOFINO__
        csicmp.subtract(hdr.icmp.checksum);
        csicmp.subtract(hdr.icmp.icmp_type);
        ig_md.icmp_cs_tmp = csicmp.get();
#endif
        transition accept;
    }

    state parse_arp {
        pkt.extract(hdr.arp);
        transition select(hdr.arp.htype, hdr.arp.ptype) {
            (ARP_HTYPE_ETHERNET, ARP_PTYPE_IPV4) : parse_arp_ipv4;
            default : accept;
        }
    }

    state parse_arp_ipv4 {
        pkt.extract(hdr.arp_ipv4);
        transition accept;
    }

    state parse_d6g {
        pkt.extract(hdr.d6gmain);
        transition select(hdr.d6gmain.nextHeader){
            ETHERTYPE_D6GINT: parse_d6gint;
            ETHERTYPE_CLOCK_SYNC: parse_clock_sync;
            default: accept;
        }
    }

    state parse_d6gint{
        pkt.extract(hdr.d6gint);
        transition accept;
    }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control NFIngress(
        inout header_t hdr,
        inout ingress_metadata_t meta,
#ifdef __TARGET_TOFINO__
        in ingress_intrinsic_metadata_t ig_intr_md,
        in ingress_intrinsic_metadata_from_parser_t ig_prsr_md,
        inout ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md,
        inout ingress_intrinsic_metadata_for_tm_t ig_tm_md
#else
        inout standard_metadata_t standard_metadata
#endif
) {

    NFR() nfrouter_sw1;
    NFR() nfrouter_sw2;
    UE2SM() ue2servicemapper_sw2;
    // a table for synchronising tofino and UE timestamps
    ClockSync() ctrl_clock_sync_sw1;


    action drop() {
#ifdef __TARGET_TOFINO__
        ig_dprsr_md.drop_ctl = ig_dprsr_md.drop_ctl | 0b001;
#else
        mark_to_drop(standard_metadata);
#endif
        exit;
    }

    action skip_egress(){
        ig_tm_md.bypass_egress = 1;
//        hdr.bridge.setInvalid();
    }

    action arp_reply(bit<48> my_mac) {
        hdr.ethernet.dstAddr = hdr.arp_ipv4.sha;
        hdr.ethernet.srcAddr = my_mac;
        hdr.arp.oper = ARP_OPER_REPLY;
        hdr.arp_ipv4.tha = hdr.arp_ipv4.sha;

        bit<32> tmp = hdr.arp_ipv4.tpa;
        hdr.arp_ipv4.tpa = hdr.arp_ipv4.spa;
        hdr.arp_ipv4.sha = my_mac;
        hdr.arp_ipv4.spa = tmp;
	    TXPORT = RXPORT;
    }

    table arp_responder_v4 {
        key = {
            hdr.arp.oper : exact;
            hdr.arp_ipv4.tpa : exact;
        }
        actions = { NoAction; arp_reply; }
        size = 1024;
        default_action = NoAction();
    }

    action icmp_reply() {
        hdr.icmp.icmp_type = 0;

        bit<32> tmp_ip = hdr.ipv4.srcAddr;
        hdr.ipv4.srcAddr = hdr.ipv4.dstAddr;
        hdr.ipv4.dstAddr = tmp_ip;

        bit<48> tmp_mac = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = hdr.ethernet.srcAddr;
        hdr.ethernet.srcAddr = tmp_mac;

        TXPORT = RXPORT;
    }

    table icmp_responder_v4 {
        key = {
            hdr.ethernet.dstAddr: exact;
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            icmp_reply;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    action do_d6gint_update_t1() {
        hdr.d6gint.t1 = ig_intr_md.ingress_mac_tstamp;
        skip_egress();
    }

    action do_d6gint_update_t2() {
        hdr.d6gint.t2 = ig_intr_md.ingress_mac_tstamp;
        skip_egress();
    }

action do_d6gint_update_t3_and_send_report(MirrorId_t mirror_session){
        meta.t3 = ig_intr_md.ingress_mac_tstamp;
        ig_dprsr_md.mirror_type = ING_PORT_MIRROR;
        hdr.d6gmain.nextHeader = hdr.d6gint.next_header;
        hdr.d6gint.setInvalid();
        skip_egress();

#ifndef P4C_3876_FIXED
        #if __TARGET_TOFINO__ > 1
        ig_dprsr_md.mirror_io_select = 1;
        #endif
#endif
        meta.mirror_header_type     = HEADER_TYPE_MIRROR_INGRESS;
        meta.mirror_header_info     = (header_info_t) ING_PORT_MIRROR;
        meta.mirror_session         = mirror_session;
    }

    /* This table is used to check where to insert the timestamp */
    table tb_d6gint_handler_sw1 {
        key = {
            hdr.d6gmain.serviceId : ternary;
        }
        actions = {
            do_d6gint_update_t1;
            do_d6gint_update_t2;
            NoAction;
        }
        size = 512;
        default_action = NoAction();
    }

    /* This table is used to check where to insert the timestamp */
    table tb_d6gint_handler_sw2 {
        key = {
            hdr.d6gmain.serviceId : ternary;
        }
        actions = {
            do_d6gint_update_t1;
            do_d6gint_update_t2;
            do_d6gint_update_t3_and_send_report;
            NoAction;
        }
        size = 512;
        default_action = NoAction();
    }




#define SW1_1 156
#define SW1_2 188

#define SW2_1 8
#define SW2_2 16
#define SW2_3 32


    action _switch_1() {
    }

    action _switch_2() {
    }

    table switch_selector {
        key = {RXPORT : exact;}
        actions = {_switch_1; _switch_2; drop();}
        size = 5;
        default_action = drop();
        const entries = {
	  SW1_1 : _switch_1();
	  SW1_2 : _switch_1();
	  SW2_1 : _switch_2();
	  SW2_2 : _switch_2();
	  SW2_3 : _switch_2();
	}
    }


    apply {
        if (hdr.clock_sync.isValid() ){
            ctrl_clock_sync_sw1.apply(hdr, ig_intr_md, ig_tm_md);
            exit;
        }

        switch ( switch_selector.apply().action_run) {
            _switch_2: { // Emulating switch 2

            if (hdr.arp_ipv4.isValid()) {
                arp_responder_v4.apply();
                skip_egress();
                exit;
            }
            if (hdr.icmp.isValid()) {
                icmp_responder_v4.apply();
                skip_egress();
                exit;
            }
              bool skipEg = true;
            if (hdr.d6gint.isValid() ){
                    tb_d6gint_handler_sw2.apply();
                    skipEg = false;
            }
            ue2servicemapper_sw2.apply(hdr, meta, ig_intr_md, ig_dprsr_md, ig_tm_md);
            nfrouter_sw2.apply(hdr, meta, ig_intr_md, ig_dprsr_md, ig_tm_md);
              if (skipEg) {
                    skip_egress();
              }
            }
            _switch_1: { // Emulating switch 1
            nfrouter_sw1.apply(hdr, meta, ig_intr_md, ig_dprsr_md, ig_tm_md);
            if (hdr.d6gint.isValid() ){
                tb_d6gint_handler_sw1.apply();
          } else {
                skip_egress();
          }
            }
        }

    }
}


#ifdef FLEXIBLE_HEADERS
#define PAD(field)  field
#else
#define PAD(field)  0, field
#endif

control NFIngressDeparser(
        packet_out pkt,
#ifdef __TARGET_TOFINO__
        inout header_t hdr,
        in ingress_metadata_t meta,
        in ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md
#else
        in header_t hdr
#endif
) {
#ifdef __TARGET_TOFINO__
    Checksum() cs;
    Mirror() ing_port_mirror;
#endif

    apply {
#ifdef __TARGET_TOFINO__
        if (hdr.icmp.isValid()) {
	        hdr.icmp.checksum = cs.update(
                {
                    hdr.icmp.icmp_type, meta.icmp_cs_tmp
                });
        }

        /*
         * If there is a mirror request, create a clone.
         * Note: Mirror() externs emits the provided header, but also
         * appends the ORIGINAL ingress packet after those
         */
        if (ig_dprsr_md.mirror_type == ING_PORT_MIRROR) {
            ing_port_mirror.emit<ing_port_mirror_h>(
                meta.mirror_session,
                {
                    meta.mirror_header_type,
                    meta.mirror_header_info,
                    PAD(meta.mirror_session),
                    meta.t3
                });

        }
#endif

//        pkt.emit(hdr.bridge);
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.d6gmain);
        pkt.emit(hdr.clock_sync);
        pkt.emit(hdr.arp);
        pkt.emit(hdr.arp_ipv4);
        pkt.emit(hdr.ipv4);
        pkt.emit(hdr.icmp);
    }
}

// EGRESS ************************************************************
#ifdef __TARGET_TOFINO__

/* need to parse the same headers for the insertion of the INT */
struct egress_header_t {
    ethernet_t         ethernet;
    d6gmain_t          d6gmain;
    d6gint_t           d6gint;
}

/********  G L O B A L   E G R E S S   M E T A D A T A  *********/

struct egress_metadata_t {
    inthdr_h           inthdr;
//    bridge_h           bridge;
    MirrorId_t         mirror_session;
    bool               ing_mirrored;
    bool               egr_mirrored;
    ing_port_mirror_h  ing_port_mirror;
    egr_port_mirror_h  egr_port_mirror;
    header_type_t      mirror_header_type;
    header_info_t      mirror_header_info;
    MirrorId_t         egr_mirror_session;
}

parser NFEgressParser(
        packet_in pkt,
        out egress_header_t hdr,
        out egress_metadata_t meta,
        out egress_intrinsic_metadata_t eg_intr_md) {

//    TofinoEgressParser() tofino_parser;

//    state start {
//        tofino_parser.apply(pkt, eg_intr_md);
//        transition accept;
//    }

    state start {
        meta.mirror_session        = 0;
        meta.ing_mirrored          = false;
        meta.egr_mirrored          = false;
        meta.mirror_header_type    = 0;
        meta.mirror_header_info    = 0;
        meta.egr_mirror_session    = 0;


        pkt.extract(eg_intr_md);
        meta.inthdr = pkt.lookahead<inthdr_h>();

        transition select(meta.inthdr.header_type, meta.inthdr.header_info) {
//            ( HEADER_TYPE_BRIDGE,         _ ) :
//                           parse_bridge;
            ( HEADER_TYPE_MIRROR_INGRESS, (header_info_t)ING_PORT_MIRROR ):
                           parse_ing_port_mirror;
            ( HEADER_TYPE_MIRROR_EGRESS,  (header_info_t)EGR_PORT_MIRROR ):
                           parse_egr_port_mirror;
            default : accept;
        }
    }

//    state parse_bridge {
//        pkt.extract(meta.bridge);
//        transition parse_ethernet;
//    }

    state parse_ing_port_mirror {
        pkt.extract(meta.ing_port_mirror);
        meta.ing_mirrored   = true;
        meta.mirror_session = meta.ing_port_mirror.mirror_session;
        transition parse_ethernet;
    }

    state parse_egr_port_mirror {
        pkt.extract(meta.egr_port_mirror);
        meta.egr_mirrored   = true;
        meta.mirror_session = meta.egr_port_mirror.mirror_session;
        transition accept;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select (hdr.ethernet.etherType) {
            ETHERTYPE_D6G: parse_d6gmain;
            default: accept;
        }
    }

    state parse_d6gmain {
        pkt.extract(hdr.d6gmain);
        transition select (hdr.d6gmain.nextHeader) {
            ETHERTYPE_D6GINT: parse_d6gint;
            default: accept;
        }
    }

    state parse_d6gint {
        pkt.extract(hdr.d6gint);
        transition accept;
    }

}

control NFEgress(
        inout egress_header_t hdr,
        inout egress_metadata_t meta,
        in egress_intrinsic_metadata_t eg_intr_md,
        in egress_intrinsic_metadata_from_parser_t eg_intr_from_prsr,
        inout egress_intrinsic_metadata_for_deparser_t eg_intr_md_for_dprsr,
        inout egress_intrinsic_metadata_for_output_port_t eg_intr_md_for_oport) {

    action update_d6gint_t3(){
        hdr.d6gint.next_header = 0;
        hdr.d6gint.t3 = meta.ing_port_mirror.t3;
    }

    table tb_handle_mirrored_packets {
        key = {
            meta.mirror_session: exact;
            }
        actions = {
            update_d6gint_t3;
            NoAction ;}

        const entries = {
            10w100: update_d6gint_t3;
        }

        default_action = NoAction;
        size = 1024;
    }

    apply {
        if ( meta.ing_port_mirror.isValid() ) {
            tb_handle_mirrored_packets.apply();
        }
    }
}

control NFEgressDeparser(
        packet_out pkt,
        inout egress_header_t hdr,
        in egress_metadata_t eg_md,
        in egress_intrinsic_metadata_for_deparser_t eg_dprsr_md) {

    apply {
        pkt.emit(hdr);
    }
}

Pipeline(
        NFIngressParser(),
        NFIngress(),
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
        update_checksum_with_payload(
	        hdr.icmp.isValid(),
            {
              hdr.icmp.icmp_type,
              hdr.icmp.icmp_code,
              16w0,
              hdr.icmp.identifier,
              hdr.icmp.sequence_number
            },
            hdr.icmp.checksum,
            HashAlgorithm.csum16);

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
            HashAlgorithm.csum16);
    }
}

V1Switch(
        NFIngressParser(),
        MyVerifyChecksum(),
        NFIngress(),
        MyEgress(),
        MyComputeChecksum(),
        NFIngressDeparser()) main;
#endif
