FROM desire6g/nfrouter-bmv2:latest AS build

FROM p4lang/p4runtime-sh:latest

RUN /p4runtime-sh/venv/bin/python -m pip install flask

COPY --from=build /src/nfrouting/data-plane/p4-v1model/nfrouting.json /src/nfrouting/data-plane/p4-v1model/
COPY --from=build /src/nfrouting/control-plane/ /src/nfrouting/control-plane/

WORKDIR /src/nfrouting/control-plane/
