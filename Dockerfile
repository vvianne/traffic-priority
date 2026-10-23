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

COPY requirements.txt /app/requirements.txt

RUN pip3 install --no-cache-dir -r /app/requirements.txt

RUN pip3 check

COPY ryu_topo.py /app/ryu_topo.py
COPY openflow_utils.py /app/openflow_utils.py
COPY policy_config.py /app/policy_config.py
COPY ovs_qos.py /app/ovs_qos.py
COPY traffic_policy.py /app/traffic_policy.py
COPY experiment_metrics.py /app/experiment_metrics.py
COPY experiment_plan.py /app/experiment_plan.py
COPY latency_probe.py /app/latency_probe.py
COPY result_analysis.py /app/result_analysis.py
COPY extended_analysis.py /app/extended_analysis.py
COPY priority_ryu_controller.py /app/priority_ryu_controller.py
COPY config /app/config
COPY run_all.sh /app/run_all.sh
COPY scripts /app/scripts
COPY tests /app/tests

RUN chmod +x /app/run_all.sh /app/scripts/*.sh

WORKDIR /app

RUN python3 -B -m unittest discover -s /app/tests -v

RUN mkdir -p /app/results/raw /app/results/analysis /app/results/plots

ENTRYPOINT ["/app/run_all.sh"]
