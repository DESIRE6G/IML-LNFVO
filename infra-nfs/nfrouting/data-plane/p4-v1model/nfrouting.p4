#include <core.p4>
#include <v1model.p4>

#include "../../../common-p4/headers.p4"

struct metadata_t {
}


struct header_t {
    ethernet_t ethernet;
    evlan_t evlan;
    d6gmain_t d6gmain;
    ipv6_t ipv6;
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

    table NFPortClassifier {
        key = {
                standard_metadata.ingress_port : exact;
        }
        actions = {
                NoAction;drop;
        }
        size = 1000;
        default_action = NoAction();
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
	standard_metadata.egress_spec = port;
	hdr.ethernet.dstAddr = dstMAC;
    }

    action NFForwardToExternal(bit<9> port, bit<48> dstMAC) { // SRC-MAC?
	standard_metadata.egress_spec = port;
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
        if (NFPortClassifier.apply().hit) {
		if (hdr.d6gmain.isValid()) {
			FWDGExecute.apply();
		}
	}

	if (hdr.d6gmain.isValid()) {
		NFRouter.apply();
	}
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
        pkt.emit(hdr.ipv6);
    }


}

V1Switch(NFParser(),
         MyVerifyChecksum(),
         NFIngress(),
         NFEgress(),
         MyComputeChecksum(),
         NFDeparser()) main;



