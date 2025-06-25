FROM p4lang/p4c:1.2.5.0 AS build

COPY ../../infra-nfs/common-p4/ /src/common-p4/
COPY ../../infra-nfs/nfrouting/ /src/nfrouting/

RUN p4c-bm2-ss -I /usr/share/p4c/p4include --std p4-16 --p4runtime-files "/src/nfrouting/control-plane/nfrouting.p4runtime.txt" -o /src/nfrouting/data-plane/p4-v1model/nfrouting.json /src/nfrouting/data-plane/p4-v1model/nfrouting.p4

FROM p4lang/behavioral-model:stable

RUN apt-get -y update && \
    apt-get install -y --no-install-recommends \
      vim \
      ca-certificates \
      build-essential \
      curl \
      git \
      iproute2 \
      iputils-ping \
      traceroute \
      tcpdump \
      iperf3 \
      dnsutils \
      net-tools \
      ethtool

COPY --from=build /src/nfrouting/control-plane/ /src/nfrouting/control-plane/
COPY --from=build /src/nfrouting/data-plane/p4-v1model/nfrouting.json /src/nfrouting/data-plane/p4-v1model/

WORKDIR /src/nfrouting/data-plane/p4-v1model
