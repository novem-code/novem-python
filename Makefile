.PHONY: test bump-version lint format build

test:
	@uv run pytest

bump-version:
	@uv run python scripts/bump_version.py

lint:
	@uv run ruff format --check .
	@uv run ruff check .
	@uv run mypy novem

format:
	@uv run ruff format .
	@uv run ruff check --fix .

build:
	@uv build
