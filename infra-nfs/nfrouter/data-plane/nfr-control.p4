control NFR(
        inout header_t hdr,
        inout ingress_metadata_t ig_md,
#ifdef __TARGET_TOFINO__
        in ingress_intrinsic_metadata_t ig_intr_md,
        inout ingress_intrinsic_metadata_for_deparser_t ig_dprsr_md,
        inout ingress_intrinsic_metadata_for_tm_t ig_tm_md
#else
        inout standard_metadata_t standard_metadata
#endif
        ) {

    action drop() {
#ifdef __TARGET_TOFINO__
        ig_dprsr_md.drop_ctl = ig_dprsr_md.drop_ctl | 0b001;
#else
        mark_to_drop(standard_metadata);
#endif
        //exit;
    }

    table NFPortClassifier {
        key = {
            RXPORT : exact;
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
            RXPORT : exact;
            hdr.d6gmain.serviceId : exact;
            hdr.d6gmain.nextNF : lpm;
        }
        actions = {
            NoAction; UpdateNF;
        }
        size = 10000;
        default_action = NoAction();
    }

    action NFForward(bit<9> port) {
        TXPORT = port;
    }

    action NFForwardMAC(bit<9> port, bit<48> srcMAC, bit<48> dstMAC) {
        TXPORT = port;
        hdr.ethernet.srcAddr = srcMAC;
        hdr.ethernet.dstAddr = dstMAC;
    }

    action NFForwardToExternal(bit<9> port, bit<48> srcMAC, bit<48> dstMAC) {
        TXPORT = port;
        hdr.ethernet.srcAddr = srcMAC;
        hdr.ethernet.dstAddr = dstMAC;
        hdr.ethernet.etherType = hdr.d6gmain.nextHeader;
        hdr.d6gmain.setInvalid();
    }

    table NFRouter {
        key = {
            hdr.d6gmain.serviceId    : exact;
            hdr.d6gmain.locationId   : exact;
            hdr.d6gmain.nextNF       : exact;
        }
        actions = {
            NFForwardMAC;NFForwardToExternal;NFForward;drop;
        }
        size = 10000;
        default_action = drop();
    }

    apply {
        if (hdr.d6gmain.isValid()) {
            if (NFPortClassifier.apply().hit) {
                FWDGExecute.apply();
            }
            NFRouter.apply();
        }
    }
}
