# NOC Simulator (NOC-Sim)

[![Topology](https://img.shields.io/badge/Topology-FRRouting%20+%20Containerlab-blue.svg)](#network-topology)
[![Telemetry](https://img.shields.io/badge/Telemetry-Prometheus%20+%20Loki-orange.svg)](#telemetry--observability-stack)
[![Dashboard](https://img.shields.io/badge/Visualization-Grafana-F46800.svg)](#grafana-dashboards)
[![Chaos](https://img.shields.io/badge/Chaos%20Engineering-Automated-critical.svg)](#chaos-engineering--fault-injection)

**NOC-Sim** is a production-grade Network Operations Center (NOC) simulation and chaos-engineering testbed. It pairs an enterprise-grade routed network topology (FRRouting OSPF mesh across dual-tier Core/Distribution layers) with modern cloud-native observability (Prometheus, Loki, Grafana, Alertmanager, and Alloy).

It features automated diurnal multi-pattern traffic generation, real-world optical/routing chaos scheduling, high-volume syslog streaming, and an incident management webhook receiver.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Quickstart Guide](#quickstart-guide)
3. [One-Click Autonomous Simulation](#one-click-autonomous-simulation)
4. [Documentation Suite](#documentation-suite)
5. [Monitoring & Port Reference](#monitoring--port-reference)
6. [Makefile Command Cheatsheet](#makefile-command-cheatsheet)
7. [Repository Structure](#repository-structure)

---

## Architecture Overview

```
                      +-------------------+
                      |   Grafana :3000   |
                      |  (NOC Dashboard)  |
                      +---------+---------+
                                |
          +---------------------+---------------------+
          |                                           |
+---------v---------+                       +---------v---------+
| Prometheus  :9090 |                       |   Loki     :3100  |
|  (Time Series)    |                       |   (Log Stream)    |
+---------+---------+                       +---------+---------+
          |                                           |
    +-----+-----+-------------------+                 |
    |           |                   |                 |
+---v---+   +---v---+           +---v---+       +-----v-----+
| ICMP  |   | SNMP/ |           | Alert |       |  Grafana  |
| Probe |   | FRR   |           |  Mgr  |       |   Alloy   |
| :9115 |   | :9348 |           | :9093 |       +-----+-----+
+---+---+   +---+---+           +---+---+             |
    |           |                   |                 |
    |           |       +-----------v-----------+     |
    |           |       | Incident Center :9095 |     |
    |           |       +-----------------------+     |
    +-----+-----+-------------------------------------+
          |
  [ Management Network: 172.20.20.0/24 ]
          |
    +-----+-------------------------------------------+
    |                     DATA PLANE                  |
    |                                                 |
    |        +-------------+         +-------------+  |
    |        |    core1    |=========|    core2    |  |
    |        +------+------+  10.0.12|------+------+  |
    |               | 10.0.13        10.0.24|         |
    |               |       10.0.23         |         |
    |               |   +---------------+   |         |
    |               \   /               \   /         |
    |             +---v---+           +---v---+       |
    |             | dist1 |           | dist2 |       |
    |             +---+---+           +---+---+       |
    |                 |                   |           |
    |                 | 192.168.10.0/24   | 192.168.20|
    |             +---v---+           +---v---+       |
    |             | host1 |           | host2 |       |
    |             +-------+           +-------+       |
    +-------------------------------------------------+
```

---

## Quickstart Guide

### Prerequisites
* Linux (Kernel $\ge$ 5.4)
* Docker & Docker Compose v2
* [Containerlab](https://containerlab.dev/) installed (`curl -sL https://containerlab.dev/setup | sudo bash -`)
* Python 3.8+ (for telemetry exporters and workload scripts)
* `promtool` (optional, for alert rule verification)

### Step 1: Launch Observability Stack
```bash
make up
```
Starts Prometheus, Alertmanager, Blackbox Exporter, Loki, Grafana Alloy, and Grafana in host-network mode.

### Step 2: Deploy Network Topology
```bash
make deploy
```
Spins up the 4 FRRouting containers and 2 Netshoot host containers via Containerlab, auto-configuring interfaces, OSPF areas, and routes.

### Step 3: Verify Convergence & Health
```bash
make verify
```
Runs end-to-end checks:
* Verifies `core1`, `core2`, `dist1`, and `dist2` reach `Full` OSPF neighbor state.
* Tests bi-directional ping between `host1` (192.168.10.10) and `host2` (192.168.20.10).
* Validates management IP connectivity.

### Step 4: Validate Alerting Rules
```bash
make test
```
Executes Prometheus unit tests using `promtool` against [noc.rules.yml](file:///home/drac/noc-sim/prometheus/rules/noc.rules.yml).

---

## One-Click Autonomous Simulation

To simulate authentic real-world enterprise operations (business-cycle traffic, synthetic HTTP/VoIP transactions, router syslogs, and active incidents):

```bash
# Standard real-world enterprise workload & telemetry
make simulate

# Enterprise workload + autonomous chaos injection & self-healing
make simulate-chaos
```

This single command launches and coordinates:
1. **FRR & Interface Telemetry Exporter** (`:9348/metrics`)
2. **Incident Management Center UI & Webhook Receiver** (`:9095`)
3. **Multi-Pattern Workload Generator** (Diurnal curve + bursts + VoIP + HTTP)
4. **High-Volume Router Syslog Streamer** (Pushes OSPF/BFD/Optics logs to Loki)
5. **Autonomous Chaos Scheduler** (Randomly executes and auto-remediates link flaps, packet loss, and jitter)

---

## Documentation Suite

Detailed guides and manuals are provided in the [docs/](file:///home/drac/noc-sim/docs) folder:

* 📖 **[Architecture & Network Topology](file:///home/drac/noc-sim/docs/architecture.md)**: Detailed link subnetting, loopback addresses, OSPF parameters, and routing design.
* 📊 **[Telemetry, Metrics & Alerts Manual](file:///home/drac/noc-sim/docs/telemetry.md)**: Full Prometheus metrics reference, Loki log schema, and PromQL alert definitions.
* 💥 **[Chaos Engineering & Operations Manual](file:///home/drac/noc-sim/docs/chaos_and_operations.md)**: Manual and automated chaos workflows, fault injection commands, and incident triage runbooks.

---

## Monitoring & Port Reference

| Service | Port | Endpoint | Description |
|---|---|---|---|
| **Grafana** | `3000` | http://127.0.0.1:3000 | Unified NOC overview dashboard (User: `admin`, Password in `.env`) |
| **Incident Center** | `9095` | http://127.0.0.1:9095 | Live Alertmanager webhook stream & incident triage dashboard |
| **Prometheus** | `9090` | http://127.0.0.1:9090 | Time-series metrics collection and PromQL engine |
| **Alertmanager** | `9093` | http://127.0.0.1:9093 | Alert deduplication, grouping, and notification routing |
| **Telemetry Exporter** | `9348` | http://127.0.0.1:9348/metrics | Real-time OSPF adjacency and Linux interface metrics |
| **Loki** | `3100` | http://127.0.0.1:3100 | Log aggregation backend for router and container logs |
| **Blackbox Exporter** | `9115` | http://127.0.0.1:9115 | ICMP and synthetic TCP/HTTP probe engine |
| **Grafana Alloy** | `12345` | http://127.0.0.1:12345 | Docker log shipping pipeline |

---

## Makefile Command Cheatsheet

### Core Lifecycle
```bash
make up               # Start docker monitoring stack
make down             # Stop docker monitoring stack
make deploy           # Deploy or reconfigure containerlab topology
make destroy          # Destroy containerlab topology and clean virtual bridges
make status           # Show container status and inspect lab
make verify           # Run convergence and connectivity checks
make test             # Run promtool alert rule tests
make logs             # Tail container logs
```

### Workload & Chaos Simulation
```bash
make simulate         # Start all telemetry & workloads in unified orchestrator
make simulate-chaos   # Start orchestrator with autonomous chaos incidents
make workload         # Run standalone multi-pattern traffic generator
make chaos            # Run standalone autonomous chaos scheduler
make syslog-stream    # Run standalone high-volume router syslog generator
make telemetry        # Run standalone FRR telemetry exporter (:9348)
make incident-receiver# Run standalone Incident Center UI (:9095)
```

### Manual Fault Scenarios
```bash
make scenario-flap     # Flap core1-core2 interconnect link 3 times
make scenario-loss     # Inject 20% loss & 60ms delay on core1-dist1 transit
make scenario-isolate  # Isolate core1 completely (validates auto-failover to core2)
make scenario-clean    # Clear all packet loss/latency rules and restore links
```

---

## Repository Structure

```
noc-sim/
├── Makefile                          # Primary operator command interface
├── README.md                         # Main repository guide
├── docker-compose.yml                # Monitoring stack definition
├── .env                              # Pinned container images and secrets
├── docs/                             # Comprehensive architectural manuals
│   ├── architecture.md               # Topology, OSPF design & IP schema
│   ├── telemetry.md                  # Metrics reference, Loki logs & alerts
│   └── chaos_and_operations.md       # Chaos injection & incident runbooks
├── topology/                         # Containerlab definitions
│   ├── noc-lab.clab.yml              # Lab topology declaration
│   └── configs/                      # FRR configuration per router
│       ├── core1/ (daemons, frr.conf)
│       ├── core2/ (daemons, frr.conf)
│       ├── dist1/ (daemons, frr.conf)
│       └── dist2/ (daemons, frr.conf)
├── prometheus/
│   ├── prometheus.yml                # Scrape configs & target definitions
│   └── rules/
│       └── noc.rules.yml             # Prometheus alerting rules
├── alertmanager/
│   └── alertmanager.yml              # Alert grouping & webhook routes
├── blackbox/
│   └── blackbox.yml                  # ICMP & HTTP probe modules
├── loki/
│   └── loki.yml                      # Loki storage and retention config
├── alloy/
│   └── config.alloy                  # Docker container log tailing config
├── grafana/
│   ├── provisioning/                 # Datasource & dashboard providers
│   └── dashboards/
│       └── noc-overview.json         # Primary NOC operations dashboard
├── scripts/
│   ├── orchestrator.py               # Master simulation runner
│   ├── workload_generator.py         # Multi-pattern enterprise traffic generator
│   ├── chaos_scheduler.py            # Autonomous chaos & incident injector
│   ├── telemetry_streamer.py         # Syslog & telemetry streamer to Loki
│   ├── frr_exporter.py               # FRR vtysh & Linux netdev exporter
│   ├── incident_receiver.py          # Incident UI & Alertmanager webhook
│   ├── fault.sh                      # Granular netem / link state CLI
│   ├── verify.sh                     # Convergence and ping verifier
│   ├── scenario.sh                   # Scripted fault scenarios
│   └── traffic.sh                    # Background iperf3 traffic tool
└── tests/
    └── noc.rules.test.yml            # Unit tests for alert rules
```
