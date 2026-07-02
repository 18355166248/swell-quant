.PHONY: help config pipeline storage acceptance smoke lint format-check test frontend-test frontend-build ci-local

PYTHON ?= python3
NPM ?= npm

help:
	@printf "Swell Quant local commands:\n"
	@printf "  make config          Check local configuration preflight\n"
	@printf "  make pipeline        Run the offline research pipeline\n"
	@printf "  make storage         Check DuckDB mirror tables, row counts, and schemas\n"
	@printf "  make acceptance      Check research acceptance gates\n"
	@printf "  make smoke           Run pipeline plus storage and acceptance checks\n"
	@printf "  make lint            Run Python lint with ruff\n"
	@printf "  make format-check    Check Python formatting with ruff\n"
	@printf "  make test            Run Python tests\n"
	@printf "  make frontend-test   Run frontend unit tests\n"
	@printf "  make frontend-build  Run TypeScript and Vite build\n"
	@printf "  make ci-local        Run the full local quality gate\n"

config:
	$(PYTHON) scripts/check_config.py

pipeline:
	$(PYTHON) scripts/run_pipeline.py

storage:
	$(PYTHON) scripts/check_storage.py

acceptance:
	$(PYTHON) scripts/check_acceptance.py

smoke:
	$(PYTHON) scripts/smoke_test.py

test:
	$(PYTHON) -m pytest

frontend-test:
	cd frontend && $(NPM) test

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m ruff format --check .

frontend-build:
	cd frontend && $(NPM) run build

ci-local: lint format-check test config smoke frontend-test frontend-build
