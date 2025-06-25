FROM p4lang/p4c:1.2.5.0 AS build
ARG NF=d6g-gw-v4

COPY ../../infra-nfs/common-p4/ /src/common-p4/
COPY ../../infra-nfs/${NF}/ /src/${NF}/

RUN p4c-bm2-ss -I /usr/share/p4c/p4include --std p4-16 --p4runtime-files "/src/${NF}/control-plane/${NF}.p4runtime.txt" -o /src/${NF}/data-plane/${NF}.json /src/${NF}/data-plane/${NF}.p4

FROM p4lang/behavioral-model:stable
ARG NF=d6g-gw-v4

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

COPY --from=build /src/${NF}/control-plane/ /src/${NF}/control-plane/
COPY --from=build /src/${NF}/data-plane/${NF}.json /src/${NF}/data-plane/

WORKDIR /src/${NF}/data-plane
