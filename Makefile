.PHONY: install install-front dev-front build run-fastapi fixture-fastapi run-litestar fixture-litestar run-sanic fixture-sanic

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

run-litestar:
	cd examples/litestar_example && ../../$(VENV)/uvicorn app:app --reload --port 8000

fixture-litestar:
	cd examples/litestar_example && ../../$(VENV)/python fixture.py

run-sanic:
	cd examples/sanic_example && ../../$(VENV)/sanic app:app --dev --port 8000

fixture-sanic:
	cd examples/sanic_example && ../../$(VENV)/python fixture.py
