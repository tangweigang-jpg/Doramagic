# Doramagic build targets — run `make check` before committing
.PHONY: lint format typecheck test check clean

PACKAGES_PATH = packages/contracts:packages/extraction:packages/shared_utils:packages/community:packages/cross_project:packages/skill_compiler:packages/orchestration:packages/platform_openclaw:packages/domain_graph:packages/controller:packages/executors:packages/racekit:packages/evals:packages/preextract_api:packages/doramagic_product:packages/judgment_schema:packages/judgment_pipeline:packages/crystal_compiler:packages/constraint_schema:packages/constraint_pipeline:packages/blueprint_pipeline:packages/agent_core:packages/constraint_agent

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

# --- Knowledge Version Management ---
.PHONY: sop-preflight sop-diff

# Snapshot blueprint + slice constraints before SOP re-run
# Usage: make sop-preflight BP=finance-bp-009 VER=1.1
sop-preflight:
	@test -n "$(BP)" || (echo "Usage: make sop-preflight BP=finance-bp-009 VER=1.1" && exit 1)
	@test -n "$(VER)" || (echo "Usage: make sop-preflight BP=finance-bp-009 VER=1.1" && exit 1)
	@echo "=== Step 1: Snapshot blueprint ==="
	.venv/bin/python scripts/snapshot_blueprint.py --blueprint $(BP)
	@echo "=== Step 2: Slice constraints ==="
	.venv/bin/python scripts/slice_constraints.py --blueprint $(BP) --version $(VER)
	@echo "=== Pre-flight complete ==="

# Structured diff after SOP re-run
# Usage: make sop-diff BP=finance-bp-009 OLD_VER=1.0.0 NEW_VER=2.0.0 CON_OLD=1.1 CON_NEW=2.0
sop-diff:
	@test -n "$(BP)" || (echo "Usage: make sop-diff BP=finance-bp-009 OLD_VER=1.0.0 NEW_VER=2.0.0 CON_OLD=1.1 CON_NEW=2.0" && exit 1)
	@echo "=== Blueprint Diff ==="
	.venv/bin/python scripts/diff_knowledge.py blueprint \
		--old knowledge/blueprints/finance/_history/$(BP)-v$(OLD_VER).yaml \
		--new knowledge/blueprints/finance/$(BP).yaml
	@echo ""
	@echo "=== Constraint Diff ==="
	.venv/bin/python scripts/diff_knowledge.py constraint \
		--old knowledge/constraints/domains/_drafts/$(shell echo $(BP) | sed 's/-/_/g; s/_bp_/_bp/g')_v$(CON_OLD)_draft.jsonl \
		--new knowledge/constraints/domains/_drafts/$(shell echo $(BP) | sed 's/-/_/g; s/_bp_/_bp/g')_v$(CON_NEW)_draft.jsonl

# --- SOP 工程化执行 ---
.PHONY: sop-extract sop-run-blueprint sop-run-constraint sop-constraint-agent sop-run-crystal sop-run sop-prepare sop-collect sop-validate sop-validate-crystal sop-status sop-resume

# LLM 配置变量（可通过环境变量或 make 参数覆盖）
# LLM 配置：优先用环境变量 LLM_MODEL/LLM_BASE_URL/LLM_API_KEY，make 参数仅用于临时覆盖
LLM_ARGS = $(if $(MODEL),--model $(MODEL),) $(if $(BASE_URL),--base-url $(BASE_URL),)

sop-run-blueprint:
	@test -n "$(BP)" || (echo "Usage: make sop-run-blueprint BP=finance-bp-009 REPO=https://github.com/zvtvz/zvt [MODEL=MiniMax-M2.7 BASE_URL=https://api.minimaxi.com/anthropic]" && exit 1)
	.venv/bin/python scripts/run_sop.py blueprint \
		--blueprint-id $(BP) \
		$(if $(REPO),--repo-url $(REPO),) \
		$(if $(REPO_PATH),--repo-path $(REPO_PATH),) \
		--domain $(or $(DOMAIN),finance) \
		$(LLM_ARGS)

sop-run-constraint:
	@test -n "$(BP)" || (echo "Usage: make sop-run-constraint BP=finance-bp-009" && exit 1)
	.venv/bin/python scripts/run_sop.py constraint \
		--blueprint knowledge/blueprints/$(or $(DOMAIN),finance)/$(BP).yaml \
		--repo-path repos/$(shell .venv/bin/python -c "import yaml; d=yaml.safe_load(open('knowledge/blueprints/$(or $(DOMAIN),finance)/$(BP).yaml')); print(d['source']['projects'][0].split('/')[1])") \
		--domain $(or $(DOMAIN),finance) \
		$(LLM_ARGS)

sop-constraint-agent:
	@test -n "$(BP)" || (echo "Usage: make sop-constraint-agent BP=finance-bp-070 [VER=v3] [MODEL=MiniMax-M2.7 BASE_URL=...]" && exit 1)
	.venv/bin/python -m doramagic_constraint_agent run \
		--blueprint knowledge/blueprints/$(or $(DOMAIN),finance)/$(BP).yaml \
		--repo-path repos/$(shell .venv/bin/python -c "import yaml; d=yaml.safe_load(open('knowledge/blueprints/$(or $(DOMAIN),finance)/$(BP).yaml')); print(d['source']['projects'][0].split('/')[1])") \
		--domain $(or $(DOMAIN),finance) \
		--version $(or $(VER),v3) \
		$(LLM_ARGS)

sop-run-crystal:
	@test -n "$(BP)" || (echo "Usage: make sop-run-crystal BP=finance-bp-009 INTENT='A股量化回测'" && exit 1)
	.venv/bin/python scripts/run_sop.py crystal \
		--blueprint knowledge/blueprints/$(or $(DOMAIN),finance)/$(BP).yaml \
		--intent "$(or $(INTENT),构建)" \
		--domain $(or $(DOMAIN),finance)

sop-run:
	@test -n "$(BP)" || (echo "Usage: make sop-run BP=finance-bp-009 [REPO_PATH=repos/zvt] [OPS=run_step24] [DRY_RUN=1] [MODEL=MiniMax-M2.7 BASE_URL=...]" && exit 1)
	.venv/bin/python scripts/run_sop.py run \
		--blueprint-id $(BP) \
		$(if $(REPO),--repo-url $(REPO),) \
		$(if $(REPO_PATH),--repo-path $(REPO_PATH),) \
		$(if $(OPS),--ops $(OPS),) \
		$(if $(DRY_RUN),--dry-run,) \
		--domain $(or $(DOMAIN),finance) \
		$(LLM_ARGS)

sop-extract:
	@test -n "$(BP)" || (echo "Usage: make sop-extract BP=finance-bp-050 [PHASE=collect]" && exit 1)
	.venv/bin/python scripts/sop_extract.py \
		--blueprint-id $(BP) \
		$(if $(REPO_PATH),--repo-path $(REPO_PATH),) \
		--domain $(or $(DOMAIN),finance) \
		$(if $(PHASE),--phase $(PHASE),)

sop-prepare:
	@test -n "$(BP)" || (echo "Usage: make sop-prepare BP=finance-bp-050 [REPO_PATH=repos/skorecard]" && exit 1)
	$(eval AUTO_REPO := $(shell .venv/bin/python -c "import yaml,sys; \
		bp='knowledge/blueprints/$(or $(DOMAIN),finance)/$(BP).yaml'; \
		d=yaml.safe_load(open(bp)); p=d.get('source',{}).get('projects',[''])[0]; \
		print('repos/'+p.split('/')[-1] if '/' in p else 'repos/'+p)" 2>/dev/null))
	.venv/bin/python scripts/sop_prepare.py \
		--blueprint-id $(BP) \
		--repo-path $(or $(REPO_PATH),$(AUTO_REPO)) \
		--domain $(or $(DOMAIN),finance)

sop-collect:
	@test -n "$(BP)" || (echo "Usage: make sop-collect BP=finance-bp-050" && exit 1)
	.venv/bin/python scripts/sop_collect.py \
		--blueprint-id $(BP) \
		--domain $(or $(DOMAIN),finance) \
		$(if $(DRY_RUN),--dry-run,)

sop-validate:
	@test -n "$(BP)" || (echo "Usage: make sop-validate BP=finance-bp-009" && exit 1)
	.venv/bin/python scripts/validate_sop.py extraction --blueprint-id $(BP) --domain $(or $(DOMAIN),finance)

sop-validate-crystal:
	@test -n "$(BP)" || (echo "Usage: make sop-validate-crystal BP=finance-bp-009" && exit 1)
	.venv/bin/python scripts/validate_sop.py crystal --blueprint-id $(BP) --domain $(or $(DOMAIN),finance)

sop-status:
	@test -n "$(BP)" || (echo "Usage: make sop-status BP=finance-bp-009" && exit 1)
	@cat _runs/$(BP)/_state.json 2>/dev/null | .venv/bin/python -m json.tool || echo "No active run for $(BP)"

sop-resume:
	@test -n "$(BP)" || (echo "Usage: make sop-resume BP=finance-bp-009" && exit 1)
	.venv/bin/python scripts/run_sop.py blueprint --blueprint-id $(BP) --resume


# --- Crystal Compilation Tooling (v3.1+) ---
# Full workflow: `make crystal-full BP=finance-bp-009--zvt VERSION=v3.3`
# Individual steps:
#   make crystal-prepare BP=<blueprint-source-dir>
#   make crystal-compile BP=<blueprint-source-dir> VERSION=<version>
#   make crystal-gate    BP=<blueprint-source-dir> VERSION=<version>
# BP format: the folder name under knowledge/sources/finance/, e.g. finance-bp-009--zvt

.PHONY: crystal-prepare crystal-compile crystal-gate crystal-full crystal-clean

CRYSTAL_BP_DIR = knowledge/sources/finance/$(BP)
CRYSTAL_SEED = $(CRYSTAL_BP_DIR)/$(BP_ID)-$(VERSION).seed.yaml
CRYSTAL_HUMAN_SUMMARY = $(CRYSTAL_BP_DIR)/$(BP_ID)-$(VERSION).human_summary.md
CRYSTAL_VALIDATE = $(CRYSTAL_BP_DIR)/validate.py

# Derive blueprint ID from BP (strip the --suffix portion)
BP_ID = $(firstword $(subst --, ,$(BP)))

crystal-prepare:
	@test -n "$(BP)" || (echo "Usage: make crystal-prepare BP=finance-bp-009--zvt" && exit 1)
	@test -d "$(CRYSTAL_BP_DIR)" || (echo "Directory not found: $(CRYSTAL_BP_DIR)" && exit 1)
	.venv/bin/python scripts/prepare_crystal_inputs.py --blueprint-dir $(CRYSTAL_BP_DIR)

crystal-compile:
	@test -n "$(BP)" || (echo "Usage: make crystal-compile BP=finance-bp-009--zvt VERSION=v3.3" && exit 1)
	@test -n "$(VERSION)" || (echo "Usage: make crystal-compile BP=finance-bp-009--zvt VERSION=v3.3" && exit 1)
	.venv/bin/python scripts/compile_crystal_skeleton.py \
		--blueprint-dir $(CRYSTAL_BP_DIR) \
		--target-host $(or $(HOST),openclaw) \
		--output-seed $(CRYSTAL_SEED) \
		--output-human-summary $(CRYSTAL_HUMAN_SUMMARY) \
		--output-validate $(CRYSTAL_VALIDATE) \
		--sop-version $(or $(SOP_VERSION),crystal-compilation-v5.3)

crystal-gate:
	@test -n "$(BP)" || (echo "Usage: make crystal-gate BP=finance-bp-009--zvt VERSION=v3.3" && exit 1)
	@test -n "$(VERSION)" || (echo "Usage: make crystal-gate BP=finance-bp-009--zvt VERSION=v3.3" && exit 1)
	.venv/bin/python scripts/crystal_quality_gate.py \
		--blueprint $(CRYSTAL_BP_DIR)/LATEST.yaml \
		--constraints $(CRYSTAL_BP_DIR)/LATEST.jsonl \
		--crystal $(CRYSTAL_SEED) \
		--schema schemas/crystal_contract.schema.yaml \
		--strict

# One-shot: prepare → compile → gate
crystal-full: crystal-prepare crystal-compile crystal-gate
	@echo ""
	@echo "===================================================================="
	@echo "Crystal $(BP_ID)-$(VERSION) compiled and gate-passed."
	@echo "Next: main thread to fill SOUL_TODO sections in $(CRYSTAL_SEED)"
	@echo "  - Human Summary (Doraemon persona, §1.7)"
	@echo "  - Per-stage narratives (6 main stages)"
	@echo "Then re-run crystal-gate to verify."
	@echo "===================================================================="

crystal-clean:
	@test -n "$(BP)" || (echo "Usage: make crystal-clean BP=finance-bp-009--zvt VERSION=v3.3" && exit 1)
	rm -f $(CRYSTAL_SEED) $(CRYSTAL_HUMAN_SUMMARY) $(CRYSTAL_SEED:.seed.yaml=.seed.quality_report.json)
	rm -rf $(CRYSTAL_BP_DIR)/crystal_inputs
	@echo "Cleaned $(BP) $(VERSION) crystal artifacts"
