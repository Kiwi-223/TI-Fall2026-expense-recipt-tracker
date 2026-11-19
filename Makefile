.PHONY: install test lint format import

# Run these inside your activated virtual environment (see docs/implementation-plan.md §8).
PYTHON ?= python

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

import:
ifndef FILE
	$(error Usage: make import FILE=path/to/receipt.jpg)
endif
	receipts import "$(FILE)"
