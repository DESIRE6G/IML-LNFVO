FROM p4lang/p4c:1.2.5.0 AS build

COPY ../../infra-nfs/common-p4/ /src/common-p4/
COPY ../../infra-nfs/reflector/ /src/reflector/

RUN p4c-bm2-ss -I /usr/share/p4c/p4include --std p4-16 --p4runtime-files "/src/reflector/reflector.p4runtime.txt" -o /src/reflector/data-plane/reflector.json /src/reflector/data-plane/reflector.p4

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

COPY --from=build /src/reflector/reflector.p4runtime.txt /src/reflector/
COPY --from=build /src/reflector/data-plane/reflector.json /src/reflector/data-plane/

WORKDIR /src/reflector/data-plane
