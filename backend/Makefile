.PHONY: install dev test lint typecheck run validate clean

PY ?= python

install:
	$(PY) -m pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	pytest -ra

lint:
	ruff check app tests

format:
	ruff format app tests

validate:
	$(PY) -m app.core.validation

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ */__pycache__ */*/__pycache__
