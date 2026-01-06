.PHONY: test bump-version pre-commit build

test:
	@uv run pytest

bump-version:
	@uv run python scripts/bump_version.py

pre-commit:
	@uv run pre-commit run --all

build:
	@uv build
