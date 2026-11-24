#!/usr/bin/env python3
"""
Enterprise Network Telemetry & High-Volume Log Streamer for NOC Simulator.
Pushes authentic network device syslog events and high-volume routing telemetry into Loki
and the local logging pipelines, matching what real Cisco / Juniper / Arista / FRR routers emit:
 - OSPF Adjacency state machine transitions (Init -> ExStart -> Exchange -> Loading -> Full)
 - BFD (Bidirectional Forwarding Detection) session state and echo packet drops
 - Interface carrier transitions (link up/down, transceiver SFP DDM temperature/power alerts)
 - Routing table fib updates and SPF calculation timings
 - Access-list denial security events
"""

import argparse
import datetime
import json
import os
import random
import sys
import time
import urllib.request

LOKI_URL = os.environ.get("LOKI_URL", "http://127.0.0.1:3100/loki/api/v1/push")
ROUTERS = ["core1", "core2", "dist1", "dist2"]

SYSLOG_TEMPLATES = [
    # OSPF
    ("OSPF-5-ADJCHANGE", "info", "Process 1, Nbr {neighbor} on {iface} from LOADING to FULL, Loading Done"),
    ("OSPF-5-ADJCHANGE", "warning", "Process 1, Nbr {neighbor} on {iface} from FULL to DOWN, Neighbor Down: Dead timer expired"),
    ("OSPF-4-ERRRCV", "warning", "OSPF: Received invalid packet on interface {iface}: Bad Checksum 0x{hex4}"),
    ("OSPF-6-SPF_CALC", "info", "SPF calculation completed in {spf_ms} ms, 14 vertices processed"),
    # BFD
    ("BFD-5-STATE_CHANGE", "info", "BFD session with neighbor {neighbor} changed state from INIT to UP"),
    ("BFD-4-TIMEOUT", "warning", "BFD session to neighbor {neighbor} on {iface} timed out after 3 missed hellos"),
    # Interface & Optics
    ("LINK-3-UPDOWN", "info", "Interface {iface}, changed state to up"),
    ("LINK-3-UPDOWN", "warning", "Interface {iface}, changed state to down"),
    ("TRANSCEIVER-4-DDM_ALARM", "warning", "SFP interface {iface}: Optical Rx Power below warning threshold (-18.4 dBm)"),
    ("TRANSCEIVER-4-TEMP", "info", "SFP interface {iface}: Operating temperature nominal 42.1 C"),
    ("ETHERNET-4-CRC_ERR", "warning", "Interface {iface}: Ingress FCS/CRC error count exceeded rate threshold (12 pkts/sec)"),
    # Security / ACL
    ("SEC-6-ACL_DENY", "info", "List INGRESS_PROTECT denied udp 192.168.10.15({port}) -> 192.168.20.16(53), 1 packet"),
    ("SEC-4-TCP_SYN_FLOOD", "warning", "Rate limit triggered for TCP SYN flood protection on {iface}")
]

def make_log_entry(node):
    tag, severity, msg_tmpl = random.choice(SYSLOG_TEMPLATES)
    ifaces = ["eth1", "eth2", "eth3"]
    nbrs = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"]
    iface = random.choice(ifaces)
    neighbor = random.choice([n for n in nbrs if n != node])

    msg = msg_tmpl.format(
        neighbor=neighbor,
        iface=iface,
        hex4=f"{random.randint(4096, 65535):04x}",
        spf_ms=random.randint(1, 14),
        port=random.randint(1024, 65535)
    )

    now_ns = str(time.time_ns())
    log_line = f"{datetime.datetime.now().strftime('%b %d %H:%M:%S')} {node} %{tag}: {msg}"
    return node, severity, now_ns, log_line

def push_to_loki(entries):
    # entries: list of (node, severity, timestamp_ns, line)
    # Stream payload for Loki JSON API
    streams = []
    streams_by_node = {}
    for node, sev, ts, line in entries:
        key = (node, sev)
        if key not in streams_by_node:
            streams_by_node[key] = []
        streams_by_node[key].append([ts, line])

    for (node, sev), values in streams_by_node.items():
        streams.append({
            "stream": {
                "job": "lab-logs",
                "lab": "noc-lab",
                "node": node,
                "level": sev,
                "facility": "daemon"
            },
            "values": values
        })

    payload = json.dumps({"streams": streams}).encode("utf-8")
    req = urllib.request.Request(
        LOKI_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 204 or resp.status == 200
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description="Real-world Network Syslog & Telemetry Streamer")
    parser.add_argument("--rate", type=float, default=3.0, help="Log events per second")
    args = parser.parse_args()

    print(f"[SYSLOG-STREAMER] Starting real-world router telemetry stream to Loki ({LOKI_URL})...")
    print(f"[SYSLOG-STREAMER] Event rate: ~{args.rate} events/sec across nodes {ROUTERS}")

    batch = []
    last_flush = time.time()

    try:
        while True:
            node = random.choice(ROUTERS)
            entry = make_log_entry(node)
            batch.append(entry)

            # Flush batch every 1-2 seconds or when batch hits 10
            now = time.time()
            if (now - last_flush) >= 1.5 or len(batch) >= 10:
                push_to_loki(batch)
                batch = []
                last_flush = now

            sleep_time = max(0.05, 1.0 / args.rate)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        if batch:
            push_to_loki(batch)
        print("\n[SYSLOG-STREAMER] Stopped.")

if __name__ == "__main__":
    main()

