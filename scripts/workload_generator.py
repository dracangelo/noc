#!/usr/bin/env python3
"""
Enterprise Network Workload & Traffic Generator for NOC Simulator.
Simulates realistic real-world network traffic profiles:
 1. Diurnal / business hour baseline variations (sine wave modulated bandwidth)
 2. Bursty application transactions (HTTP API queries, large file transfer spikes)
 3. VoIP/Video conference RTP UDP flows (constant low-latency packet streams)
 4. Continuous synthetic SLA active probes (DNS, HTTP synthetic transactions, jitter probes)
"""

import argparse
import math
import os
import random
import subprocess
import sys
import threading
import time

LAB = os.environ.get("LAB_NAME", "noc-lab")
HOST1 = f"clab-{LAB}-host1"
HOST2 = f"clab-{LAB}-host2"
HOST1_IP = "192.168.10.10"
HOST2_IP = "192.168.20.10"

running = True

def run_container_cmd(container, cmd, timeout=5):
    full_cmd = ["docker", "exec", container] + cmd
    try:
        res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    try:
        res = subprocess.run(["sudo"] + full_cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return None

def setup_servers():
    print("[INIT] Ensuring destination services are listening on host2...")
    # Start iperf3 server daemon on host2
    run_container_cmd(HOST2, ["pkill", "-f", "iperf3"])
    run_container_cmd(HOST2, ["iperf3", "-s", "-D"])
    
    # Start simple HTTP benchmark server on host2 (port 8080)
    run_container_cmd(HOST2, ["pkill", "-f", "python3 -m http.server"])
    run_container_cmd(HOST2, ["sh", "-c", "python3 -m http.server 8080 >/dev/null 2>&1 &"])
    print("[INIT] Services started on host2.")

def worker_diurnal_bandwidth(base_mbps=5, amplitude=4):
    """Generates continuous UDP flows with realistic diurnal rhythm."""
    print("[WORKLOAD] Starting Diurnal Flow Generator (simulating business day traffic curves)...")
    while running:
        # Calculate dynamic rate based on sine curve + small random jitter
        now = time.time()
        # 120s simulated business cycle for demo purposes
        cycle = (math.sin(now / 20.0) + 1.0) / 2.0  # 0.0 to 1.0
        current_rate_mbps = round(base_mbps + (amplitude * cycle) + random.uniform(-0.5, 0.5), 2)
        current_rate_mbps = max(1.0, current_rate_mbps)

        # Run a 10s UDP flow burst at current_rate_mbps
        run_container_cmd(HOST1, [
            "iperf3", "-c", HOST2_IP,
            "-u",
            "-b", f"{current_rate_mbps}M",
            "-t", "10",
            "-l", "1200"
        ], timeout=15)

def worker_transaction_bursts():
    """Simulates periodic heavy transactional data transfers or backups."""
    print("[WORKLOAD] Starting Transaction & Backup Spike Generator...")
    while running:
        # Sleep for realistic random gap between transactions
        sleep_dur = random.randint(8, 25)
        for _ in range(sleep_dur):
            if not running:
                return
            time.sleep(1)

        burst_mbps = random.choice([25, 40, 60, 80])
        burst_sec = random.randint(4, 10)
        print(f"[WORKLOAD] 🚀 Traffic Spike: {burst_mbps} Mbps for {burst_sec}s")
        run_container_cmd(HOST1, [
            "iperf3", "-c", HOST2_IP,
            "-u",
            "-b", f"{burst_mbps}M",
            "-t", str(burst_sec),
            "-l", "1400"
        ], timeout=burst_sec + 5)

def worker_http_synthetic_transactions():
    """Generates constant API / HTTP synthetic traffic and measures latency."""
    print("[WORKLOAD] Starting Synthetic HTTP/API Transaction Generator...")
    while running:
        # Run curl requests against host2 HTTP server
        run_container_cmd(HOST1, [
            "curl", "-s", "-o", "/dev/null",
            "-w", "%{http_code} %{time_total}s\\n",
            f"http://{HOST2_IP}:8080"
        ], timeout=4)
        time.sleep(random.uniform(0.5, 2.0))

def worker_voip_rtp_simulation():
    """Simulates real-time RTP voice stream (50 pkts/sec, 64kbps audio)."""
    print("[WORKLOAD] Starting VoIP / Conference RTP Stream...")
    while running:
        # 15 seconds RTP-like UDP packet flow
        run_container_cmd(HOST1, [
            "iperf3", "-c", HOST2_IP,
            "-u",
            "-b", "128K",
            "-t", "15",
            "-l", "160"
        ], timeout=20)

def main():
    parser = argparse.ArgumentParser(description="NOC Enterprise Workload Generator")
    parser.add_argument("--rate", type=float, default=6.0, help="Base baseline rate in Mbps")
    args = parser.parse_args()

    setup_servers()

    threads = [
        threading.Thread(target=worker_diurnal_bandwidth, args=(args.rate,), daemon=True),
        threading.Thread(target=worker_transaction_bursts, daemon=True),
        threading.Thread(target=worker_http_synthetic_transactions, daemon=True),
        threading.Thread(target=worker_voip_rtp_simulation, daemon=True),
    ]

    print("[START] Launching all workload simulation engines...")
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down workload generators...")
        global running
        running = False
        run_container_cmd(HOST1, ["pkill", "-f", "iperf3"])
        run_container_cmd(HOST1, ["pkill", "-f", "curl"])
        run_container_cmd(HOST2, ["pkill", "-f", "iperf3"])
        run_container_cmd(HOST2, ["pkill", "-f", "http.server"])
        print("[STOP] Cleaned up.")

if __name__ == "__main__":
    main()

