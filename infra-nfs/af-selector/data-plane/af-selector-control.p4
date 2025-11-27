control AFLB(
        inout header_t hdr,
        inout ingress_metadata_t ig_md,
#ifdef __TARGET_TOFINO__
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
        exit;
    }

    action setInstance(bit<16> instId) {
        ig_md.instId = instId;
    }

    table InstanceSelector {
        key = {
            hdr.ipv4.srcAddr : ternary;
            hdr.ipv4.dstAddr : ternary;
        }
        actions = {
            setInstance;drop;
        }
        size = 1000;
        default_action = drop;
    }

    action forwardToInstance(bit<9> port, bit<32> instIp) {
        TXPORT = port;
        hdr.ipv4.dstAddr = instIp;
    }

    action forwardToUplink(bit<9> port, bit<32> nfIp) {
        TXPORT = port;
        hdr.ipv4.srcAddr = nfIp;
    }

    table Forwarder {
        key = {
            ig_md.instId: exact;
        }
        actions = {
            forwardToInstance;forwardToUplink;drop;
        }
        size = 10000;
        default_action = drop();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            InstanceSelector.apply();
            Forwarder.apply();
        } else {
            drop();
        }
    }
}
