.PHONY: test

bump-version:
	@poetry run python scripts/bump_version.py

pre-commit:
	@poetry run pre-commit run --all

test:
	@poetry run pytest
