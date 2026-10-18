FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    mininet \
    iputils-ping \
    iperf \
    net-tools \
    iproute2 \
    traceroute

RUN pip3 install eventlet==0.30.2

RUN pip3 install ryu

RUN pip3 install mininet

COPY ryu_topo.py /app/ryu_topo.py
COPY openflow_utils.py /app/openflow_utils.py
COPY traffic_policy.py /app/traffic_policy.py
COPY priority_ryu_controller.py /app/priority_ryu_controller.py
COPY run_all.sh /app/run_all.sh

RUN chmod +x /app/run_all.sh

WORKDIR /app

CMD ["/app/run_all.sh"]
