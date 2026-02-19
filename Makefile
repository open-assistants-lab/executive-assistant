.PHONY: help db-up db-down db-logs ea cli http telegram test

help:
	@echo "Executive Assistant - Make Commands"
	@echo ""
	@echo "Database:"
	@echo "  make db-up       - Start PostgreSQL"
	@echo "  make db-down     - Stop PostgreSQL"
	@echo "  make db-logs     - View PostgreSQL logs"
	@echo ""
	@echo "Run Commands:"
	@echo "  make ea cli      - Start CLI"
	@echo "  make ea http    - Start HTTP server"
	@echo "  make ea telegram - Start Telegram bot"
	@echo ""
	@echo "Test:"
	@echo "  make test        - Run tests"

db-up:
	cd docker && docker compose up -d

db-down:
	cd docker && docker compose down

db-logs:
	cd docker && docker compose logs -f postgres

ea cli:
	uv run ea cli

ea http:
	uv run ea http

ea telegram:
	uv run ea telegram

test:
	uv run pytest
