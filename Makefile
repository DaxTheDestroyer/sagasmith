.PHONY: install lint format format-check typecheck test smoke precommit secret-scan release-gate clean

install:
	uv sync --all-groups

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

format-check:
	uv run ruff format --check src tests

typecheck:
	uv run pyright

test:
	uv run pytest -q

smoke:
	uv run pytest -q -m smoke

precommit:
	uv run pre-commit run --all-files

secret-scan:
	uv run pre-commit run gitleaks --all-files

release-gate:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) typecheck
	$(MAKE) test
	uv run sagasmith smoke --mode mvp
	$(MAKE) secret-scan

clean:
	rm -rf .pytest_cache .ruff_cache .venv dist build *.egg-info
