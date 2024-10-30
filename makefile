default: fmt fix

run-app:
	python -m main

run-api:
	python -m api

fmt:
	ruff format

lint:
	ruff check

fix:
	ruff check --fix

test:
	python -m pytest
