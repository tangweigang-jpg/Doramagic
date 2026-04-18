"""Phase 2: Constraints — generates field group D.

Produces:
  D. Constraints: constraints[] — filtered to severity fatal/critical/high,
     with bilingual summaries and evidence_url constructed from commit hash.

SOP references: §1.3D
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any

from doramagic_web_publisher.errors import PhaseParsingError
from doramagic_web_publisher.phases.base import Phase
from doramagic_web_publisher.runtime.models import PhaseContext, PhaseResult
from doramagic_web_publisher.runtime.tool_use import ToolUseExecutor

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)

_SEVERITY_FILTER = {"fatal", "critical", "high"}

_CONSTRAINT_ITEM_SCHEMA = {
    "type": "object",
    "required": [
        "constraint_id",
        "severity",
        "type",
        "when",
        "action",
        "consequence",
        "summary",
        "summary_en",
        "evidence_url",
        "evidence_locator",
        "machine_checkable",
        "confidence",
        "is_cross_project",
        "source_blueprint_id",
    ],
    "properties": {
        "constraint_id": {
            "type": "string",
            "description": "Unique constraint ID e.g. 'finance-C-042'",
        },
        "severity": {
            "type": "string",
            "enum": ["fatal", "critical", "high"],
        },
        "type": {
            "type": "string",
            "enum": ["RC", "B", "BA", "M", "T", "DK"],
            "description": (
                "Constraint type: RC=Regulatory/Compliance, B=Business, "
                "BA=Best-practice-by-analogy, M=Mathematical, T=Technical, DK=Domain-Knowledge"
            ),
        },
        "when": {
            "type": "string",
            "description": "Trigger condition (English)",
        },
        "action": {
            "type": "string",
            "description": "Required/forbidden behavior (English)",
        },
        "consequence": {
            "type": "string",
            "description": "Consequence description (English)",
        },
        "summary": {
            "type": "string",
            "description": "Chinese plain-language summary ≤80 chars. Format: 如果{触发}，{后果}。正确做法：{行为}。",  # noqa: E501
            "maxLength": 80,
        },
        "summary_en": {
            "type": "string",
            "description": (
                "English plain-language summary ≤160 chars. "
                "Format: If {trigger}, {consequence}. Correct approach: {action}."
            ),
            "maxLength": 160,
        },
        "evidence_url": {
            "type": ["string", "null"],
            "description": "GitHub permalink (full commit hash). Null if locator cannot be parsed.",
        },
        "evidence_locator": {
            "type": "string",
            "description": "Source code locator e.g. 'src/factor.py:L89'",
        },
        "machine_checkable": {
            "type": "boolean",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "is_cross_project": {
            "type": "boolean",
        },
        "source_blueprint_id": {
            "type": ["string", "null"],
            "description": "Required when is_cross_project=true",
        },
    },
    "additionalProperties": False,
}

# Max constraints per batch to avoid token limit issues
# MiniMax-M2.7-highspeed hits max_tokens=8192 with 20 constraints; 10 is safe
_BATCH_SIZE = 10


def _build_evidence_url(repo: str, commit: str, locator: str) -> str | None:
    """Build a GitHub permalink from repo + commit + locator.

    Args:
        repo: GitHub owner/repo e.g. 'zvtvz/zvt'
        commit: 40-char commit hash
        locator: Source locator e.g. 'src/zvt/factors/factor.py:L89' or 'src/file.py:107'

    Returns:
        GitHub permalink or None if cannot parse.
    """
    if not repo or not commit or not locator:
        return None

    # Extract path and line number from locator
    # Formats: "path/to/file.py:L89" or "path/to/file.py:89" or "path/to/file.py:107-108"
    m = re.match(r"^([^:]+):L?(\d+)", locator)
    if not m:
        return None

    path = m.group(1).strip()
    line = m.group(2)

    # Normalize path (remove leading /)
    path = path.lstrip("/")

    return f"https://github.com/{repo}/blob/{commit}/{path}#L{line}"


def _extract_constraint_fields(raw: dict) -> dict:
    """Normalize a raw JSONL constraint to the fields needed by the prompt.

    Handles the actual constraint schema from LATEST.jsonl which uses:
    - raw.id → constraint_id
    - raw.core.when, raw.core.action, raw.core.consequence.description
    - raw.confidence.score → confidence
    - raw.confidence.evidence_refs[] → evidence_refs
    - raw.machine_checkable → machine_checkable
    - raw.applies_to, raw.scope → for is_cross_project detection
    - raw.constraint_kind → type mapping
    """
    # Extract core fields
    core = raw.get("core", {})
    consequence = core.get("consequence", {})
    if isinstance(consequence, dict):
        consequence_text = consequence.get("description", "")
    else:
        consequence_text = str(consequence)

    # Evidence refs
    confidence_obj = raw.get("confidence", {})
    confidence_score = confidence_obj.get("score", 0.8) if isinstance(confidence_obj, dict) else 0.8
    evidence_refs = (
        confidence_obj.get("evidence_refs", []) if isinstance(confidence_obj, dict) else []
    )

    # Extract first locator
    locator = ""
    for ref in evidence_refs:
        if isinstance(ref, dict) and ref.get("locator"):
            locator = ref["locator"]
            break

    # Constraint type mapping
    ck = raw.get("constraint_kind", "")
    type_map = {
        "domain_rule": "B",
        "regulatory": "RC",
        "mathematical": "M",
        "technical": "T",
        "best_practice": "BA",
    }
    con_type = type_map.get(ck, "B")
    # Also check tags
    tags = raw.get("tags", [])
    if "RC" in tags or "regulatory" in tags:
        con_type = "RC"

    # Check cross-project:
    # A constraint is cross-project ONLY if derived_from.blueprint_id points to a DIFFERENT one.
    # Constraints with applies_to.blueprint_ids == [this_blueprint] are NOT cross-project.
    derived = raw.get("derived_from")
    is_cross_project = bool(derived and isinstance(derived, dict) and derived.get("blueprint_id"))

    # Build action text: combine modality + action
    action_text = core.get("action", "")
    modality = core.get("modality", "")
    if (
        modality
        and action_text
        and not action_text.lower().startswith(("must", "should", "do not", "never", "always"))
    ):
        action_text = f"{modality} {action_text}"

    source_bp_id = None
    if is_cross_project and derived and isinstance(derived, dict):
        source_bp_id = derived.get("blueprint_id")

    return {
        "constraint_id": raw.get("id", ""),
        "severity": raw.get("severity", ""),
        "type": con_type,
        "when": core.get("when", ""),
        "action": action_text,
        "consequence": consequence_text,
        "evidence_locator": locator,
        "machine_checkable": raw.get("machine_checkable", False),
        "confidence": confidence_score,
        "is_cross_project": bool(is_cross_project),
        "source_blueprint_id": source_bp_id,
        "_has_evidence": bool(locator),
    }


class ConstraintsPhase(Phase):
    """Phase 2: Generate D (constraints) field group."""

    def __init__(self, include_high: bool = False) -> None:
        """Initialize ConstraintsPhase.

        Args:
            include_high: If True, include 'high' severity constraints in addition
                          to 'fatal' and 'critical'. Default False (only fatal+critical).
        """
        super().__init__()
        self.include_high = include_high

    @property
    def name(self) -> str:
        return "constraints"

    def submit_tool_schema(self) -> dict[str, Any]:
        """JSON Schema for submit_constraints_fields tool."""
        return {
            "name": "submit_constraints_fields",
            "description": (
                "Submit the processed constraints for the Crystal Package. "
                "Only include constraints with severity fatal, critical, or high "
                "that have evidence_refs. Generate bilingual summaries. "
                "Build evidence_url from commit hash + locator."
            ),
            "parameters": {
                "type": "object",
                "required": ["constraints"],
                "properties": {
                    "constraints": {
                        "type": "array",
                        "description": "Filtered and enriched constraint list. ≥1 required.",
                        "minItems": 1,
                        "items": _CONSTRAINT_ITEM_SCHEMA,
                    }
                },
                "additionalProperties": False,
            },
        }

    def _filter_constraints(self, ctx: PhaseContext) -> list[dict]:
        """Filter constraints to severity fatal/critical/high with evidence refs.

        Returns normalized constraint dicts ready for the prompt.
        Always includes at least all fatal constraints (TRUST-FATAL gate requirement).
        """
        result = []
        for raw in ctx.constraints:
            sev = raw.get("severity", "")
            if sev not in _SEVERITY_FILTER:
                continue

            normalized = _extract_constraint_fields(raw)
            # For TRUST-FATAL compliance, always include fatal constraints
            # For others, require evidence locator (SOP §1.3D filter rule)
            if sev == "fatal" or normalized.get("_has_evidence"):
                result.append(normalized)

        logger.info(
            "ConstraintsPhase: filtered %d/%d constraints (fatal=%d, others_with_evidence=%d)",
            len(result),
            len(ctx.constraints),
            sum(1 for r in result if r["severity"] == "fatal"),
            sum(1 for r in result if r["severity"] != "fatal"),
        )
        return result

    def build_prompt(self, ctx: PhaseContext, batch: list[dict] | None = None) -> str:
        """Build the Phase 2 constraints prompt.

        Args:
            ctx: PhaseContext with manifest and constraints.
            batch: Specific batch of normalized constraints to process.
                   If None, uses all filtered constraints.
        """
        manifest = ctx.manifest
        repo = manifest.blueprint_source  # e.g. "zvtvz/zvt"
        commit = manifest.blueprint_commit  # 40-char hash

        if batch is None:
            batch = self._filter_constraints(ctx)

        # Build evidence URLs for the prompt
        constraints_for_prompt = []
        for c in batch:
            evidence_url = _build_evidence_url(repo, commit, c.get("evidence_locator", ""))
            c_copy = {k: v for k, v in c.items() if not k.startswith("_")}
            c_copy["evidence_url_prebuilt"] = evidence_url
            constraints_for_prompt.append(c_copy)

        constraints_json = json.dumps(constraints_for_prompt, ensure_ascii=False, indent=2)

        rerun_section = self._format_rerun_errors(ctx)

        _summary_fmt_cn = "如果{触发条件}，{后果}。正确做法：{行为}。"
        _summary_fmt_en = (
            "If {simplified trigger}, {simplified consequence}. "
            "Correct approach: {simplified action}."
        )
        _example_en = (
            "Using 365 days to annualize volatility underestimates it by 22.7%. "
            "Correct: Use 242 trading days for A-shares."
        )
        _keep_fields = (
            "constraint_id, severity, type, when, action, consequence, "
            "evidence_locator, machine_checkable, confidence, "
            "is_cross_project, source_blueprint_id"
        )
        prompt = f"""You are a Doramagic constraint processor. Your task is to generate
Web-displayable constraint entries by calling `submit_constraints_fields`.

## Task

For each constraint below, generate:
1. **summary** (Chinese, ≤80 chars): "{_summary_fmt_cn}"
2. **summary_en** (English, ≤160 chars): "{_summary_fmt_en}"
3. **evidence_url**: Use the pre-built URL in `evidence_url_prebuilt` field (or null if empty)

## Summary Format Rules (SOP §1.3D)

**Chinese format**: 如果{{简化的触发条件}}，{{简化的后果}}。正确做法：{{简化的行为}}。
- Maximum 80 Chinese characters
- No technical jargon (translate code variable names to plain language)
- Include at least 1 specific number if the constraint has one

**English format**: If {{trigger}}, {{consequence}}. Correct approach: {{action}}.
- Maximum 160 characters
- Plain language, no code syntax

**Examples from SOP**:
  when: "When annualizing A-share strategy returns"
  action: "MUST use sqrt(242) instead of sqrt(365)"
  consequence: "Volatility underestimated by 22.7%"

  summary_en: "{_example_en}"
  summary: "如果年化A股波动率时用365天，会低估22.7%。正确做法：用242交易日。"

## evidence_url

Use the `evidence_url_prebuilt` value from each constraint. If it's None/null, output null.

## Cross-Project Rules

- If `is_cross_project=true`, keep `source_blueprint_id` non-empty.
- If `is_cross_project=false`, set `source_blueprint_id=null`.

## Repository Info

- GitHub repo: {repo}
- Commit hash: {commit}

## Constraints to Process

{constraints_json}

{rerun_section}

## Instructions

Call `submit_constraints_fields` with a `constraints` array. For EACH constraint above:
- Keep all original fields ({_keep_fields})
- Add: summary (Chinese ≤80 chars), summary_en (English ≤160 chars)
- Set evidence_url from evidence_url_prebuilt (or null)

IMPORTANT:
- At least 1 constraint with severity=fatal MUST be included (TRUST-FATAL gate)
- summary must be ≤80 chars (Chinese)
- summary_en must be ≤160 chars (English)
- If is_cross_project=true, source_blueprint_id must be non-empty
"""
        return prompt

    def parse_result(self, args: dict[str, Any]) -> PhaseResult:
        """Validate and parse the submit_constraints_fields tool arguments."""
        errors: list[str] = []

        constraints = args.get("constraints", [])

        if len(constraints) < 1:
            errors.append("constraints array must have ≥1 item")

        # Check for at least 1 fatal (TRUST-FATAL gate)
        has_fatal = any(c.get("severity") == "fatal" for c in constraints)
        if not has_fatal:
            errors.append("TRUST-FATAL: at least 1 constraint with severity=fatal required")

        for i, c in enumerate(constraints):
            # summary length — auto-truncate if slightly over (LLM often overshoots by a few chars)
            summary = c.get("summary", "") or ""
            if len(summary) > 80:
                # Truncate at last sentence boundary within limit, or hard truncate
                truncated = summary[:80]
                # Try to truncate at last Chinese sentence-ending punctuation
                for punct in ("。", "！", "？", "；"):
                    last_pos = truncated.rfind(punct)
                    if last_pos > 40:  # keep at least 40 chars
                        truncated = truncated[: last_pos + 1]
                        break
                else:
                    # Hard truncate at exactly 80 chars (no ellipsis to avoid exceeding limit)
                    truncated = truncated[:80]
                logger.warning(
                    "constraints[%d].summary truncated from %d to %d chars",
                    i,
                    len(summary),
                    len(truncated),
                )
                c["summary"] = truncated

            # summary_en length — auto-truncate if slightly over
            summary_en = c.get("summary_en", "") or ""
            if len(summary_en) > 160:
                truncated_en = summary_en[:160]
                # Try to truncate at last sentence-ending punctuation
                for punct in (". ", "! ", "? "):
                    last_pos = truncated_en.rfind(punct)
                    if last_pos > 80:
                        truncated_en = truncated_en[: last_pos + 1]
                        break
                else:
                    truncated_en = truncated_en.rstrip()
                logger.warning(
                    "constraints[%d].summary_en truncated from %d to %d chars",
                    i,
                    len(summary_en),
                    len(truncated_en),
                )
                c["summary_en"] = truncated_en

            # evidence_url format (if non-null must be HTTPS + github.com)
            ev_url = c.get("evidence_url")
            if ev_url is not None and not (
                str(ev_url).startswith("https://") and "github.com" in str(ev_url)
            ):
                errors.append(
                    f"constraints[{i}].evidence_url={ev_url!r} must be HTTPS github.com URL or null"
                )

            # cross-project consistency
            # If LLM set is_cross_project=true but source_blueprint_id is empty,
            # auto-correct to is_cross_project=false (safe: we pre-computed this)
            if c.get("is_cross_project") and not c.get("source_blueprint_id"):
                logger.warning(
                    "constraints[%d]: auto-correcting is_cross_project=true→false "
                    "(source_blueprint_id is empty; this is a same-project constraint)",
                    i,
                )
                c["is_cross_project"] = False

        if errors:
            raise PhaseParsingError("constraints", errors)

        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields={"constraints": constraints},
        )

    def _get_active_severities(self) -> set[str]:
        """Return the set of severities to include based on include_high flag."""
        if self.include_high:
            return {"fatal", "critical", "high"}
        return {"fatal", "critical"}

    def _run_single_batch(
        self,
        ctx: PhaseContext,
        batch: list[dict],
        batch_num: int,
        total_batches: int,
        model_id: str,
        adapter: LLMAdapter,
    ) -> list[dict] | None:
        """Process a single batch of constraints via LLM.

        Returns list of processed constraints, or None on failure (non-fatal error).
        """
        import time

        tool_def = self._make_tool_definition()
        system_prompt = (
            "You are a constraint processor for Doramagic crystal packages. "
            "Generate bilingual plain-language summaries for technical constraints. "
            "Always call submit_constraints_fields with the complete processed list. "
            "Follow summary length limits strictly (Chinese ≤80 chars, English ≤160 chars). "
            "Preserve all original constraint fields."
        )

        severity_label = batch[0]["severity"] if batch else "unknown"
        logger.info(
            "batch %d/%d: severity=%s, %d constraints, starting MiniMax call",
            batch_num,
            total_batches,
            severity_label,
            len(batch),
        )

        user_message = self.build_prompt(ctx, batch=batch)

        executor = ToolUseExecutor(
            adapter=adapter,
            model_id=model_id,
            system_prompt=system_prompt,
            tools=[tool_def],
            submit_tool_name="submit_constraints_fields",
            max_iter=3,
            temperature=0.1,
            max_tokens=8192,
        )

        start_time = time.time()
        try:
            result = executor.run(user_message)
        except Exception as exc:
            elapsed = time.time() - start_time
            logger.error(
                "batch %d/%d failed after %.1fs: %s",
                batch_num,
                total_batches,
                elapsed,
                exc,
            )
            return None

        elapsed = time.time() - start_time

        if result.submitted_args is None:
            logger.error(
                "batch %d/%d: submit_constraints_fields was never called (%.1fs)",
                batch_num,
                total_batches,
                elapsed,
            )
            return None

        try:
            parsed = self.parse_result(result.submitted_args)
            processed = parsed.fields["constraints"]
        except Exception as exc:
            logger.error(
                "batch %d/%d: parse_result failed: %s",
                batch_num,
                total_batches,
                exc,
            )
            return None

        logger.info(
            "batch %d/%d done in %.1fs, %d summaries generated",
            batch_num,
            total_batches,
            elapsed,
            len(processed),
        )
        return processed

    def run(self, ctx: PhaseContext, adapter: LLMAdapter) -> PhaseResult:
        """Execute constraints phase with multi-batch merging.

        Default mode: processes fatal+critical constraints in batches of _BATCH_SIZE.
        With include_high=True: also processes high severity constraints.

        Each batch is processed independently — if a batch fails, it is logged but
        other batches continue. Results from all successful batches are merged.
        """
        logger.info(
            "ConstraintsPhase.run(): blueprint_id=%s, total_raw=%d, include_high=%s",
            ctx.manifest.blueprint_id,
            len(ctx.constraints),
            self.include_high,
        )

        # Filter all eligible constraints (fatal+critical+high depending on flag)
        # _filter_constraints already filters to _SEVERITY_FILTER = {fatal,critical,high}
        all_filtered = self._filter_constraints(ctx)

        if not all_filtered:
            # No eligible constraints — check if any fatal exists
            fatal_count = sum(1 for c in ctx.constraints if c.get("severity") == "fatal")
            if fatal_count > 0:
                # Use first fatal even without evidence
                first_fatal = None
                for raw in ctx.constraints:
                    if raw.get("severity") == "fatal":
                        first_fatal = _extract_constraint_fields(raw)
                        break
                if first_fatal:
                    all_filtered = [first_fatal]
                    logger.warning(
                        "ConstraintsPhase: no constraints with evidence_refs; "
                        "using first fatal constraint without evidence for TRUST-FATAL compliance"
                    )

        if not all_filtered:
            from doramagic_web_publisher.errors import PhaseError

            raise PhaseError(
                "constraints", "No eligible constraints found (need severity∈{fatal,critical,high})"
            )

        # Split into active severities: default=fatal+critical, include_high=all three
        active_severities = self._get_active_severities()
        eligible = [c for c in all_filtered if c["severity"] in active_severities]

        # Always ensure fatal constraints are included (TRUST-FATAL gate)
        fatal_only = [c for c in all_filtered if c["severity"] == "fatal"]
        if not eligible and fatal_only:
            eligible = fatal_only
            logger.warning("ConstraintsPhase: no fatal/critical constraints — using fatals only")

        if not eligible:
            eligible = all_filtered  # fallback to all filtered

        # Sort by severity priority (fatal → critical → high) then by evidence_locator for stability
        _severity_order = {"fatal": 0, "critical": 1, "high": 2}
        eligible.sort(
            key=lambda c: (_severity_order.get(c["severity"], 9), c.get("evidence_locator", ""))
        )

        # Split into batches of _BATCH_SIZE
        batches: list[list[dict]] = []
        for i in range(0, len(eligible), _BATCH_SIZE):
            batches.append(eligible[i : i + _BATCH_SIZE])

        total_batches = len(batches)
        logger.info(
            "ConstraintsPhase: %d eligible constraints → %d batches "
            "(active_severities=%s, include_high=%s)",
            len(eligible),
            total_batches,
            sorted(active_severities),
            self.include_high,
        )

        model_id = os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed")

        # Process all batches, accumulate results
        all_processed: list[dict] = []
        failed_batches: list[int] = []

        for batch_idx, batch in enumerate(batches, start=1):
            processed = self._run_single_batch(
                ctx=ctx,
                batch=batch,
                batch_num=batch_idx,
                total_batches=total_batches,
                model_id=model_id,
                adapter=adapter,
            )
            if processed is None:
                failed_batches.append(batch_idx)
                logger.error(
                    "batch %d/%d failed — continuing with remaining batches",
                    batch_idx,
                    total_batches,
                )
            else:
                all_processed.extend(processed)

        if failed_batches:
            logger.warning(
                "ConstraintsPhase: %d/%d batches failed: %s",
                len(failed_batches),
                total_batches,
                failed_batches,
            )

        # Validate merged result has at least 1 fatal (TRUST-FATAL gate)
        if not all_processed:
            from doramagic_web_publisher.errors import PhaseError

            raise PhaseError("constraints", "All batches failed — no constraints processed")

        has_fatal = any(c.get("severity") == "fatal" for c in all_processed)
        if not has_fatal:
            from doramagic_web_publisher.errors import PhaseError

            raise PhaseError(
                "constraints", "TRUST-FATAL: at least 1 fatal constraint required but none produced"
            )

        logger.info(
            "ConstraintsPhase.run(): merged %d constraints from %d batches (%d batches failed)",
            len(all_processed),
            total_batches,
            len(failed_batches),
        )

        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields={"constraints": all_processed},
        )

    def mock_result(self) -> PhaseResult:
        """Return placeholder PhaseResult for --mock mode."""
        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields={
                "constraints": [
                    {
                        "constraint_id": "finance-C-001",
                        "severity": "fatal",
                        "type": "M",
                        "when": "When annualizing A-share strategy returns",
                        "action": "MUST use sqrt(242) instead of sqrt(365)",
                        "consequence": "Volatility underestimated by 22.7%",
                        "summary": (
                            "如果年化A股波动率时用365天，会低估22.7%。正确做法：用242交易日。"
                        ),
                        "summary_en": (
                            "Using 365 days to annualize volatility underestimates it by 22.7%. "
                            "Correct: Use 242 trading days for A-shares."
                        ),
                        "evidence_url": (
                            "https://github.com/zvtvz/zvt/blob/"
                            "f971f00c2181bc7d7fb7987a7875d4ec5960881a/"
                            "src/zvt/factors/factor_cls.py#L89"
                        ),
                        "evidence_locator": "src/zvt/factors/factor_cls.py:L89",
                        "machine_checkable": True,
                        "confidence": 0.95,
                        "is_cross_project": False,
                        "source_blueprint_id": None,
                    }
                ]
            },
        )
