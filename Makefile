.PHONY: up down logs api worker ui test lint migrate seed analyze-sample demo eval-gold health

COMPOSE ?= docker compose
UV ?= uv
API_HOST ?= 127.0.0.1
API_PORT ?= 8000

## Datastores only (recommended on Mac)
up:
	$(COMPOSE) up -d postgres redis

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f postgres redis

## Host processes (preferred topology)
api:
	$(UV) run uvicorn blastradius.main:app --reload --host $(API_HOST) --port $(API_PORT)

worker:
	$(UV) run arq blastradius.workers.settings.WorkerSettings

ui:
	API_BASE_URL=http://127.0.0.1:$(API_PORT) $(UV) run streamlit run apps/ui/app.py --server.port 8501 --server.address 127.0.0.1

migrate:
	$(UV) run alembic upgrade head

migrate-rev:
	$(UV) run alembic revision --autogenerate -m "$(m)"

seed:
	@echo "Seed stub — /demo/seed lands later"
	@exit 1

analyze-sample:
	@echo "Analyze-sample stub — lands with analyze API"
	@exit 1

eval-gold:
	@echo "Eval-gold stub — scripts/eval_gold.py lands later"
	@exit 1

demo:
	@echo "Demo stub — wires up + migrate + seed + analyze-sample + eval-gold later"
	@exit 1

test:
	APP_MODE=ci $(UV) run pytest -q

lint:
	$(UV) run ruff check src tests apps scripts

health:
	curl -sf "http://$(API_HOST):$(API_PORT)/health" | python3 -m json.tool
