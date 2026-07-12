.PHONY: help lint format-check test

PYTHON ?= python

help:
	@printf "Swell Quant commands:\n"
	@printf "  make test          Run the test suite\n"
	@printf "  make lint          Run ruff lint\n"
	@printf "  make format-check  Check formatting with ruff\n"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m ruff format --check .
