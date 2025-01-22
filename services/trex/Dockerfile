ARG DEBIAN_VERSION="11"
FROM debian:${DEBIAN_VERSION}
ARG TREX_VERSION="3.06"
#ARG TREX_VERSION="2.98"

WORKDIR /trex
RUN apt-get -y update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      vim \
      curl \
      python3 \
      python3-distutils \
      pciutils \
      iproute2 \
      libarchive-tools \
      procps \
      netbase \
      iputils-ping \
      traceroute \
      tcpdump \
      net-tools \
      iperf \
      iperf3

RUN curl --insecure -L "https://trex-tgn.cisco.com/trex/release/v${TREX_VERSION}.tar.gz" | tar -xz --strip-components=1

CMD ["/bin/bash"]
