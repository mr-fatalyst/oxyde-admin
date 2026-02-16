.PHONY: install install-front dev-front build run-fastapi fixture-fastapi

VENV = .venv/bin

install:
	$(VENV)/pip install -e ".[dev]"

install-front:
	cd frontend && npm install

dev-front:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

run-fastapi:
	cd examples/fastapi_example && ../../$(VENV)/uvicorn app:app --reload --port 8000

fixture-fastapi:
	cd examples/fastapi_example && ../../$(VENV)/python fixture.py
