"""Phase 3: FAQ — generates field group F.

Produces:
  F. FAQ: faqs[] — 5-8 bilingual Q&A pairs covering the 5 mandatory categories
     defined in SOP §1.3F.

SOP references: §1.3F
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from doramagic_web_publisher.errors import PhaseParsingError
from doramagic_web_publisher.phases.base import Phase
from doramagic_web_publisher.runtime.models import PhaseContext, PhaseResult
from doramagic_web_publisher.runtime.tool_use import ToolUseExecutor

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)

# SOP §1.3F category keywords for variety classification.
# Each category maps to 3-5 trigger keywords (Chinese + English, case-insensitive).
# The "domain" category is a catch-all fallback.
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "core": [
        "能做什么",
        "帮我做",
        "能帮",
        "做什么",
        "作用",
        "what does",
        "can help",
        "what can",
        "what will",
        "capable",
    ],
    "pitfall": [
        "失败",
        "错误",
        "坑",
        "常见问题",
        "常见错误",
        "风险",
        "注意",
        "fail",
        "error",
        "pitfall",
        "common mistake",
        "avoid",
        "wrong",
        "risk",
    ],
    "host": [
        "支持",
        "哪些 ai",
        "哪些ai",
        "哪个 ai",
        "哪个ai",
        "claude",
        "gpt",
        "openclaw",
        "claude_code",
        "宿主",
        "环境",
        "support",
        "which ai",
        "which model",
        "host",
        "environment",
        "compatible",
    ],
    "inputs": [
        "需要",
        "准备",
        "输入",
        "前提",
        "条件",
        "准备什么",
        "需要什么",
        "require",
        "prepare",
        "input",
        "need",
        "prerequisite",
        "setup",
    ],
    "domain": [],  # catch-all: domain-specific or CTA questions
}


def _classify_faq(question: str, answer: str) -> str:
    """Classify a FAQ entry into one of the 5 SOP §1.3F categories.

    Searches both question and answer for category keywords.
    Returns the best matching category name; falls back to 'domain'.
    """
    combined = (question + " " + answer).lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if category == "domain":
            continue  # domain is fallback only
        for kw in keywords:
            if kw.lower() in combined:
                return category
    return "domain"


def _validate_category_coverage(faqs: list[dict]) -> None:
    """Validate that FAQs cover at least 4 of the 5 SOP §1.3F categories.

    Args:
        faqs: List of FAQ dicts with 'question', 'answer' fields.

    Raises:
        PhaseParsingError: If fewer than 4 categories are covered.
    """
    from doramagic_web_publisher.errors import PhaseParsingError

    covered: set[str] = set()
    for faq in faqs:
        question = faq.get("question", "") or ""
        answer = faq.get("answer", "") or ""
        category = _classify_faq(question, answer)
        covered.add(category)

    category_count = len(covered)
    logger.info(
        "FaqPhase: FAQ variety check — %d categories covered: %s",
        category_count,
        sorted(covered),
    )

    if category_count < 4:
        raise PhaseParsingError(
            "faq",
            [
                f"GEO-FAQ-VARIETY: FAQ variety: only {category_count} categories covered "
                f"(need ≥4). Covered: {sorted(covered)}. "
                "Must cover at least 4 of: core, pitfall, host, inputs, domain."
            ],
        )


_FAQ_ITEM_SCHEMA = {
    "type": "object",
    "required": ["question", "answer", "question_en", "answer_en"],
    "properties": {
        "question": {
            "type": "string",
            "description": "Chinese question in user's natural phrasing (as in Perplexity/ChatGPT)",
        },
        "answer": {
            "type": "string",
            "description": (
                "Chinese answer, 80-120 chars. "
                "Conclusion first, then supplement. Contains ≥1 specific number."
            ),
            "minLength": 30,
            "maxLength": 200,
        },
        "question_en": {
            "type": "string",
            "description": "English question",
        },
        "answer_en": {
            "type": "string",
            "description": "English answer, 120-200 chars.",
            "minLength": 50,
            "maxLength": 400,
        },
    },
    "additionalProperties": False,
}


class FaqPhase(Phase):
    """Phase 3: Generate F (FAQ) field group."""

    @property
    def name(self) -> str:
        return "faq"

    def submit_tool_schema(self) -> dict[str, Any]:
        """JSON Schema for submit_faq_fields tool."""
        return {
            "name": "submit_faq_fields",
            "description": (
                "Submit the generated FAQ entries for the Crystal Package. "
                "Must include 5-8 bilingual Q&A pairs covering the 5 mandatory categories: "
                "1) core capability, 2) pitfall value, 3) applicable scope, "
                "4) input requirements, 5) domain-specific. "
                "At least one answer must contain 'doramagic.ai' (zero-click protection). "
                "Last FAQ answer must contain 'doramagic.ai'."
            ),
            "parameters": {
                "type": "object",
                "required": ["faqs"],
                "properties": {
                    "faqs": {
                        "type": "array",
                        "description": (
                            "5-8 FAQ entries covering the 5 mandatory categories from SOP §1.3F"
                        ),
                        "minItems": 5,
                        "maxItems": 8,
                        "items": _FAQ_ITEM_SCHEMA,
                    }
                },
                "additionalProperties": False,
            },
        }

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the Phase 3 FAQ prompt."""
        crystal_ir = ctx.crystal_ir or {}
        content_fields = ctx.phase_fields("content")
        constraints_fields = ctx.phase_fields("constraints")

        # Crystal IR fields
        user_intent = crystal_ir.get("user_intent", {})
        user_intent_desc = user_intent.get("description", "")
        target_market = user_intent.get("target_market", "")
        stages = crystal_ir.get("stages", [])
        # host_adapters lives under harness.host_adapters in the IR YAML
        _harness = crystal_ir.get("harness", {}) or {}
        _ha_raw = _harness.get("host_adapters", crystal_ir.get("host_adapters", {}))
        if isinstance(_ha_raw, dict):
            host_adapters = list(_ha_raw.keys())
        elif isinstance(_ha_raw, list):
            host_adapters = [ha.get("host", ha) if isinstance(ha, dict) else ha for ha in _ha_raw]
        else:
            host_adapters = []
        context_acquisition = crystal_ir.get("context_acquisition", {})
        required_inputs_ir = context_acquisition.get("required_inputs", [])

        # Content phase outputs
        slug = content_fields.get("slug", "")
        crystal_name = content_fields.get("name", "")
        crystal_name_en = content_fields.get("name_en", "")

        # Constraints - top 3 fatal for FAQ #2 (pitfall value)
        all_constraints = constraints_fields.get("constraints", [])
        fatal_constraints = [c for c in all_constraints if c.get("severity") == "fatal"]
        top_3_fatal = fatal_constraints[:3]
        top_3_fatal_json = json.dumps(top_3_fatal, ensure_ascii=False, indent=2)

        # Blueprint info
        blueprint = ctx.blueprint or {}
        applicability = blueprint.get("applicability", {})
        bp_description = applicability.get("description", "")

        # Host names for FAQ #3 — host_adapters is already a list of host name strings
        hosts_str = " / ".join(h for h in host_adapters if h)

        # Stages summary for FAQ #1
        stages_summary = ""
        if stages:
            stage_names = [s.get("name", "") or s.get("id", "") for s in stages[:5]]
            stages_summary = "、".join(n for n in stage_names if n)

        # Required inputs for FAQ #4
        inputs_summary = ""
        if required_inputs_ir:
            input_names = [inp.get("name", "") for inp in required_inputs_ir[:5]]
            inputs_summary = "、".join(n for n in input_names if n)

        # Constraint count
        total_constraints = len(all_constraints)
        fatal_count = len(fatal_constraints)

        rerun_section = self._format_rerun_errors(ctx)

        prompt = f"""You are a Doramagic FAQ generator. Generate 5-8 bilingual FAQ entries
for a Crystal Package by calling `submit_faq_fields`.

## Crystal Information

- **Name (ZH)**: {crystal_name}
- **Name (EN)**: {crystal_name_en}
- **Slug**: {slug}
- **User Intent**: {user_intent_desc}
- **Target Market**: {target_market}
- **Total Constraints**: {total_constraints} (Fatal: {fatal_count})
- **Host Environments**: {hosts_str}
- **Blueprint Applicability**: {bp_description}

## Stages (for FAQ #1)

{stages_summary if stages_summary else "(Use user_intent description)"}

## Required Inputs (for FAQ #4)

{inputs_summary if inputs_summary else "None (no user inputs required)"}

## Top 3 Fatal Constraints (for FAQ #2)

{top_3_fatal_json}

---

## Generation Rules (SOP §1.3F)

### 5 Mandatory Question Categories

You MUST cover at least 4 of these 5 categories:

| # | Category | Chinese question template | Source |
|---|----------|--------------------------|--------|
| 1 | Core capability | "这个配方能帮我做什么？" | user_intent + stages |
| 2 | Pitfall value | "使用时有哪些常见失败？" | fatal constraints top 3 |
| 3 | Applicable scope | "这个配方支持哪些 AI 环境？" | host_adapters |
| 4 | Input requirements | "使用这个配方需要准备什么？" | required_inputs |
| 5 | Domain-specific | Domain-specific question | blueprint applicability |

### Question Format
- Write as real user natural language queries (Perplexity/ChatGPT style)
- ✅ "用 Claude 做 A 股 MACD 回测需要什么？"
- ❌ "MACD 回测配方的输入参数有哪些？" (too formal/technical)

### Answer Format
- Chinese: 80-120 chars. Conclusion first, then details. Include ≥1 specific number.
- English: 120-200 chars. Same structure. Include ≥1 specific number.
- Be direct — no preamble

### Critical Rules
- **Total**: 5-8 FAQ entries
- **CTA Rule (MANDATORY)**: At least 1 answer MUST contain "doramagic.ai"
- The LAST FAQ answer MUST contain "doramagic.ai/r/{slug}"
  (zero-click protection, GEO-FAQ-CTA gate)
- Keep answers concise but include concrete numbers

### CTA Format
The last FAQ should be about "how to get the full recipe" and answer:
- ZH: "完整配方请访问 doramagic.ai/r/{slug}，直接下载 seed.md 在 1 分钟内加载到 {hosts_str}。"
- EN: "Get the full recipe at doramagic.ai/r/{slug}.
  Download seed.md and load it into {hosts_str} in under 1 minute."

{rerun_section}

---

## Task

Generate 5-8 FAQ entries covering the 5 categories (must cover ≥4).
Call `submit_faq_fields` with the complete faqs array.

Remember:
- Chinese answers: 30-200 chars (ideally 80-120)
- English answers: 50-400 chars (ideally 120-200)
- Last answer MUST contain "doramagic.ai/r/{slug}"
- Include ≥1 specific number in each answer
"""
        return prompt

    def parse_result(self, args: dict[str, Any]) -> PhaseResult:
        """Validate and parse the submit_faq_fields tool arguments."""
        errors: list[str] = []

        faqs = args.get("faqs", [])

        # Pre-filter: remove FAQs with empty answer fields (LLM occasionally omits answer_en)
        valid_faqs = []
        for faq in faqs:
            answer = faq.get("answer", "") or ""
            answer_en = faq.get("answer_en", "") or ""
            if not answer_en and answer:
                # Auto-generate a minimal English answer from the Chinese answer
                # (better than failing — the LLM dropped it by accident)
                logger.warning(
                    "FaqPhase.parse_result: FAQ '%s' has empty answer_en — using placeholder",
                    faq.get("question", "")[:40],
                )
                faq["answer_en"] = f"See Chinese version for details. {answer[:100]}"
            valid_faqs.append(faq)
        faqs = valid_faqs
        args["faqs"] = faqs

        # Count: 5-8
        if not (5 <= len(faqs) <= 8):
            errors.append(f"faqs must have 5-8 items, got {len(faqs)}")

        # Check each FAQ
        for i, faq in enumerate(faqs):
            question = faq.get("question", "") or ""
            answer = faq.get("answer", "") or ""
            question_en = faq.get("question_en", "") or ""
            answer_en = faq.get("answer_en", "") or ""

            if not question:
                errors.append(f"faqs[{i}].question is empty")
            if not question_en:
                errors.append(f"faqs[{i}].question_en is empty")

            # Chinese answer length: 30-200
            if len(answer) < 30:
                errors.append(f"faqs[{i}].answer is {len(answer)} chars < 30 (minimum)")
            if len(answer) > 200:
                errors.append(f"faqs[{i}].answer is {len(answer)} chars > 200 (maximum)")

            # English answer length: 50-400
            if len(answer_en) < 50:
                errors.append(f"faqs[{i}].answer_en is {len(answer_en)} chars < 50 (minimum)")
            if len(answer_en) > 400:
                errors.append(f"faqs[{i}].answer_en is {len(answer_en)} chars > 400 (maximum)")

        # GEO-FAQ-CTA: at least 1 answer contains "doramagic.ai"
        has_cta = any(
            "doramagic.ai" in (faq.get("answer", "") or "")
            or "doramagic.ai" in (faq.get("answer_en", "") or "")
            for faq in faqs
        )
        if not has_cta:
            errors.append("GEO-FAQ-CTA: at least 1 FAQ answer must contain 'doramagic.ai'")

        if errors:
            raise PhaseParsingError("faq", errors)

        # GEO-FAQ-VARIETY: must cover ≥4 of the 5 SOP §1.3F categories
        # Note: this check is done AFTER other validations so errors are clear
        _validate_category_coverage(faqs)

        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields={"faqs": faqs},
        )

    def run(self, ctx: PhaseContext, adapter: LLMAdapter) -> PhaseResult:
        """Execute FAQ phase: build prompt → tool_use loop → parse_result."""
        logger.info("FaqPhase.run(): blueprint_id=%s", ctx.manifest.blueprint_id)

        user_message = self.build_prompt(ctx)
        tool_def = self._make_tool_definition()

        system_prompt = (
            "You are a precise FAQ generator for Doramagic crystal packages. "
            "Always call submit_faq_fields with 5-8 bilingual Q&A pairs. "
            "Follow all format rules strictly. "
            "Critical rules: "
            "(1) At least 1 answer must contain 'doramagic.ai'; "
            "(2) Chinese answers 30-200 chars; "
            "(3) English answers 50-400 chars; "
            "(4) Cover at least 4 of the 5 mandatory question categories; "
            "(5) Include specific numbers in answers."
        )

        model_id = os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed")

        executor = ToolUseExecutor(
            adapter=adapter,
            model_id=model_id,
            system_prompt=system_prompt,
            tools=[tool_def],
            submit_tool_name="submit_faq_fields",
            max_iter=3,
            temperature=0.1,
            max_tokens=4096,
        )

        logger.info("FaqPhase.run(): starting tool_use loop (model=%s)", model_id)
        result = executor.run(user_message)

        logger.info(
            "FaqPhase.run(): done (iterations=%d, prompt_tokens=%d, "
            "client_input_chars=%d, client_output_chars=%d)",
            result.iterations,
            result.llm_response.prompt_tokens,
            result.client_input_chars,
            result.client_output_chars,
        )

        if result.submitted_args is None:
            from doramagic_web_publisher.errors import ToolUseError

            raise ToolUseError("submit_faq_fields tool was never called", result.iterations)

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
        slug = "mock-crystal-placeholder"
        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields={
                "faqs": [
                    {
                        "question": "这个配方能帮我做什么？",
                        "answer": (
                            "这个配方帮你完成模拟任务，覆盖 42 条防坑规则，"
                            "支持 openclaw 和 claude_code 两个宿主环境。"
                        ),
                        "question_en": "What can this recipe do for me?",
                        "answer_en": (
                            "This recipe helps you complete simulated tasks, "
                            "covering 42 pitfall rules "
                            "across openclaw and claude_code host environments."
                        ),
                    },
                    {
                        "question": "使用时有哪些常见失败？",
                        "answer": (
                            "最常见的失败是年化波动率计算用了 365 天而非 242 交易日，"
                            "导致低估 22.7%。"
                        ),
                        "question_en": "What are the common failure modes?",
                        "answer_en": (
                            "The most common failure is using 365 days instead of 242 trading days "
                            "for annualizing volatility, causing a 22.7% underestimation."
                        ),
                    },
                    {
                        "question": "这个配方支持哪些 AI 环境？",
                        "answer": "支持 openclaw 和 claude_code，两个宿主均已通过官方自测。",
                        "question_en": "Which AI environments does this recipe support?",
                        "answer_en": "Supports openclaw and claude_code, both officially verified.",
                    },
                    {
                        "question": "使用这个配方需要准备什么？",
                        "answer": (
                            "无需额外输入，直接加载配方文件即可。seed.md 文件约 50KB，下载后即用。"
                        ),
                        "question_en": "What do I need to use this recipe?",
                        "answer_en": (
                            "No additional inputs required. Load the recipe file directly. "
                            "The seed.md is approximately 50KB and ready to use."
                        ),
                    },
                    {
                        "question": "如何获取完整配方？",
                        "answer": (
                            f"完整配方请访问 doramagic.ai/r/{slug}，"
                            "可直接下载 seed.md 并在 1 分钟内加载到宿主 AI。"
                        ),
                        "question_en": "How do I get the full recipe?",
                        "answer_en": (
                            f"Get the full recipe at doramagic.ai/r/{slug}. "
                            "Download seed.md and load it into your AI host in under 1 minute."
                        ),
                    },
                ]
            },
        )
