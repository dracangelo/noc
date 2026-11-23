#!/usr/bin/env bash
# Simple fault injector for the lab. Run from anywhere; uses sudo.
#   fault.sh down    NODE IFACE        take an interface down
#   fault.sh up      NODE IFACE        bring it back
#   fault.sh delay   NODE IFACE MS     add latency
#   fault.sh loss    NODE IFACE PCT    add packet loss
#   fault.sh clear   NODE IFACE        remove delay/loss
#   fault.sh isolate NODE              take ALL interfaces down (node looks dead)
#   fault.sh restore NODE              bring all interfaces back up
set -euo pipefail
LAB=noc-lab
cmd="${1:-}"; node="${2:-}"
[[ -n "$cmd" && -n "$node" ]] || { sed -n '2,11p' "$0"; exit 1; }
c="clab-$LAB-$node"
ns() { sudo nsenter -t "$(sudo docker inspect -f '{{.State.Pid}}' "$c")" -n "$@"; }
ifaces() { ns ip -br link show | awk '{sub(/@.*/,"",$1); if ($1 ~ /^eth/) print $1}'; }
case "$cmd" in
  down)    ns ip link set "$3" down ;;
  up)      ns ip link set "$3" up ;;
  delay)   ns tc qdisc replace dev "$3" root netem delay "${4}ms" ;;
  loss)    ns tc qdisc replace dev "$3" root netem loss "${4}%" ;;
  clear)   ns tc qdisc del dev "$3" root 2>/dev/null || true ;;
  isolate) for i in $(ifaces); do ns ip link set "$i" down; done ;;
  restore) for i in $(ifaces); do ns ip link set "$i" up; done ;;
  *) echo "unknown command: $cmd" >&2; exit 1 ;;
esac
echo "ok: $cmd $node ${3:-}"
