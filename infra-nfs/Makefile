NFS:=${shell find . -mindepth 1 -maxdepth 1 -path ./common-p4 -prune -o -type d -printf '%P\n'}

all: $(NFS)

.SECONDEXPANSION:
$(NFS): % : $$*/data-plane/$$*.json

%.json: %.p4
	docker run --rm --user $$(id -u):$$(id -g) -v ./:/src p4lang/p4c:1.2.5.0 p4c-bm2-ss --std p4-16 --p4runtime-files /src/$*.p4info.txtpb -o /src/$@ /src/$^

clean:
	find . -type f \( -name "*.txtpb" -o -name "*.json" \) -delete

.PHONY: all clean $(NFS)
