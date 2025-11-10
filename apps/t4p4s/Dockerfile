ARG IMG="ubuntu"
ARG IMG_TAG="20.04"
FROM "${IMG}:${IMG_TAG}"

ARG DEP_COMMON="vim git curl xz-utils"
ARG DEP_DPDK="build-essential pkg-config python3 meson ninja-build python3-pyelftools libnuma-dev"
ARG DEP_GRPC="build-essential autoconf libtool pkg-config"
ARG DEP_PI="gcc libjudy-dev libreadline-dev valgrind libtool-bin libboost-dev libboost-system-dev libboost-thread-dev libssl-dev"
ARG DEP_P4C="cmake g++ git automake libtool libgc-dev bison flex libfl-dev libgmp-dev libboost-dev libboost-iostreams-dev libboost-graph-dev llvm pkg-config python3 python3-ipaddr python3-pip tcpdump python3-scapy python3-ply"
ARG DEP_T4P4S="sudo lsof net-tools netcat gdb python3-more-itertools"

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ${DEP_COMMON} \
    ${DEP_DPDK} \
    ${DEP_GRPC} \
    ${DEP_PI} \
    ${DEP_P4C} \
    ${DEP_T4P4S} \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

# DPDK
# https://doc.dpdk.org/guides-23.11/linux_gsg/sys_reqs.html#compilation-of-the-dpdk

ARG DPDK_VER="23.11.1"
RUN mkdir -p ./dpdk && \
    curl -L http://fast.dpdk.org/rel/dpdk-${DPDK_VER}.tar.xz | tar -xJ -C ./dpdk --strip-components=1

RUN cd ./dpdk && \
    meson setup -Dbuildtype=debugoptimized -Dplatform=native -Db_pch=true -Dtests=false build && \
    ninja -C build && \
    ninja -C build install && \
    ldconfig

# GRPC
# https://github.com/grpc/grpc/blob/master/BUILDING.md

ARG GRPC_REV="v1.37.0"
RUN git clone -b ${GRPC_REV} --recursive --shallow-submodules --depth=1 https://github.com/grpc/grpc ./grpc

# see: https://github.com/grpc/grpc/issues/25949#issuecomment-823427625
RUN mkdir -p ./grpc/third_party/abseil-cpp/cmake/build && \
    cd ./grpc/third_party/abseil-cpp/cmake/build && \
    cmake -DCMAKE_POSITION_INDEPENDENT_CODE=TRUE ../.. && \
    make -j$(nproc) install && \
    ldconfig

RUN mkdir -p ./grpc/cmake/build && \
    cd ./grpc/cmake/build && \
    cmake ../.. -DCMAKE_CXX_STANDARD=17 -DCMAKE_C_FLAGS="-fPIC" \
        -DCMAKE_CXX_FLAGS="-Wno-cpp -fPIC" -GNinja -DBUILD_TESTS=OFF \
        -DBUILD_CONFORMANCE=OFF -DBUILD_EXAMPLES=OFF \
        -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_CONFORMANCE=OFF \
        -Dprotobuf_BUILD_EXAMPLES=OFF && \
    ninja -j$(nproc) && \
    ninja install && \
    ldconfig

# Protobuf

ARG PROTOBUF_REV="v3.20.1"
RUN git clone -b ${PROTOBUF_REV} --recursive --shallow-submodules --depth=1 https://github.com/google/protobuf ./protobuf

RUN mkdir -p ./protobuf/cmake/build && \
    cd ./protobuf/cmake/build && \
    cmake .. -DCMAKE_C_FLAGS="-fPIC" -DCMAKE_CXX_FLAGS="-Wno-cpp -fPIC" \
    -GNinja  -DBUILD_TESTS=OFF -DBUILD_CONFORMANCE=OFF -DBUILD_EXAMPLES=OFF \
    -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_CONFORMANCE=OFF \
    -Dprotobuf_BUILD_EXAMPLES=OFF && \
    ninja -j$(nproc) && \
    ninja install && \
    ldconfig

# PI
# https://github.com/p4lang/PI/tree/a5fd855d4b3293e23816ef6154e83dc6621aed6a?tab=readme-ov-file#installing-other-dependencies-from-source

ARG PI_REV="a5fd855d4b3293e23816ef6154e83dc6621aed6a"
#RUN git clone --revision="${PI_REV}" --recursive --shallow-submodules --depth=1 https://github.com/p4lang/PI ./PI
RUN mkdir ./PI && \
    cd ./PI && \
    git init && \
    git remote add origin https://github.com/p4lang/PI && \
    git fetch origin --depth=1 ${PI_REV} && \
    git reset --hard FETCH_HEAD && \
    git submodule update --init --recursive --depth=1 --recommend-shallow

RUN cd ./PI && \
    ./autogen.sh && \
    ./configure --with-proto && \
    make -j$(nrpoc) && \
    make install

# P4C
# 1.2.3.4

ARG P4C_REV="d0056fc401b7b9589902210ce541cb6ea7771176"
#RUN git clone --revision="${P4C_REV}" --recursive --shallow-submodules --depth=1 https://github.com/p4lang/p4c.git ./p4c

RUN mkdir ./p4c && \
    cd ./p4c && \
    git init && \
    git remote add origin https://github.com/p4lang/p4c.git && \
    git fetch origin --depth=1 ${P4C_REV} && \
    git reset --hard FETCH_HEAD && \
    git submodule update --init --recursive --depth=1 --recommend-shallow

    # temporary fix
    # ninja build may run out of mem so just -j2
RUN mkdir ./p4c/build && \
    cd ./p4c/build && \
    sed -i "s/Status::OK/OkStatus()/g" ../control-plane/p4RuntimeSerializer.cpp && \
    cmake .. -GNinja -DCMAKE_BUILD_TYPE=MinSizeRel \
        -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
        -DCMAKE_C_FLAGS="-fPIC" -DCMAKE_CXX_FLAGS="-Wno-cpp -fPIC" \
        -DENABLE_P4TEST=ON -DENABLE_BMV2=OFF -DENABLE_DOCS=OFF \
        -DENABLE_DPDK=OFF -DENABLE_EBPF=OFF -DENABLE_GTESTS=OFF \
        -DENABLE_MULTITHREAD=OFF -DENABLE_P4C_GRAPHS=OFF \
        -DENABLE_PROTOBUF_STATIC=OFF -DENABLE_UBPF=OFF && \
    ninja -j2 && \
    ninja install

# T4P4S

ARG T4P4S_REV="fdf9727886b6b16b5988b29ddd66baefbb9d5a6e"
ARG T4P4S_REPO="https://github.com/P4EDGE/t4p4s.git"
#RUN git clone --revision="${T4P4S_REV}" --recursive --shallow-submodules --depth=1 "${T4P4S_REPO}" ./t4p4s
RUN mkdir ./t4p4s && \
    cd ./t4p4s && \
    git init && \
    git remote add origin ${T4P4S_REPO} && \
    git fetch origin --depth=1 ${T4P4S_REV} && \
    git reset --hard FETCH_HEAD && \
    git submodule update --init --recursive --depth=1 --recommend-shallow


# P4Runtime_GRPCPP

ARG P4RTGRPCPP_REV="261bdc73f149d15e61e73b4afa80c8085de9445f"
#RUN git clone --revision="${P4RTGRPCPP_REV}" --depth=1 https://github.com/P4ELTE/P4Runtime_GRPCPP ./P4Runtime_GRPCPP
RUN mkdir ./P4Runtime_GRPCPP && \
    cd ./P4Runtime_GRPCPP && \
    git init && \
    git remote add origin https://github.com/P4ELTE/P4Runtime_GRPCPP.git && \
    git fetch origin --depth=1 ${P4RTGRPCPP_REV} && \
    git reset --hard FETCH_HEAD && \
    git submodule update --init --recursive --depth=1 --recommend-shallow

RUN cd ./P4Runtime_GRPCPP && \
    ./install.sh && \
    ./compile.sh

ENV P4C="/opt/p4c"
ENV GRPC="/opt/grpc"
ENV P4PI="/opt/PI"
ENV GRPCPP="/opt/P4Runtime_GRPCPP"
#ENV T4P4S="/opt/t4p4s"

COPY patches /opt/t4p4s/patches
RUN find /opt/t4p4s/patches -type f -name '*.patch' -print0 | xargs -0 -n 1 patch -d /opt/t4p4s -p1 -i

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD /bin/bash -c 'printf "GET / HTTP/1.1\n\n" > /dev/tcp/127.0.0.1/50051 || exit 1'

WORKDIR /opt/t4p4s
