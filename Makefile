# ═══════════════════════════════════════════════════════════════
#  APEX CODING AGENT — Developer Commands
# ═══════════════════════════════════════════════════════════════

.PHONY: install dev run test lint clean docker-up docker-down

# ── Setup ─────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black mypy

# ── Run ───────────────────────────────────────────────────────
run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# ── Test ──────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=. --cov-report=html

# ── Code Quality ──────────────────────────────────────────────
lint:
	ruff check . --fix
	ruff format .

typecheck:
	mypy . --ignore-missing-imports

# ── Docker ────────────────────────────────────────────────────
docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f apex-api

# ── Clean ─────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov
