# Computer Use Agent Backend Makefile
.PHONY: help install dev test build run clean docker-build docker-run docker-stop migration upgrade lint format check

# Default target
help:
	@echo "Computer Use Agent Backend - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  install     - Install dependencies"
	@echo "  dev         - Start development server"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linting"
	@echo "  format      - Format code"
	@echo "  check       - Run type checking"
	@echo ""
	@echo "Database:"
	@echo "  migration   - Create new migration"
	@echo "  upgrade     - Apply migrations"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run with Docker Compose"
	@echo "  docker-stop  - Stop Docker services"
	@echo ""
	@echo "Utilities:"
	@echo "  build       - Build for production"
	@echo "  clean       - Clean temporary files"

# Development setup
install:
	pip install -r requirements.txt
	cp .env.example .env
	@echo "Please edit .env file with your configuration"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest --cov=app tests/ -v

# Code quality
lint:
	ruff check app/ tests/

format:
	black app/ tests/
	ruff check --fix app/ tests/

check:
	mypy app/

# Database operations
migration:
	alembic revision --autogenerate -m "$(MSG)"

upgrade:
	alembic upgrade head

# Docker operations
docker-build:
	docker-compose build

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Production build
build:
	pip install --upgrade pip
	pip install -r requirements.txt --no-cache-dir

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/

# Setup development environment
setup-dev: install
	@echo "Setting up development environment..."
	@echo "1. Installing pre-commit hooks..."
	pre-commit install
	@echo "2. Creating database..."
	alembic upgrade head
	@echo "Development setup complete!"

# Run full quality checks
quality: lint check test
	@echo "All quality checks passed!"

# Database reset (development only)
reset-db:
	rm -f computer_use.db
	alembic upgrade head

# View logs
logs:
	tail -f logs/app.log

# Quick start for demo
demo: setup-dev docker-run
	@echo ""
	@echo "🚀 Computer Use Agent Backend Demo Started!"
	@echo ""
	@echo "📋 Services:"
	@echo "  • API Server: http://localhost:8000"
	@echo "  • API Docs: http://localhost:8000/docs" 
	@echo "  • Frontend Demo: http://localhost:3001"
	@echo "  • VNC Desktop: http://localhost:3000"
	@echo "  • Database: localhost:5432"
	@echo ""
	@echo "📖 Usage:"
	@echo "  1. Open http://localhost:3001 for the demo interface"
	@echo "  2. Create a new session"
	@echo "  3. Try: 'Search the weather in Dubai'"
	@echo "  4. Watch the agent work in the VNC viewer"
	@echo ""
	@echo "🛠️  Management:"
	@echo "  • Stop: make docker-stop"
	@echo "  • Logs: make docker-logs"
	@echo "  • API: make dev (for local development)"
	@echo ""

# Health check
health:
	@curl -s http://localhost:8000/health | python -m json.tool

# API test
test-api:
	@echo "Testing API endpoints..."
	@echo "Health check:"
	@curl -s http://localhost:8000/health | python -m json.tool
	@echo "\nCreating test session:"
	@curl -s -X POST http://localhost:8000/api/v1/sessions/ \
		-H "Content-Type: application/json" \
		-d '{"title": "Test Session"}' | python -m json.tool

# Development shortcuts
run-api:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-tests:
	python -m pytest tests/ -v

run-lint:
	python -m ruff check app/ tests/
	python -m black --check app/ tests/

# Production deployment preparation
prod-check:
	@echo "🔍 Production readiness check..."
	@echo "✓ Running tests..."
	@$(MAKE) test
	@echo "✓ Checking code quality..."
	@$(MAKE) lint
	@echo "✓ Type checking..."
	@$(MAKE) check
	@echo "✓ Building Docker image..."
	@$(MAKE) docker-build
	@echo "🎉 Production ready!"

# Help for specific commands
help-docker:
	@echo "Docker Commands Help:"
	@echo ""
	@echo "docker-build  - Build all Docker images"
	@echo "docker-run    - Start all services in background"
	@echo "docker-stop   - Stop all services"
	@echo "docker-logs   - View logs from all services"
	@echo ""
	@echo "Example workflow:"
	@echo "  make docker-build"
	@echo "  make docker-run"
	@echo "  # Use the application"
	@echo "  make docker-stop"

help-dev:
	@echo "Development Commands Help:"
	@echo ""
	@echo "install    - Install Python dependencies"
	@echo "dev        - Start development server with auto-reload"
	@echo "test       - Run test suite with coverage"
	@echo "lint       - Check code style and errors"
	@echo "format     - Auto-format code"
	@echo ""
	@echo "Example workflow:"
	@echo "  make install"
	@echo "  make dev"
	@echo "  # Make changes"
	@echo "  make test"
	@echo "  make format"