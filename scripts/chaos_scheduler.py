#!/usr/bin/env python3
"""
Autonomous Chaos & Incident Scheduler for NOC Simulator.
Runs in the background, executing realistic real-world network operational events:
 - Sudden transit path jitter / packet loss spikes (micro-burst buffer overflows)
 - Optical link flap simulation (cable degradation / transceiver CRC errors)
 - Core node maintenance & unannounced failover events
 - Automatic recovery / MTTR tracking
"""

import argparse
import datetime
import os
import random
import subprocess
import sys
import time

LAB = os.environ.get("LAB_NAME", "noc-lab")
DIR = os.path.dirname(os.path.abspath(__file__))
FAULT_SH = os.path.join(DIR, "fault.sh")

CHAOS_EVENTS = [
    {
        "name": "Buffer Bloat & Transit Jitter",
        "description": "Injects 65ms latency + 15ms jitter on core1 <-> dist1 transit interface",
        "apply": lambda: run_cmd([FAULT_SH, "delay", "core1", "eth2", "65"]),
        "clear": lambda: run_cmd([FAULT_SH, "clear", "core1", "eth2"]),
        "duration": (20, 45)
    },
    {
        "name": "Dirty Fiber / Packet Loss Degradation",
        "description": "Induces 18% packet loss on core2 <-> dist2 link (simulating optic degradation)",
        "apply": lambda: run_cmd([FAULT_SH, "loss", "core2", "eth3", "18"]),
        "clear": lambda: run_cmd([FAULT_SH, "clear", "core2", "eth3"]),
        "duration": (25, 50)
    },
    {
        "name": "Inter-Core Link Flap Storm",
        "description": "Flaps core1 <-> core2 interconnect link 2 times causing OSPF reconvergence",
        "apply": lambda: flap_link("core1", "eth1", 2, 4),
        "clear": lambda: run_cmd([FAULT_SH, "up", "core1", "eth1"]),
        "duration": (15, 30)
    },
    {
        "name": "Asymmetric Routing Degradation",
        "description": "Degrades return path on dist1:eth2 with 90ms latency and 12% loss",
        "apply": lambda: apply_asymmetric(),
        "clear": lambda: clear_asymmetric(),
        "duration": (25, 45)
    }
]

def run_cmd(cmd):
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass

def flap_link(node, iface, count=2, gap=4):
    for _ in range(count):
        run_cmd([FAULT_SH, "down", node, iface])
        time.sleep(gap)
        run_cmd([FAULT_SH, "up", node, iface])
        time.sleep(gap)

def apply_asymmetric():
    run_cmd([FAULT_SH, "delay", "dist1", "eth2", "90"])
    run_cmd([FAULT_SH, "loss", "dist1", "eth2", "12"])

def clear_asymmetric():
    run_cmd([FAULT_SH, "clear", "dist1", "eth2"])

def log_event(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = "\033[1;36m"
    if level == "INCIDENT":
        color = "\033[1;31m"
    elif level == "RECOVERY":
        color = "\033[1;32m"
    print(f"{color}[{ts}] [{level}]\033[0m {msg}")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Chaos Scheduler")
    parser.add_argument("--min-gap", type=int, default=40, help="Minimum seconds between chaos incidents")
    parser.add_argument("--max-gap", type=int, default=90, help="Maximum seconds between chaos incidents")
    args = parser.parse_args()

    log_event("Starting Autonomous Chaos & Real-world Incident Scheduler...")
    log_event(f"Schedule: 1 random incident every {args.min_gap}-{args.max_gap}s.")

    try:
        while True:
            gap = random.randint(args.min_gap, args.max_gap)
            log_event(f"All links healthy. Next incident will trigger in {gap}s.")
            time.sleep(gap)

            event = random.choice(CHAOS_EVENTS)
            dur = random.randint(event["duration"][0], event["duration"][1])

            log_event(f"🔥 INCIDENT TRIGGERED: {event['name']} (Duration: {dur}s)", level="INCIDENT")
            log_event(f"Details: {event['description']}")
            event["apply"]()

            time.sleep(dur)

            log_event(f"✅ RECOVERY: Auto-remediation / incident resolution completed for {event['name']}", level="RECOVERY")
            event["clear"]()
            run_cmd([os.path.join(DIR, "scenario.sh"), "clean"])

    except KeyboardInterrupt:
        log_event("Stopping Chaos Scheduler. Restoring all interfaces...")
        run_cmd([os.path.join(DIR, "scenario.sh"), "clean"])
        log_event("Cleaned and restored.")

if __name__ == "__main__":
    main()

