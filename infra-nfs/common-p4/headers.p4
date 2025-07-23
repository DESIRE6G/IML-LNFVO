#ifndef COMMON_HEADERS_H
#define COMMON_HEADERS_H

// HEADERS AND TYPES ************************************************************

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    bit<48>   dstAddr;
    bit<48>   srcAddr;
    bit<16>   etherType;
}

header evlan_t {
    bit<3>    pcp;
    bit<1>    dei;
    bit<12>   vid;
    bit<16>   etherType;
}

header icmp_t {
    bit<8> icmp_type;
    bit<8> icmp_code;
    bit<16> checksum;
    bit<16> identifier;
    bit<16> sequence_number;
}

// Address Resolution Protocol -- RFC 6747
header arp_generic_h {
    bit<16> htype;
    bit<16> ptype;
    bit<8> hlen;
    bit<8> plen;
    bit<16> oper;
}

header arp_ipv4_h {
    bit<48> sha;
    bit<32> spa;
    bit<48> tha;
    bit<32> tpa;
}

// VXLAN -- RFC 7348
header vxlan_t {
    bit<8> flags;
    bit<24> reserved;
    bit<24> vni;
    bit<8> reserved2;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<6>  diffserv;
    bit<2>  ecn;
    bit<16> totalLen;
    bit<16> identification;
    bit<1>  _reserved;
    bit<1>  dont_fragment;
    bit<1>  more_fragments;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdrChecksum;
    bit<32> srcAddr;
    bit<32> dstAddr;
}

header ipv6_t {
    bit<4>   version;
    bit<12>  trafficClass;
    bit<16>  flowLabel;
    bit<16>  totalLen;
    bit<8>   nextHeader;
    bit<8>   hopLimit;
    bit<128> srcAddr;
    bit<128> dstAddr;
}

header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> length_;
    bit<16> checksum;
}

#define ETHERTYPE_VLAN 16w0x8100 // IEEE 802.1Q
#define ETHERTYPE_IPV4 16w0x0800
#define ETHERTYPE_IPV6 16w0x86DD
#define ETHERTYPE_D6G  16w0xD6D6
#define ETHERTYPE_ARP  16w0x0806

const bit<16> ARP_HTYPE_ETHERNET = 0x0001;
const bit<16> ARP_PTYPE_IPV4     = 0x0800;
const bit<8>  ARP_HLEN_ETHERNET  = 6;
const bit<8>  ARP_PLEN_IPV4      = 4;
const bit<16> ARP_OPER_REQUEST   = 1;
const bit<16> ARP_OPER_REPLY     = 2;

const bit<8>  ICMP_ECHO_REQUEST  = 8;
const bit<8>  ICMP_ECHO_REPLY    = 0;

typedef bit<8> ip_proto_t;
const ip_proto_t IPPROTO_ICMP = 1;
const ip_proto_t IPPROTO_IP   = 4;
const ip_proto_t IPPROTO_TCP  = 6;
const ip_proto_t IPPROTO_UDP  = 17;

const bit<16> UDP_PORT_VXLAN = 4789;

#define ETH_HDR_SIZE 14
#define D6G_HDR_SIZE 9
#define IPV4_HDR_SIZE 20
#define UDP_HDR_SIZE 8
#define VXLAN_HDR_SIZE 8

// DESIRE6G HEADER AND ITS OPTIONS

header d6gmain_t {
   bit<16> serviceId; 	// Network service or slice
   bit<16> locationId;  // UE location if applicable
   bit<1>  hhFlag;
   bit<7>  _reserved;
   bit<16> nextNF;      // next network function in the service graph
   bit<16> nextHeader;	// identifier of the next header elements
}

#define D6GOPTION_QOS 16w0x1100

header d6gqos_t {
   bit<16> packetValue;
   bit<8>  delayClass;
   bit<16> nextHeader;
}

// #define D6GOPTION_INTv1 16w0x1101
//
// header d6gintv1_t {
//   ...
// }
#endif
