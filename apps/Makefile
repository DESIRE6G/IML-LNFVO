IMGS:=${shell find . -name 'Dockerfile' -printf '%h\n'}
NS:=desire6g

all: $(IMGS)

$(IMGS): % : %.tar

$(addsuffix .tar,$(IMGS)): %.tar : %/Dockerfile
	docker build -t ${NS}/$(basename $@) -f $< $(basename $@)/
	docker save -o $@ ${NS}/$(basename $@)
	sudo ctr -n=k8s.io i import $@

clean:
	rm -f $(addsuffix .tar,$(IMGS))

.PHONY: all clean $(IMGS)
