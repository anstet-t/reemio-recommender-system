# =============================================================================
# Reemio Recommender System - Makefile
# =============================================================================

.PHONY: help install install-dev run-api run-email-worker run-sync-worker \
        test test-cov lint format typecheck check clean docker-build \
        docker-up docker-down migrate migrate-new

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python
PIP := pip
PYTEST := pytest
UVICORN := uvicorn
CELERY := celery
ALEMBIC := alembic

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo "$(BLUE)Reemio Recommender System$(NC)"
	@echo ""
	@echo "$(GREEN)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# Installation
# =============================================================================

install: ## Install production dependencies
	$(PIP) install -e .

install-dev: ## Install development dependencies
	$(PIP) install -e ".[dev]"

install-docs: ## Install documentation dependencies
	$(PIP) install -e ".[docs]"

# =============================================================================
# Running Services
# =============================================================================

run-api: ## Run the FastAPI server (development mode)
	$(UVICORN) recommendation_service.main:app --reload --host 0.0.0.0 --port 8000

run-api-prod: ## Run the FastAPI server (production mode)
	$(UVICORN) recommendation_service.main:app --host 0.0.0.0 --port 8000 --workers 4

run-email-worker: ## Run the email worker
	$(CELERY) -A email_worker.main worker --loglevel=info -Q email

run-sync-worker: ## Run the sync worker
	$(CELERY) -A sync_worker.main worker --loglevel=info -Q sync

run-beat: ## Run the Celery beat scheduler
	$(CELERY) -A email_worker.main beat --loglevel=info

run-all: ## Run all services (requires multiple terminals or use docker-compose)
	@echo "$(YELLOW)Use docker-compose for running all services together:$(NC)"
	@echo "  docker-compose up -d"

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	$(PYTEST) tests/ -v

test-unit: ## Run unit tests only
	$(PYTEST) tests/unit -v

test-integration: ## Run integration tests only
	$(PYTEST) tests/integration -v -m integration

test-e2e: ## Run end-to-end tests only
	$(PYTEST) tests/e2e -v -m e2e

test-cov: ## Run tests with coverage report
	$(PYTEST) tests/ --cov=src --cov-report=html --cov-report=term-missing

test-fast: ## Run tests excluding slow tests
	$(PYTEST) tests/ -v -m "not slow"

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run linter (ruff)
	ruff check src tests

lint-fix: ## Run linter and fix issues
	ruff check src tests --fix

format: ## Format code (black + isort)
	black src tests
	isort src tests

format-check: ## Check code formatting without making changes
	black src tests --check
	isort src tests --check-only

typecheck: ## Run type checker (mypy)
	mypy src

check: lint format-check typecheck ## Run all code quality checks

# =============================================================================
# Database
# =============================================================================

migrate: ## Run database migrations
	$(ALEMBIC) upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="migration message")
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	$(ALEMBIC) downgrade -1

migrate-history: ## Show migration history
	$(ALEMBIC) history

# =============================================================================
# Docker
# =============================================================================

docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-down: ## Stop all Docker services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-clean: ## Remove all Docker containers, images, and volumes
	docker-compose down -v --rmi all

# =============================================================================
# Kubernetes
# =============================================================================

k8s-dev: ## Deploy to development environment
	kubectl apply -k k8s/overlays/development

k8s-staging: ## Deploy to staging environment
	kubectl apply -k k8s/overlays/staging

k8s-prod: ## Deploy to production environment
	kubectl apply -k k8s/overlays/production

k8s-status: ## Check Kubernetes deployment status
	kubectl get pods -n reemio-recommender
	kubectl get services -n reemio-recommender

# =============================================================================
# Development Utilities
# =============================================================================

seed: ## Seed database with test data
	$(PYTHON) scripts/seed_data.py

setup-pinecone: ## Set up Pinecone indexes
	./scripts/setup_pinecone.sh

clean: ## Clean up build artifacts and cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# =============================================================================
# Documentation
# =============================================================================

docs-serve: ## Serve documentation locally
	mkdocs serve

docs-build: ## Build documentation
	mkdocs build

# =============================================================================
# CI/CD Helpers
# =============================================================================

ci-check: install-dev lint typecheck test ## Run all CI checks
	@echo "$(GREEN)All CI checks passed!$(NC)"
