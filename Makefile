.PHONY: install lint typecheck test check migrate run zip smoke docker-build

install:
	uv sync --all-groups

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy app scripts

test:
	uv run pytest

check: lint typecheck test

migrate:
	uv run alembic upgrade head

run:
	uv run python -m app

zip:
	uv run python scripts/build_deploy_zip.py

smoke:
	uv run python scripts/smoke_kino.py

docker-build:
	docker build -t kino-ticket-bot .

