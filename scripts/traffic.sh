#!/usr/bin/env bash
# Traffic generator for noc-lab.
# Generates realistic continuous background traffic between host1 and host2:
# - iperf3 continuous stream / burst
# - continuous HTTP/DNS/ping synthetic probe traffic
# Usage:
#   scripts/traffic.sh start [rate_in_mbps]
#   scripts/traffic.sh stop
#   scripts/traffic.sh burst [duration_sec] [mbps]
set -euo pipefail

LAB=noc-lab
ACTION="${1:-start}"
RATE="${2:-5M}"

dx() {
  if docker info >/dev/null 2>&1; then
    docker exec "clab-$LAB-$1" "${@:2}"
  else
    sudo docker exec "clab-$LAB-$1" "${@:2}"
  fi
}

case "$ACTION" in
  start)
    echo "Starting iperf3 server on host2..."
    dx host2 pkill -f iperf3 2>/dev/null || true
    dx host2 iperf3 -s -D || true
    
    echo "Starting continuous background traffic from host1 -> host2 ($RATE)..."
    dx host1 pkill -f iperf3 2>/dev/null || true
    dx host1 nohup iperf3 -c 192.168.20.10 -u -b "$RATE" -t 0 >/dev/null 2>&1 &
    
    echo "Starting continuous ICMP probes host1 -> host2..."
    dx host1 pkill -f "ping -i 0.5" 2>/dev/null || true
    dx host1 nohup ping -i 0.5 192.168.20.10 >/dev/null 2>&1 &
    echo "Traffic generation active."
    ;;

  burst)
    DUR="${2:-15}"
    BURST_RATE="${3:-50M}"
    echo "Triggering high-volume traffic spike ($BURST_RATE for ${DUR}s)..."
    dx host1 iperf3 -c 192.168.20.10 -u -b "$BURST_RATE" -t "$DUR"
    echo "Traffic spike completed."
    ;;

  stop)
    echo "Stopping traffic generators..."
    dx host1 pkill -f iperf3 2>/dev/null || true
    dx host1 pkill -f ping 2>/dev/null || true
    dx host2 pkill -f iperf3 2>/dev/null || true
    echo "Stopped."
    ;;

  status)
    echo "Checking traffic status:"
    echo -n "host2 iperf3 server: "
    dx host2 pgrep -a iperf3 || echo "inactive"
    echo -n "host1 traffic generator: "
    dx host1 pgrep -a iperf3 || echo "inactive"
    ;;

  *)
    echo "Usage: $0 {start [rate]|burst [duration] [rate]|stop|status}"
    exit 1
    ;;
esac

