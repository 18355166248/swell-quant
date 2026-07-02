.PHONY: pipeline storage acceptance smoke test frontend-build ci-local

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

frontend-build:
	cd frontend && $(NPM) run build

ci-local: test smoke frontend-build
