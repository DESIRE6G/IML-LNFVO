ARG DEBIAN_VERSION="11"
FROM debian:${DEBIAN_VERSION}

RUN apt-get -y update && \
    apt-get install -y --no-install-recommends \
      vim \
      git \
      tmux \
      build-essential \
      curl \
      python3 \
      gnupg2 \
      sudo \
      ca-certificates

RUN echo 'deb [signed-by=/usr/share/keyrings/p4edge-archive-keyring.gpg] http://download.opensuse.org/repositories/home:/p4edge/Debian_11/ /' | tee /etc/apt/sources.list.d/p4edge.list
RUN curl -fsSL https://download.opensuse.org/repositories/home:/p4edge/Debian_11/Release.key | gpg --dearmor > /usr/share/keyrings/p4edge-archive-keyring.gpg

RUN echo 'deb [signed-by=/usr/share/keyrings/p4edge-p4lang-testing-archive-keyring.gpg] http://download.opensuse.org/repositories/home:/p4edge:/p4lang-testing/Debian_11/ /' | tee /etc/apt/sources.list.d/p4edge-p4lang-testing.list
RUN curl -fsSL https://download.opensuse.org/repositories/home:/p4edge:/p4lang-testing/Debian_11/Release.key | gpg --dearmor > /usr/share/keyrings/p4edge-p4lang-testing-archive-keyring.gpg

RUN apt-get -y update && \
    apt-get install -y --no-install-recommends \
      p4lang-pi \
      p4lang-p4c \
      p4lang-bmv2 \
      p4edge-t4p4s \
      bridge-utils \
      iperf \
      libpcap-dev \
      gdb \
      iputils-ping \
      net-tools \
      python3-scapy

COPY src/ /root/t4p4s/examples/
RUN python3 -m venv /root/t4p4s/examples/nfr-controlplane/venv
RUN /root/t4p4s/examples/nfr-controlplane/venv/bin/python3 -m pip install -r /root/t4p4s/examples/nfr-controlplane/requirements.txt
RUN p4c-bm2-ss --p4runtime-files "/root/t4p4s/examples/nfr-controlplane/config/nfrouter.p4runtime.txt,/root/t4p4s/examples/nfr-controlplane/config/nfrouter.p4runtime.bin" "/root/t4p4s/examples/nfrouter.p4"

RUN   echo "nfrouter arch=dpdk model=v1model smem vethmode nfroutereal nfrouterports" >> /root/t4p4s/examples.cfg

WORKDIR /root/t4p4s
