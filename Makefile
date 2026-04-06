PYTHON ?= python3

.PHONY: dev test migrate lint validate-stack provenance

dev:
	$(PYTHON) -m uvicorn backend.app.main:app --reload

test:
	$(PYTHON) -m pytest

migrate:
	$(PYTHON) -m alembic upgrade head

lint:
	$(PYTHON) -m compileall backend

validate-stack:
	./infra/scripts/validate-stack.sh

provenance:
	./infra/scripts/capture-provenance.sh
