.PHONY: help setup run stop logs build dev dev-web test test-backend test-frontend e2e clean

help:
	@echo "Ollama Chat — Developer Commands"
	@echo ""
	@echo "  make setup          First-time setup: copy .env, pull Ollama models"
	@echo "  make run            Start backend + frontend in Docker"
	@echo "  make stop           Stop all containers"
	@echo "  make logs           Tail container logs"
	@echo "  make build          Rebuild Docker images without cache"
	@echo ""
	@echo "  make dev            Run backend natively with hot reload"
	@echo "  make dev-web        Run Flutter web in Chrome (connects to local backend)"
	@echo ""
	@echo "  make test           Run all tests (backend + frontend)"
	@echo "  make test-backend   Run backend tests only (offline, ~1s)"
	@echo "  make test-frontend  Run Flutter widget tests only (offline, ~3s)"
	@echo "  make e2e            Run end-to-end tests in macOS window (requires backend running)"
	@echo ""
	@echo "  make clean          Remove containers and local images"

setup:
	@[ -f .env ] && echo ".env already exists" || (cp .env.example .env && echo "Created .env from .env.example")
	@echo "Checking Ollama models..."
	@ollama list 2>/dev/null | grep -q "llama3.1:8b" \
		|| (echo "Pulling llama3.1:8b..." && ollama pull llama3.1:8b)
	@ollama list 2>/dev/null | grep -q "nomic-embed-text" \
		|| (echo "Pulling nomic-embed-text..." && ollama pull nomic-embed-text)
	@echo "Setup complete. Run 'make run' to start."

run:
	docker compose up --build -d
	@echo ""
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API docs: http://localhost:8000/docs"

stop:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build --no-cache

dev:
	@echo "Starting backend with hot reload..."
	cd backend && .venv/bin/python main.py

dev-web:
	@echo "Starting Flutter web in Chrome..."
	cd frontend && flutter run -d chrome

test: test-backend test-frontend

test-backend:
	cd backend && .venv/bin/pytest -v

test-frontend:
	cd frontend && flutter test

e2e:
	@echo "Running E2E tests in macOS window (backend must be running on :8000)..."
	cd frontend && flutter test integration_test/ -d macos

clean:
	docker compose down --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
