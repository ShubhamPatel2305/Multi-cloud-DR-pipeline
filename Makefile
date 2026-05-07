.PHONY: help up down logs build test lint clean drill-failover drill-failback pool seed

ROUTER ?= http://localhost:8000

help:
	@echo "Targets:"
	@echo "  up               start the full 3-region stack + mock router + mongo"
	@echo "  down             stop the stack"
	@echo "  build            rebuild images"
	@echo "  logs             tail combined logs"
	@echo "  test             run app + router unit tests"
	@echo "  pool             show current router pool state"
	@echo "  seed             insert a few sample courses through the router"
	@echo "  drill-failover   inject failure on aws-mumbai and watch failover"
	@echo "  drill-failback   recover aws-mumbai and run a canary failback"
	@echo "  clean            remove containers + volumes"

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f --tail=200

test:
	cd app && pip install -r requirements.txt -q && pip install pytest pytest-asyncio -q && PYTHONPATH=. pytest -q
	cd router && pip install -r requirements.txt -q && pip install pytest pytest-asyncio -q && PYTHONPATH=. pytest -q

pool:
	@curl -s $(ROUTER)/admin/pool | python -m json.tool

seed:
	@curl -s -X POST $(ROUTER)/proxy/api/courses -H 'content-type: application/json' \
		-d '{"code":"CS101","title":"Intro to CS","instructor":"Dr. Iyer","seats":120}' | python -m json.tool
	@curl -s -X POST $(ROUTER)/proxy/api/courses -H 'content-type: application/json' \
		-d '{"code":"DS200","title":"Data Structures","instructor":"Prof. Khanna","seats":80}' | python -m json.tool

drill-failover:
	bash scripts/simulate-failure.sh aws-mumbai

drill-failback:
	bash scripts/canary-failback.sh aws-mumbai

clean:
	docker compose down -v
