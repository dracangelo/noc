# Telemetry, Metrics & Alerting Reference Manual

## 1. Observability Architecture

NOC-Sim implements the **Three Pillars of Observability** tailored specifically for network infrastructure:
1. **Metrics (Time-Series)**: Gathered at 5s scrape intervals by Prometheus via Blackbox Exporter and the FRR Telemetry Exporter.
2. **Logs (Structured Streams)**: Tailed directly from container stdout/stderr by Grafana Alloy and pushed to Loki, enriched with authentic router syslog events.
3. **Alerts & Incidents**: Evaluated continuously by Prometheus rules, dispatched to Alertmanager, and streamed into the local Incident Management Center.

---

## 2. Prometheus Metrics Reference

### 2.1 FRR & Routing Telemetry (Job: `frr-telemetry`, Port `:9348`)
Collected via `scripts/frr_exporter.py` by scraping FRR's `vtysh` daemon JSON outputs:

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `frr_ospf_neighbor_state` | Gauge | `node`, `neighbor`, `interface`, `state` | `1` if neighbor state is `Full`, `0` for any degraded state (`Init`, `2-Way`, `ExStart`, `Down`). |
| `frr_ospf_neighbor_dead_time_seconds` | Gauge | `node`, `neighbor`, `interface` | Seconds remaining before OSPF neighbor dead-timer expires without hellos. |
| `frr_routes_total` | Gauge | `node`, `protocol` | Total routes installed in RIB/FIB, grouped by protocol (`ospf`, `connected`, `kernel`). |

---

### 2.2 Network Interface Telemetry (Job: `frr-telemetry`, Port `:9348`)
Collected via `/proc/net/dev` and `ip -j link` on each container node:

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `network_interface_up` | Gauge | `node`, `device`, `state` | `1` if administrative/operational carrier flag is `UP`, `0` if `DOWN`. |
| `network_receive_bytes_total` | Counter | `node`, `device` | Total inbound bytes received on the interface. Use `rate(...[30s]) * 8` for bps throughput. |
| `network_transmit_bytes_total` | Counter | `node`, `device` | Total outbound bytes transmitted on the interface. |
| `network_receive_packets_total` | Counter | `node`, `device` | Total inbound packets. |
| `network_transmit_packets_total`| Counter | `node`, `device` | Total outbound packets. |
| `network_receive_drop_total` | Counter | `node`, `device` | Ingress packet drops (e.g. netem packet loss or buffer overflows). |
| `network_transmit_drop_total`| Counter | `node`, `device` | Egress packet drops. |
| `network_receive_errs_total` | Counter | `node`, `device` | Inbound CRC/FCS framing errors. |
| `network_transmit_errs_total`| Counter | `node`, `device` | Outbound interface transmission errors. |

---

### 2.3 Synthetic ICMP Probes (Job: `lab-icmp`, Port `:9115`)
Collected via Prometheus Blackbox Exporter targeting management addresses `172.20.20.11-16`:

| Metric Name | Type | Labels | Description |
|---|---|---|---|
| `probe_success` | Gauge | `instance`, `node`, `role` | `1` if ICMP echo reply received, `0` if probe timed out. |
| `probe_icmp_duration_seconds` | Gauge | `instance`, `node`, `role`, `phase="rtt"` | Round-trip time (RTT) in seconds. Multiply by 1000 for ms. |
| `probe_duration_seconds` | Gauge | `instance`, `node` | Total execution time of the synthetic probe transaction. |

---

## 3. Loki Log Streams & Syslog Schema

### 3.1 Container Log Ingestion (Grafana Alloy)
Grafana Alloy dynamically discovers Docker containers with prefix `clab-noc-lab-` and tails `/var/run/docker.sock`, shipping stdout/stderr to Loki under:
* Stream labels: `{job="lab-logs", lab="noc-lab", node="<node>", container="<name>"}`

### 3.2 High-Volume Router Syslog Telemetry (`telemetry_streamer.py`)
Directly ingests realistic Cisco/Juniper/FRR operational logs into Loki under `{job="lab-logs", lab="noc-lab", level="<level>", facility="daemon"}`:
* **OSPF Adjacency Events**:
  `%OSPF-5-ADJCHANGE: Process 1, Nbr 2.2.2.2 on eth1 from LOADING to FULL, Loading Done`
  `%OSPF-5-ADJCHANGE: Process 1, Nbr 2.2.2.2 on eth1 from FULL to DOWN, Neighbor Down: Dead timer expired`
* **Transceiver & Optical Diagnostics**:
  `%TRANSCEIVER-4-DDM_ALARM: SFP interface eth2: Optical Rx Power below warning threshold (-18.4 dBm)`
  `%ETHERNET-4-CRC_ERR: Interface eth1: Ingress FCS/CRC error count exceeded rate threshold (12 pkts/sec)`
* **SPF Timing**:
  `%OSPF-6-SPF_CALC: SPF calculation completed in 4 ms, 14 vertices processed`
* **Security & ACL Drops**:
  `%SEC-6-ACL_DENY: List INGRESS_PROTECT denied udp 192.168.10.15(52341) -> 192.168.20.16(53), 1 packet`

---

## 4. Alerting Rules Reference ([noc.rules.yml](file:///home/drac/noc-sim/prometheus/rules/noc.rules.yml))

| Alert Name | Severity | Condition (PromQL) | Duration (`for`) | Description |
|---|---|---|---|---|
| `NodeDown` | `critical` | `probe_success{job="lab-icmp"} == 0` | `15s` | Management ICMP ping to node failed. |
| `HighLatency` | `warning` | `probe_icmp_duration_seconds{phase="rtt"} > 0.05` | `30s` | ICMP round-trip latency exceeded 50 ms. |
| `OspfNeighborDown`| `critical`| `frr_ospf_neighbor_state == 0` | `10s` | OSPF adjacency state fell below `Full`. |
| `InterfaceDown` | `warning` | `network_interface_up{device=~"eth[0-9]+"} == 0` | `10s` | Carrier state of network link is DOWN. |
| `HighInterfaceDropRate` | `warning` | `rate(network_receive_drop_total[1m]) > 5 or rate(network_transmit_drop_total[1m]) > 5` | `20s` | Interface is actively dropping $> 5$ packets per second. |

### Unit Testing Alert Rules
To ensure rule syntax and timing conditions remain robust across edits, unit tests are defined in [tests/noc.rules.test.yml](file:///home/drac/noc-sim/tests/noc.rules.test.yml) and verified via:
```bash
make test
```

