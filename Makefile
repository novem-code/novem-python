.PHONY: test bump-version pre-commit

test:
	@poetry run pytest

bump-version:
	@poetry run python scripts/bump_version.py

pre-commit:
	@poetry run pre-commit run --all
