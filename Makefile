.PHONY: help install dev test test-unit test-integration lint format clean docker-postgres serve telegram ea

help:
	@echo "Executive Assistant Agent - Available Commands"
	@echo "=============================="
	@echo ""
	@echo "Setup:"
	@echo "  install        Install production dependencies"
	@echo "  dev            Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test           Run all tests with coverage"
	@echo "  test-unit      Run unit tests only"
	@echo "  test-integration Run integration tests"
	@echo "  test-file FILE Run specific test file"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint           Run ruff linter"
	@echo "  format         Format code with ruff"
	@echo "  typecheck      Run mypy type checking"
	@echo ""
	@echo "Running (with uv):"
	@echo "  serve          Start API server locally (uv run)"
	@echo "  telegram       Start Telegram bot (uv run)"
	@echo "  ea             Run CLI (uv run ea --help)"
	@echo ""
	@echo "Docker (Postgres only for dev):"
	@echo "  docker-postgres Start only Postgres container for local dev"
	@echo "  docker-stop     Stop Postgres container"
	@echo ""
	@echo "Docker (Full stack):"
	@echo "  docker-up      Start all services (production)"
	@echo "  docker-dev     Start services (development with hot reload)"
	@echo "  docker-down    Stop all services"
	@echo "  docker-logs    View container logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean          Remove cache and build artifacts"

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"

test:
	uv run pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	uv run pytest tests/unit/ -v --cov=src --cov-report=term-missing

test-integration:
	uv run pytest tests/integration/ -v --cov=src --cov-report=term-missing

test-file:
	uv run pytest $(FILE) -v

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

typecheck:
	uv run mypy src/

docker-postgres:
	docker run -d --name ea-postgres \
		-e POSTGRES_USER=ea \
		-e POSTGRES_PASSWORD=testpassword123 \
		-e POSTGRES_DB=ea_db \
		-p 5432:5432 \
		postgres:16-alpine

docker-stop:
	docker stop ea-postgres || true
	docker rm ea-postgres || true

docker-up:
	docker compose -f docker/docker-compose.yml up -d --build

docker-dev:
	docker compose -f docker/docker-compose.dev.yml up -d --build

docker-down:
	docker compose -f docker/docker-compose.yml down -v

docker-logs:
	docker compose -f docker/docker-compose.yml logs -f

serve:
	uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

telegram:
	uv run python -m src.telegram.bot

ea:
	uv run ea $(ARGS)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/ .eggs/
