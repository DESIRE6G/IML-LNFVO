IMGS:=alternator-bmv2 reflector-bmv2 d6g-gw-v4-controlplane d6g-gw-v4-bmv2 nfrouter-controlplane nfrouter-bmv2 trex iperf3 #nfrouter-dpdk nfrouter-t4p4s
NS:=desire6g

all: $(IMGS)

d6g-gw-v4-controlplane.tar: d6g-gw-v4-bmv2.tar d6g-gw-v4-controlplane/Dockerfile
nfrouter-controlplane.tar: nfrouter-bmv2.tar nfrouter-controlplane/Dockerfile

$(IMGS): % : %.tar

d6g-gw-v4-bmv2.tar: ../infra-nfs/d6g-gw-v4/data-plane/d6g-gw-v4.p4 d6g-gw-v4-bmv2/Dockerfile
nfrouter-bmv2.tar: ../infra-nfs/nfrouting/data-plane/p4-v1model/nfrouting.p4 nfrouter-bmv2/Dockerfile
reflector-bmv2.tar: ../infra-nfs/reflector/data-plane/reflector.p4 reflector-bmv2/Dockerfile
alternator-bmv2.tar: ../infra-nfs/alternator/data-plane/alternator.p4 alternator-bmv2/Dockerfile

$(addsuffix .tar,$(IMGS)):
	cd ../ && docker build -t ${NS}/$(basename $@) -f apps/$(basename $@)/Dockerfile .
	docker save -o $@ ${NS}/$(basename $@)
	sudo ctr -n=k8s.io i import $@

clean:
	rm -f $(addsuffix .tar,$(IMGS))

.PHONY: all clean $(IMGS)
