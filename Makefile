.PHONY: help up down build logs shell test migrate seed lint format

help:   ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker ────────────────────────────────────────────────────────────────────
up:     ## Start all services in dev mode
	docker compose up --build -d
	@echo "API  → http://localhost:8000/api/v1/docs"
	@echo "Flower → http://localhost:5555"

down:   ## Stop all services
	docker compose down

build:  ## Rebuild images without cache
	docker compose build --no-cache

logs:   ## Tail API logs
	docker compose logs -f api

logs-all: ## Tail all service logs
	docker compose logs -f

shell:  ## Open a shell inside the API container
	docker compose exec api bash

# ── Database ──────────────────────────────────────────────────────────────────
migrate:    ## Run Alembic migrations
	docker compose exec api alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="add orders table")
	docker compose exec api alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	docker compose exec api alembic downgrade -1

# ── Dev ───────────────────────────────────────────────────────────────────────
test:   ## Run test suite
	docker compose exec api pytest tests/ -v --cov=app

lint:   ## Lint with ruff
	ruff check app/ tests/

format: ## Format with ruff
	ruff format app/ tests/

# ── Local (without Docker) ────────────────────────────────────────────────────
install:    ## Install Python deps locally
	pip install -r requirements.txt aiosqlite

run-local:  ## Run API locally (needs .env)
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker-local: ## Run Celery worker locally
	celery -A app.tasks.celery_app worker --loglevel=info
