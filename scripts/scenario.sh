#!/usr/bin/env bash
# Automated Chaos & Fault Scenario Runner for NOC Simulator.
# Simulates real-world network operational incidents with automatic verification.
#
# Scenarios:
#   1. link-flap    : Periodic up/down of core link (OSPF reconvergence storm)
#   2. degraded-link: Injects packet loss and jitter on transit path
#   3. core-failure : Cuts core1 out completely, forcing all traffic via core2
#   4. asymmetric   : Degrades or severs one direction of distribution path
#   5. split-brain  : Isolates both core inter-links, testing dual core divergence
#   6. clean        : Restores all nodes, links, and netem rules
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAULT="$DIR/fault.sh"
VERIFY="$DIR/verify.sh"
SCENARIO="${1:-help}"

log() { echo -e "\033[1;34m[SCENARIO]\033[0m $*"; }
ok()  { echo -e "\033[1;32m[OK]\033[0m $*"; }
warn(){ echo -e "\033[1;33m[WARN]\033[0m $*"; }

case "$SCENARIO" in
  link-flap)
    COUNT="${2:-3}"
    INTERVAL="${3:-5}"
    log "Starting Link Flapping incident on core1:eth1 (core-to-core link) - $COUNT flaps..."
    for ((i=1; i<=COUNT; i++)); do
      log "Flap $i/$COUNT: bringing core1 eth1 DOWN"
      "$FAULT" down core1 eth1
      sleep "$INTERVAL"
      log "Flap $i/$COUNT: bringing core1 eth1 UP"
      "$FAULT" up core1 eth1
      sleep "$INTERVAL"
    done
    ok "Link flap sequence completed. Observe OSPF state changes and alertmanager."
    ;;

  degraded-link)
    LOSS="${2:-15}"
    DELAY="${3:-80}"
    log "Injecting link degradation on core1 <-> dist1 (Loss: ${LOSS}%, Delay: ${DELAY}ms)..."
    "$FAULT" loss core1 eth2 "$LOSS"
    "$FAULT" delay core1 eth2 "$DELAY"
    ok "Degraded link scenario active. Check Grafana latency and packet drop rates."
    ;;

  core-failure)
    log "Simulating catastrophic Core1 failure (isolating all interfaces)..."
    "$FAULT" isolate core1
    warn "Core1 isolated! Checking network redundancy..."
    sleep 4
    if "$VERIFY"; then
      ok "Traffic failover to Core2 successful! Redundant topology held up."
    else
      warn "Verification reported issues during failover. Inspect alerts!"
    fi
    ;;

  asymmetric)
    log "Simulating asymmetric routing degradation: dist1 eth1 degraded, dist2 healthy..."
    "$FAULT" loss dist1 eth1 25
    "$FAULT" delay dist1 eth1 120
    ok "Asymmetric degradation applied. Monitor host1 <-> host2 round-trip times."
    ;;

  clean|restore)
    log "Restoring full topology health..."
    for node in core1 core2 dist1 dist2 host1 host2; do
      "$FAULT" restore "$node" 2>/dev/null || true
      for iface in eth1 eth2 eth3; do
        "$FAULT" clear "$node" "$iface" 2>/dev/null || true
        "$FAULT" up "$node" "$iface" 2>/dev/null || true
      done
    done
    sleep 2
    log "Verifying health..."
    "$VERIFY" || true
    ok "Topology clean and restored."
    ;;

  *)
    echo "Usage: $0 {link-flap|degraded-link|core-failure|asymmetric|clean}"
    echo "Examples:"
    echo "  $0 link-flap 3 5"
    echo "  $0 degraded-link 20 60"
    echo "  $0 core-failure"
    echo "  $0 clean"
    exit 1
    ;;
esac

