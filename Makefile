IMAGE_NAME ?= ml-service

.PHONY: help install install-dev server server-dev test test-unit test-integration test-e2e test-cov test-report test-watch test-db-up test-db-down test-db-logs clean docker-build docker-run docker-stop migrate-up migrate-down migrate-new migrate-status

help:
	@echo "Available commands:"
	@echo "  make install          - Install runtime dependencies"
	@echo "  make install-dev      - Install runtime + test dependencies"
	@echo "  make server           - Run the application"
	@echo "  make server-dev       - Run with auto-reload (development)"
	@echo ""
	@echo "Testing:"
	@echo "  make test-db-up       - Start MySQL 8.0 test database (required for repository tests)"
	@echo "  make test-db-down     - Stop and remove test database"
	@echo "  make test-db-logs     - View test database logs"
	@echo "  make test             - Run all tests with coverage"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-e2e         - Run end-to-end tests only"
	@echo "  make test-cov         - Run tests and open coverage report"
	@echo "  make test-report      - Generate HTML test report and coverage (opens in browser)"
	@echo "  make test-watch       - Run tests in watch mode"
	@echo ""
	@echo "Docker (IMAGE_NAME=$(IMAGE_NAME)):"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-run       - Run Docker container"
	@echo "  make docker-stop      - Stop Docker container"
	@echo ""
	@echo "Database migrations:"
	@echo "  make migrate-up       - Apply all pending migrations"
	@echo "  make migrate-down     - Rollback last migration"
	@echo "  make migrate-new MSG='message' - Create new migration script"
	@echo "  make migrate-status   - Show current migration status"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean            - Remove cache files"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

server:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

server-dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test Database Commands
test-db-up:
	@echo "Starting MySQL 8.0 test database on port 3307..."
	docker-compose -f docker-compose.test.yml up -d
	@echo "Waiting for MySQL to be ready..."
	@sleep 5
	@docker-compose -f docker-compose.test.yml ps

test-db-down:
	@echo "Stopping and removing test database..."
	docker-compose -f docker-compose.test.yml down -v

test-db-logs:
	docker-compose -f docker-compose.test.yml logs -f mysql-test

# Test Commands
test:
	@echo "Running tests (repository tests require the MySQL test DB on port 3307)"
	@echo "Start with: make test-db-up"
	pytest -v --cov=app --cov-report=term-missing --cov-report=html

test-unit:
	pytest tests/unit -v -m unit

test-integration:
	pytest tests/integration -v -m integration

test-e2e:
	pytest tests/e2e -v -m e2e

test-cov:
	pytest -v --cov=app --cov-report=html
	@echo "\nOpening coverage report..."
	open htmlcov/index.html || xdg-open htmlcov/index.html

test-report:
	@echo "Generating comprehensive HTML test report and coverage..."
	pytest tests/unit -v -m unit \
		--html=test-report.html --self-contained-html \
		--cov=app --cov-report=html:htmlcov --tb=short
	@echo "\nReports generated:"
	@echo "   Test Report:     test-report.html"
	@echo "   Coverage Report: htmlcov/index.html"
	@echo "\nOpening reports in browser..."
	@sleep 1
	open test-report.html || xdg-open test-report.html
	@sleep 1
	open htmlcov/index.html || xdg-open htmlcov/index.html

test-watch:
	pytest-watch -- -v --cov=app

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Docker. Build args: USE_GPU=true|false, INSTALL_TORCH=true|false
#   make docker-build DOCKER_BUILD_ARGS="--build-arg INSTALL_TORCH=true --build-arg USE_GPU=true"
docker-build:
	docker build $(DOCKER_BUILD_ARGS) -t $(IMAGE_NAME) .

docker-run:
	docker run -d -p 8000:8000 --name $(IMAGE_NAME) --env-file .env $(IMAGE_NAME)

docker-stop:
	docker stop $(IMAGE_NAME) && docker rm $(IMAGE_NAME)

# Database Migration Commands
migrate-up:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migrate-new:
	@if [ -z "$(MSG)" ]; then \
		echo "Error: MSG is required. Usage: make migrate-new MSG='your message'"; \
		exit 1; \
	fi
	alembic revision -m "$(MSG)"

migrate-status:
	alembic current
	@echo "\nMigration history:"
	@alembic history
