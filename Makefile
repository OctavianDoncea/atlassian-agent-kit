.PHONY: install up down migrate revision seed verify test lint

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