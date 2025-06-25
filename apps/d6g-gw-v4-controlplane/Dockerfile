FROM desire6g/d6g-gw-v4-bmv2:latest AS build

FROM p4lang/p4runtime-sh:latest
ARG NF=d6g-gw-v4

RUN /p4runtime-sh/venv/bin/python -m pip install flask

COPY --from=build /src/${NF}/control-plane/ /src/${NF}/control-plane/
COPY --from=build /src/${NF}/data-plane/${NF}.json /src/${NF}/data-plane/

WORKDIR /src/${NF}/control-plane/
