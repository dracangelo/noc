#!/usr/bin/env python3
"""
NOC Master Simulation & Automation Orchestrator.
Orchestrates the entire enterprise NOC environment:
 1. FRR and interface telemetry exporter (:9348)
 2. Incident webhook receiver (:9095)
 3. Continuous multi-pattern enterprise traffic & transactions
 4. Realistic router syslog & OSPF/BFD telemetry streamer (into Loki)
 5. Autonomous chaos and real-world incident injection engine (optional flag)
"""

import argparse
import os
import signal
import subprocess
import sys
import time

DIR = os.path.dirname(os.path.abspath(__file__))

subprocesses = []

def spawn(cmd, name):
    print(f"\033[1;32m[SPAWN]\033[0m Starting {name} ({' '.join(cmd)})...")
    p = subprocess.Popen(cmd)
    subprocesses.append((name, p))
    return p

def shutdown(sig, frame):
    print("\n\033[1;33m[SHUTDOWN]\033[0m Gracefully terminating all simulation services...")
    for name, p in subprocesses:
        try:
            print(f"Stopping {name}...")
            p.terminate()
        except Exception:
            pass
    time.sleep(1)
    for name, p in subprocesses:
        try:
            p.kill()
        except Exception:
            pass
    # Run scenario clean
    try:
        subprocess.run([os.path.join(DIR, "scenario.sh"), "clean"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    print("\033[1;32m[DONE]\033[0m All simulation processes stopped.")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Master NOC Simulator Orchestrator")
    parser.add_argument("--with-chaos", action="store_true", help="Enable autonomous chaos & incident scheduler")
    parser.add_argument("--rate", type=float, default=5.0, help="Base workload bandwidth in Mbps")
    parser.add_argument("--syslog-rate", type=float, default=2.0, help="Syslog event rate/sec to Loki")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 65)
    print("      🚀 NOC ENTERPRISE TELEMETRY & WORKLOAD ORCHESTRATOR 🚀      ")
    print("=" * 65)
    print("Monitoring Stack Endpoints:")
    print("  • Grafana Dashboard  : http://127.0.0.1:3000")
    print("  • Prometheus         : http://127.0.0.1:9090")
    print("  • Alertmanager       : http://127.0.0.1:9093")
    print("  • Incident Center UI : http://127.0.0.1:9095")
    print("  • Telemetry Exporter : http://127.0.0.1:9348/metrics")
    print("=" * 65)

    # 1. Telemetry Exporter
    spawn([sys.executable, os.path.join(DIR, "frr_exporter.py")], "FRR Telemetry Exporter")
    time.sleep(1)

    # 2. Incident Receiver
    spawn([sys.executable, os.path.join(DIR, "incident_receiver.py")], "Incident Receiver & Webhook UI")
    time.sleep(1)

    # 3. Workload Generator
    spawn([sys.executable, os.path.join(DIR, "workload_generator.py"), "--rate", str(args.rate)], "Enterprise Workload Generator")
    time.sleep(1)

    # 4. Syslog & Telemetry Streamer
    spawn([sys.executable, os.path.join(DIR, "telemetry_streamer.py"), "--rate", str(args.syslog_rate)], "Router Syslog Streamer")

    # 5. Optional Chaos Scheduler
    if args.with_chaos:
        time.sleep(2)
        spawn([sys.executable, os.path.join(DIR, "chaos_scheduler.py")], "Autonomous Chaos Scheduler")

    print("\n\033[1;36m[STATUS]\033[0m All engines running. Press Ctrl+C at any time to halt.")

    while True:
        time.sleep(2)
        for name, p in subprocesses:
            if p.poll() is not None:
                print(f"\033[1;31m[WARN]\033[0m Service {name} exited unexpectedly (code {p.returncode})")

if __name__ == "__main__":
    main()

