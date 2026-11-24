.RECIPEPREFIX := >
.PHONY: up down deploy destroy status verify test logs traffic-start traffic-stop scenario-flap scenario-loss scenario-isolate scenario-clean incident-ui telemetry-daemon simulate simulate-chaos

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

## --- Enterprise Simulation & Telemetry Automation ---

simulate:         ## run full real-world enterprise workload, telemetry & incident automation
> python3 scripts/orchestrator.py

simulate-chaos:   ## run full simulation WITH autonomous real-world chaos & incidents
> python3 scripts/orchestrator.py --with-chaos

workload:         ## run multi-pattern traffic (diurnal, burst spikes, VoIP, HTTP)
> python3 scripts/workload_generator.py

chaos:            ## run autonomous chaos & fault injector
> python3 scripts/chaos_scheduler.py

syslog-stream:    ## stream authentic router syslog & telemetry into Loki
> python3 scripts/telemetry_streamer.py

telemetry:        ## run the FRR & interface telemetry exporter (port 9348)
> python3 scripts/frr_exporter.py

incident-receiver: ## run the Alertmanager webhook & incident receiver UI (port 9095)
> python3 scripts/incident_receiver.py

traffic-start:    ## start continuous background traffic host1 -> host2
> ./scripts/traffic.sh start 5M

traffic-burst:    ## inject a 50Mbps burst traffic spike
> ./scripts/traffic.sh burst 15 50M

traffic-stop:     ## stop traffic generators
> ./scripts/traffic.sh stop

scenario-flap:    ## simulate core link flapping incident
> ./scripts/scenario.sh link-flap 3 5

scenario-loss:    ## simulate degraded transit path (packet loss + high delay)
> ./scripts/scenario.sh degraded-link 20 60

scenario-isolate: ## simulate catastrophic core router outage
> ./scripts/scenario.sh core-failure

scenario-clean:   ## clear all network chaos and restore normal state
> ./scripts/scenario.sh clean
