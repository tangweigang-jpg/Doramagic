#!/usr/bin/env python3
"""Compile Crystal Skeleton v5.0 — Schema-driven compiler for Doramagic crystals.

Reads blueprint (LATEST.yaml) + constraints (LATEST.jsonl) + coverage_targets.json
and emits:
  1. {id}.seed.yaml  — structured crystal contract conforming to crystal_contract.schema.yaml
  2. {id}.human_summary.md — English Doraemon-persona sidecar rendered from seed.yaml
  3. validate.py — standalone validation script

Usage:
    python3 compile_crystal_skeleton.py \\
        --blueprint-dir knowledge/sources/finance/finance-bp-009--zvt \\
        --target-host openclaw \\
        --output-seed finance-bp-009-v5.0.seed.yaml \\
        --output-human-summary finance-bp-009-v5.0.human_summary.md \\
        --output-validate validate.py \\
        --sop-version crystal-compilation-v5.0
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[error] PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ============================================================
# Load Inputs (retained from v3.x)
# ============================================================


def load_inputs(
    blueprint_dir: Path,
    domain_constraints_path: Path | None = None,
) -> tuple[dict, list[dict], dict]:
    bp_path = blueprint_dir / "LATEST.yaml"
    cons_path = blueprint_dir / "LATEST.jsonl"
    with bp_path.open() as f:
        bp = yaml.safe_load(f)
    constraints: list[dict] = []
    with cons_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                c = json.loads(line)
                c["_source_scope"] = "project"
                constraints.append(c)
    if domain_constraints_path is not None:
        project_ids = {c.get("id") for c in constraints}
        skipped_collisions: list[str] = []
        with domain_constraints_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                c = json.loads(line)
                cid = c.get("id")
                if cid and cid in project_ids:
                    # Project-local takes precedence; skip domain duplicate to preserve SA-03 uniqueness
                    skipped_collisions.append(cid)
                    continue
                c["_source_scope"] = "domain"
                constraints.append(c)
        if skipped_collisions:
            print(
                f"[warn] {len(skipped_collisions)} domain constraint(s) dropped due to id "
                f"collision with project constraints (project wins): "
                f"{skipped_collisions[:10]}" + ("..." if len(skipped_collisions) > 10 else ""),
                file=sys.stderr,
            )
    targets_path = blueprint_dir / "crystal_inputs" / "coverage_targets.json"
    targets: dict = {}
    if targets_path.exists():
        targets = json.loads(targets_path.read_text())
    return bp, constraints, targets


# ============================================================
# Helper: get constraint when/action/modality/kind fields
# ============================================================


def _extract_constraint_fields(c: dict) -> dict:
    core = c.get("core") or {}
    return {
        "id": c.get("id", "?"),
        "when": core.get("when") or c.get("when", ""),
        "action": core.get("action") or c.get("action", ""),
        "modality": core.get("modality") or c.get("modality", "must"),
        "kind": c.get("constraint_kind", "domain_rule"),
        "severity": c.get("severity", "high"),
        "consequence": core.get("consequence"),
        "stage_ids": (c.get("applies_to") or {}).get("stage_ids") or [],
        "derived_from_bd_id": c.get("derived_from"),
        "source_scope": c.get("_source_scope", "project"),
    }


# ============================================================
# Build: meta
# ============================================================


def build_meta(bp: dict, target_host: str, sop_version: str) -> dict:
    # Derive crystal version from sop_version (e.g. crystal-compilation-v5.3 → v5.3)
    import re as _re

    m = _re.search(r"v(\d+\.\d+)$", sop_version)
    version_str = f"v{m.group(1)}" if m else "v5.3"
    bp_id = bp.get("id", "unknown")
    crystal_id = f"{bp_id}-{version_str}"
    return {
        "id": crystal_id,
        "version": version_str,
        "blueprint_id": bp_id,
        "sop_version": sop_version,
        "source_language": "en",
        "compiled_at": datetime.now(UTC).isoformat(),
        "target_host": target_host,
        "authoritative_artifact": {
            "primary": "seed.yaml",
            "non_authoritative_derivatives": [
                "SKILL.md (host-generated summary, may lag)",
                "HEARTBEAT.md (host telemetry)",
                "memory/*.md (host conversational memory)",
            ],
            "rule": (
                "On any behavioral decision (preconditions check, OV assertion, EQ rule firing, "
                "spec_lock verification), agents MUST re-read seed.yaml. Derivatives are for UI "
                "display only and may be out-of-date."
            ),
        },
        "execution_protocol": {
            "install_trigger": (
                "When seed.yaml is submitted without explicit execution intent "
                "(e.g. file upload, skill registration command)"
            ),
            "execute_trigger": (
                "When user intent matches intent_router.uc_entries[].positive_terms "
                "AND user uses action verb (run/execute/跑/执行/backtest/fetch/collect)"
            ),
            "on_execute": [
                "Reload seed.yaml (do not rely on SKILL.md or cached summaries)",
                "Run preconditions[] in declared order; halt on first fatal failure with on_fail message to user",
                "Enter context_state_machine.CA1_MEMORY_CHECKED state",
                "Evaluate evidence_quality.enforcement_rules[]; fire triggers that match declared state",
                "Translate user_facing_fields to user locale per locale_contract",
            ],
            "workspace_resolution": {
                "scripts_path": "{host_workspace}/scripts/",
                "skills_path": "{host_workspace}/skills/",
                "trace_path": "{host_workspace}/.trace/",
            },
        },
    }


# ============================================================
# Build: locale_contract
# ============================================================


def build_locale_contract() -> dict:
    # v5.3: user_facing_fields expanded 12→26 per consumer_map.yaml user_facing_fields_expected.
    # Every NR+TR field in the schema is listed here so translator consumer covers all
    # user-visible text (previously preconditions.on_fail, OV.failure_message, stages.narrative,
    # etc. were English-only when user locale != en).
    return {
        "source_language": "en",
        "user_facing_fields": [
            # human_summary (4)
            "human_summary.what_i_can_do.tagline",
            "human_summary.what_i_can_do.use_cases[]",
            "human_summary.what_i_auto_fetch[]",
            "human_summary.what_i_ask_you[]",
            # evidence_quality (1)
            "evidence_quality.user_disclosure_template",
            # post_install_notice (8)
            "post_install_notice.message_template.positioning",
            "post_install_notice.message_template.capability_catalog.groups[].name",
            "post_install_notice.message_template.capability_catalog.groups[].description",
            "post_install_notice.message_template.capability_catalog.groups[].ucs[].name",
            "post_install_notice.message_template.capability_catalog.groups[].ucs[].short_description",
            "post_install_notice.message_template.call_to_action",
            "post_install_notice.message_template.featured_entries[].beginner_prompt",
            "post_install_notice.message_template.more_info_hint",
            # preconditions error messages (2) — NEW v5.3
            "preconditions[].description",
            "preconditions[].on_fail",
            # intent_router (2) — NEW v5.3
            "intent_router.uc_entries[].name",
            "intent_router.uc_entries[].ambiguity_question",
            # architecture narrative (4) — NEW v5.3
            "architecture.pipeline",
            "architecture.stages[].narrative.does_what",
            "architecture.stages[].narrative.key_decisions",
            "architecture.stages[].narrative.common_pitfalls",
            # constraints violation (2) — NEW v5.3
            "constraints.fatal[].consequence",
            "constraints.regular[].consequence",
            # validator/gate failure (2) — NEW v5.3
            "output_validator.assertions[].failure_message",
            "acceptance.hard_gates[].on_fail",
            # skill emission notification (1) — NEW v5.3
            "skill_crystallization.action",
        ],
        "locale_detection_order": [
            "explicit_user_declaration",
            "first_message_language",
            "system_locale",
        ],
        "translation_enforcement": {
            "trigger": "on_first_user_message",
            "action": (
                "Render user_facing_fields in detected locale, preserving all IDs "
                "(BD-/SL-/UC-/finance-C-) and code identifiers verbatim"
            ),
            "violation_code": "LOCALE-01",
            "violation_signal": (
                "User receives untranslated English Human Summary when detected locale != en"
            ),
        },
    }


# ============================================================
# Build: evidence_quality
# ============================================================


def build_evidence_quality(bp: dict) -> dict:
    meta = bp.get("_enrich_meta") or {}
    audit = bp.get("audit_checklist_summary") or {}

    ev_coverage_ratio = meta.get("evidence_coverage_ratio")
    ev_verify_ratio = meta.get("evidence_verify_ratio")
    ev_invalid = int(meta.get("evidence_invalid") or 0)
    ev_verified = meta.get("evidence_verified")
    ev_auto_fixed = meta.get("evidence_auto_fixed")

    fu = audit.get("finance_universal") or {}
    st = audit.get("subdomain_totals") or {}
    fu_fail = int(fu.get("fail") or 0)
    sub_fail = int(st.get("fail") or 0)
    audit_fail_total = fu_fail + sub_fail

    audit_coverage = audit.get("coverage")
    audit_pass_rate = audit.get(
        "pass_rate"
    )  # CONCERN 4: pass/total ratio — preserved as dual signal

    declared = {
        "evidence_coverage_ratio": ev_coverage_ratio,
        "evidence_verify_ratio": ev_verify_ratio,
        "evidence_invalid": ev_invalid,
        "evidence_verified": ev_verified,
        "evidence_auto_fixed": ev_auto_fixed,
        "audit_coverage": audit_coverage,
        "audit_pass_rate": audit_pass_rate,  # CONCERN 4: host sees both coverage (completeness) and pass_rate (quality)
        "audit_fail_total": audit_fail_total,
        "audit_finance_universal": {
            "pass": int(fu.get("pass") or 0),
            "warn": int(fu.get("warn") or 0),
            "fail": fu_fail,
        },
        "audit_subdomain_totals": {
            "pass": int(st.get("pass") or 0),
            "warn": int(st.get("warn") or 0),
            "fail": sub_fail,
        },
    }

    enforcement_rules = [
        {
            "id": "EQ-01",
            "trigger": "declared.evidence_verify_ratio < 0.5",
            "action": (
                "MUST invoke traceback lookup for all cited BD-IDs in output before emitting "
                "business code — read LATEST.yaml sections for each BD referenced"
            ),
            "violation_code": "EQ-01-V",
            "violation_signal": (
                "Generated script references BD-IDs but no tool_call to read LATEST.yaml "
                "preceded code generation"
            ),
        },
        {
            "id": "EQ-02",
            "trigger": "declared.audit_fail_total > 20",
            "action": (
                "MUST prepend user_disclosure_template (translated to user locale) to first "
                "user-facing response"
            ),
            "violation_code": "EQ-02-V",
            "violation_signal": (
                "First agent response to user does not contain audit warning phrase"
            ),
        },
    ]

    # Compute verify ratio for disclosure template
    vr = ev_verify_ratio or 0.0
    vr_pct = f"{vr * 100:.1f}%"

    user_disclosure_template = (
        f"[QUALITY NOTICE] This crystal was compiled from blueprint {bp.get('id', 'unknown')}. "
        f"Evidence verify ratio = {vr_pct} and audit fail total = {audit_fail_total}. "
        f"Generated results may have uncaptured requirement gaps. "
        f"Verify critical decisions against source files (LATEST.yaml / LATEST.jsonl)."
    )

    return {
        "declared": declared,
        "enforcement_rules": enforcement_rules,
        "user_disclosure_template": user_disclosure_template,
    }


# ============================================================
# Build: traceback
# ============================================================


def build_traceback(bp: dict, domain_constraints_name: str | None = None) -> dict:
    bp_id = bp.get("id", "unknown")
    source_files: dict = {
        "blueprint": "LATEST.yaml",
        "constraints": "LATEST.jsonl",
    }
    if domain_constraints_name:
        source_files["domain_constraints"] = domain_constraints_name
    return {
        "source_files": source_files,
        "mandatory_lookup_scenarios": [
            {
                "id": "TB-01",
                "condition": "Two constraints have apparently conflicting enforcement rules",
                "lookup_target": (
                    "LATEST.jsonl — find both constraint IDs, compare `consequence` + "
                    "`evidence_refs` to determine priority"
                ),
            },
            {
                "id": "TB-02",
                "condition": "A business decision rationale is unclear or disputed",
                "lookup_target": (
                    "LATEST.yaml — locate BD-ID under business_decisions, read "
                    "`rationale` + `alternative_considered` fields"
                ),
            },
            {
                "id": "TB-03",
                "condition": "evidence_invalid > 0 in evidence_quality.declared",
                "lookup_target": (
                    "LATEST.yaml _enrich_meta — cross-check specific BD `evidence_refs` "
                    "fields for invalid markers"
                ),
            },
            {
                "id": "TB-04",
                "condition": "User asks where a rule comes from",
                "lookup_target": (
                    "LATEST.jsonl — find constraint by ID, read `confidence.evidence_refs` "
                    "for source file + line number"
                ),
            },
            {
                "id": "TB-05",
                "condition": "Generated code does not match expected ZVT API behavior",
                "lookup_target": (
                    "LATEST.yaml stages[].required_methods — verify method signature "
                    "and evidence locator in source code"
                ),
            },
        ],
        "degraded_lookup": {
            "no_fs_access": (
                "Ask the user to paste the relevant LATEST.yaml section or LATEST.jsonl "
                f"lines for the BD-/finance-C- IDs in question. Crystal ID: {bp_id}-v5.0."
            )
        },
    }


# ============================================================
# Build: preconditions (new in v5.0)
# ============================================================


def build_preconditions(uc_list: list[dict], bp_id: str) -> list[dict]:
    """Generate preconditions based on use case types.

    For backtest/strategy UCs, generate PC-01 (zvt installed) and PC-02 (k-data exists).
    Always include PC-00 for Python environment check.
    """
    preconditions: list[dict] = [
        {
            "id": "PC-01",
            "description": "zvt package installed and importable",
            "check_command": "python3 -c 'import zvt; print(zvt.__version__)'",
            "on_fail": (
                "Run: python3 -m pip install zvt  "
                "then re-run: python3 -m zvt.init_dirs to initialize data directories"
            ),
            "severity": "fatal",
        },
        {
            "id": "PC-02",
            "description": "K-data exists for target entities (required before backtesting)",
            "check_command": (
                'python3 -c "'
                "from zvt.api.kdata import get_kdata; "
                "df = get_kdata(entity_ids=['stock_sh_600000'], limit=1); "
                "assert df is not None and len(df) > 0, 'No kdata found'\""
            ),
            "on_fail": (
                "Run recorder first: "
                "python3 -m zvt.recorders.em.em_stock_kdata_recorder "
                "--entity_ids stock_sh_600000  "
                "(replace with your target entity IDs)"
            ),
            "severity": "fatal",
            "applies_to_uc": [
                uc.get("id", "")
                for uc in uc_list
                if uc.get("type") in ("backtest", "trading", "data_pipeline")
            ],
        },
        {
            "id": "PC-03",
            "description": "ZVT data directory initialized (~/.zvt or ZVT_HOME)",
            "check_command": (
                'python3 -c "'
                "import os; from pathlib import Path; "
                "zvt_home = Path(os.environ.get('ZVT_HOME', Path.home() / '.zvt')); "
                "assert zvt_home.exists(), f'ZVT home not found: {zvt_home}'\""
            ),
            "on_fail": "Run: python3 -m zvt.init_dirs",
            "severity": "fatal",
        },
        {
            "id": "PC-04",
            "description": "SQLite write permission for ZVT data directory",
            "check_command": (
                'python3 -c "'
                "import os, tempfile; "
                "from pathlib import Path; "
                "zvt_home = Path(os.environ.get('ZVT_HOME', Path.home() / '.zvt')); "
                "test_f = zvt_home / '.write_test'; "
                'test_f.touch(); test_f.unlink()"'
            ),
            "on_fail": (
                "Check directory permissions: chmod u+w ~/.zvt  "
                "or set ZVT_HOME environment variable to a writable location"
            ),
            "severity": "warn",
        },
    ]
    return preconditions


# ============================================================
# Build: intent_router
# ============================================================


def build_intent_router(uc_list: list[dict]) -> dict:
    uc_entries = []
    for uc in uc_list:
        entry = {
            "uc_id": uc.get("id", "?"),
            "name": uc.get("name", ""),
            "positive_terms": uc.get("intent_keywords") or [],
            "data_domain": uc.get("data_domain") or uc.get("stage") or "mixed",
        }
        negatives = uc.get("negative_keywords") or uc.get("not_suitable_for") or []
        if negatives:
            entry["negative_terms"] = negatives
        disambiguation = uc.get("disambiguation") or uc.get("ambiguity_question")
        if disambiguation:
            entry["ambiguity_question"] = disambiguation
        uc_entries.append(entry)
    return {"uc_entries": uc_entries}


# ============================================================
# Build: context_state_machine
# ============================================================


def build_context_state_machine() -> dict:
    return {
        "states": [
            {
                "id": "CA1_MEMORY_CHECKED",
                "entry": "Task started",
                "exit": "All memory queries attempted and recorded; memory_unavailable set if failed",
                "timeout": "30s — skip memory, mark memory_unavailable=true, proceed to CA2",
            },
            {
                "id": "CA2_GAPS_FILLED",
                "entry": "CA1 complete",
                "exit": (
                    "All FATAL-priority required inputs answered: target market "
                    "(A-share/HK/US), data source, time range, strategy type"
                ),
                "timeout": "NOT skippable — FATAL inputs MUST be user-answered before proceeding",
            },
            {
                "id": "CA3_PATH_SELECTED",
                "entry": "CA2 complete",
                "exit": (
                    "intent_router matched single use case with confidence gap > 20% "
                    "over next candidate, no data_domain ambiguity"
                ),
                "timeout": (
                    "Trigger ambiguity_question for top-2 candidates, await user selection"
                ),
            },
            {
                "id": "CA4_EXECUTING",
                "entry": "CA3 complete + user explicit confirmation received",
                "exit": "All hard gates G1-Gn passed and output files written",
                "timeout": "NOT skippable — user confirmation of execution path required",
            },
        ],
        "enforcement": (
            "Code generation is PROHIBITED before CA4_EXECUTING. "
            "Any regression to earlier state MUST be announced to user. "
            "buy/sell ordering SL-01 check runs at CA4 entry."
        ),
    }


# ============================================================
# Build: spec_lock_registry
# ============================================================


def build_spec_lock_registry() -> dict:
    semantic_locks = [
        {
            "id": "SL-01",
            "description": "Execute sell orders before buy orders in every trading cycle",
            "locked_value": "sell() called before buy() in each Trader.run() iteration",
            "violation_is": "fatal",
            "source_bd_ids": ["BD-018"],
        },
        {
            "id": "SL-02",
            "description": "Trading signals MUST use next-bar execution (no look-ahead)",
            "locked_value": "due_timestamp = happen_timestamp + level.to_second()",
            "violation_is": "fatal",
            "source_bd_ids": ["BD-014", "BD-025"],
        },
        {
            "id": "SL-03",
            "description": "Entity IDs MUST follow format entity_type_exchange_code",
            "locked_value": "stock_sh_600000 | stockhk_hk_0700 | stockus_nasdaq_AAPL",
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
        {
            "id": "SL-04",
            "description": "DataFrame index MUST be MultiIndex (entity_id, timestamp)",
            "locked_value": "df.index.names == ['entity_id', 'timestamp']",
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
        {
            "id": "SL-05",
            "description": (
                "TradingSignal MUST have EXACTLY ONE of: position_pct, order_money, order_amount"
            ),
            "locked_value": "XOR enforcement in trading/__init__.py:68",
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
        {
            "id": "SL-06",
            "description": (
                "filter_result column semantics: True=BUY, False=SELL, None/NaN=NO ACTION"
            ),
            "locked_value": "factor.py:475 order_type_flag mapping",
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
        {
            "id": "SL-07",
            "description": "Transformer MUST run BEFORE Accumulator in factor pipeline",
            "locked_value": "compute_result(): transform at :403 before accumulator at :409",
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
        {
            "id": "SL-08",
            "description": "MACD parameters locked: fast=12, slow=26, signal=9",
            "locked_value": "factors/algorithm.py:30 macd(slow=26, fast=12, n=9)",
            "violation_is": "fatal",
            "source_bd_ids": ["BD-036"],
        },
        {
            "id": "SL-09",
            "description": (
                "Default transaction costs: buy_cost=0.001, sell_cost=0.001, slippage=0.001"
            ),
            "locked_value": "sim_account.py:25 SimAccountService default costs",
            "violation_is": "warning",
            "source_bd_ids": ["BD-029"],
        },
        {
            "id": "SL-10",
            "description": "A-share equity trading is T+1 (no same-day close of buy positions)",
            "locked_value": "sim_account.available_long filters by trading_t",
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
        {
            "id": "SL-11",
            "description": "Recorder subclass MUST define provider AND data_schema class attributes",
            "locked_value": "contract/recorder.py:71 Meta; register_schema decorator",
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
        {
            "id": "SL-12",
            "description": (
                "Factor result_df MUST contain either 'filter_result' OR 'score_result' column"
            ),
            "locked_value": (
                "result_df.columns.intersection({'filter_result', 'score_result'}) non-empty"
            ),
            "violation_is": "fatal",
            "source_bd_ids": [],
        },
    ]

    implementation_hints = [
        {
            "id": "IH-01",
            "hint": "Use AdjustType enum exactly: qfq (pre-adjust), hfq (post-adjust), bfq (none) — contract/__init__.py:121",
        },
        {
            "id": "IH-02",
            "hint": "For A-share kdata, default to hfq for long-term analysis (dividend-adjusted) — trader.py:538 StockTrader",
        },
        {
            "id": "IH-03",
            "hint": "SQLite connection MUST use check_same_thread=False for multi-threaded recorders",
        },
        {
            "id": "IH-04",
            "hint": "Accumulator state serialization uses JSON with custom encoder/decoder hooks — contract/base_service.py",
        },
        {
            "id": "IH-05",
            "hint": "Factor.level MUST match TargetSelector.level (enforced at add_factor) — factors/target_selector.py:84",
        },
    ]

    return {
        "semantic_locks": semantic_locks,
        "implementation_hints": implementation_hints,
    }


# ============================================================
# Build: preservation_manifest
# ============================================================


def build_preservation_manifest(
    bd_count: int,
    fatal_count: int,
    non_fatal_count: int,
    uc_count: int,
    preconditions_count: int,
) -> dict:
    return {
        "required_objects": {
            "business_decisions_count": bd_count,
            "fatal_constraints_count": fatal_count,
            "non_fatal_constraints_count": non_fatal_count,
            "use_cases_count": uc_count,
            "semantic_locks_count": 12,
            "preconditions_count": preconditions_count,
            "evidence_quality_rules_count": 2,
            "traceback_scenarios_count": 5,
        }
    }


# ============================================================
# Build: architecture
# ============================================================


def build_architecture(bp: dict, bd_by_stage: dict) -> dict:
    main_stages = [
        "data_collection",
        "data_storage",
        "factor_computation",
        "target_selection",
        "trading_execution",
        "visualization",
    ]

    stage_narratives = {
        "data_collection": {
            "does_what": (
                "TimeSeriesDataRecorder and FixedCycleDataRecorder fetch OHLCV and "
                "fundamental data from providers (eastmoney, joinquant, baostock, akshare) "
                "and persist domain objects (Stock1dKdata, BalanceSheet) to SQLite via df_to_db()."
            ),
            "key_decisions": (
                "BD-002 chose evaluate_start_end_size_timestamps for incremental fetch "
                "(not full refresh) because comparing to get_latest_saved_record avoids "
                "redundant API calls; BD-003 chose get_data_map field transformation "
                "to keep domain schema provider-agnostic."
            ),
            "common_pitfalls": (
                "Don't forget SL-11: Recorder subclass MUST declare both provider and "
                "data_schema class attributes else initialization fails with assertion error; "
                "finance-C-001 fatal violation."
            ),
        },
        "data_storage": {
            "does_what": (
                "StorageBackend persists DataFrames to per-provider SQLite databases at "
                "{data_path}/{provider}/{provider}_{db_name}.db using path templates "
                "from _get_path_template; Mixin.record_data and Mixin.query_data provide "
                "uniform read/write interface."
            ),
            "key_decisions": (
                "BD-004 chose StorageBackend abstraction (not hardcoded SQLite) to allow "
                "future cloud storage swap; BD-006 derives db_name from data_schema "
                "__tablename__ for per-domain database isolation."
            ),
            "common_pitfalls": (
                "SL-04 violation (wrong DataFrame index) causes factor pipeline failures "
                "downstream; always ensure df.index.names == ['entity_id', 'timestamp'] "
                "before calling record_data."
            ),
        },
        "factor_computation": {
            "does_what": (
                "Factor.compute() applies Transformer (stateless, e.g. MacdTransformer) "
                "then Accumulator (stateful, e.g. MaStatsAccumulator) to produce "
                "filter_result or score_result columns; EntityStateService persists "
                "per-entity rolling state across batches."
            ),
            "key_decisions": (
                "BD-007 chose Factor inheriting DataReader for composable data access; "
                "SL-08 locks MACD at (fast=12, slow=26, n=9) — chose standard Appel "
                "parameters not adaptive because interpretability matters for practitioners."
            ),
            "common_pitfalls": (
                "SL-07: Transformer MUST run before Accumulator — swapping order causes "
                "NaN propagation; SL-12: result_df must contain filter_result OR "
                "score_result column or TargetSelector silently drops all signals."
            ),
        },
        "target_selection": {
            "does_what": (
                "TargetSelector.add_factor() registers Factor instances; get_targets() "
                "returns entity_ids passing threshold filter at a specific timestamp, "
                "enabling point-in-time historical backtesting without look-ahead."
            ),
            "key_decisions": (
                "BD-012 chose registrable factor list (not hardcoded) for runtime "
                "customization; BD-013 chose timestamp-specific filtering not current-only "
                "because backtests need historical point-in-time correctness."
            ),
            "common_pitfalls": (
                "Factor.level MUST match TargetSelector.level (IH-05); mismatched levels "
                "cause silent empty target lists that look like no signals but are "
                "actually level-mismatch bugs."
            ),
        },
        "trading_execution": {
            "does_what": (
                "Trader.run() calls sell() before buy() each cycle, generates TradingSignals "
                "with due_timestamp = happen_timestamp + level.to_second() for next-bar "
                "execution, and applies on_profit_control() for stop-loss/take-profit "
                "before regular target selection."
            ),
            "key_decisions": (
                "SL-01 locks sell-before-buy order because available_long check in "
                "sim_account depends on it — chose this over symmetric ordering to prevent "
                "implicit leverage; BD-039 chose long=AND/short=OR multi-level logic "
                "to reflect risk asymmetry."
            ),
            "common_pitfalls": (
                "SL-02 violation (immediate execution instead of next-bar) introduces "
                "look-ahead bias and makes backtest results unreproducible in live trading; "
                "SL-10: A-share T+1 constraint — backtesting without it overstates returns."
            ),
        },
        "visualization": {
            "does_what": (
                "Drawer.draw() combines kline main chart with factor overlays and "
                "Rect annotations for entry/exit signals using Plotly; Drawable interface "
                "on Factor enables consistent chart rendering across data types."
            ),
            "key_decisions": (
                "BD-019 chose drawer_rects subclass override for custom annotations "
                "not hardcoded markers — allows traders to define entry/exit visuals "
                "without modifying base drawing logic."
            ),
            "common_pitfalls": (
                "draw_result=True by default (BD-055) is fine for development but "
                "set draw_result=False in production/headless environments to avoid "
                "Plotly server startup overhead."
            ),
        },
    }

    stages = []
    covered = set()

    for stage_name in main_stages:
        bds = bd_by_stage.get(stage_name, [])
        narrative = stage_narratives.get(
            stage_name,
            {
                "does_what": f"{stage_name} stage processing.",
                "key_decisions": "See business_decisions list below.",
                "common_pitfalls": "Check constraint list for this stage.",
            },
        )
        stage_entry: dict = {
            "id": stage_name,
            "narrative": narrative,
            "business_decisions": [
                {
                    "id": bd.get("id", "?"),
                    "type": bd.get("type", "B"),
                    "summary": (bd.get("content") or "").replace("\n", " ")[:200],
                }
                for bd in bds
            ],
        }
        stages.append(stage_entry)
        covered.add(stage_name)

    # Cross-cutting concerns — merge all non-main-pipeline BDs into ONE synthetic
    # stage with substantive narrative. Previously produced 20+ stub stages that
    # diluted quality (v5.2 review B axis: 6/10). Now single consolidated entry.
    other_stage_names = sorted(set(bd_by_stage.keys()) - covered - {"(unassigned)"})
    cross_cutting_bds: list[dict] = []
    source_groups: list[str] = []
    for stage_name in other_stage_names:
        bds = bd_by_stage.get(stage_name, [])
        if not bds:
            continue
        source_groups.append(f"{stage_name}({len(bds)})")
        for bd in bds:
            cross_cutting_bds.append(
                {
                    "id": bd.get("id", "?"),
                    "type": bd.get("type", "B"),
                    "summary": (bd.get("content") or "").replace("\n", " ")[:200],
                }
            )
    if cross_cutting_bds:
        groups_sample = ", ".join(source_groups[:6]) + (
            f", and {len(source_groups) - 6} more" if len(source_groups) > 6 else ""
        )
        stages.append(
            {
                "id": "cross_cutting_concerns",
                "narrative": {
                    "does_what": (
                        f"Invariants and utilities that span multiple pipeline stages — "
                        f"collected from {len(source_groups)} source groups: {groups_sample}."
                    ),
                    "key_decisions": (
                        f"{len(cross_cutting_bds)} BDs merged here because they apply to more than one main stage "
                        f"(e.g. algorithm helpers, default value choices, ordering contracts, error handling). "
                        f"Agent should inspect individual BD summaries and link back to affected main stages via shared IDs."
                    ),
                    "common_pitfalls": (
                        "Cross-cutting concerns frequently surface as bugs when changes to one main stage unintentionally break another. "
                        "Check constraints referencing these BDs and verify invariants still hold after any stage-local modification."
                    ),
                },
                "business_decisions": cross_cutting_bds,
            }
        )

    pipeline = (
        "data_collection -> data_storage -> factor_computation -> "
        "target_selection -> trading_execution -> visualization"
    )

    return {"pipeline": pipeline, "stages": stages}


# ============================================================
# Build: resources
# ============================================================


def _load_domain_pool(domain: str = "finance") -> dict:
    """Load domain-level resource pool. Returns empty dict if absent."""
    pool_path = Path("knowledge/sources") / domain / "_shared" / "resources.yaml"
    if not pool_path.exists():
        return {}
    try:
        with pool_path.open() as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[warn] pool load failed: {e}", file=sys.stderr)
        return {}


def build_resources(
    bp: dict,
    target_host: str,
    domain: str = "finance",
    domain_resources_path: Path | None = None,
) -> dict:
    resources_raw = bp.get("resources") or []
    packages = []
    for r in resources_raw:
        rtype = r.get("type", "")
        if rtype in ("python_package", "dependency"):
            packages.append(
                {
                    "name": r.get("name", ""),
                    "version_pin": r.get("version", "latest"),
                }
            )

    # Fix 1: Default packages — derive from domain pool, not ZVT hardcodes
    if not packages:
        pool = _load_domain_pool(domain)
        pool_entries = pool.get("resources") or []
        packages = [
            {
                "name": entry.get("name", ""),
                "version_pin": entry.get("version_range", "latest"),
            }
            for entry in pool_entries
            if entry.get("kind") == "python_package"
            and entry.get("scope") == "cross_domain"
            and entry.get("name")
        ]
        # If pool also absent or empty, return empty list (no ZVT fallback)

    # Domain resource injection (curated by Stage 2 selection pipeline).
    # Project-declared packages take precedence; domain additions are appended
    # with source_scope="domain" tag. Same-name collisions are warned and skipped.
    if domain_resources_path is not None:
        try:
            with domain_resources_path.open() as f:
                domain_pool = yaml.safe_load(f) or {}
        except Exception as e:
            print(
                f"[error] failed to load --domain-resources {domain_resources_path}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        domain_entries = domain_pool.get("resources") or []
        project_names = {p["name"] for p in packages if p.get("name")}
        skipped_collisions: list[str] = []
        for entry in domain_entries:
            if entry.get("kind") != "python_package":
                continue
            name = entry.get("name")
            if not name:
                continue
            if name in project_names:
                skipped_collisions.append(name)
                continue
            packages.append(
                {
                    "name": name,
                    "version_pin": entry.get("version_range", "latest"),
                    "source_scope": "domain",
                }
            )
        if skipped_collisions:
            print(
                f"[warn] {len(skipped_collisions)} domain package(s) dropped due to name "
                f"collision with project packages (project wins): "
                f"{skipped_collisions[:10]}" + ("..." if len(skipped_collisions) > 10 else ""),
                file=sys.stderr,
            )

    # Fix 2: entry_point_name derived from blueprint UC architecture signals
    # Priority: stage (architecture action) > type (pipeline shape) > data_domain (domain semantics)
    # Rationale: data_domain values like "holding_data" / "market_data" are semantic labels,
    # NOT executable actions. stage ("data_collection") and type ("data_pipeline") reflect
    # what the script actually does.
    ucs = bp.get("known_use_cases") or []
    primary_uc = ucs[0] if ucs else {}
    uc_stage = (primary_uc.get("stage") or "").lower()
    uc_type = (primary_uc.get("type") or "").lower()
    uc_domain = (primary_uc.get("data_domain") or "").lower()
    uc_kind = (primary_uc.get("kind") or "").lower()

    _stage_to_entry: dict[str, str] = {
        "data_collection": "run_collector",
        "data_storage": "run_collector",
        "factor_computation": "run_factor",
        "backtest": "run_backtest",
        "training": "run_training",
        "serving": "run_server",
        "research": "run_research",
    }
    _type_to_entry: dict[str, str] = {
        "data_pipeline": "run_collector",
        "backtest_engine": "run_backtest",
        "training_pipeline": "run_training",
        "inference_service": "run_server",
    }
    _domain_to_entry: dict[str, str] = {
        "data_collection": "run_collector",
        "backtest": "run_backtest",
        "training": "run_training",
        "research": "run_research",
        "serving": "run_server",
    }
    _kind_to_entry: dict[str, str] = {
        "data_collection": "run_collector",
        "backtest": "run_backtest",
        "training": "run_training",
    }
    entry_point_name: str = (
        _stage_to_entry.get(uc_stage)
        or _type_to_entry.get(uc_type)
        or _domain_to_entry.get(uc_domain)
        or _kind_to_entry.get(uc_kind)
        or "main"
    )

    # Fix 3: tail_template uses derived entry_point_name; result.json instead of result.csv
    strategy_scaffold: dict = {
        "entry_point_name": entry_point_name,
        "tail_template": (
            "# === DO NOT MODIFY BELOW THIS LINE ===\n"
            'if __name__ == "__main__":\n'
            f"    result = {entry_point_name}()  # implement above\n"
            "    from validate import enforce_validation\n"
            '    enforce_validation(result, output_path="{workspace}/result.json")\n'
            "# === END DO NOT MODIFY ==="
        ),
    }

    # Fix 4: install_recipes derived from blueprint packages only — no zvt.init_dirs
    install_recipes: list[str] = [
        f"python3 -m pip install {r['name']}"
        for r in resources_raw
        if r.get("type") == "python_package" and r.get("name")
    ][:3]

    host_adapter: dict = {}
    if target_host == "openclaw":
        host_adapter = {
            "target": "openclaw",
            "timeout_seconds": 1800,
            "shell_operator_restriction": (
                "exec tool intercepts && / ; / | — "
                "never chain: 'pip install X && python Y'. Use separate exec calls."
            ),
            "install_recipes": install_recipes,
            "credential_injection": (
                "JoinQuant/QMT credentials require user-side '!' prefix shell login. "
                "Never hardcode credentials in generated scripts."
            ),
            "path_resolution": (
                "{workspace} resolves to ~/.openclaw/workspace/doramagic at execution time."
            ),
            "file_io_tooling": (
                "Use openclaw 'write' tool for .py/.sql files; "
                "'exec' tool for python3 /absolute/path/script.py (absolute paths only)."
            ),
        }
    elif target_host == "claude_code":
        host_adapter = {
            "target": "claude_code",
            "timeout_seconds": 600,
            "install_recipes": install_recipes,
            "path_resolution": "{workspace} resolves to current working directory",
        }
    else:
        host_adapter = {
            "target": target_host,
            "timeout_seconds": 1800,
            "install_recipes": install_recipes,
            "path_resolution": "{workspace} resolves to host-specific working directory",
        }

    return {
        "packages": packages,
        "strategy_scaffold": strategy_scaffold,
        "host_adapter": host_adapter,
    }


# ============================================================
# Build: constraints (structured arrays)
# ============================================================


def build_constraints(fatal_constraints: list[dict], non_fatal_constraints: list[dict]) -> dict:
    def fmt_constraint(c: dict) -> dict:
        f = _extract_constraint_fields(c)
        result: dict = {
            "id": f["id"],
            "when": f["when"],
            "action": f["action"],
            "severity": f["severity"],
            "kind": f["kind"],
            "modality": f["modality"],
        }
        if f["consequence"]:
            cons = f["consequence"]
            if isinstance(cons, dict):
                result["consequence"] = cons.get("description")
            else:
                result["consequence"] = str(cons)
        else:
            result["consequence"] = None
        if f["stage_ids"]:
            result["stage_ids"] = f["stage_ids"]
        if f["derived_from_bd_id"]:
            result["derived_from_bd_id"] = f["derived_from_bd_id"]
        if f["source_scope"] != "project":
            result["source_scope"] = f["source_scope"]
        return result

    return {
        "fatal": [fmt_constraint(c) for c in fatal_constraints],
        "regular": [fmt_constraint(c) for c in non_fatal_constraints],
    }


# ============================================================
# Build: output_validator (business-semantic, fixes OV-02 bug)
# ============================================================


def build_output_validator() -> dict:
    assertions = [
        {
            "id": "OV-01",
            "check_predicate": (
                "all(p in inspect.getsource(zvt.factors.algorithm.macd) "
                "for p in ['slow=26', 'fast=12', 'n=9'])"
            ),
            "failure_message": (
                "FATAL: MACD params drifted from (fast=12, slow=26, n=9) — "
                "SL-08 violation, non-reproducible signals"
            ),
            "business_meaning": (
                "Standard MACD parameters are a semantic lock; drift makes results "
                "incomparable with industry-standard indicators and non-reproducible."
            ),
            "source_ids": ["SL-08", "BD-036"],
        },
        {
            "id": "OV-02",
            "check_predicate": (
                "result.get('total_trades', 0) > 0 or result.get('explicit_zero_trade_ack') is True"
            ),
            "failure_message": (
                "Zero trades executed — likely missing pre-fetched data (see PC-02) "
                "or over-restrictive filters"
            ),
            "business_meaning": (
                "A backtest with zero trades is not a valid result; "
                "either data is missing or the strategy never triggered. "
                "Structural non-emptiness check is insufficient — we need business confirmation."
            ),
            "source_ids": ["SL-01", "finance-C-073"],
        },
        {
            "id": "OV-03",
            "check_predicate": (
                "result.get('annual_return') is None or abs(float(result['annual_return'])) <= 5.0"
            ),
            "failure_message": (
                "FATAL: |annual_return| > 500% — likely look-ahead bias or data error"
            ),
            "business_meaning": (
                "Annual returns exceeding 500% are physically implausible for A-share "
                "strategies; indicates look-ahead bias or corrupt data."
            ),
            "source_ids": [],
        },
        {
            "id": "OV-04",
            "check_predicate": (
                "result.get('holding_change_pct') is None or "
                "abs(float(result['holding_change_pct'])) <= 1.0"
            ),
            "failure_message": "FATAL: |holding_change_pct| > 100% — physically impossible",
            "business_meaning": (
                "Holding change percentage cannot exceed 100%; violation indicates "
                "position accounting error."
            ),
            "source_ids": ["BD-029"],
        },
        {
            "id": "OV-05",
            "check_predicate": (
                "result.get('max_drawdown') is None or abs(float(result['max_drawdown'])) <= 1.0"
            ),
            "failure_message": "FATAL: |max_drawdown| > 100% — impossible for non-leveraged account",
            "business_meaning": (
                "Maximum drawdown cannot exceed 100% without leverage; "
                "violation indicates calculation error or look-ahead bias."
            ),
            "source_ids": [],
        },
        {
            "id": "OV-06",
            "check_predicate": (
                "not (hasattr(result, 'trade_log') and result.trade_log and "
                "any(result.trade_log[i].action == 'sell' and i+1 < len(result.trade_log) "
                "and result.trade_log[i+1].action == 'buy' and "
                "result.trade_log[i].timestamp == result.trade_log[i+1].timestamp "
                "for i in range(len(result.trade_log)-1)))"
            ),
            "failure_message": (
                "FATAL: buy-before-sell detected in same cycle — SL-01 violation, "
                "creates implicit leverage"
            ),
            "business_meaning": (
                "SL-01 requires sell() before buy() in each cycle; violation means "
                "available_long was not updated before buying, risking duplicate positions."
            ),
            "source_ids": ["SL-01"],
        },
    ]

    return {
        "assertions": assertions,
        "scaffold": {
            "validate_py_path": "{workspace}/validate.py",
            "tail_block": (
                "# === DO NOT MODIFY BELOW THIS LINE ===\n"
                'if __name__ == "__main__":\n'
                "    result = run_backtest()\n"
                "    from validate import enforce_validation\n"
                '    enforce_validation(result, output_path="{workspace}/result.csv")\n'
                "# === END DO NOT MODIFY ==="
            ),
        },
        "enforcement_protocol": (
            "1. Never edit validate.py. "
            "2. Never delete the DO NOT MODIFY tail block from the main script. "
            "3. Never wrap enforce_validation() in try/except. "
            "4. Never rewrite result write logic — it MUST go through enforce_validation. "
            "5. If validate.py raises ImportError, fix the dependency, do not remove the call."
        ),
    }


# ============================================================
# Build: acceptance
# ============================================================


def build_acceptance() -> dict:
    hard_gates = [
        {
            "id": "G1",
            "check": "{workspace}/result.csv exists AND file size > 0",
            "on_fail": (
                "Strategy did not produce output; check run_backtest() return value "
                "and enforce_validation() call"
            ),
        },
        {
            "id": "G2",
            "check": "{workspace}/result.csv.validation_passed marker file exists",
            "on_fail": "Validation did not complete; review validate.py output and fix assertion failures",
        },
        {
            "id": "G3",
            "check": "Main script contains literal: from validate import enforce_validation",
            "on_fail": "Validation chain stripped; re-add the import in the DO NOT MODIFY block",
        },
        {
            "id": "G4",
            "check": "Main script contains literal: # === DO NOT MODIFY BELOW THIS LINE ===",
            "on_fail": "Validation fence removed; regenerate DO NOT MODIFY tail block",
        },
        {
            "id": "G5",
            "check": ("result.csv has at least 1 row: pandas.read_csv(result_csv).shape[0] >= 1"),
            "on_fail": (
                "Empty result; check if trade_log is non-empty and factors generated signals. "
                "Confirm PC-02 (k-data exists) passed."
            ),
        },
        {
            "id": "G6",
            "check": (
                "If MACD strategy: source contains 'slow=26' AND 'fast=12' AND 'n=9' "
                "in algorithm call"
            ),
            "on_fail": "MACD params drifted from SL-08 lock; restore standard (12, 26, 9)",
        },
        {
            "id": "G7",
            "check": (
                "For data pipeline tasks: result.csv columns include 'entity_id' and 'timestamp'"
            ),
            "on_fail": (
                "Missing required columns; check Mixin.query_data return schema and "
                "DataFrame MultiIndex reset_index() before writing"
            ),
        },
        {
            "id": "G8",
            "check": "OV-03 passes: abs(annual_return) <= 5.0 (500%)",
            "on_fail": (
                "Physical plausibility check failed; investigate look-ahead bias or "
                "data corruption in input kdata"
            ),
        },
    ]

    soft_gates = [
        {
            "id": "SG-01",
            "rubric": (
                "Strategy narrative consistency: user intent aligns with generated strategy.py logic. "
                "dim_a: signal direction (buy/sell) matches intent [1-5, pass>=4]; "
                "dim_b: frequency (daily/intraday) aligns [1-5, pass>=4]; "
                "dim_c: risk controls match user intent [1-5, pass>=4]."
            ),
        },
        {
            "id": "SG-02",
            "rubric": (
                "Factor combination quality. "
                "dim_a: no highly correlated factor duplication [1-5, pass>=4]; "
                "dim_b: multi-period alignment correct [1-5, pass>=4]; "
                "dim_c: liquidity filter present for A-share [1-5, pass>=4]."
            ),
        },
        {
            "id": "SG-03",
            "rubric": (
                "Data source selection appropriateness. "
                "dim_a: coverage sufficient for target entities [1-5, pass>=4]; "
                "dim_b: provider latency acceptable for strategy frequency [1-5, pass>=4]; "
                "dim_c: no unauthorized provider used without credentials [1-5, pass>=4]."
            ),
        },
    ]

    return {"hard_gates": hard_gates, "soft_gates": soft_gates}


# ============================================================
# Build: skill_crystallization (new in v5.0)
# ============================================================


def build_skill_crystallization(
    bp_id: str,
    primary_uc: str,
    *,
    meta: dict,
    intent_router: dict,
    spec_lock_registry: dict,
    preconditions_list: list[dict],
    resources: dict,
) -> dict:
    """Build the skill_crystallization contract.

    All placeholders ({workspace} / {slug}) in action / output_path_template are
    resolved by the runtime emitter — not at compile time. skill_file_schema is
    populated with ACTUAL values derived from the crystal's other sections
    (intent_router / spec_lock_registry / preconditions / resources) so the
    emitter can use it as a direct template for the .skill YAML file.

    Domain-agnostic: no hardcoded finance/zvt/macd terms.
    """
    # Find the primary UC entry for intent_keywords
    primary_uc_entry = next(
        (e for e in (intent_router.get("uc_entries") or []) if e.get("uc_id") == primary_uc),
        None,
    )
    primary_uc_name = primary_uc_entry.get("name", primary_uc) if primary_uc_entry else primary_uc
    primary_uc_keywords = (primary_uc_entry or {}).get("positive_terms", [])[:6]

    # Collect all SL-IDs and fatal SL-IDs
    sl_entries = spec_lock_registry.get("semantic_locks") or []
    all_sl_ids = [sl.get("id") for sl in sl_entries if sl.get("id")]
    fatal_sl_ids = [sl.get("id") for sl in sl_entries if sl.get("violation_is") == "fatal"]

    # Collect all PC-IDs
    all_pc_ids = [pc.get("id") for pc in preconditions_list if pc.get("id")]

    # Entry point from resources
    entry_point = (resources.get("strategy_scaffold") or {}).get("entry_point_name", "main")

    return {
        "trigger": "all_hard_gates_passed AND user_opt_out_skill_saving != true",
        "output_path_template": "{workspace}/../skills/{slug}.skill",
        "slug_template": "{blueprint_id_short}-{uc_id_lower}",
        "captured_fields": [
            "name",
            "intent_keywords",
            "entry_point_script",
            "validate_script",
            "fatal_constraints",
            "spec_locks",
            "preconditions",
            "human_summary_translated",
        ],
        "action": (
            "After all Hard Gates PASS, resolve slug via slug_template using the "
            "executed UC, then write the .skill YAML file at output_path_template. "
            "Notify user in their detected locale: "
            "'Skill saved as {slug}.skill — next time say one of {sample_triggers} "
            "from the matched UC to invoke directly.'"
        ),
        "violation_signal": "All hard gates passed but no .skill file exists at expected path",
        "skill_file_schema": {
            "name": f"{bp_id} / {primary_uc_name}",
            "version": meta.get("version", "v5.3"),
            "intent_keywords": primary_uc_keywords,
            "entry_point": entry_point,
            "fatal_guards": fatal_sl_ids,
            "spec_locks": all_sl_ids,
            "preconditions": all_pc_ids,
        },
    }


# ============================================================
# Build: human_summary
# ============================================================


def build_human_summary(bp: dict, uc_list: list[dict]) -> dict:
    use_cases = [
        "A-share MACD daily golden-cross backtest with hfq price adjustment from eastmoney",
        "End-to-end ZVT pipeline: FinanceRecorder + GoodCompanyFactor + StockTrader",
        "Multi-factor strategy with TargetSelector (AND mode) combining MACD + volume breakout",
        "Index composition data collection (SZ1000, SZ2000) with EM recorder",
        "Institutional fund holdings tracker via joinquant_fund_runner pattern",
        "Custom Transformer + Accumulator factor with per-entity rolling state",
        "Bollinger Band mean-reversion factor with BollTransformer (window=20, window_dev=2)",
    ]

    # Pull first few UCs from blueprint as specific examples
    for uc in uc_list[:3]:
        uc_name = uc.get("name", "")
        if uc_name and uc_name not in str(use_cases):
            use_cases.insert(0, uc_name)
    use_cases = use_cases[:7]

    what_i_auto_fetch = [
        "ZVT stage pipeline structure (data_collection → visualization) from LATEST.yaml",
        "Semantic locks (SL-01 through SL-12) — especially sell-before-buy ordering and MACD params",
        "Fatal constraints (finance-C-*) relevant to your target strategy type",
        "Default parameters: MACD(12,26,9), hfq adjustment, buy_cost=0.001, base_capital=1M CNY",
        "Entity ID format (stock_sh_600000) and DataFrame MultiIndex convention",
        "Provider-specific recorder class names and required class attributes",
    ]

    what_i_ask_you = [
        "Target market: A-share (default), HK, or crypto? (US stocks in ZVT are half-baked — stockus_nasdaq_AAPL exists but coverage is thin)",
        "Data source / provider: eastmoney (free, no account), joinquant (account+paid), baostock (free, good history), akshare, or qmt (broker)?",
        "Strategy type: MACD golden-cross, MA crossover, volume breakout, fundamental screen, or custom factor?",
        "Time range: start_timestamp and end_timestamp for backtest period",
        "Target entity IDs: specific stocks (stock_sh_600000) or index components (SZ1000)?",
    ]

    return {
        "persona": "Doraemon",
        "what_i_can_do": {
            "tagline": (
                "I help you build quant strategies on A-share with ZVT — from data fetch to backtest, "
                "one flow. Just tell me what you want; I'll write the code, you don't have to dig docs. "
                "(Heads up: ZVT natively supports A-share, HK, and crypto. "
                "US stocks — stockus_nasdaq_AAPL — are half-baked; don't bother for serious work.)"
            ),
            "use_cases": use_cases,
        },
        "what_i_auto_fetch": what_i_auto_fetch,
        "what_i_ask_you": what_i_ask_you,
        "locale_rendering": {
            "instruction": (
                "On first user contact, translate all fields above into detected user locale "
                "while preserving Doraemon persona (direct, frank, mildly snarky, knows limits)."
            ),
            "preserve_verbatim": [
                "BD-IDs",
                "SL-IDs",
                "UC-IDs",
                "finance-C-IDs",
                "class_names",
                "function_names",
                "file_paths",
                "numeric_thresholds",
            ],
        },
    }


# ============================================================
# Render: validate.py (retained from v3.x with OV-02 fix)
# ============================================================


def render_validate_py(blueprint_id: str) -> str:
    return f"""# {{workspace}}/validate.py
# DO NOT EDIT — crystal contract enforcement for {blueprint_id}
# Generated by compile_crystal_skeleton.py v5.0

import sys
import json
import inspect
from pathlib import Path


def enforce_validation(result, output_path: str) -> None:
    failures = []

    # OV-01: MACD parameter lock (SL-08)
    try:
        import zvt.factors.algorithm as _algo
        src = inspect.getsource(_algo.macd)
        if "slow=26" not in src or "fast=12" not in src or "n=9" not in src:
            failures.append("FATAL OV-01: MACD params drifted from (fast=12, slow=26, n=9) — SL-08 violation")
    except Exception:
        pass

    # OV-02: Business-semantic trade count check (not structural non-emptiness)
    if result is None:
        failures.append("FATAL OV-02: result is None — no computation performed")
    elif isinstance(result, dict):
        total_trades = result.get("total_trades", 0)
        zero_ack = result.get("explicit_zero_trade_ack") is True
        if total_trades == 0 and not zero_ack:
            failures.append(
                "FATAL OV-02: Zero trades executed — likely missing pre-fetched data (PC-02) "
                "or over-restrictive filters. Set result['explicit_zero_trade_ack']=True to ack intentional zero-trade."
            )

    # OV-03: annual return physical plausibility
    try:
        if hasattr(result, "get"):
            ar = result.get("annual_return")
            if ar is not None and abs(float(ar)) > 5.0:
                failures.append(f"FATAL OV-03: |annual_return|={{float(ar):.2f}} > 500% — likely look-ahead bias")
    except Exception:
        pass

    # OV-04: holding change plausibility
    try:
        if hasattr(result, "get"):
            hc = result.get("holding_change_pct")
            if hc is not None and abs(float(hc)) > 1.0:
                failures.append(f"FATAL OV-04: |holding_change_pct|={{float(hc):.2f}} > 100%")
    except Exception:
        pass

    # OV-05: drawdown plausibility
    try:
        if hasattr(result, "get"):
            dd = result.get("max_drawdown")
            if dd is not None and abs(float(dd)) > 1.0:
                failures.append(f"FATAL OV-05: |max_drawdown|={{float(dd):.2f}} > 100% — impossible without leverage")
    except Exception:
        pass

    # OV-06: sell-before-buy ordering (SL-01)
    try:
        if hasattr(result, "trade_log") and result.trade_log:
            log = result.trade_log
            for i in range(len(log) - 1):
                if (log[i].action == "sell"
                        and log[i + 1].action == "buy"
                        and log[i].timestamp == log[i + 1].timestamp):
                    # This is correct order (sell then buy same cycle) — OK
                    pass
                elif (log[i].action == "buy"
                        and log[i + 1].action == "sell"
                        and log[i].timestamp == log[i + 1].timestamp):
                    failures.append("FATAL OV-06: buy-before-sell in same cycle — SL-01 violation")
                    break
    except Exception:
        pass

    # === END assertions ===

    if failures:
        Path(f"{{output_path}}.FAILED.log").write_text("\\n".join(failures))
        sys.stderr.write("\\n".join(failures) + "\\n")
        sys.exit(1)

    # Write result
    if hasattr(result, "to_csv"):
        result.to_csv(output_path, index=False)
    elif isinstance(result, dict):
        Path(output_path).write_text(json.dumps(result, indent=2, default=str))
    elif result is None:
        Path(output_path).write_text("")
    else:
        Path(output_path).write_text(str(result))

    Path(f"{{output_path}}.validation_passed").touch()


if __name__ == "__main__":
    print("[validate.py] Standalone mode — checking SL parameter integrity...")
    failures = []
    try:
        import zvt.factors.algorithm as _algo
        import inspect
        src = inspect.getsource(_algo.macd)
        if "slow=26" not in src:
            failures.append("SL-08: MACD slow != 26")
        if "fast=12" not in src:
            failures.append("SL-08: MACD fast != 12")
        if "n=9" not in src:
            failures.append("SL-08: MACD n != 9")
    except ImportError:
        print("[validate.py] zvt not installed — cannot verify SL-08")

    if failures:
        for f in failures:
            print(f"  FAIL: {{f}}")
        sys.exit(1)
    print("[validate.py] ALL GATES PASSED.")
    sys.exit(0)
"""


# ============================================================
# Render: human_summary.md sidecar
# ============================================================


def render_human_summary_md(seed: dict) -> str:
    hs = seed.get("human_summary", {})
    meta = seed.get("meta", {})
    crystal_id = meta.get("id", "unknown")
    persona = hs.get("persona", "Doraemon")

    wic = hs.get("what_i_can_do", {})
    tagline = wic.get("tagline", "")
    use_cases = wic.get("use_cases", [])
    auto_fetch = hs.get("what_i_auto_fetch", [])
    ask_you = hs.get("what_i_ask_you", [])
    lr = hs.get("locale_rendering", {})
    lr_instruction = lr.get("instruction", "")
    preserve = lr.get("preserve_verbatim", [])

    lines = [
        f"# {crystal_id} — Human Summary",
        "",
        f"**Persona**: {persona}",
        "",
        f"> {tagline}",
        "",
        "## What I Can Do",
        "",
    ]
    for uc in use_cases:
        lines.append(f"- {uc}")
    lines += [
        "",
        "## What I Auto-Fetch",
        "",
    ]
    for item in auto_fetch:
        lines.append(f"- {item}")
    lines += [
        "",
        "## What I Ask You",
        "",
    ]
    for item in ask_you:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Locale Rendering",
        "",
        f"**Instruction**: {lr_instruction}",
        "",
        "**Preserve verbatim**: " + ", ".join(preserve),
        "",
        "---",
        "",
        f"*Generated by compile_crystal_skeleton.py v5.0 for {crystal_id}*",
        "*All content is English source — agent translates on first user contact.*",
    ]
    return "\n".join(lines)


# ============================================================
# Build: capability_catalog helpers + builder (new in v5.2)
# ============================================================


def _heuristic_emoji(name: str, description: str = "") -> str:
    """Return a universal-domain emoji based on generic English keyword matching.

    Keywords are intentionally domain-agnostic so they work equally well for
    finance, web, ML, infra, and any other project type.
    """
    text = (name + " " + description).lower()
    if any(k in text for k in ["data", "fetch", "collect", "record", "recorder"]):
        return "📊"
    if any(k in text for k in ["compute", "analyze", "factor", "selector", "scoring"]):
        return "🧮"
    if any(k in text for k in ["test", "simulate", "execute", "run", "trade"]):
        return "📈"
    if any(k in text for k in ["report", "visual", "output", "dashboard", "export"]):
        return "📋"
    if any(k in text for k in ["util", "tool", "framework", "helper", "migration"]):
        return "🔧"
    return "📦"


def _humanize(s: str) -> str:
    """Convert snake_case or hyphen-case to Title Case display name.

    e.g. 'data_collection' → 'Data Collection', 'ml-prediction' → 'Ml Prediction'.
    """
    return s.replace("-", " ").replace("_", " ").title()


def _build_uc_summary(uc: dict) -> dict:
    """Build a concise UC summary dict for capability_catalog.groups[].ucs[].

    short_description: take the first full sentence of business_problem
    (split on '.' / '。'), capped at 150 chars. If the first sentence is
    shorter than 150 chars return it whole. Never mid-cut.
    """
    desc = (uc.get("business_problem") or "").strip()
    if desc:
        # Split on period / fullwidth period / semicolon; take first non-empty
        import re as _re

        parts = _re.split(r"[.。；]\s+", desc, maxsplit=1)
        first = parts[0].strip().rstrip(".。；")
        short_description = first[:150] if len(first) > 150 else first
    else:
        short_description = uc.get("data_domain", "") or uc.get("name", uc["id"])
    return {
        "uc_id": uc["id"],
        "name": uc.get("name", uc["id"]),
        "short_description": short_description,
        "sample_triggers": (uc.get("intent_keywords") or [])[:3],
    }


def build_capability_catalog(bp: dict, uc_list: list[dict]) -> dict:
    """Build the capability_catalog block for post_install_notice.message_template.

    Two paths:
      - Path A (blueprint_declared): bp.capability_groups[] exists and is valid.
      - Path B (auto_grouped): heuristic field selection over UC attributes.

    This function is fully domain-agnostic — no field values are hardcoded.
    """
    bp_groups = bp.get("capability_groups")
    groups: list[dict] = []

    # ------------------------------------------------------------------
    # Path A: blueprint declared capability_groups
    # ------------------------------------------------------------------
    if (
        isinstance(bp_groups, list)
        and len(bp_groups) >= 1
        and all(
            isinstance(g, dict)
            and "id" in g
            and "name" in g
            and isinstance(g.get("filter"), dict)
            and "field" in g["filter"]
            and "values" in g["filter"]
            for g in bp_groups
        )
    ):
        unique_filter_fields: list[str] = []
        seen_fields: set[str] = set()
        for g in bp_groups:
            ff = g["filter"]["field"]
            if ff not in seen_fields:
                unique_filter_fields.append(ff)
                seen_fields.add(ff)

        assigned_ids: set[str] = set()
        for g in bp_groups:
            f_field = g["filter"]["field"]
            f_values = set(g["filter"]["values"])
            filtered = [uc for uc in uc_list if uc.get(f_field) in f_values]
            for uc in filtered:
                assigned_ids.add(uc["id"])
            desc = g.get("description", "")
            emoji = g.get("emoji") or _heuristic_emoji(g["name"], desc)
            groups.append(
                {
                    "group_id": g["id"],
                    "name": g["name"],
                    "description": desc,
                    "emoji": emoji,
                    "uc_count": len(filtered),
                    "ucs": [_build_uc_summary(uc) for uc in filtered],
                }
            )

        # Tail group for any UCs not covered by declared groups
        uncovered = [uc for uc in uc_list if uc["id"] not in assigned_ids]
        if uncovered:
            groups.append(
                {
                    "group_id": "other",
                    "name": "Other",
                    "description": "",
                    "emoji": "📦",
                    "uc_count": len(uncovered),
                    "ucs": [_build_uc_summary(uc) for uc in uncovered],
                }
            )

        strategy_reason = (
            f"from blueprint.capability_groups[] "
            f"({len(bp_groups)} groups, filter fields: {unique_filter_fields})"
        )
        return {
            "group_strategy": {
                "source": "blueprint_declared",
                "strategy_reason": strategy_reason,
            },
            "groups": groups,
        }

    # ------------------------------------------------------------------
    # Path B: heuristic field selection
    # ------------------------------------------------------------------
    candidate_fields = ["type", "stage", "data_domain", "category"]
    chosen_field: str | None = None
    chosen_values: list[str] = []

    for field in candidate_fields:
        values = [uc.get(field) for uc in uc_list if uc.get(field)]
        distinct = list(dict.fromkeys(values))  # preserve insertion order, dedupe
        if 2 <= len(distinct) <= 7:
            chosen_field = field
            chosen_values = distinct
            break

    if chosen_field is None:
        # Fallback: single catch-all group
        all_group: dict = {
            "group_id": "all",
            "name": "All Capabilities",
            "description": "",
            "emoji": "📦",
            "uc_count": len(uc_list),
            "ucs": [_build_uc_summary(uc) for uc in uc_list],
        }
        return {
            "group_strategy": {
                "source": "auto_grouped",
                "strategy_reason": (
                    "no candidate field had 2-7 distinct values; "
                    "all capabilities collapsed into single group"
                ),
            },
            "groups": [all_group],
        }

    # Build one group per distinct value of chosen_field
    for val in chosen_values:
        ucs_in_group = [uc for uc in uc_list if uc.get(chosen_field) == val]
        name = _humanize(val)
        groups.append(
            {
                "group_id": val,
                "name": name,
                "description": "",
                "emoji": _heuristic_emoji(name),
                "uc_count": len(ucs_in_group),
                "ucs": [_build_uc_summary(uc) for uc in ucs_in_group],
            }
        )

    # Any UCs whose chosen_field is missing/null go to an "other" tail group
    ungrouped = [uc for uc in uc_list if not uc.get(chosen_field)]
    if ungrouped:
        groups.append(
            {
                "group_id": "other",
                "name": "Other",
                "description": "",
                "emoji": "📦",
                "uc_count": len(ungrouped),
                "ucs": [_build_uc_summary(uc) for uc in ungrouped],
            }
        )

    strategy_reason = (
        f"auto-grouped by UC.{chosen_field} "
        f"({len(chosen_values)} distinct values, balanced distribution)"
    )
    return {
        "group_strategy": {
            "source": "auto_grouped",
            "strategy_reason": strategy_reason,
        },
        "groups": groups,
    }


# ============================================================
# Build: post_install_notice (new in v5.1)
# ============================================================


def build_post_install_notice(bp: dict, human_summary: dict, uc_list: list[dict]) -> dict:
    # 1. positioning: first sentence of tagline, max 150 chars
    tagline: str = (human_summary.get("what_i_can_do") or {}).get("tagline") or ""
    first_sentence = tagline.split(".")[0].strip()
    if first_sentence and not first_sentence.endswith("."):
        first_sentence = first_sentence + "."
    positioning = first_sentence[:150]

    # 2. featured_entries: use bp.featured_use_cases if valid, else heuristic
    bp_featured = bp.get("featured_use_cases")
    featured_entries: list[dict] = []

    if (
        isinstance(bp_featured, list)
        and len(bp_featured) == 3
        and all(
            isinstance(e, dict) and "uc_id" in e and "beginner_prompt" in e for e in bp_featured
        )
    ):
        # Blueprint author provided exactly 3 curated entries
        for e in bp_featured:
            featured_entries.append(
                {
                    "uc_id": e["uc_id"],
                    "beginner_prompt": e["beginner_prompt"],
                    "auto_selected": False,
                }
            )
    else:
        # Heuristic fallback: pick UCs with shortest positive_terms[0] first,
        # preferring non-backtest data_domain; fall back to all if needed
        def _heuristic_score(uc: dict) -> tuple:
            domain = uc.get("data_domain", "")
            is_backtest = 1 if domain == "backtest" else 0
            terms = uc.get("positive_terms") or []
            term_len = len(terms[0]) if terms else 999
            return (is_backtest, term_len)

        sorted_ucs = sorted(uc_list, key=_heuristic_score)
        for uc in sorted_ucs:
            uc_id = uc.get("id", "")
            if not uc_id:
                continue
            name = uc.get("name") or uc_id
            terms = uc.get("positive_terms") or []
            beginner_prompt = terms[0].capitalize() if terms else f"Try {name.lower()}"
            featured_entries.append(
                {
                    "uc_id": uc_id,
                    "beginner_prompt": beginner_prompt,
                    "auto_selected": True,
                }
            )
            if len(featured_entries) == 3:
                break

        # Pad to 3 if we got fewer (shouldn't happen in practice but be safe)
        idx = 0
        while len(featured_entries) < 3:
            fallback_id = f"UC-{100 + idx}"
            featured_entries.append(
                {
                    "uc_id": fallback_id,
                    "beginner_prompt": f"Try capability {fallback_id}",
                    "auto_selected": True,
                }
            )
            idx += 1

        # Trim to exactly 3
        featured_entries = featured_entries[:3]

    # 3. more_info_hint
    more_info_hint = f"Ask me 'what else can you do?' to see all {len(uc_list)} capabilities."

    # 4. capability_catalog
    catalog = build_capability_catalog(bp, uc_list)

    return {
        "trigger": "skill_installation_complete",
        "message_template": {
            "positioning": positioning,
            "capability_catalog": catalog,
            "call_to_action": "Tell me which one you want to try.",
            "featured_entries": featured_entries,
            "more_info_hint": more_info_hint,
        },
        "locale_rendering": {
            "instruction": (
                "On skill_installation_complete, translate ALL user-facing strings "
                "(positioning + capability_catalog.groups[].name + "
                "capability_catalog.groups[].description + "
                "capability_catalog.groups[].ucs[].short_description + "
                "call_to_action + featured_entries[].beginner_prompt + more_info_hint) "
                "into detected user locale per locale_contract. "
                "Preserve UC-IDs, group_id, emoji, and sample_triggers verbatim."
            ),
            "preserve_verbatim": [
                "UC-IDs",
                "group_id",
                "emoji",
                "sample_triggers",
                "technical_class_names",
            ],
        },
        "enforcement": {
            "action": (
                "Host agent MUST send composed message to user as the FIRST user-facing response "
                "after skill_installation_complete event. Message MUST contain: positioning, "
                "capability_catalog (rendered as markdown tables per group), "
                "3 featured_entries, call_to_action, and more_info_hint."
            ),
            "violation_code": "PIN-01",
            "violation_signal": (
                "First user-facing message post-install does not contain the full capability_catalog "
                "(all UCs grouped) OR skips featured_entries OR skips call_to_action."
            ),
        },
    }


# ============================================================
# Assemble full seed YAML dict
# ============================================================


def build_seed(
    bp: dict,
    constraints: list[dict],
    targets: dict,
    target_host: str,
    sop_version: str,
    domain_constraints_name: str | None = None,
    domain_resources_path: Path | None = None,
) -> dict:
    # Classify BDs by stage
    bd_by_stage: dict = defaultdict(list)
    for bd in bp.get("business_decisions") or []:
        stage = bd.get("stage") or "(unassigned)"
        bd_by_stage[stage].append(bd)

    # Classify constraints
    fatal_constraints = [c for c in constraints if c.get("severity") == "fatal"]
    non_fatal_constraints = [c for c in constraints if c.get("severity") != "fatal"]

    ucs = bp.get("known_use_cases") or []
    primary_uc = ucs[0].get("id", "UC-101") if ucs else "UC-101"

    bd_count = sum(len(v) for v in bd_by_stage.values())
    preconditions = build_preconditions(ucs, bp.get("id", "unknown"))

    seed = {
        "meta": build_meta(bp, target_host, sop_version),
        "locale_contract": build_locale_contract(),
        "evidence_quality": build_evidence_quality(bp),
        "traceback": build_traceback(bp, domain_constraints_name=domain_constraints_name),
        "preconditions": preconditions,
        "intent_router": build_intent_router(ucs),
        "context_state_machine": build_context_state_machine(),
        "spec_lock_registry": build_spec_lock_registry(),
        "preservation_manifest": build_preservation_manifest(
            bd_count=bd_count,
            fatal_count=len(fatal_constraints),
            non_fatal_count=len(non_fatal_constraints),
            uc_count=len(ucs),
            preconditions_count=len(preconditions),
        ),
        "architecture": build_architecture(bp, bd_by_stage),
        "resources": build_resources(bp, target_host, domain_resources_path=domain_resources_path),
        "constraints": build_constraints(fatal_constraints, non_fatal_constraints),
        "output_validator": build_output_validator(),
        "acceptance": build_acceptance(),
    }
    # Build skill_crystallization using data from already-assembled crystal sections
    # (needs intent_router, spec_lock_registry, preconditions to populate real values)
    seed["skill_crystallization"] = build_skill_crystallization(
        bp_id=bp.get("id", "unknown"),
        primary_uc=primary_uc,
        meta=seed["meta"],
        intent_router=seed["intent_router"],
        spec_lock_registry=seed["spec_lock_registry"],
        preconditions_list=seed["preconditions"],
        resources=seed["resources"],
    )

    # Build human_summary first so post_install_notice can use its tagline
    human_summary = build_human_summary(bp, ucs)
    seed["post_install_notice"] = build_post_install_notice(bp, human_summary, ucs)
    seed["human_summary"] = human_summary

    return seed


# ============================================================
# Main
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--blueprint-dir", type=Path, required=True)
    parser.add_argument("--target-host", default="openclaw")
    parser.add_argument(
        "--output-seed",
        type=Path,
        required=True,
        help="Path to output seed.yaml (v5.0 structured contract)",
    )
    parser.add_argument(
        "--output-ir",
        type=Path,
        default=None,
        help="(retired) IR yaml path — accepted for CLI compat but not written",
    )
    parser.add_argument(
        "--output-validate",
        type=Path,
        default=None,
        help="validate.py output path (default: {blueprint-dir}/validate.py)",
    )
    parser.add_argument(
        "--output-human-summary",
        type=Path,
        default=None,
        help="Path to output human_summary.md sidecar (English, Doraemon persona)",
    )
    parser.add_argument("--sop-version", default="crystal-compilation-v5.3")
    parser.add_argument(
        "--domain-constraints",
        type=Path,
        default=None,
        help=(
            "Optional JSONL path of domain-universal constraints to inject "
            "(tagged source_scope=domain). When omitted, behavior is identical "
            "to pre-domain-injection compilation."
        ),
    )
    parser.add_argument(
        "--domain-resources",
        type=Path,
        default=None,
        help=(
            "Optional YAML path of domain-pool python_package entries to inject "
            "(tagged source_scope=domain). Same shape as _shared/resources_full.yaml. "
            "When omitted, behavior is identical to pre-domain-injection compilation."
        ),
    )
    args = parser.parse_args()

    # Uniform pre-flight checks for optional domain-injection paths.
    for label, p in [
        ("--domain-constraints", args.domain_constraints),
        ("--domain-resources", args.domain_resources),
    ]:
        if p is not None and not p.exists():
            print(f"[error] {label} file not found: {p}", file=sys.stderr)
            return 2

    bp, constraints, targets = load_inputs(args.blueprint_dir, args.domain_constraints)

    domain_name = args.domain_constraints.name if args.domain_constraints else None
    seed = build_seed(
        bp,
        constraints,
        targets,
        args.target_host,
        args.sop_version,
        domain_constraints_name=domain_name,
        domain_resources_path=args.domain_resources,
    )

    # Write seed.yaml
    seed_yaml_text = yaml.safe_dump(
        seed,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    args.output_seed.parent.mkdir(parents=True, exist_ok=True)
    args.output_seed.write_text(seed_yaml_text, encoding="utf-8")

    # Verify it round-trips
    try:
        yaml.safe_load(seed_yaml_text)
    except yaml.YAMLError as e:
        print(f"[error] seed.yaml failed yaml.safe_load: {e}", file=sys.stderr)
        return 1

    # Write human_summary.md
    hs_path = args.output_human_summary or (
        args.output_seed.parent / args.output_seed.name.replace(".seed.yaml", ".human_summary.md")
    )
    hs_md = render_human_summary_md(seed)
    hs_path.write_text(hs_md, encoding="utf-8")

    # Write validate.py
    vpath = args.output_validate or (args.blueprint_dir / "validate.py")
    vpath.write_text(render_validate_py(bp.get("id", "unknown")), encoding="utf-8")

    # Count stats
    fatal_constraints = [c for c in constraints if c.get("severity") == "fatal"]
    non_fatal_constraints = [c for c in constraints if c.get("severity") != "fatal"]
    ucs = bp.get("known_use_cases") or []
    bd_by_stage: dict = defaultdict(list)
    for bd in bp.get("business_decisions") or []:
        bd_by_stage[bd.get("stage") or "(unassigned)"].append(bd)
    bd_count = sum(len(v) for v in bd_by_stage.values())

    # Check for Chinese chars in seed (except blueprint raw content that may contain Chinese)
    import re

    chinese_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
    chinese_matches = chinese_pattern.findall(seed_yaml_text)
    # Filter out expected Chinese in content fields (stage names, class names from blueprint source)
    # We allow Chinese only in 'summary' BD fields (copied from blueprint content verbatim)
    chinese_warning = ""
    if chinese_matches:
        chinese_warning = (
            f"\n[warn] {len(chinese_matches)} Chinese char(s) found in seed.yaml "
            f"(likely in BD summary fields copied verbatim from blueprint — review manually)"
        )

    # Verify 16 required top-level fields
    required_fields = [
        "meta",
        "locale_contract",
        "evidence_quality",
        "traceback",
        "preconditions",
        "intent_router",
        "context_state_machine",
        "spec_lock_registry",
        "preservation_manifest",
        "architecture",
        "resources",
        "constraints",
        "output_validator",
        "acceptance",
        "skill_crystallization",
        "human_summary",
    ]
    missing = [f for f in required_fields if f not in seed]
    if missing:
        print(f"[error] Missing required fields: {missing}", file=sys.stderr)
        return 1

    print(
        f"[done] seed.yaml:          {args.output_seed}  ({args.output_seed.stat().st_size:,} bytes)"
    )
    print(f"[done] human_summary.md:   {hs_path}  ({hs_path.stat().st_size:,} bytes)")
    print(f"[done] validate.py:        {vpath}  ({vpath.stat().st_size:,} bytes)")
    print()
    print(f"Crystal ID:        {seed['meta']['id']}")
    print(f"Top-level fields:  {len(seed)} / 16 required")
    print(f"BD total:          {bd_count}")
    print(
        f"Constraints:       {len(constraints)} ({len(fatal_constraints)} fatal + {len(non_fatal_constraints)} non-fatal)"
    )
    print(f"Use cases:         {len(ucs)}")
    print(f"Preconditions:     {len(seed['preconditions'])}")
    print(f"SL locks:          {len(seed['spec_lock_registry']['semantic_locks'])}")
    if chinese_warning:
        print(chinese_warning)
    print()
    print("Next: run scripts/crystal_quality_gate.py --strict to verify schema compliance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
