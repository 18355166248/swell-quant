.PHONY: help config progress akshare-universe akshare-trial akshare-trial-dry-run akshare-trial-status fund-trial fund-trial-dry-run fund-trial-status data-source pipeline storage acceptance smoke lint format-check test frontend-test frontend-build ci-local

PYTHON ?= python
NPM ?= npm

help:
	@printf "Swell Quant local commands:\n"
	@printf "  make config          Check local configuration preflight\n"
	@printf "  make progress        Show project stage progress\n"
	@printf "  make akshare-universe Check AKShare universe resolution\n"
	@printf "  make akshare-trial   Run bounded AKShare real-data trial\n"
	@printf "  make akshare-trial-dry-run Preview AKShare trial without network calls\n"
	@printf "  make akshare-trial-status Check latest AKShare trial summary\n"
	@printf "  make fund-trial      Run bounded AKShare fund data trial\n"
	@printf "  make fund-trial-dry-run Preview fund trial without network calls\n"
	@printf "  make fund-trial-status Check latest fund trial summary\n"
	@printf "  make data-source     Check latest data acquisition metadata\n"
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

progress:
	$(PYTHON) scripts/check_progress.py

akshare-universe:
	$(PYTHON) scripts/check_akshare_universe.py

akshare-trial:
	$(PYTHON) scripts/run_akshare_trial.py

akshare-trial-dry-run:
	$(PYTHON) scripts/run_akshare_trial.py --dry-run

akshare-trial-status:
	$(PYTHON) scripts/check_akshare_trial.py

fund-trial:
	$(PYTHON) scripts/run_fund_trial.py

fund-trial-dry-run:
	$(PYTHON) scripts/run_fund_trial.py --dry-run

fund-trial-status:
	$(PYTHON) scripts/check_fund_trial.py

data-source:
	$(PYTHON) scripts/check_data_source.py

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

ci-local: lint format-check test config akshare-universe smoke data-source akshare-trial-dry-run akshare-trial-status fund-trial-dry-run fund-trial-status progress frontend-test frontend-build
