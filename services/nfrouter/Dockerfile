ARG UBUNTU_VERSION="jammy"
FROM ubuntu:${UBUNTU_VERSION}
ARG DPDK_VERSION="23.11.2"

WORKDIR /dpdk
RUN apt-get -y update && \
    apt-get install -y --no-install-recommends \
      vim \
      build-essential \
      curl \
      xz-utils \
      libnuma-dev \
      python3-pyelftools \
      pkg-config \
      meson \
      ninja-build \
      iproute2 \
      iputils-ping \
      traceroute \
      pciutils \
      tcpdump \
      net-tools \
      `apt-cache depends libdpdk-dev | awk '/Depends:/{print$2}'`

RUN curl -L "http://fast.dpdk.org/rel/dpdk-${DPDK_VERSION}.tar.xz" | tar -xJ --strip-components=1 && \
    meson build && \
    ninja -C build && \
    ninja -C build install

WORKDIR /dpdk/examples/l3fwd
COPY ./debug_print.patch /dpdk/examples/l3fwd/
RUN patch -p1 < debug_print.patch && make static

WORKDIR /dpdk/examples/l3fwd/build

CMD ["/bin/bash"]
