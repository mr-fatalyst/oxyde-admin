.PHONY: install install-front dev-front build lint test run-fastapi fixture-fastapi run-litestar fixture-litestar run-sanic fixture-sanic run-quart fixture-quart run-falcon fixture-falcon

VENV = .venv/bin

install:
	$(VENV)/pip install -e ".[dev]"

install-front:
	cd frontend && npm install

dev-front:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

lint:
	$(VENV)/ruff check oxyde_admin tests
	$(VENV)/ruff format --check oxyde_admin tests

test:
	$(VENV)/pytest -v

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

run-quart:
	cd examples/quart_example && ../../$(VENV)/hypercorn app:app --reload --bind 0.0.0.0:8000

fixture-quart:
	cd examples/quart_example && ../../$(VENV)/python fixture.py

run-falcon:
	cd examples/falcon_example && ../../$(VENV)/uvicorn app:app --reload --port 8000

fixture-falcon:
	cd examples/falcon_example && ../../$(VENV)/python fixture.py
