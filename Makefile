.PHONY: install up down migrate revision seed verify test lint evals evals-dry-run run keygen web

install:
	pip install -e ".[dev]"

up:
	docker compose up -d db

down:
	docker compose down

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

seed:
	python scripts/seed_demo.py

verify:
	python scripts/verify_setup.py

test:
	pytest

lint:
	ruff check src tests scripts

keygen:
	python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

run:
	uvicorn agentkit.api.main:app --reload --port 8000

evals:
	python scripts/run_evals.py

evals-dry-run:
	python scripts/run_evals.py --dry-run

tune:
	python scripts/run_tuning.py --tool $(or $(tool),search_issues) --trials $(or $(trials),3) --temperature $(or $(temp),0.7)

web:
	cd frontend && npm run dev