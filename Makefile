.RECIPEPREFIX := >
.PHONY: up down deploy destroy status verify test logs
LAB := topology/noc-lab.clab.yml
export PATH := $(HOME)/.local/bin:$(PATH)
DC := $(shell docker info >/dev/null 2>&1 && echo docker compose || echo sudo docker compose)

up:       ## start Prometheus, Alertmanager, blackbox, Loki, Alloy, Grafana
> $(DC) up -d
down:     ## stop the monitoring stack (data volumes are kept)
> $(DC) down
deploy:   ## (re)deploy the containerlab topology
> sudo containerlab deploy -t $(LAB) --reconfigure
destroy:  ## tear down the lab
> sudo containerlab destroy -t $(LAB) --cleanup
status:
> $(DC) ps
> sudo containerlab inspect -t $(LAB)
verify:   ## OSPF neighbours + end-to-end ping
> ./scripts/verify.sh
test:     ## lint and unit-test the alert rules
> promtool check rules prometheus/rules/*.yml
> promtool test rules tests/*.test.yml
logs:
> $(DC) logs -f --tail=50
