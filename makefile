default: fmt fix

fmt:
	ruff format

lint:
	ruff check

fix:
	ruff check --fix
