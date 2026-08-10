.PHONY: up down logs api worker ui test lint migrate seed analyze-sample demo eval-gold health

COMPOSE ?= docker compose
UV ?= uv
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
API ?= http://$(API_HOST):$(API_PORT)
SAMPLE_ROOT ?= $(CURDIR)/data

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
	API_BASE_URL=$(API) $(UV) run streamlit run apps/ui/app.py --server.port 8501 --server.address 127.0.0.1

migrate:
	$(UV) run alembic upgrade head

migrate-rev:
	$(UV) run alembic revision --autogenerate -m "$(m)"

seed:
	curl -sf -X POST "$(API)/api/v1/demo/seed" | python3 -m json.tool

analyze-sample:
	$(UV) run python scripts/analyze_sample.py --api $(API)

eval-gold:
	APP_MODE=$${APP_MODE:-ci} EMBEDDING_PROVIDER=$${EMBEDDING_PROVIDER:-hash} LLM_PROVIDER=$${LLM_PROVIDER:-template} \
		$(UV) run python scripts/eval_gold.py

demo: up migrate
	@echo "Start API in another terminal: make api"
	@echo "Then: make seed && make analyze-sample && make eval-gold"
	@echo "Or run one-shot in-process eval (seeds via ASGI): make eval-gold"

test:
	APP_MODE=ci EMBEDDING_PROVIDER=hash LLM_PROVIDER=template $(UV) run pytest -q

lint:
	$(UV) run ruff check src tests apps scripts

health:
	curl -sf "$(API)/health" | python3 -m json.tool
