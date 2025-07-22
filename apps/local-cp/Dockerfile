FROM p4lang/p4runtime-sh:latest

RUN /p4runtime-sh/venv/bin/python -m pip install flask

COPY ./local-cp.py /local-cp/
COPY ./shell_wrapper.py /local-cp/

WORKDIR /local-cp
