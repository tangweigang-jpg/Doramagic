"""Phase Runner — Doramagic 单项目提取管线编排核心 (Race G / S1-Sonnet)

编排逻辑：
  Stage 0  → extract_repo_facts (package call)
  Brick    → load_and_inject_bricks (optional)
  Stage 1.5 → run_stage15_agentic (optional, adapter 存在时)
  Stage 3.5 → validate_all + run_evidence_tagging + run_dsd_checks
  Stage 4.5 → compile_knowledge
  Stage 5   → assemble

Stage 1/2/3/4 仍由 OpenClaw 中的 SKILL.md 驱动（LLM 执行）。
Phase Runner 只负责确定性部分（Stage 0/3.5/4.5/5）和可选的 Stage 1.5 调度。

降级策略（任何阶段 fail → 记录 stages_failed，不崩溃管线）:
  - adapter=None        → 跳过 Stage 1.5
  - bricks_dir 不存在  → 跳过积木注入
  - Stage 3.5 验证失败 → 记录 failed，不继续 Stage 4.5
  - DSD SUSPICIOUS     → 记录 WARNING，继续
  - assemble 失败      → 记录 failed，返回已有产出
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports (soft-fail if packages not installed)
# ---------------------------------------------------------------------------


def _import_extraction_modules():
    """Import extraction modules; return None tuple on ImportError."""
    try:
        from doramagic_extraction.confidence_system import run_evidence_tagging
        from doramagic_extraction.deceptive_source_detection import run_dsd_checks
        from doramagic_extraction.knowledge_compiler import compile_knowledge
        from doramagic_extraction.stage15_agentic import run_stage15_agentic

        return run_evidence_tagging, run_dsd_checks, compile_knowledge, run_stage15_agentic
    except ImportError as exc:
        logger.warning("Could not import extraction modules: %s", exc)
        return None, None, None, None


def _import_validate():
    try:
        from doramagic_orchestration.validate_extraction import validate_all, write_report

        return validate_all, write_report
    except ImportError as exc:
        logger.warning("Could not import validate_extraction: %s", exc)
        return None, None


def _import_assemble():
    try:
        from doramagic_orchestration.assemble_output import assemble

        return assemble
    except ImportError as exc:
        logger.warning("Could not import assemble_output: %s", exc)
        return None


def _import_brick_injector():
    try:
        from doramagic_extraction.brick_injection import load_and_inject_bricks

        return load_and_inject_bricks
    except ImportError as exc:
        logger.warning("Could not import brick_injection: %s", exc)
        return None


def _import_stage0():
    try:
        from doramagic_extraction.stage0 import extract_repo_facts

        return extract_repo_facts
    except ImportError as exc:
        logger.warning("Could not import extract_repo_facts: %s", exc)
        return None


def _resolve_bricks_dir(config: PipelineConfig) -> str | None:
    """Resolve bricks dir without relying on CWD."""
    candidate = config.bricks_dir or os.environ.get("DORAMAGIC_BRICKS_DIR")
    if not candidate:
        return None
    return str(Path(candidate).expanduser().resolve())


# ---------------------------------------------------------------------------
# Config + Result models
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    """管线配置，所有字段都有合理默认值。"""

    enable_stage15: bool = True
    """是否启用 Stage 1.5 Agentic Exploration（需要 adapter != None）。"""

    enable_bricks: bool = True
    """是否启用积木注入。"""

    enable_dsd: bool = True
    """是否运行 DSD 检查（Deceptive Source Detection）。"""

    bricks_dir: str | None = None
    """积木 JSONL 文件目录。优先显式值，其次 DORAMAGIC_BRICKS_DIR，否则跳过。"""

    knowledge_budget: int = 1800
    """Knowledge Compiler token 预算。"""

    skip_assembly: bool = False
    """是否跳过 Stage 5（assemble）；主要用于测试。"""

    extract_repo_facts_script: str | None = None
    """Deprecated compatibility field; Stage 0 now imports package code directly."""


class PipelineResult(BaseModel):
    """管线执行结果汇总。"""

    stages_completed: list[str]
    stages_skipped: list[str]
    stages_failed: list[str]
    output_dir: str
    inject_dir: str | None
    dsd_report: dict | None
    total_cards: int
    total_bricks_loaded: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_cards_as_dicts(output_dir: str) -> list[dict]:
    """从 soul/cards/ 加载所有卡片为 dict 列表（供 confidence + DSD 使用）。"""
    import re

    soul_dir = os.path.join(output_dir, "soul")
    cards_base = os.path.join(soul_dir, "cards")
    cards: list[dict] = []

    for subdir in ("concepts", "workflows", "rules"):
        dirpath = os.path.join(cards_base, subdir)
        if not os.path.isdir(dirpath):
            continue
        for fname in sorted(os.listdir(dirpath)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                continue

            # Minimal frontmatter parse (same pattern as other modules)
            meta: dict = {}
            if text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    yaml_block = text[3:end].strip()
                    current_key = None
                    for line in yaml_block.split("\n"):
                        stripped = line.strip()
                        if stripped.startswith("- ") and current_key is not None:
                            if not isinstance(meta.get(current_key), list):
                                meta[current_key] = []
                            meta[current_key].append(stripped[2:].strip().strip('"').strip("'"))
                            continue
                        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)", line)
                        if m:
                            current_key = m.group(1)
                            raw_val = m.group(2).strip()
                            if raw_val and raw_val != "|":
                                meta[current_key] = raw_val.strip('"').strip("'")
                            elif not raw_val:
                                meta[current_key] = []
            meta["_filename"] = fname
            meta["_subdir"] = subdir
            # Normalise evidence_refs: may be missing from YAML; keep as list[dict]
            if "evidence_refs" not in meta:
                meta["evidence_refs"] = []
            cards.append(meta)

    return cards


def _load_repo_facts(output_dir: str) -> dict | None:
    """加载 artifacts/repo_facts.json。"""
    path = os.path.join(output_dir, "artifacts", "repo_facts.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _load_community_signals(output_dir: str) -> str | None:
    """加载 artifacts/community_signals.md。"""
    path = os.path.join(output_dir, "artifacts", "community_signals.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def _write_validation_report(output_dir: str, report: dict) -> None:
    """将 validation_report.json 写入 soul/ 目录。"""
    soul_dir = os.path.join(output_dir, "soul")
    os.makedirs(soul_dir, exist_ok=True)
    path = os.path.join(soul_dir, "validation_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def _write_dsd_report(output_dir: str, dsd_dict: dict) -> None:
    """将 DSD 报告写入 artifacts/dsd_report.json。"""
    artifacts_dir = os.path.join(output_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    path = os.path.join(artifacts_dir, "dsd_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dsd_dict, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Stage runners (each returns (completed: bool, skipped: bool))
# ---------------------------------------------------------------------------


def _run_stage0(
    repo_path: str,
    output_dir: str,
    config: PipelineConfig,
    stages_completed: list[str],
    stages_skipped: list[str],
    stages_failed: list[str],
) -> bool:
    """Stage 0: 确定性提取 — directly call package stage0 code."""
    extract_repo_facts = _import_stage0()
    if extract_repo_facts is None:
        logger.warning("Stage 0: extract_repo_facts not importable — skipping")
        stages_skipped.append("stage0")
        return False

    # Check if repo_facts.json already exists (idempotent re-run)
    facts_path = Path(output_dir) / "artifacts" / "repo_facts.json"
    if facts_path.exists():
        logger.info("Stage 0: repo_facts.json already exists, skipping re-extraction")
        stages_completed.append("stage0")
        return True

    try:
        repo_facts = extract_repo_facts(repo_path)
        payload = (
            repo_facts.model_dump(mode="json")
            if hasattr(repo_facts, "model_dump")
            else repo_facts.dict()
        )
        payload.setdefault("repo_path", repo_path)
        payload.setdefault("skills", [])
        payload.setdefault("files", [])
        payload.setdefault("config_keys", [])
        if not payload.get("project_narrative"):
            payload["project_narrative"] = payload.get("repo_summary", "")

        facts_path.parent.mkdir(parents=True, exist_ok=True)
        facts_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Stage 0 complete: repo_facts=%s", facts_path)
        stages_completed.append("stage0")
        return True
    except Exception as exc:
        logger.error("Stage 0 unexpected error: %s", exc)
        stages_failed.append("stage0")
        return False


def _run_brick_injection(
    output_dir: str,
    config: PipelineConfig,
    stages_completed: list[str],
    stages_skipped: list[str],
    stages_failed: list[str],
) -> int:
    """积木注入：根据 repo_facts.frameworks 加载领域积木。

    Returns number of bricks loaded (0 on skip/failure).
    """
    if not config.enable_bricks:
        logger.info("Brick injection: disabled by config")
        stages_skipped.append("brick_injection")
        return 0

    bricks_dir = _resolve_bricks_dir(config)
    if not bricks_dir:
        logger.info(
            "Brick injection: no explicit bricks dir and DORAMAGIC_BRICKS_DIR unset — skipping"
        )
        stages_skipped.append("brick_injection")
        return 0
    if not os.path.isdir(bricks_dir):
        logger.info("Brick injection: bricks_dir '%s' not found — skipping", bricks_dir)
        stages_skipped.append("brick_injection")
        return 0

    load_and_inject_bricks = _import_brick_injector()
    if load_and_inject_bricks is None:
        logger.warning("Brick injection: brick_injection module not importable — skipping")
        stages_skipped.append("brick_injection")
        return 0

    repo_facts = _load_repo_facts(output_dir)
    if not repo_facts:
        logger.info("Brick injection: no repo_facts.json found — skipping")
        stages_skipped.append("brick_injection")
        return 0

    frameworks = repo_facts.get("frameworks", [])
    if not frameworks:
        logger.info("Brick injection: no frameworks detected — skipping")
        stages_skipped.append("brick_injection")
        return 0

    try:
        result = load_and_inject_bricks(
            frameworks=frameworks,
            bricks_dir=bricks_dir,
            output_dir=output_dir,
        )
        logger.info(
            "Brick injection: loaded %d bricks for frameworks %s",
            result.bricks_loaded,
            result.frameworks_matched,
        )
        stages_completed.append("brick_injection")
        return result.bricks_loaded
    except Exception as exc:
        logger.error("Brick injection failed: %s\n%s", exc, traceback.format_exc())
        stages_failed.append("brick_injection")
        return 0


def _run_stage15(
    repo_path: str,
    output_dir: str,
    adapter,
    router,
    config: PipelineConfig,
    stages_completed: list[str],
    stages_skipped: list[str],
    stages_failed: list[str],
) -> None:
    """Stage 1.5: Agentic Exploration（可选）。"""
    if not config.enable_stage15 or adapter is None:
        reason = "disabled by config" if not config.enable_stage15 else "adapter=None"
        logger.info("Stage 1.5: skipping (%s)", reason)
        stages_skipped.append("stage1.5")
        return

    (
        _run_evidence_tagging,
        _run_dsd_checks,
        _compile_knowledge,
        run_stage15_agentic,
    ) = _import_extraction_modules()

    if run_stage15_agentic is None:
        logger.warning("Stage 1.5: run_stage15_agentic not importable — skipping")
        stages_skipped.append("stage1.5")
        return

    # Build Stage15AgenticInput from repo_facts + soul output
    try:
        from doramagic_contracts.base import RepoRef
        from doramagic_contracts.extraction import (
            RepoFacts,
            Stage1Coverage,
            Stage1ScanOutput,
            Stage15AgenticInput,
            Stage15Budget,
            Stage15Toolset,
        )
    except ImportError as exc:
        logger.warning("Stage 1.5: contracts not importable (%s) — skipping", exc)
        stages_skipped.append("stage1.5")
        return

    repo_facts_raw = _load_repo_facts(output_dir)
    if not repo_facts_raw:
        logger.warning("Stage 1.5: no repo_facts.json — skipping")
        stages_skipped.append("stage1.5")
        return

    # Load existing Stage 1 output from soul/00-soul.md if available
    # Stage 1 output is not a structured JSON in the default pipeline —
    # we build a minimal Stage1ScanOutput from what we know.
    try:
        _repo_basename = os.path.basename(repo_path.rstrip("/"))
        repo_ref = RepoRef(
            repo_id=_repo_basename,
            full_name=repo_facts_raw.get("full_name", _repo_basename),
            url=repo_facts_raw.get(
                "repo_url",
                repo_facts_raw.get("url", f"https://github.com/unknown/{_repo_basename}"),
            ),
            default_branch=repo_facts_raw.get("default_branch", "main"),
            commit_sha=repo_facts_raw.get("commit_sha", "unknown"),
            local_path=repo_path,
        )
        repo_facts_obj = RepoFacts(
            repo=repo_ref,
            languages=repo_facts_raw.get("languages", []),
            frameworks=repo_facts_raw.get("frameworks", []),
            entrypoints=repo_facts_raw.get("entrypoints", repo_facts_raw.get("commands", [])),
            commands=repo_facts_raw.get("commands", []),
            storage_paths=repo_facts_raw.get("storage_paths", []),
            dependencies=repo_facts_raw.get("dependencies", []),
            repo_summary=repo_facts_raw.get("project_narrative", ""),
            project_narrative=repo_facts_raw.get("project_narrative", ""),
        )
        stage1_output = Stage1ScanOutput(
            repo=repo_ref,
            findings=[],
            hypotheses=[],
            coverage=Stage1Coverage(
                answered_questions=[],
                partial_questions=[],
                uncovered_questions=["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"],
            ),
            recommended_for_stage15=True,
        )
        agentic_input = Stage15AgenticInput(
            repo=repo_ref,
            repo_facts=repo_facts_obj,
            stage1_output=stage1_output,
            budget=Stage15Budget(),
            toolset=Stage15Toolset(),
        )
    except Exception as exc:
        logger.error("Stage 1.5: failed to build input: %s\n%s", exc, traceback.format_exc())
        stages_failed.append("stage1.5")
        return

    try:
        envelope = run_stage15_agentic(agentic_input, adapter=adapter, router=router)
        if envelope.status in ("ok", "degraded"):
            logger.info(
                "Stage 1.5 complete: %d promoted claims",
                len(envelope.data.promoted_claims) if envelope.data else 0,
            )
            stages_completed.append("stage1.5")
        else:
            logger.warning(
                "Stage 1.5 returned status=%s error=%s",
                envelope.status,
                envelope.error_code,
            )
            stages_failed.append("stage1.5")
    except Exception as exc:
        logger.error("Stage 1.5 failed: %s\n%s", exc, traceback.format_exc())
        stages_failed.append("stage1.5")


def _run_stage35(
    output_dir: str,
    config: PipelineConfig,
    stages_completed: list[str],
    stages_skipped: list[str],
    stages_failed: list[str],
) -> tuple[bool, dict | None, list[dict]]:
    """Stage 3.5: 验证 + 置信度标注 + DSD。

    Returns (validation_passed, dsd_report_dict, tagged_cards).
    """
    validate_all, write_report = _import_validate()
    (
        run_evidence_tagging,
        run_dsd_checks,
        _compile_knowledge,
        _run_stage15_agentic,
    ) = _import_extraction_modules()

    # ---- 3.5a: Validation ----
    # Check if card files exist (LLM stages 1-3 produce cards; without them, skip validation)
    cards_base = os.path.join(output_dir, "soul", "cards")
    has_card_files = False
    for subdir in ("concepts", "workflows", "rules"):
        dirpath = os.path.join(cards_base, subdir)
        if os.path.isdir(dirpath) and any(f.endswith(".md") for f in os.listdir(dirpath)):
            has_card_files = True
            break

    if not has_card_files:
        logger.info("Stage 3.5: no card files found (LLM stages not yet run) — skipping validation")
        stages_skipped.append("stage3.5_validate")
        stages_skipped.append("stage3.5_confidence")
        stages_skipped.append("stage3.5_dsd")
        return True, None, []  # validation_passed=True so downstream stages can proceed

    if validate_all is None:
        logger.warning("Stage 3.5: validate_all not importable — skipping validation")
        stages_skipped.append("stage3.5_validate")
        validation_passed = False
    else:
        try:
            report = validate_all(output_dir)

            # Write report to soul/validation_report.json
            if write_report is not None:
                try:
                    write_report(report, output_dir)
                except Exception as exc:
                    logger.warning("Stage 3.5: write_report failed: %s", exc)
            else:
                _write_validation_report(output_dir, report)

            overall_pass = report.get("summary", {}).get("overall_pass", False)
            total_errors = report.get("summary", {}).get("total_errors", -1)
            logger.info(
                "Stage 3.5 validation: overall_pass=%s errors=%s",
                overall_pass,
                total_errors,
            )

            if overall_pass:
                stages_completed.append("stage3.5_validate")
                validation_passed = True
            else:
                stages_failed.append("stage3.5_validate")
                validation_passed = False
        except Exception as exc:
            logger.error("Stage 3.5 validation error: %s\n%s", exc, traceback.format_exc())
            stages_failed.append("stage3.5_validate")
            validation_passed = False

    # ---- 3.5b: Evidence tagging ----
    cards = _load_cards_as_dicts(output_dir)
    tagged_cards: list[dict] = cards

    if run_evidence_tagging is None:
        logger.warning("Stage 3.5: run_evidence_tagging not importable — skipping")
        stages_skipped.append("stage3.5_confidence")
    elif not cards:
        logger.info("Stage 3.5: no cards found — skipping confidence tagging")
        stages_skipped.append("stage3.5_confidence")
    else:
        try:
            tagged_cards = run_evidence_tagging(cards)
            logger.info("Stage 3.5: tagged %d cards with evidence", len(tagged_cards))
            stages_completed.append("stage3.5_confidence")
        except Exception as exc:
            logger.error("Stage 3.5 confidence tagging error: %s\n%s", exc, traceback.format_exc())
            stages_failed.append("stage3.5_confidence")

    # ---- 3.5c: DSD ----
    dsd_report_dict: dict | None = None

    if not config.enable_dsd:
        stages_skipped.append("stage3.5_dsd")
    elif run_dsd_checks is None:
        logger.warning("Stage 3.5: run_dsd_checks not importable — skipping DSD")
        stages_skipped.append("stage3.5_dsd")
    else:
        repo_facts = _load_repo_facts(output_dir)
        community_signals = _load_community_signals(output_dir)
        try:
            dsd_report = run_dsd_checks(
                cards=tagged_cards,
                repo_facts=repo_facts,
                community_signals=community_signals,
            )
            dsd_report_dict = dsd_report.to_dict()
            overall_status = dsd_report_dict.get("overall_status", "UNKNOWN")
            logger.info("Stage 3.5 DSD: overall_status=%s", overall_status)

            if overall_status == "SUSPICIOUS":
                logger.warning(
                    "Stage 3.5 DSD returned SUSPICIOUS — continuing with warning (not blocking)"
                )

            _write_dsd_report(output_dir, dsd_report_dict)
            stages_completed.append("stage3.5_dsd")
        except Exception as exc:
            logger.error("Stage 3.5 DSD error: %s\n%s", exc, traceback.format_exc())
            stages_failed.append("stage3.5_dsd")

    return validation_passed, dsd_report_dict, tagged_cards


def _run_stage45(
    output_dir: str,
    config: PipelineConfig,
    stages_completed: list[str],
    stages_skipped: list[str],
    stages_failed: list[str],
) -> bool:
    """Stage 4.5: Knowledge Compiler。"""
    (
        _run_evidence_tagging,
        _run_dsd_checks,
        compile_knowledge,
        _run_stage15_agentic,
    ) = _import_extraction_modules()

    if compile_knowledge is None:
        logger.warning("Stage 4.5: compile_knowledge not importable — skipping")
        stages_skipped.append("stage4.5")
        return False

    try:
        success = compile_knowledge(output_dir, budget=config.knowledge_budget)
        if success:
            logger.info("Stage 4.5: Knowledge Compiler complete")
            stages_completed.append("stage4.5")
        else:
            logger.error("Stage 4.5: compile_knowledge returned False")
            stages_failed.append("stage4.5")
        return success
    except Exception as exc:
        logger.error("Stage 4.5 error: %s\n%s", exc, traceback.format_exc())
        stages_failed.append("stage4.5")
        return False


def _run_stage5(
    output_dir: str,
    config: PipelineConfig,
    stages_completed: list[str],
    stages_skipped: list[str],
    stages_failed: list[str],
) -> str | None:
    """Stage 5: 组装 inject/ 目录。

    Returns inject_dir path or None on failure/skip.
    """
    if config.skip_assembly:
        logger.info("Stage 5: skipped by config (skip_assembly=True)")
        stages_skipped.append("stage5")
        return None

    assemble = _import_assemble()
    if assemble is None:
        logger.warning("Stage 5: assemble not importable — skipping")
        stages_skipped.append("stage5")
        return None

    try:
        success = assemble(output_dir)
        inject_dir = os.path.join(output_dir, "inject")
        if success:
            logger.info("Stage 5: Assembly complete → %s", inject_dir)
            stages_completed.append("stage5")
            return inject_dir if os.path.isdir(inject_dir) else None
        else:
            logger.error("Stage 5: assemble returned False")
            stages_failed.append("stage5")
            return None
    except Exception as exc:
        logger.error("Stage 5 error: %s\n%s", exc, traceback.format_exc())
        stages_failed.append("stage5")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_single_project_pipeline(
    repo_path: str,
    output_dir: str,
    adapter=None,
    router=None,
    config: PipelineConfig | None = None,
) -> PipelineResult:
    """运行单项目完整提取管线（确定性部分）。

    Stage 1/2/3/4 在 OpenClaw 中由 SKILL.md 驱动，不在此处调用。
    此函数编排：
      Stage 0  (extract_repo_facts)
      Brick injection (optional)
      Stage 1.5 (agentic, optional)
      Stage 3.5 (validate + confidence + DSD)
      Stage 4.5 (knowledge_compiler)
      Stage 5  (assemble)

    Args:
        repo_path: 本地 repo 路径（已 clone）。
        output_dir: 提取输出目录（soul/, artifacts/ 将在此目录下）。
        adapter:  LLMAdapter 实例；None = 跳过 Stage 1.5。
        router:   CapabilityRouter 实例；None = 自动构建。
        config:   PipelineConfig；None = 使用默认值。

    Returns:
        PipelineResult 汇总。
    """
    if config is None:
        config = PipelineConfig()

    repo_path = os.path.abspath(repo_path)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=== Phase Runner: start ===")
    logger.info("  repo_path  = %s", repo_path)
    logger.info("  output_dir = %s", output_dir)

    stages_completed: list[str] = []
    stages_skipped: list[str] = []
    stages_failed: list[str] = []

    # ---- Stage 0: extract_repo_facts ----
    _run_stage0(repo_path, output_dir, config, stages_completed, stages_skipped, stages_failed)

    # ---- Brick injection ----
    bricks_loaded = _run_brick_injection(
        output_dir, config, stages_completed, stages_skipped, stages_failed
    )

    # ---- Stage 1.5: Agentic Exploration (optional) ----
    _run_stage15(
        repo_path,
        output_dir,
        adapter,
        router,
        config,
        stages_completed,
        stages_skipped,
        stages_failed,
    )

    # ---- Stage 3.5: Validation + Confidence + DSD ----
    validation_passed, dsd_report_dict, tagged_cards = _run_stage35(
        output_dir, config, stages_completed, stages_skipped, stages_failed
    )

    # Stage 3.5 failure blocks Stage 4.5 — but only if we have no Stage 0 data
    if "stage3.5_validate" in stages_failed:
        if "stage0" in stages_completed:
            logger.info(
                "Stage 3.5 validation failed but Stage 0 data available — proceeding in degraded mode"
            )
            # Skip Knowledge Compiler (needs cards) but try assembly
            stages_skipped.append("stage4.5")
        else:
            logger.warning("Stage 3.5 validation failed — skipping Stage 4.5 (Knowledge Compiler)")
            stages_skipped.append("stage4.5")
            stages_skipped.append("stage5")
            inject_dir = None
    else:
        # ---- Stage 4.5: Knowledge Compiler ----
        _run_stage45(output_dir, config, stages_completed, stages_skipped, stages_failed)

        # ---- Stage 5: Assemble ----
        inject_dir = _run_stage5(
            output_dir, config, stages_completed, stages_skipped, stages_failed
        )

    total_cards = len(tagged_cards)

    logger.info("=== Phase Runner: done ===")
    logger.info("  completed=%s", stages_completed)
    logger.info("  skipped=%s", stages_skipped)
    logger.info("  failed=%s", stages_failed)

    return PipelineResult(
        stages_completed=stages_completed,
        stages_skipped=stages_skipped,
        stages_failed=stages_failed,
        output_dir=output_dir,
        inject_dir=inject_dir,
        dsd_report=dsd_report_dict,
        total_cards=total_cards,
        total_bricks_loaded=bricks_loaded,
    )


# ---------------------------------------------------------------------------
# CLI entry point (for direct invocation)
# ---------------------------------------------------------------------------


def _cli():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Doramagic Phase Runner — single-project extraction pipeline"
    )
    parser.add_argument("--repo-path", required=True, help="Local path to cloned repo")
    parser.add_argument(
        "--output-dir", required=True, help="Output directory (soul/, artifacts/ etc.)"
    )
    parser.add_argument(
        "--bricks-dir",
        default=None,
        help="Domain bricks directory (default: explicit path or DORAMAGIC_BRICKS_DIR)",
    )
    parser.add_argument(
        "--knowledge-budget",
        type=int,
        default=1800,
        help="Token budget for Knowledge Compiler (default: 1800)",
    )
    parser.add_argument(
        "--skip-stage15", action="store_true", help="Disable Stage 1.5 agentic exploration"
    )
    parser.add_argument("--skip-dsd", action="store_true", help="Disable DSD checks")
    parser.add_argument("--skip-bricks", action="store_true", help="Disable brick injection")
    parser.add_argument("--skip-assembly", action="store_true", help="Skip Stage 5 assembly")
    args = parser.parse_args()

    cfg = PipelineConfig(
        enable_stage15=not args.skip_stage15,
        enable_bricks=not args.skip_bricks,
        enable_dsd=not args.skip_dsd,
        bricks_dir=args.bricks_dir,
        knowledge_budget=args.knowledge_budget,
        skip_assembly=args.skip_assembly,
    )

    result = run_single_project_pipeline(
        repo_path=args.repo_path,
        output_dir=args.output_dir,
        adapter=None,  # CLI mode: no LLM adapter
        router=None,
        config=cfg,
    )

    print("\n=== Phase Runner Result ===")
    print(f"completed : {result.stages_completed}")
    print(f"skipped   : {result.stages_skipped}")
    print(f"failed    : {result.stages_failed}")
    print(f"output_dir: {result.output_dir}")
    print(f"inject_dir: {result.inject_dir}")
    print(f"total_cards: {result.total_cards}")
    print(f"bricks_loaded: {result.total_bricks_loaded}")
    if result.dsd_report:
        print(f"dsd_status: {result.dsd_report.get('overall_status')}")

    sys.exit(1 if result.stages_failed else 0)


if __name__ == "__main__":
    _cli()
