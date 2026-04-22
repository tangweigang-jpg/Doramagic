# Constraint SOP Compliance Audit Report

> Audit date: 2026-04-05
> Scope: 7 draft files (347 constraints), finance-C-341 ~ finance-C-687
> Auditor: Automated schema + SOP validator

---

## Per-File Audit Results

### finance_bp004_draft.jsonl (Qlib / Microsoft)
- **Constraint count**: 54
- **Schema compliance rate**: 0.0%
- **P0-P5 violations**: 1 (P0=0)
- **Stage coverage**: 5 stages (data_pipeline, model_training, backtest_trading, evaluation_reporting, portfolio_construction)
- **Edge constraints**: Yes
- **Global constraints**: Yes
- **FATAL ratio**: 25.9% (14/54) -- below target 30-40%
- **Critical issues**:
  - ALL 54 constraints missing 6 top-level fields: `hash`, `version`, `machine_checkable`, `promote_to_acceptance`, `relations`, `tags`
  - ALL 54 constraints use `source_type: "source_code"` instead of `"code_analysis"`
  - ALL evidence_refs use `type: "code"` instead of `"source_code"`
  - No `version.schema_version` field (missing version block entirely)
  - 19 constraints use invalid `consequence.kind` values (`runtime_error`, `logic_error`, `data_loss`, `silent_failure`, etc.)
  - ID format uses `bp004-cNNN` instead of `finance-C-NNN` pattern
  - bp004-c043: P4 - consequence contains vague word "建议"

### finance_bp005_draft.jsonl (RQAlpha / Ricequant)
- **Constraint count**: 55
- **Schema compliance rate**: 50.9%
- **P0-P5 violations**: 4 (P0=0)
- **Stage coverage**: 5 stages (system_init, strategy_execution, order_matching, risk_management, result_analysis)
- **Edge constraints**: No
- **Global constraints**: No
- **FATAL ratio**: 38.2% (21/55) -- within target
- **Critical issues**:
  - 27 constraints use invalid `consequence.kind: "wrong_result"` (should map to `bug` or `data_corruption`)
  - bp005-C-014/016/017: P3 - `when` field has <10% Chinese characters
  - bp005-C-053: P4 - consequence contains vague word "合理"

### finance_bp006_draft.jsonl (QUANTAXIS)
- **Constraint count**: 53
- **Schema compliance rate**: 20.8%
- **P0-P5 violations**: 3 (P0=0)
- **Stage coverage**: 5 stages (strategy_engine, data_pipeline, broker_interface, portfolio_management, visualization)
- **Edge constraints**: No
- **Global constraints**: No
- **FATAL ratio**: 17.0% (9/53) -- significantly below target
- **Critical issues**:
  - 33 constraints use invalid `modality: "should_know"` (not in schema)
  - 17 constraints use invalid `constraint_kind: "pitfall"` (not in schema)
  - 7 constraints use invalid `constraint_kind: "environment_requirement"` (not in schema)
  - 15+ constraints use invalid `consequence.kind: "silent_failure"` (not in schema)
  - finance-C-006-021/029: P4 - consequence.description < 20 chars
  - finance-C-006-042: P3 - `when` has <10% Chinese

### finance_bp007_draft.jsonl (Stock / myhhub)
- **Constraint count**: 42
- **Schema compliance rate**: 85.7%
- **P0-P5 violations**: 3 (P0=2)
- **Stage coverage**: 7 stages (data_acquisition, indicator_calculation, stock_selection, visualization, web_server, data_caching, system_config)
- **Edge constraints**: No
- **Global constraints**: No
- **FATAL ratio**: 19.0% (8/42) -- below target
- **Critical issues**:
  - **finance-C-216: P0a - expert_reasoning score=0.95 > 0.7**
  - **finance-C-239: P0a - expert_reasoning score=0.95 > 0.7**
  - finance-C-208: P4 - consequence contains vague word "try to"
  - 6 constraints use invalid `consequence.kind` values (`security`, `availability`, `misuse`)

### finance_bp008_draft.jsonl (CZSC / 缠中说禅)
- **Constraint count**: 50
- **Schema compliance rate**: 0.0%
- **P0-P5 violations**: 1 (P0=1)
- **Stage coverage**: 5 stages (position_management, signal_analysis, morphology_analysis, czsc_data, portfolio_strategy)
- **Edge constraints**: Yes
- **Global constraints**: No
- **FATAL ratio**: 54.0% (27/50) -- significantly above target
- **Critical issues**:
  - ALL 50 constraints use `consensus: "single"` (not in schema, should be `mixed` or `contested`)
  - **finance-C-116: P0a - expert_reasoning score=0.9 > 0.7**
  - 7 constraints use invalid `constraint_kind: "interface_contract"` (should be `architecture_guardrail`)
  - 1 constraint uses invalid `constraint_kind: "security_constraint"`
  - 2 constraints use invalid `target_scope: "blueprint"` (finance-C-135, finance-C-140)
  - 2 constraints use invalid `consequence.kind: "degradation"`

### finance_bp009_draft.jsonl (ZVT)
- **Constraint count**: 48
- **Schema compliance rate**: 47.9%
- **P0-P5 violations**: 1 (P0=0)
- **Stage coverage**: 7 stages (schema_layer, data_collection, data_storage, factor_analysis, selection_strategy, visualization, notification)
- **Edge constraints**: No
- **Global constraints**: No
- **FATAL ratio**: 0.0% (0/48) -- critically low, no fatal constraints at all
- **Critical issues**:
  - 18 constraints use invalid `modality: "must_understand"` (not in schema)
  - 15+ constraints use invalid `consequence.kind` values (`wrong_result`, `silent_error`, `data_loss`, `subtle_bug`, `info`, `redundancy`, `architecture_violation`)
  - finance-C-bp009-022: P4 - consequence.description < 20 chars
  - ID format uses `finance-C-bp009-NNN` instead of `finance-C-NNN`

### finance_bp010_draft.jsonl (Daily Stock Analysis)
- **Constraint count**: 45
- **Schema compliance rate**: 66.7%
- **P0-P5 violations**: 4 (P0=0)
- **Stage coverage**: 5 stages (data_acquisition, indicator_calculation, signal_detection, visualization, reporting)
- **Edge constraints**: Yes
- **Global constraints**: No
- **FATAL ratio**: 22.2% (10/45) -- below target
- **Critical issues**:
  - 12 constraints use invalid `consequence.kind: "degraded_quality"`
  - 6 constraints use invalid `constraint_kind: "content_integrity_check"` (not in schema)
  - bp010-C-002: P3 - `when` has <10% Chinese
  - bp010-C-013/029/038: P4 - consequence contains vague word "建议"
  - ID format uses `bp010-C-NNN` instead of `finance-C-NNN`

---

## Summary

### Overall Rating: **D (Fail -- requires systematic rework)**

| Metric | Value |
|---|---|
| Total constraints audited | 347 |
| Schema-compliant constraints | 124 / 347 (35.7%) |
| Total P0 violations | 3 |
| Total P0-P5 violations | 17 |
| ID format violations | 155 / 347 (44.7%) |
| Invalid enum value instances | 253 |
| Average FATAL ratio | 25.2% (target 30-40%) |

### Structure Diff with Gold Standard (340 existing constraints)

| Diff Type | File(s) | Details |
|---|---|---|
| **Missing 6 fields** | bp004 | `hash`, `version`, `machine_checkable`, `promote_to_acceptance`, `relations`, `tags` -- entire version block absent |
| **Invalid `source_type`** | bp004 | Uses `"source_code"` instead of `"code_analysis"` (52 instances) |
| **Invalid `evidence_ref.type`** | bp004 | Uses `"code"` instead of `"source_code"` (70 instances) |
| **Invalid `modality`** | bp006, bp009 | Invented `"should_know"` (33x) and `"must_understand"` (18x) |
| **Invalid `constraint_kind`** | bp006, bp008, bp010 | Invented `"pitfall"` (17x), `"environment_requirement"` (7x), `"interface_contract"` (7x), `"content_integrity_check"` (6x), `"security_constraint"` (1x) |
| **Invalid `consequence.kind`** | ALL files | 140 constraints use non-schema values: `wrong_result` (36x), `silent_failure` (27x), `runtime_error` (19x), `logic_error` (17x), `degraded_quality` (12x), `data_loss` (6x), etc. |
| **Invalid `consensus`** | bp008 | Uses `"single"` (50x) instead of `mixed`/`contested` |
| **Invalid `target_scope`** | bp008 | Uses `"blueprint"` (2x), not in schema |
| **ID format** | bp004, bp009, bp010 | 155 IDs do not match `^[a-z0-9][a-z0-9_-]*-C-\d{3,}$` pattern |

### Mandatory P0 Fix List

| # | Constraint ID | File | Violation | Required Fix |
|---|---|---|---|---|
| 1 | finance-C-216 | bp007 | P0a: `expert_reasoning` with `score=0.95` | Lower score to <= 0.7, or change `source_type` to `code_analysis` with evidence |
| 2 | finance-C-239 | bp007 | P0a: `expert_reasoning` with `score=0.95` | Lower score to <= 0.7, or change `source_type` to `code_analysis` with evidence |
| 3 | finance-C-116 | bp008 | P0a: `expert_reasoning` with `score=0.9` | Lower score to <= 0.7, or change `source_type` to `code_analysis` with evidence |

### Systemic Issues Requiring Batch Fix

These are not individual P0 violations but systemic extraction pipeline failures that affect large swaths of constraints:

1. **bp004 (54 constraints): Complete schema mismatch.** Missing 6 required fields, wrong enum values for `source_type` and `evidence_ref.type`. This file was clearly extracted with a different (older or non-standard) schema template. **Requires full re-extraction or automated migration.**

2. **bp006 (42/53 invalid): Invented enum values.** The extraction agent created `modality: "should_know"` and `constraint_kind: "pitfall"` which do not exist in Schema v2.0. These need semantic mapping:
   - `should_know` -> `should` (with action rewritten from knowledge to behavior)
   - `pitfall` -> `operational_lesson`
   - `environment_requirement` -> `resource_boundary`

3. **bp008 (50/50 invalid): `consensus: "single"` everywhere.** Must map to `mixed` or `contested`. The extraction agent apparently misunderstood the consensus enum.

4. **bp009 (25/48 invalid): Invented `must_understand` modality.** Similar to bp006's `should_know` -- needs mapping to `should` with action rewrite.

5. **ALL files: `consequence.kind` vocabulary drift.** 140 constraints use 15+ non-schema values. Mapping table needed:
   - `runtime_error` -> `bug`
   - `logic_error` -> `bug`
   - `wrong_result` -> `bug` or `data_corruption`
   - `silent_failure` / `silent_error` -> `bug`
   - `data_loss` -> `data_corruption`
   - `degradation` / `degraded_quality` -> `performance`
   - `performance_degradation` -> `performance`
   - `security` -> `safety`
   - `availability` -> `service_disruption`
   - `architecture_violation` -> `operational_failure`
   - `resource_leak` -> `performance`
   - `legal_risk` -> `compliance`
   - `misuse` / `misinterpretation` -> `operational_failure`
   - `subtle_bug` -> `bug`
   - `info` / `redundancy` -> `operational_failure`

6. **ID format inconsistency in 3 files (155 constraints).** bp004 uses `bp004-cNNN`, bp009 uses `finance-C-bp009-NNN`, bp010 uses `bp010-C-NNN`. All should follow `finance-C-NNN` pattern.

7. **FATAL ratio imbalance.** bp009 has 0% fatal (too low), bp008 has 54% fatal (too high). Target is 30-40%.

### Recommended Action Plan

1. **Immediate**: Fix 3 P0a violations (expert_reasoning score)
2. **Batch migration script**: Create an automated fixer for the 5 systemic enum mapping issues above
3. **Re-extract bp004**: The schema gap is too large for patching; re-run extraction with correct template
4. **ID renumbering**: Assign sequential `finance-C-341` through `finance-C-687` IDs after all fixes
5. **FATAL calibration**: Review bp009 (0% fatal) and bp008 (54% fatal) for severity misclassification
6. **Add edge + global constraints**: bp005, bp006, bp007, bp009 lack edge constraints; bp005-bp010 lack global constraints

---

*Generated by constraint-sop-audit pipeline. Total constraints: 347, Schema violations: 223, P0 violations: 3.*
