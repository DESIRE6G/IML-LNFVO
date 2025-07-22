/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>
#include "../../common-p4/headers.p4"

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

struct metadata {
    bit<24> vni;
    macAddr_t vtep_src_mac;
    macAddr_t vtep_dst_mac;
    ip4Addr_t vtep_src_ip;
    ip4Addr_t vtep_dst_ip;
}

struct headers {
    ethernet_t   ethernet;
    d6gmain_t    d6gmain;
    ipv4_t       ipv4;
    udp_t        udp;
    vxlan_t      vxlan;
    ethernet_t   inner_ethernet;
    d6gmain_t    inner_d6g;
    ipv4_t       inner_ipv4;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            ETHERTYPE_IPV4: parse_ipv4;
            ETHERTYPE_D6G: parse_d6g;
            default: accept;
        }
    }

    state parse_d6g {
        packet.extract(hdr.d6gmain);
        transition select(hdr.d6gmain.nextHeader) {
            ETHERTYPE_IPV4: parse_inner_ipv4;
            default: accept;
        }
    }
    state parse_inner_ipv4 {
        packet.extract(hdr.inner_ipv4);
        transition accept;
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            IPPROTO_UDP: parse_udp;
            default: accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        transition select(hdr.udp.dst_port) {
            UDP_PORT_VXLAN: parse_vxlan;
            default: accept;
        }
    }

    state parse_vxlan {
        packet.extract(hdr.vxlan);
        transition parse_inner_ethernet;
    }

    state parse_inner_ethernet {
        packet.extract(hdr.inner_ethernet);
        transition accept;
    }
}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
        exit;
    }

    action set_vni(bit<24> vni) {
        meta.vni = vni;
    }

    //table vni {

    //    key = {
    //        hdr.d6gmain.serviceId : exact;
    //    }

    //    actions = {
    //        set_vni;
    //        NoAction;
    //        drop;
    //    }
    //    size = 1024;
    //    default_action = drop();
    //}

    action set_vtep_dst_ip(ip4Addr_t vtep_dst_ip, macAddr_t smac, macAddr_t dmac, egressSpec_t port) {
        meta.vtep_dst_ip = vtep_dst_ip;
        meta.vtep_src_mac = smac;
        meta.vtep_dst_mac = dmac;
        standard_metadata.egress_spec = port;
    }

    table vtep_dst {

        key = {
            hdr.ethernet.dstAddr : exact;
        }

        actions = {
            set_vtep_dst_ip;
            NoAction;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    action set_vtep_src_ip(ip4Addr_t vtep_src_ip) {
        meta.vtep_src_ip = vtep_src_ip;
    }

    table vtep_src {
        key = {
            hdr.ethernet.srcAddr : exact;
        }

        actions = {
            set_vtep_src_ip;
            NoAction;
            drop;
        }
        size = 1024;
        default_action = drop();

    }

    action vxlan_encap() {

        hdr.inner_ethernet = hdr.ethernet;
        hdr.inner_d6g = hdr.d6gmain;
        hdr.d6gmain.setInvalid();

        hdr.ethernet.setValid();
        hdr.ethernet.srcAddr = meta.vtep_src_mac;
        hdr.ethernet.dstAddr = meta.vtep_dst_mac;
        hdr.ethernet.etherType = ETHERTYPE_IPV4;

        hdr.ipv4.setValid();
        hdr.ipv4.version = 4;
        hdr.ipv4.ihl = 5;
        hdr.ipv4.diffserv = 0;
        hdr.ipv4.ecn = 0;
        hdr.ipv4.totalLen = hdr.inner_ipv4.totalLen + (IPV4_HDR_SIZE + UDP_HDR_SIZE + VXLAN_HDR_SIZE + ETH_HDR_SIZE + D6G_HDR_SIZE);
        hdr.ipv4.identification = 0x1513; /* From NGIC */
        hdr.ipv4._reserved = 0;
        hdr.ipv4.dont_fragment = 0;
        hdr.ipv4.more_fragments = 0;
        hdr.ipv4.fragOffset = 0;
        hdr.ipv4.ttl = 64;
        hdr.ipv4.protocol = IPPROTO_UDP;
        hdr.ipv4.srcAddr = meta.vtep_src_ip;
        hdr.ipv4.dstAddr = meta.vtep_dst_ip;
        hdr.ipv4.hdrChecksum = 0;

        hdr.udp.setValid();
        // The VTEP calculates the source port by performing the hash of the inner Ethernet frame's header.
        hash(hdr.udp.src_port, HashAlgorithm.crc16, (bit<13>)0, { hdr.inner_ethernet }, (bit<32>)65536);
        hdr.udp.dst_port = UDP_PORT_VXLAN;
        hdr.udp.length_ = hdr.inner_ipv4.totalLen + (UDP_HDR_SIZE + VXLAN_HDR_SIZE + ETH_HDR_SIZE + D6G_HDR_SIZE);
        hdr.udp.checksum = 0;

        hdr.vxlan.setValid();
        hdr.vxlan.reserved = 0;
        hdr.vxlan.reserved2 = 0;
        hdr.vxlan.flags = 0; // bit 5 needs to be 1?
        hdr.vxlan.vni = meta.vni;
    }

    action vxlan_decap(egressSpec_t port) {
        hdr.ethernet.setInvalid();
        hdr.ipv4.setInvalid();
        hdr.udp.setInvalid();
        hdr.vxlan.setInvalid();
        standard_metadata.egress_spec = port;
    }

    table vxlan_fwd {
        key = {
            hdr.inner_ethernet.dstAddr: exact;
        }
        actions = {
            vxlan_decap;
            NoAction;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    apply {
        if (hdr.d6gmain.isValid()) {
            vtep_src.apply();
            //vni.apply();
            set_vni((bit<24>)hdr.d6gmain.serviceId);
            vtep_dst.apply();
            vxlan_encap();
        } else if (hdr.vxlan.isValid()) {
            vxlan_fwd.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {

    apply { }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
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
            HashAlgorithm.csum16);

        update_checksum_with_payload(
            hdr.ipv4.isValid() && hdr.udp.isValid(),
            {
                hdr.ipv4.srcAddr,
                hdr.ipv4.dstAddr,
                8w0,
                hdr.ipv4.protocol,
                hdr.udp.length_,
                hdr.udp.src_port,
                hdr.udp.dst_port,
                hdr.udp.length_,
                16w0,
                hdr.vxlan,
                hdr.inner_ethernet,
                hdr.inner_d6g,
                hdr.inner_ipv4
            },
            hdr.udp.checksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
        packet.emit(hdr.vxlan);
        packet.emit(hdr.inner_ethernet);
        packet.emit(hdr.inner_d6g);
        packet.emit(hdr.inner_ipv4);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
