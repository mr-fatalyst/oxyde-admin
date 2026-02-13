.PHONY: install dev-back dev-front build dev fixture

VENV = .venv/bin

install:
	$(VENV)/pip install -e ".[dev]"
	$(VENV)/pip install uvicorn

install-front:
	cd frontend && npm install

dev-back:
	cd example && ../$(VENV)/uvicorn app:app --reload --port 8000

dev-front:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

fixture:
	cd example && ../$(VENV)/python fixture.py

dev:
	$(MAKE) dev-back & $(MAKE) dev-front & wait
