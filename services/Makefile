IMGS:=nfrouter trex iperf3
NS:=desire6g

all: $(IMGS)

$(IMGS): % : %.tar
$(addsuffix .tar,$(IMGS)):
	docker build -t ${NS}/$(basename $@) $(basename $@)
	docker save -o $@ ${NS}/$(basename $@)
	sudo ctr -n=k8s.io i import $@

clean:
	rm -f $(addsuffix .tar,$(IMGS))

.PHONY: all clean $(IMGS)
