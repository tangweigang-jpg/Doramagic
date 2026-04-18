"""Phase 1: Content — generates field groups A + E + G.

Produces:
  A. Basic identification: slug, name, name_en, definition, definition_en,
     description, description_en, category_slug, tags, version
  E. Known gaps: known_gaps[]
  G. Changelog: changelog, changelog_en, contributors

SOP references: §1.3A, §1.3E, §1.3G
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from doramagic_web_publisher.phases.base import Phase
from doramagic_web_publisher.runtime.models import PhaseContext, PhaseResult
from doramagic_web_publisher.runtime.tool_use import ToolUseExecutor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMAdapter


class ContentPhase(Phase):
    """Phase 1: Generate A + E + G field groups."""

    @property
    def name(self) -> str:
        return "content"

    def submit_tool_schema(self) -> dict[str, Any]:
        """JSON Schema for submit_content_fields tool.

        Covers SOP §1.2 field groups A, E, G.
        """
        return {
            "name": "submit_content_fields",
            "description": (
                "Submit the generated content fields for the Crystal Package. "
                "Call this once you have generated all required fields for groups A, E, and G."
            ),
            "parameters": {
                "type": "object",
                "required": [
                    "slug",
                    "name",
                    "name_en",
                    "definition",
                    "definition_en",
                    "description",
                    "description_en",
                    "category_slug",
                    "tags",
                    "version",
                    "known_gaps",
                    "changelog",
                    "changelog_en",
                    "contributors",
                ],
                "properties": {
                    # ---- A. Basic identification ----
                    "slug": {
                        "type": "string",
                        "description": (
                            "URL-safe permanent identifier. "
                            "Format: action-object-context, 3-6 words, lowercase, hyphens. "
                            "≤60 chars. Must NOT contain 'bp-' pattern. "
                            "Example: 'macd-backtest-a-shares'"
                        ),
                        "pattern": "^[a-z][a-z0-9-]{2,59}$",
                    },
                    "name": {
                        "type": "string",
                        "description": "Chinese name, task-oriented, 10-25 chars, must contain '配方'",  # noqa: E501
                        "minLength": 1,
                        "maxLength": 50,
                    },
                    "name_en": {
                        "type": "string",
                        "description": "English name, ≤60 chars, no 'Recipe' suffix",
                        "minLength": 1,
                        "maxLength": 100,
                    },
                    "definition": {
                        "type": "string",
                        "description": (
                            "One-sentence Chinese definition, 40-80 chars. "
                            "Template: '{配方名} 是一个帮你 {动作} 的 AI 任务配方，"
                            "覆盖 {N} 条防坑规则，适用于 {场景}。' "
                            "Must contain at least one number."
                        ),
                        "minLength": 40,
                        "maxLength": 200,
                    },
                    "definition_en": {
                        "type": "string",
                        "description": "English definition, 80-160 chars, same structure as Chinese",  # noqa: E501
                        "minLength": 80,
                        "maxLength": 400,
                    },
                    "description": {
                        "type": "string",
                        "description": (
                            "Detailed Chinese description (Markdown), 300-800 chars. "
                            "Structure: ## 这个配方帮你做什么 / ## 你需要准备什么 "
                            "/ ## 执行流程 / ## 适用场景. "
                            "Must end with 'doramagic.ai' or '完整配方请访问'"
                        ),
                        "minLength": 200,
                        "maxLength": 5000,
                    },
                    "description_en": {
                        "type": "string",
                        "description": "Detailed English description (Markdown), 500-1200 chars",
                        "minLength": 300,
                        "maxLength": 8000,
                    },
                    "category_slug": {
                        "type": "string",
                        "description": (
                            "Category slug as it exists in the DB "
                            "(e.g. 'finance', 'quantitative-trading')"
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3-8 tag slugs, must exist in DB tag table",
                        "minItems": 3,
                        "maxItems": 8,
                    },
                    "version": {
                        "type": "string",
                        "description": (
                            "Semantic version, format: vMAJOR.MINOR.PATCH. First publish: v1.0.0"
                        ),
                        "pattern": "^v\\d+\\.\\d+\\.\\d+$",
                    },
                    # ---- E. Known gaps ----
                    "known_gaps": {
                        "type": "array",
                        "description": (
                            "Known limitations from blueprint business_decisions "
                            "where known_gap=true. ≤10 items."
                        ),
                        "maxItems": 10,
                        "items": {
                            "type": "object",
                            "required": [
                                "description",
                                "description_en",
                                "severity",
                                "impact",
                                "impact_en",
                            ],
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": "Chinese description of the gap",
                                },
                                "description_en": {
                                    "type": "string",
                                    "description": "English description of the gap",
                                },
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "high"],
                                },
                                "impact": {
                                    "type": "string",
                                    "description": "Chinese impact description",
                                },
                                "impact_en": {
                                    "type": "string",
                                    "description": "English impact description",
                                },
                            },
                        },
                    },
                    # ---- G. Changelog ----
                    "changelog": {
                        "type": "string",
                        "description": (
                            "Chinese changelog for this version. "
                            "First publish: '首次发布。覆盖 {N} 条防坑规则，支持 {宿主列表}。'"
                        ),
                    },
                    "changelog_en": {
                        "type": "string",
                        "description": "English changelog",
                    },
                    "contributors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Contributor list. Always include '@doramagic-bot'.",
                        "minItems": 1,
                    },
                },
                "additionalProperties": False,
            },
        }

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the Phase 1 content prompt using real crystal IR, blueprint, and constraints."""

        # --- Extract data from crystal IR ---
        crystal_ir = ctx.crystal_ir or {}
        user_intent = crystal_ir.get("user_intent", {})
        user_intent_desc = user_intent.get("description", "")
        target_market = user_intent.get("target_market", "")
        crystal_name = crystal_ir.get("crystal_name", "")

        # --- Extract data from blueprint ---
        blueprint = ctx.blueprint or {}
        applicability = blueprint.get("applicability", {})
        bp_description = applicability.get("description", "")
        bp_task_type = applicability.get("task_type", "")
        bp_domain = applicability.get("domain", "")

        # --- Constraint counts ---
        total_constraints = len(ctx.constraints)
        fatal_constraints = sum(1 for c in ctx.constraints if c.get("severity") == "fatal")

        # --- Known gaps from blueprint ---
        known_gaps_raw: list[dict] = []
        for stage in blueprint.get("stages", []):
            for bd in stage.get("business_decisions", []):
                if bd.get("known_gap"):
                    known_gaps_raw.append(bd)
            for _ in stage.get("key_behaviors", []):
                pass  # not in this level
        # Also check top-level business_decisions if exists
        for bd in blueprint.get("business_decisions", []):
            if bd.get("known_gap"):
                known_gaps_raw.append(bd)

        # --- Manifest info ---
        manifest = ctx.manifest
        blueprint_source = manifest.blueprint_source  # "zvtvz/zvt"
        blueprint_commit = manifest.blueprint_commit
        blueprint_id = manifest.blueprint_id

        # --- Rerun errors ---
        rerun_section = self._format_rerun_errors(ctx)

        prompt = f"""You are a Doramagic crystal web-content generator.
Your job: generate Crystal Package JSON content fields via `submit_content_fields` tool.

## Crystal Information

**Crystal IR summary:**
- Crystal name: {crystal_name}
- User intent: {user_intent_desc}
- Target market: {target_market}

**Blueprint:**
- Blueprint ID: {blueprint_id}
- Source repo: {blueprint_source} (commit: {blueprint_commit[:12]}...)
- Domain: {bp_domain}
- Task type: {bp_task_type}
- Description: {bp_description}

**Constraint statistics:**
- Total constraints: {total_constraints}
- Fatal severity: {fatal_constraints}

## Generation Rules (SOP §1.3A)

### slug
- Format: action-object-context, 3-6 hyphen-separated words
- Lowercase letters and hyphens only, ≤60 chars
- Must start with a letter
- MUST NOT contain 'bp-' followed by digits (e.g. 'bp-009' is forbidden)
- MUST NOT have pure numeric segments (e.g. 'strategy-009' is forbidden)
- Good examples: 'macd-backtest-a-shares', 'zvt-factor-backtesting', 'a-share-quant-trading'

### name (Chinese)
- 10-25 chars, task-oriented, MUST contain '配方'
- Example: 'A股MACD金叉策略回测配方'

### name_en (English)
- ≤60 chars, NO 'Recipe' suffix
- Example: 'A-Share MACD Crossover Backtest'

### definition (Chinese)
- Exactly ONE sentence, 40-80 Chinese characters
- Template: '{{配方名}} 是一个帮你 {{动作}} 的 AI 任务配方，
  覆盖 {total_constraints} 条防坑规则，适用于 {{场景}}。'
- MUST contain at least one number (use {total_constraints})

### definition_en (English)
- 80-160 characters (NOT Chinese chars — ASCII/English characters)
- Same structure as Chinese definition, same number ({total_constraints})

### description (Chinese)
- 300-800 Chinese characters, Markdown format
- 4 sections exactly:
  ## 这个配方帮你做什么
  ## 你需要准备什么
  ## 执行流程
  ## 适用场景
- MUST end with: '完整配方请访问 doramagic.ai'

### description_en (English)
- 500-1200 characters, same 4-section structure in English

### category_slug
- Use: 'finance'

### tags
- 3-8 slugs relevant to this crystal (lowercase, hyphens)
- Examples: 'quantitative-trading', 'backtesting', 'macd', 'a-shares', 'python', 'zvt'

### version
- 'v1.0.0' (first publish)

### known_gaps
- Extract from blueprint known_gap entries (severity critical or high only)
- ≤10 items, user-facing language (not technical code)
- If none in blueprint, use []

### changelog / changelog_en
- Chinese: '首次发布。覆盖 {total_constraints} 条防坑规则，支持 openclaw / claude_code。'
- English: 'Initial release. Covers {total_constraints} pitfall rules.
  Supports openclaw / claude_code.'

### contributors
- Always include '@doramagic-bot'

{rerun_section}

## Task

Generate all fields above and call `submit_content_fields` with the complete result.
Be precise with character counts. The definition fields are GEO-critical — make them
specific and include the constraint count number.
"""
        return prompt

    def parse_result(self, args: dict[str, Any]) -> PhaseResult:
        """Validate and parse the submit_content_fields tool arguments."""
        import re as _re

        from doramagic_web_publisher.errors import WebPublisherError

        # Validate slug format
        slug = args.get("slug", "")
        if not _re.match(r"^[a-z][a-z0-9-]{2,59}$", slug):
            raise WebPublisherError(
                f"parse_result[content]: slug '{slug}' does not match /^[a-z][a-z0-9-]{{2,59}}$/"
            )
        if _re.search(r"bp-\d+", slug):
            raise WebPublisherError(
                f"parse_result[content]: slug '{slug}' contains forbidden 'bp-NNN' pattern"
            )

        # Validate definition lengths
        definition = args.get("definition", "")
        if not (40 <= len(definition) <= 200):
            logger.warning(
                "content parse_result: definition length %d is outside [40, 200]; proceeding",
                len(definition),
            )

        definition_en = args.get("definition_en", "")
        if not (80 <= len(definition_en) <= 400):
            logger.warning(
                "content parse_result: definition_en length %d is outside [80, 400]; proceeding",
                len(definition_en),
            )

        # Merge: real fields from LLM + mock fallbacks for fields not yet implemented
        mock = self.mock_result().fields
        merged = dict(mock)  # start with mock defaults
        merged.update(args)  # override with real LLM output

        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields=merged,
        )

    def run(self, ctx: PhaseContext, adapter: LLMAdapter) -> PhaseResult:
        """Execute content phase: build prompt → tool_use loop → parse_result."""
        logger.info(
            "ContentPhase.run(): building prompt for blueprint_id=%s", ctx.manifest.blueprint_id
        )

        user_message = self.build_prompt(ctx)
        tool_def = self._make_tool_definition()

        system_prompt = (
            "You are a precise content generator for Doramagic crystal packages. "
            "Always call the required tool with exact field values. "
            "Follow all format rules strictly. "
            "Do not ask clarifying questions — generate and submit."
        )

        executor = ToolUseExecutor(
            adapter=adapter,
            model_id=ctx.manifest.blueprint_id,  # will be overridden by calling context
            system_prompt=system_prompt,
            tools=[tool_def],
            submit_tool_name="submit_content_fields",
            max_iter=5,
            temperature=0.1,
            max_tokens=8192,
        )

        # We need the model_id from the adapter's context. Read from env or use default.
        import os as _os

        model_id = _os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed")

        executor._model_id = model_id

        logger.info("ContentPhase.run(): starting tool_use loop (model=%s)", model_id)
        result = executor.run(user_message)

        logger.info(
            "ContentPhase.run(): tool_use loop done "
            "(iterations=%d, token_usage=prompt=%d completion=%d)",
            result.iterations,
            result.llm_response.prompt_tokens,
            result.llm_response.completion_tokens,
        )

        if result.submitted_args is None:
            from doramagic_web_publisher.errors import ToolUseError

            raise ToolUseError("submit_content_fields tool was never called", result.iterations)

        phase_result = self.parse_result(result.submitted_args)
        phase_result.token_usage = {
            "prompt_tokens": result.llm_response.prompt_tokens,
            "completion_tokens": result.llm_response.completion_tokens,
            "client_input_chars": result.client_input_chars,
            "client_output_chars": result.client_output_chars,
        }
        phase_result.iterations = result.iterations
        return phase_result

    def mock_result(self) -> PhaseResult:
        """Return placeholder PhaseResult for --mock mode."""
        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields={
                "slug": "mock-crystal-placeholder",
                "name": "模拟配方（占位）",
                "name_en": "Mock Crystal Placeholder",
                "definition": (
                    "模拟配方是一个帮你测试流水线的 AI 任务配方，"
                    "覆盖 42 条防坑规则，适用于开发调试场景。"
                ),
                "definition_en": (
                    "Mock Crystal is an AI task recipe for testing the pipeline, "
                    "covering 42 pitfall rules for development and debugging scenarios."
                ),
                "description": (
                    "## 这个配方帮你做什么\n\n"
                    "这是一个用于测试 web_publisher 流水线的占位配方。\n\n"
                    "## 你需要准备什么\n\n"
                    "- 无需任何输入\n\n"
                    "## 执行流程\n\n"
                    "1. 初始化：加载占位数据\n"
                    "2. 运行：跑通流水线\n\n"
                    "## 适用场景\n\n"
                    "- ✅ 开发调试\n"
                    "- ❌ 生产发布\n\n"
                    "完整配方请访问 doramagic.ai"
                ),
                "description_en": (
                    "## What This Recipe Does\n\n"
                    "This is a placeholder recipe for testing the web_publisher pipeline. "
                    "It covers 42 pitfall rules for development and debugging. "
                    "Get the full recipe at doramagic.ai\n\n"
                    "## What You Need\n\n"
                    "- No inputs required\n\n"
                    "## Execution Flow\n\n"
                    "1. Init: load placeholder data\n"
                    "2. Run: execute pipeline\n"
                ),
                "category_slug": "finance",
                "tags": ["mock", "test", "pipeline"],
                "version": "v1.0.0",
                "known_gaps": [],
                "changelog": "首次发布。覆盖 42 条防坑规则，支持 openclaw / claude_code。",
                "changelog_en": (
                    "Initial release. Covers 42 pitfall rules. Supports openclaw / claude_code."
                ),
                "contributors": ["@doramagic-bot"],
            },
        )
