#include <core.p4>
#include <v1model.p4>

#include "../../common-p4/headers.p4"

struct metadata_t {
}

struct header_t {
    ethernet_t ethernet;
    evlan_t evlan;
    d6gmain_t d6gmain;
    ipv4_t ipv4;
}

parser NFParser(
        packet_in pkt,
        out header_t hdr,
        inout metadata_t meta,
        inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        pkt.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            ETHERTYPE_VLAN: parse_evlan;
            ETHERTYPE_IPV4: parse_ipv4;
            ETHERTYPE_D6G:  parse_d6g;
            default: accept;
        }
    }

    state parse_evlan {
        pkt.extract(hdr.evlan);
        transition select(hdr.evlan.etherType) {
            ETHERTYPE_IPV4: parse_ipv4;
            ETHERTYPE_D6G:  parse_d6g;
            default: accept;
        }
    }

    state parse_ipv4 {
        pkt.extract(hdr.ipv4);
        transition accept;
    }

    state parse_d6g {
        pkt.extract(hdr.d6gmain);
        transition accept;
    }
}

/*************************************************************************
 ************   C H E C K S U M    V E R I F I C A T I O N   *************
 *************************************************************************/

control MyVerifyChecksum(inout header_t hdr, inout metadata_t meta) {
    apply {  }
}

/*************************************************************************
 **************  I N G R E S S   P R O C E S S I N G   *******************
 *************************************************************************/

control NFIngress(
        inout header_t hdr,
        inout metadata_t meta,
        inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
        exit;
    }

    register<bit<32>>(1) r;

    apply {
        if (!hdr.d6gmain.isValid())
            drop();

        bit<48> tmp_mac = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = hdr.ethernet.srcAddr;
        hdr.ethernet.srcAddr = tmp_mac;

        bit<32> last_seen;
        r.read(last_seen, 0);
        standard_metadata.egress_spec = (bit<9>)last_seen;
        last_seen = (last_seen + 1) & 1;
        r.write(0, last_seen);
    }
}

// EGRESS ************************************************************


control NFEgress(
        inout header_t hdr,
        inout metadata_t meta,
        inout standard_metadata_t standard_metadata) {

    apply {}

}

/*************************************************************************
 *************   C H E C K S U M    C O M P U T A T I O N   **************
 *************************************************************************/

control MyComputeChecksum(inout header_t  hdr, inout metadata_t meta) {
    apply {
    }
}

control NFDeparser(
        packet_out pkt,
        in header_t hdr) {

    apply {
        pkt.emit(hdr.ethernet);
        pkt.emit(hdr.evlan);
        pkt.emit(hdr.d6gmain);
        pkt.emit(hdr.ipv4);
    }
}

V1Switch(NFParser(),
         MyVerifyChecksum(),
         NFIngress(),
         NFEgress(),
         MyComputeChecksum(),
         NFDeparser()) main;
