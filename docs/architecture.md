# Architecture & Network Topology Manual

## 1. Overview
The **NOC-Sim** data plane is designed as a redundant, dual-tier routed Clos network topology deployed in [Containerlab](https://containerlab.dev/). It models standard enterprise campus and data-center aggregation architectures with no single point of failure (SPOF).

The routing protocol is **OSPFv2** (Open Shortest Path First) running across **FRRouting (FRR) 10.2.1** Linux containers.

---

## 2. IP Addressing & Subnet Schema

### 2.1 Management Network
The out-of-band management network enables Prometheus, Blackbox Exporter, and administrative tooling to monitor nodes independently of data-plane link failures:
* **Subnet**: `172.20.20.0/24`
* **Docker Network**: `noc-mgmt`

| Node | Role | Management IP | Image |
|---|---|---|---|
| `core1` | Core Router 1 | `172.20.20.11` | `quay.io/frrouting/frr:10.2.1` |
| `core2` | Core Router 2 | `172.20.20.12` | `quay.io/frrouting/frr:10.2.1` |
| `dist1` | Distribution Router 1 | `172.20.20.13` | `quay.io/frrouting/frr:10.2.1` |
| `dist2` | Distribution Router 2 | `172.20.20.14` | `quay.io/frrouting/frr:10.2.1` |
| `host1` | Workstation / Edge 1 | `172.20.20.15` | `nicolaka/netshoot:latest` |
| `host2` | Server / Edge 2 | `172.20.20.16` | `nicolaka/netshoot:latest` |

---

### 2.2 Point-to-Point Transit Links (Area 0)
All transit interfaces use `/30` point-to-point subnets with aggressive hello/dead timers to support sub-second convergence testing:

| Link | End A (IP) | End B (IP) | Subnet | OSPF Type |
|---|---|---|---|---|
| `core1:eth1` $\leftrightarrow$ `core2:eth1` | `10.0.12.1/30` | `10.0.12.2/30` | `10.0.12.0/30` | point-to-point |
| `core1:eth2` $\leftrightarrow$ `dist1:eth1` | `10.0.13.1/30` | `10.0.13.2/30` | `10.0.13.0/30` | point-to-point |
| `core1:eth3` $\leftrightarrow$ `dist2:eth1` | `10.0.14.1/30` | `10.0.14.2/30` | `10.0.14.0/30` | point-to-point |
| `core2:eth2` $\leftrightarrow$ `dist1:eth2` | `10.0.23.1/30` | `10.0.23.2/30` | `10.0.23.0/30` | point-to-point |
| `core2:eth3` $\leftrightarrow$ `dist2:eth2` | `10.0.24.1/30` | `10.0.24.2/30` | `10.0.24.0/30` | point-to-point |

---

### 2.3 Access & Host Subnets
Edge hosts connect directly to distribution routers on stub networks:
* **Host 1 Subnet**: `192.168.10.0/24`
  * Gateway (`dist1:eth3`): `192.168.10.1` (configured as OSPF `passive-interface`)
  * Host (`host1:eth1`): `192.168.10.10`
* **Host 2 Subnet**: `192.168.20.0/24`
  * Gateway (`dist2:eth3`): `192.168.20.1` (configured as OSPF `passive-interface`)
  * Host (`host2:eth1`): `192.168.20.10`

---

### 2.4 Loopback Addresses (Router IDs)
Each router maintains a unique 32-bit loopback address serving as its OSPF Router ID:
* `core1`: `1.1.1.1/32`
* `core2`: `2.2.2.2/32`
* `dist1`: `3.3.3.3/32`
* `dist2`: `4.4.4.4/32`

---

## 3. OSPF Protocol Design & Tuning

### Fast Convergence Timers
To ensure faults and link flaps propagate immediately into telemetry and alerts without waiting for default 40-second dead times, all transit links are configured with fast timers:
```text
interface eth1
 ip ospf network point-to-point
 ip ospf hello-interval 1
 ip ospf dead-interval 4
```
* **Hello interval**: `1 second`
* **Dead interval**: `4 seconds`
* **Adjacency expectation**:
  * `core1`: 3 Full neighbors (`core2`, `dist1`, `dist2`)
  * `core2`: 3 Full neighbors (`core1`, `dist1`, `dist2`)
  * `dist1`: 2 Full neighbors (`core1`, `core2`)
  * `dist2`: 2 Full neighbors (`core1`, `core2`)

### Multipath (ECMP) Redundancy
Because link metrics are equal across the core mesh, traffic between `host1` and `host2` can dynamically use either `core1` or `core2`. If either core router fails or an interconnect is cut, OSPF Dijkstra SPF recalculation converges in $\le 4$ seconds, rerouting 100% of packets through the surviving core without human intervention.

