# Doramagic build targets — run `make check` before committing
.PHONY: lint format typecheck test check clean

PACKAGES_PATH = packages/contracts:packages/extraction:packages/shared_utils:packages/community:packages/cross_project:packages/skill_compiler:packages/orchestration:packages/platform_openclaw:packages/domain_graph:packages/controller:packages/executors:packages/racekit:packages/evals:packages/preextract_api:packages/doramagic_product:packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler

lint:
	.venv/bin/python -m ruff check packages/ tests/

format:
	.venv/bin/python -m ruff format packages/ tests/

typecheck:
	.venv/bin/python -m mypy packages/contracts/doramagic_contracts/

test:
	PYTHONPATH=$(PACKAGES_PATH) .venv/bin/python -m pytest tests/ packages/ -v \
		--ignore=packages/preextract_api \
		--ignore=packages/doramagic_product \
		--ignore=packages/orchestration/doramagic_orchestration/tests/test_phase_runner_gemini.py \
		--ignore=packages/skill_compiler/tests/test_compiler.py \
		--ignore=tests/smoke/test_e2e_pipeline.py \
		--ignore=tests/test_doramagic_pipeline.py

check: lint typecheck test

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
