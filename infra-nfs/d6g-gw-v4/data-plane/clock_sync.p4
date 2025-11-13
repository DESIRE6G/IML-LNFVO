control ClockSync(
    inout header_t hdr,
    in ingress_intrinsic_metadata_t ig_intr_md,
    inout ingress_intrinsic_metadata_for_tm_t ig_tm_md

    ){
    /* This table is for bouncing a special packet back
         and forth between Tofino and the UE for clock
         synchronisation purposes for the INT timestamps.
    */

    action just_forward(PortId_t port) {
        ig_tm_md.ucast_egress_port = port;
        ig_tm_md.bypass_egress = 1;
    }

    action clock_sync_add_t0(PortId_t port){
        hdr.clock_sync.t0 = ig_intr_md.ingress_mac_tstamp;
        hdr.clock_sync.count = hdr.clock_sync.count + 1;
        just_forward(port);
    }

    action clock_sync_add_t1(PortId_t port){
        hdr.clock_sync.t1 = ig_intr_md.ingress_mac_tstamp;
        hdr.clock_sync.count = hdr.clock_sync.count + 1;
        just_forward(port);
    }

    action clock_sync_add_t2(PortId_t port){
        hdr.clock_sync.t2 = ig_intr_md.ingress_mac_tstamp;
        hdr.clock_sync.count = hdr.clock_sync.count + 1;
        just_forward(port);
    }

    action clock_sync_add_t3(PortId_t port){
        hdr.clock_sync.t3 = ig_intr_md.ingress_mac_tstamp;
        hdr.clock_sync.count = hdr.clock_sync.count + 1;
        just_forward(port);
    }

    table tb_clock_sync {
        key = {
            hdr.clock_sync.count: exact;
        }
        actions = {
            just_forward;
            clock_sync_add_t0;
            clock_sync_add_t1;
            clock_sync_add_t2;
            clock_sync_add_t3;
            NoAction;
            }

        default_action = NoAction;
        size = 32;
    }

    apply {
        tb_clock_sync.apply();
    }

}
