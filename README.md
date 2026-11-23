# NOC simulator

Phase 1: 6-node containerlab lab (4 FRR routers running OSPF, 2 hosts) monitored by
Prometheus + blackbox_exporter, Alertmanager, Loki (+ Grafana Alloy shipping the lab container logs) and Grafana.

    make up        # monitoring stack
    make deploy    # lab topology
    make verify    # OSPF + ping checks
    make test      # promtool lint + alert rule unit tests
    scripts/fault.sh isolate core1   # break something, watch the dashboard

Grafana: http://127.0.0.1:3000 (admin / see GRAFANA_ADMIN_PASSWORD in .env)
Prometheus: http://127.0.0.1:9090   Alertmanager: http://127.0.0.1:9093
