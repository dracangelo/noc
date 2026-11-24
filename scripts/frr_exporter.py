#!/usr/bin/env python3
"""
Lightweight FRR & Linux Network Telemetry Exporter for Containerlab.
Connects via docker exec or management IP to collect:
 - OSPF neighbor state (Full, 2-Way, Init, Down)
 - Interface metrics (rx/tx bytes, rx/tx packets, errors, drops, operstate)
 - Route count (total, ospf, connected, kernel)
Exposes metrics on :9348/metrics for Prometheus scraping.
"""

import http.server
import json
import os
import re
import socketserver
import subprocess
import threading
import time

PORT = int(os.environ.get("EXPORTER_PORT", 9348))
LAB = os.environ.get("LAB_NAME", "noc-lab")
ROUTERS = ["core1", "core2", "dist1", "dist2"]
HOSTS = ["host1", "host2"]

cached_metrics = ""
cache_lock = threading.Lock()

def run_cmd(node, cmd):
    container = f"clab-{LAB}-{node}"
    # Prefer docker exec (fast and direct within docker host network)
    full_cmd = ["docker", "exec", container] + cmd
    try:
        res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    # Fallback to sudo docker exec if needed
    try:
        res = subprocess.run(["sudo"] + full_cmd, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return None

def collect_router_telemetry(node):
    lines = []
    
    # 1. OSPF Neighbor JSON
    ospf_json = run_cmd(node, ["vtysh", "-c", "show ip ospf neighbor json"])
    if ospf_json:
        try:
            data = json.loads(ospf_json)
            # data has structure: {"neighbors": {"10.0.12.2": [{"converged": "Full", ...}]}} or similar depending on frr version
            # Alternatively parse keys
            nbrs = data.get("neighbors", {})
            for nbr_ip, nbr_list in nbrs.items():
                if isinstance(nbr_list, list):
                    for n in nbr_list:
                        router_id = n.get("routerId", nbr_ip)
                        iface = n.get("interfaceName", "unknown")
                        nbr_state_str = n.get("nbrState", "")
                        state_val = 1 if "Full" in nbr_state_str else 0
                        dead_time = n.get("deadTimeMsecs", 0) / 1000.0
                        lines.append(f'frr_ospf_neighbor_state{{node="{node}",neighbor="{router_id}",interface="{iface}",state="{nbr_state_str}"}} {state_val}')
                        lines.append(f'frr_ospf_neighbor_dead_time_seconds{{node="{node}",neighbor="{router_id}",interface="{iface}"}} {dead_time}')
        except Exception:
            pass

    # 2. Routing table count
    route_summary = run_cmd(node, ["vtysh", "-c", "show ip route summary json"])
    if route_summary:
        try:
            rdata = json.loads(route_summary)
            # e.g., {"ospf": {"totalRoutes": 5}, "connected": {"totalRoutes": 4}}
            for proto, stats in rdata.items():
                if isinstance(stats, dict) and "totalRoutes" in stats:
                    lines.append(f'frr_routes_total{{node="{node}",protocol="{proto}"}} {stats["totalRoutes"]}')
        except Exception:
            pass

    # 3. Interface stats via /proc/net/dev
    netdev = run_cmd(node, ["cat", "/proc/net/dev"])
    if netdev:
        for line in netdev.splitlines():
            line = line.strip()
            if ":" not in line or line.startswith("Inter-") or line.startswith("face"):
                continue
            iface, stats = line.split(":", 1)
            iface = iface.strip()
            fields = stats.split()
            if len(fields) >= 16:
                rx_bytes, rx_packets, rx_errs, rx_drop = fields[0], fields[1], fields[2], fields[3]
                tx_bytes, tx_packets, tx_errs, tx_drop = fields[8], fields[9], fields[10], fields[11]
                lines.append(f'network_receive_bytes_total{{node="{node}",device="{iface}"}} {rx_bytes}')
                lines.append(f'network_receive_packets_total{{node="{node}",device="{iface}"}} {rx_packets}')
                lines.append(f'network_receive_errs_total{{node="{node}",device="{iface}"}} {rx_errs}')
                lines.append(f'network_receive_drop_total{{node="{node}",device="{iface}"}} {rx_drop}')
                lines.append(f'network_transmit_bytes_total{{node="{node}",device="{iface}"}} {tx_bytes}')
                lines.append(f'network_transmit_packets_total{{node="{node}",device="{iface}"}} {tx_packets}')
                lines.append(f'network_transmit_errs_total{{node="{node}",device="{iface}"}} {tx_errs}')
                lines.append(f'network_transmit_drop_total{{node="{node}",device="{iface}"}} {tx_drop}')

    # 4. Interface state
    iplink = run_cmd(node, ["ip", "-j", "link", "show"])
    if iplink:
        try:
            link_data = json.loads(iplink)
            for l in link_data:
                ifname = l.get("ifname", "")
                flags = l.get("flags", [])
                operstate = l.get("operstate", "UNKNOWN")
                is_up = 1 if ("UP" in flags or operstate == "UP") else 0
                lines.append(f'network_interface_up{{node="{node}",device="{ifname}",state="{operstate}"}} {is_up}')
        except Exception:
            pass

    return lines

def collect_host_telemetry(node):
    lines = []
    netdev = run_cmd(node, ["cat", "/proc/net/dev"])
    if netdev:
        for line in netdev.splitlines():
            line = line.strip()
            if ":" not in line or line.startswith("Inter-") or line.startswith("face"):
                continue
            iface, stats = line.split(":", 1)
            iface = iface.strip()
            fields = stats.split()
            if len(fields) >= 16:
                rx_bytes, rx_packets, rx_errs, rx_drop = fields[0], fields[1], fields[2], fields[3]
                tx_bytes, tx_packets, tx_errs, tx_drop = fields[8], fields[9], fields[10], fields[11]
                lines.append(f'network_receive_bytes_total{{node="{node}",device="{iface}"}} {rx_bytes}')
                lines.append(f'network_transmit_bytes_total{{node="{node}",device="{iface}"}} {tx_bytes}')
                lines.append(f'network_receive_drop_total{{node="{node}",device="{iface}"}} {rx_drop}')
    return lines

def scrape_worker():
    global cached_metrics
    while True:
        output_lines = [
            "# HELP frr_ospf_neighbor_state OSPF neighbor state (1=Full, 0=not full)",
            "# TYPE frr_ospf_neighbor_state gauge",
            "# HELP frr_ospf_neighbor_dead_time_seconds OSPF neighbor dead time in seconds",
            "# TYPE frr_ospf_neighbor_dead_time_seconds gauge",
            "# HELP frr_routes_total Number of routes by protocol",
            "# TYPE frr_routes_total gauge",
            "# HELP network_interface_up Network interface administrative / operational state",
            "# TYPE network_interface_up gauge",
            "# HELP network_receive_bytes_total Total received bytes",
            "# TYPE network_receive_bytes_total counter",
            "# HELP network_transmit_bytes_total Total transmitted bytes",
            "# TYPE network_transmit_bytes_total counter",
            "# HELP network_receive_packets_total Total received packets",
            "# TYPE network_receive_packets_total counter",
            "# HELP network_transmit_packets_total Total transmitted packets",
            "# TYPE network_transmit_packets_total counter",
            "# HELP network_receive_errs_total Total receive errors",
            "# TYPE network_receive_errs_total counter",
            "# HELP network_transmit_errs_total Total transmit errors",
            "# TYPE network_transmit_errs_total counter",
            "# HELP network_receive_drop_total Total receive dropped packets",
            "# TYPE network_receive_drop_total counter",
            "# HELP network_transmit_drop_total Total transmit dropped packets",
            "# TYPE network_transmit_drop_total counter",
        ]

        for r in ROUTERS:
            output_lines.extend(collect_router_telemetry(r))
        for h in HOSTS:
            output_lines.extend(collect_host_telemetry(h))

        body = "\n".join(output_lines) + "\n"
        with cache_lock:
            cached_metrics = body

        time.sleep(3)

class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            with cache_lock:
                data = cached_metrics.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def main():
    t = threading.Thread(target=scrape_worker, daemon=True)
    t.start()
    
    server = socketserver.TCPServer(("0.0.0.0", PORT), MetricsHandler)
    print(f"FRR & Network Telemetry Exporter listening on :{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()

