control UE2SM(
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
        exit;
    }

    action setHH() {
        hdr.d6gmain.hhFlag = 1;
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

    action setUpstreamMode4() {
        ig_md.ueid = (bit<32>) hdr.ipv4.srcAddr;
        ig_md.direction = 0;
    }

    action setDownstreamMode4() {
        ig_md.ueid = (bit<32>) hdr.ipv4.dstAddr;
        ig_md.direction = 1;
    }

    table ModeSelector {
        key = {
            RXPORT : exact;
        }
        actions = {
            setDownstreamMode4;
            setUpstreamMode4;
            drop;
        }
        size = 8;
        default_action = drop();
    }

    action setD6GService(bit<16> serviceId, bit<16> nextNF) {
        hdr.d6gmain.setValid();
        hdr.d6gmain.serviceId = serviceId;
        hdr.d6gmain.nextNF = nextNF;
        hdr.d6gmain.nextHeader = hdr.ethernet.etherType;
        hdr.ethernet.etherType = ETHERTYPE_D6G;
    }

    table ServiceMapper {
        key = {
            RXPORT : exact;
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

    action UEMapping(bit<16> locationId) {
        hdr.d6gmain.locationId = locationId;
        hdr.d6gmain.hhFlag = 0;
    }

    table UEMapper {
        key = {
            ig_md.ueid: exact; // -> may be reduced by splitting the ip to UE id and using the service id together
        }
        actions = {
            UEMapping;
            drop;
        }
        size = 10000; // table size may be different for upstream and downstream cases - TODO
        default_action = drop();
    }

    apply {
        if (!hdr.d6gmain.isValid() && hdr.ipv4.isValid()) {
            ModeSelector.apply();
            ServiceMapper.apply();
            if (ig_md.direction == 1) {
                if (IsHH.apply().hit) {
                    // TODO: HH handling
                } else {
                    UEMapper.apply();
                }
            } else {
                UEMapper.apply();
            }
        }
    }
}
