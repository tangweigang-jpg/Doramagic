.PHONY: lint format typecheck test check clean

lint:
	python3 -m ruff check packages/ tests/

format:
	python3 -m ruff format packages/ tests/

typecheck:
	python3 -m mypy packages/contracts/doramagic_contracts/

test:
	python3 -m pytest tests/ packages/ -v

check: lint typecheck test

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
