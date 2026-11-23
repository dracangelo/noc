#!/usr/bin/env bash
# Checks that the lab converged: OSPF neighbours Full, hosts reach each other, mgmt reachable.
set -u
LAB=noc-lab
pass=0; fail=0
dx() { sudo docker exec "clab-$LAB-$1" "${@:2}"; }
check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS  $desc"; pass=$((pass+1))
  else echo "FAIL  $desc"; fail=$((fail+1)); fi
}
expect_full() {
  local node="$1" want="$2" got
  got=$(dx "$node" vtysh -c 'show ip ospf neighbor' 2>/dev/null | grep -c 'Full' || true)
  check "OSPF $node: $want Full neighbours (found $got)" test "$got" -eq "$want"
}
expect_full core1 3
expect_full core2 3
expect_full dist1 2
expect_full dist2 2
check "host1 -> host2 (192.168.20.10)" dx host1 ping -c 2 -W 2 192.168.20.10
check "host2 -> host1 (192.168.10.10)" dx host2 ping -c 2 -W 2 192.168.10.10
for ip in 172.20.20.11 172.20.20.12 172.20.20.13 172.20.20.14 172.20.20.15 172.20.20.16; do
  check "mgmt ping $ip" ping -c 1 -W 2 "$ip"
done
echo; echo "passed=$pass failed=$fail"
[[ $fail -eq 0 ]]
