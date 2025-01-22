ARG DEBIAN_VERSION="11"
FROM debian:${DEBIAN_VERSION}
ARG IPERF3_VERSION="3.18"

WORKDIR /iperf
RUN apt-get -y update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      vim \
      ca-certificates \
      curl \
      git \
      iproute2 \
      netbase \
      iputils-ping \
      traceroute \
      tcpdump \
      net-tools

RUN git clone --depth 1 --branch ${IPERF3_VERSION} https://github.com/esnet/iperf.git /iperf && \
    ./configure && \
    make && \
    make install && \
    ldconfig

CMD ["/bin/bash"]
