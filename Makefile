.PHONY: pipeline storage acceptance smoke lint format-check frontend-build ci-local

PYTHON ?= python3
NPM ?= npm

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

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m ruff format --check .

frontend-build:
	cd frontend && $(NPM) run build

ci-local: lint format-check test smoke frontend-build
