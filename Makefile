.PHONY: lint format typecheck test check clean

PACKAGES_PATH = packages/contracts:packages/extraction:packages/shared_utils:packages/community:packages/cross_project:packages/skill_compiler:packages/orchestration:packages/platform_openclaw:packages/domain_graph:packages/controller:packages/executors:packages/racekit:packages/evals:packages/preextract_api:packages/doramagic_product

lint:
	python3 -m ruff check packages/ tests/

format:
	python3 -m ruff format packages/ tests/

typecheck:
	python3 -m mypy packages/contracts/doramagic_contracts/

test:
	PYTHONPATH=$(PACKAGES_PATH) .venv/bin/python -m pytest tests/ packages/ -v \
		--ignore=packages/preextract_api \
		--ignore=packages/doramagic_product \
		--ignore=packages/extraction/tests/test_confidence_system.py \
		--ignore=packages/extraction/tests/test_dsd.py \
		--ignore=packages/extraction/tests/test_knowledge_compiler.py \
		--ignore=tests/smoke/test_e2e_pipeline.py \
		--ignore=tests/test_doramagic_pipeline.py

check: lint typecheck test

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
