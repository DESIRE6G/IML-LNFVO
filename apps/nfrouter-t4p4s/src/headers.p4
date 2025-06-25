// HEADERS AND TYPES ************************************************************

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


#define ETHERTYPE_VLAN 16w0x8100 // IEEE 802.1Q
#define ETHERTYPE_IPV4 16w0x0800
#define ETHERTYPE_IPV6 16w0x86DD
#define ETHERTYPE_D6G  16w0xD6D6
// DESIRE6G HEADER AND ITS OPTIONS

header d6gmain_t {
   bit<16> serviceId; 	// Network service or slice
   bit<16> locationId; 	// UE location if applicable
   bit<1>  hhFlag;
   bit<7>  _reserved;
   bit<16> nextNF;	// next network function in the service graph
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

