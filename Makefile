.PHONY: install test lint format demo docker clean

install:  ## Instala en modo desarrollo
	pip install -e ".[dev]"

test:  ## Tests con cobertura
	pytest --cov

lint:
	ruff check . && ruff format --check .

format:
	ruff check . --fix && ruff format .

demo:  ## Genera el reporte de ejemplo en ./driftradar-demo
	driftradar demo

docker:
	docker build -t driftradar .

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .coverage driftradar-demo
