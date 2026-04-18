"""Phase 4: Evaluator — generates field groups H + I + J + K + L.

Produces:
  H. Consumer evaluation data: sample_output, applicable_scenarios,
     inapplicable_scenarios, host_adapters
  I. Variable injection: required_inputs[]
  J. Trust data: creator_proof[], model_compatibility[]
  K. Discovery metadata: tier, is_flagship, parent_flagship_slug, presets
  L. SEO/GEO fields: core_keywords, meta_title_suffix, og_image_fields

This phase depends on prior phase outputs (content, constraints, faq)
and ctx.creator_proof loaded from QA manifest.

SOP references: §1.3H, §1.3I, §1.3J, §1.3K, §1.3L
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from doramagic_web_publisher.errors import PhaseParsingError
from doramagic_web_publisher.phases.base import Phase
from doramagic_web_publisher.runtime.models import PhaseContext, PhaseResult
from doramagic_web_publisher.runtime.placeholder import parse_seed_placeholders
from doramagic_web_publisher.runtime.tool_use import ToolUseExecutor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMAdapter


class EvaluatorPhase(Phase):
    """Phase 4: Generate H/I/J/K/L field groups."""

    @property
    def name(self) -> str:
        return "evaluator"

    def submit_tool_schema(self) -> dict[str, Any]:
        """JSON Schema for submit_evaluator_fields tool.

        Covers SOP §1.2 field groups H (partial), I, J (partial), K, L (partial).

        Fields handled statically by Assembler (NOT submitted by LLM):
          - host_adapters       → Assembler injects from Crystal IR
          - creator_proof       → Assembler pass-through from ctx.creator_proof
          - sample_output       → Assembler derives from creator_proof[0]
          - og_image_fields.stat_primary/stat_primary_en/stat_secondary/stat_secondary_en
                                → Assembler computes from constraint counts
        """
        return {
            "name": "submit_evaluator_fields",
            "description": (
                "Submit consumer evaluation, variable injection, trust data, "
                "discovery metadata, and SEO/GEO fields for the Crystal Package. "
                "NOTE: host_adapters, creator_proof, sample_output, and og stat fields "
                "are injected automatically — do NOT include them here. "
                "Call once all field groups are ready."
            ),
            "parameters": {
                "type": "object",
                "required": [
                    "applicable_scenarios",
                    "inapplicable_scenarios",
                    "required_inputs",
                    "model_compatibility",
                    "tier",
                    "is_flagship",
                    "parent_flagship_slug",
                    "core_keywords",
                    "og_image_fields",
                ],
                "properties": {
                    # ---- H. Consumer evaluation data ----
                    # (partial — sample_output and host_adapters injected by Assembler)
                    "applicable_scenarios": {
                        "type": "array",
                        "description": "≥2 scenarios where this recipe applies",
                        "minItems": 2,
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "required": ["text", "text_en"],
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Chinese, 15-40 chars",
                                    "minLength": 15,
                                    "maxLength": 40,
                                },
                                "text_en": {
                                    "type": "string",
                                    "description": "English, 30-80 chars",
                                    "minLength": 30,
                                    "maxLength": 80,
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                    "inapplicable_scenarios": {
                        "type": "array",
                        "description": (
                            "≥2 scenarios where this recipe does NOT apply (honest boundary)"
                        ),
                        "minItems": 2,
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "required": ["text", "text_en"],
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "minLength": 15,
                                    "maxLength": 40,
                                },
                                "text_en": {
                                    "type": "string",
                                    "minLength": 30,
                                    "maxLength": 80,
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                    # ---- I. Variable injection ----
                    "required_inputs": {
                        "type": "array",
                        "description": "Must exactly match {{placeholders}} found in seed.md",
                        "items": {
                            "type": "object",
                            "required": [
                                "name",
                                "type",
                                "required",
                                "default",
                                "enum_options",
                                "hint",
                                "hint_en",
                                "example",
                            ],
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "pattern": "^[a-z][a-z0-9_]{0,31}$",
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["string", "number", "date", "enum", "multiline"],
                                },
                                "required": {"type": "boolean"},
                                "default": {"type": ["string", "null"]},
                                "enum_options": {
                                    "type": ["array", "null"],
                                    "items": {"type": "string"},
                                },
                                "hint": {
                                    "type": "string",
                                    "description": "Chinese hint ≤30 chars",
                                    "maxLength": 30,
                                },
                                "hint_en": {
                                    "type": "string",
                                    "maxLength": 80,
                                },
                                "example": {"type": ["string", "null"]},
                            },
                            "additionalProperties": False,
                        },
                    },
                    # ---- J. Trust data (partial — creator_proof injected by Assembler) ----
                    "model_compatibility": {
                        "type": "array",
                        "description": "≥1 entry; model values must be unique",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["model", "status", "note", "note_en"],
                            "properties": {
                                "model": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "recommended",
                                        "compatible",
                                        "partial",
                                        "not_recommended",
                                    ],
                                },
                                "note": {"type": ["string", "null"]},
                                "note_en": {"type": ["string", "null"]},
                            },
                            "additionalProperties": False,
                        },
                    },
                    # ---- K. Discovery metadata ----
                    "tier": {
                        "type": "string",
                        "enum": ["standard", "verified"],
                        "description": "Default: 'standard'. Never set to 'battle_tested'.",
                    },
                    "is_flagship": {"type": "boolean"},
                    "parent_flagship_slug": {
                        "type": ["string", "null"],
                        "description": (
                            "null when is_flagship=true; required when is_flagship=false"
                        ),
                    },
                    "presets": {
                        "type": ["array", "null"],
                        "description": "Only non-null when is_flagship=true",
                    },
                    # ---- L. SEO/GEO fields (og stat fields injected by Assembler) ----
                    "core_keywords": {
                        "type": "array",
                        "description": (
                            "5-10 long-tail keywords as real user queries. ≥2 Chinese, ≥2 English."
                        ),
                        "minItems": 5,
                        "maxItems": 10,
                        "items": {"type": "string"},
                    },
                    "meta_title_suffix": {
                        "type": ["string", "null"],
                        "description": "Usually null (defaults to 'Doramagic')",
                        "maxLength": 20,
                    },
                    "og_image_fields": {
                        "type": "object",
                        "required": [
                            "headline",
                            "headline_en",
                        ],
                        "description": (
                            "OG image fields. Provide ONLY headline and headline_en — "
                            "stat_primary/stat_secondary are computed from constraint counts."
                        ),
                        "properties": {
                            "headline": {
                                "type": "string",
                                "description": (
                                    "Chinese OG headline ≤24 chars. "
                                    "Starts with action verb. No '配方'."
                                ),
                                "maxLength": 24,
                            },
                            "headline_en": {
                                "type": "string",
                                "description": "English OG headline ≤40 chars.",
                                "maxLength": 40,
                            },
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        }

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the Phase 4 evaluator prompt.

        Reads:
        - ctx.crystal_ir for user_intent, host_adapters, context_acquisition, output_validator
        - ctx.blueprint for applicability, out_of_scope, known_use_cases
        - ctx.creator_proof (stub, to be passed through)
        - ctx.results["content"] for name/definition
        - ctx.seed_content for placeholder extraction (S_seed)
        """
        crystal_ir = ctx.crystal_ir or {}
        blueprint = ctx.blueprint or {}
        content_fields = ctx.phase_fields("content")
        constraints_fields = ctx.phase_fields("constraints")

        # --- Crystal IR fields ---
        user_intent = crystal_ir.get("user_intent", {})
        user_intent_desc = user_intent.get("description", "")
        target_market = user_intent.get("target_market", "")
        context_acquisition = crystal_ir.get("context_acquisition", {})
        ir_required_inputs = context_acquisition.get("required_inputs", [])
        output_validator = crystal_ir.get("output_validator", {})
        # Crystal IR has host_adapters under harness.host_adapters (dict keyed by host name)
        # or possibly at the top level — check both locations
        harness = crystal_ir.get("harness", {}) or {}
        ir_host_adapters_raw = harness.get("host_adapters", crystal_ir.get("host_adapters", {}))
        valid_host_set = {"openclaw", "claude_code", "codex_cli", "gemini_cli"}
        # Crystal IR host_adapters can be a dict keyed by host name, or a list
        if isinstance(ir_host_adapters_raw, dict):
            # Convert dict form to list form: {openclaw: {...}} → [{host: openclaw, ...}]
            ir_host_adapters = [
                {"host": host_name, **{k: v for k, v in spec.items() if k != "host"}}
                for host_name, spec in ir_host_adapters_raw.items()
                if host_name in valid_host_set
            ]
        else:
            ir_host_adapters = (
                ir_host_adapters_raw if isinstance(ir_host_adapters_raw, list) else []
            )

        # --- Blueprint fields ---
        applicability = blueprint.get("applicability", {})
        bp_description = applicability.get("description", "")
        out_of_scope = blueprint.get("out_of_scope", [])
        known_use_cases = blueprint.get("known_use_cases", {})
        if isinstance(known_use_cases, list):
            # known_use_cases is a list of use case objects — extract negative_keywords from each
            negative_keywords = []
            for uc in known_use_cases:
                if isinstance(uc, dict):
                    negative_keywords.extend(uc.get("negative_keywords", []))
        else:
            negative_keywords = (
                known_use_cases.get("negative_keywords", [])
                if isinstance(known_use_cases, dict)
                else []
            )

        # --- Content phase outputs ---
        crystal_name = content_fields.get("name", "")
        crystal_name_en = content_fields.get("name_en", "")
        definition = content_fields.get("definition", "")

        # --- Constraint stats ---
        all_constraints = constraints_fields.get("constraints", [])
        total_constraints = len(all_constraints)
        fatal_constraints = sum(1 for c in all_constraints if c.get("severity") == "fatal")
        source_files = set()
        for c in all_constraints:
            loc = c.get("evidence_locator", "")
            if loc and ":" in loc:
                source_files.add(loc.split(":")[0])

        # --- Placeholder extraction (SOP §2.4.1) ---
        parsed = parse_seed_placeholders(ctx.seed_content)
        s_seed = sorted(parsed.valid)
        s_seed_invalid = sorted(parsed.invalid)

        s_seed_hint = (
            f"S_seed (valid placeholders found in seed.md) = {json.dumps(s_seed)}\n"
            f"Invalid placeholders (naming violations) = {json.dumps(s_seed_invalid)}\n\n"
            "CRITICAL CONSTRAINT: required_inputs[] MUST contain EXACTLY the entries whose "
            f"name matches S_seed = {json.dumps(s_seed)}. "
            "If S_seed is empty, required_inputs MUST be []. "
            "Do NOT add extra inputs or omit any that appear in S_seed."
        )

        # --- Manifest ---
        manifest = ctx.manifest
        blueprint_id = manifest.blueprint_id

        # --- Rerun errors ---
        rerun_section = self._format_rerun_errors(ctx)

        prompt = f"""You are a Doramagic crystal evaluator. Your task: generate field groups
H (partial), I, J (partial), K, L (partial) for a Crystal Package JSON
by calling `submit_evaluator_fields`.

## Crystal Summary

- **Crystal name (ZH)**: {crystal_name}
- **Crystal name (EN)**: {crystal_name_en}
- **Definition**: {definition}
- **Blueprint ID**: {blueprint_id}
- **User intent**: {user_intent_desc}
- **Target market**: {target_market}

## Constraint Statistics (reference only)
- Total constraints published: {total_constraints}
- Fatal constraints: {fatal_constraints}
- Unique source files: {len(source_files)}

## Crystal IR — Context Acquisition (required_inputs from IR)

{json.dumps(ir_required_inputs, ensure_ascii=False, indent=2)}

## Placeholder Alignment (SOP §2.4.1) — MANDATORY CHECK

{s_seed_hint}

## Crystal IR — Host Adapters (reference only — injected automatically by Assembler)

{json.dumps(ir_host_adapters, ensure_ascii=False, indent=2)}

## Crystal IR — Output Validator

{json.dumps(output_validator, ensure_ascii=False, indent=2)}

## Blueprint — Applicability

{bp_description}

## Blueprint — Out of Scope / Negative Keywords

Out of scope: {json.dumps(out_of_scope, ensure_ascii=False)}
Negative keywords: {json.dumps(negative_keywords, ensure_ascii=False)}

---

## Generation Rules (SOP §1.3 H/I/J/K/L)

### IMPORTANT: Fields injected automatically — do NOT include them
- **host_adapters** — injected from Crystal IR by Assembler
- **creator_proof** — pass-through from QA manifest by Assembler
- **sample_output** — derived from creator_proof[0] by Assembler
- **og_image_fields.stat_primary/stat_primary_en/stat_secondary/stat_secondary_en**
  — computed from constraint counts by Assembler

### H. applicable_scenarios / inapplicable_scenarios
- applicable_scenarios: ≥2, ≤6 items. Each: text=15-40 Chinese chars, text_en=30-80 English chars
  - Focus on concrete user types and situations from blueprint applicability
- inapplicable_scenarios: ≥2, ≤6 items. Same format. From out_of_scope + negative_keywords.
  - Be honest about boundaries — this is a trust signal

### I. required_inputs
- MUST exactly match S_seed above.
- If S_seed = [] → required_inputs = []
- For each name in S_seed: provide type, required, default, enum_options,
  hint (≤30 ZH chars), hint_en (≤80 chars), example

### J. model_compatibility
- One entry per unique model used for testing
- The verified model is "MiniMax-M2.7-highspeed" → status="recommended"
- Add "claude-sonnet-4-6" as "compatible" (commonly used for this type of task)
- model values must be unique

### K. tier
- First publish default → tier = "standard"

### K. is_flagship / parent_flagship_slug
- is_flagship = true (this is the first and only crystal for this blueprint)
- parent_flagship_slug = null (because is_flagship=true)

### K. presets
- null for now (no presets defined yet)

### L. core_keywords (SOP §1.3L)
- 5-10 items. ≥2 Chinese, ≥2 English
- Format as real user questions/queries (Perplexity/ChatGPT style)
- Include at least 1 with a host name (Claude / OpenClaw)
- Examples:
  - Chinese: "用 Claude 做 A 股 MACD 回测需要什么？"
  - English: "how to backtest MACD strategy on a-shares with claude"

### L. og_image_fields (SOP §1.3L) — ONLY provide headline and headline_en
- headline: action verb start, ≤24 Chinese chars, NO "配方"
  - Example: "回测 A 股 MACD 金叉策略"
- headline_en: ≤40 chars
  - Example: "Backtest MACD Crossover on A-Shares"
- DO NOT include stat_primary, stat_primary_en, stat_secondary, stat_secondary_en
  — these are auto-computed.

### L. meta_title_suffix
- null (use default "Doramagic")

{rerun_section}

---

## Task

Call `submit_evaluator_fields` with all fields above completed. Be precise:
- required_inputs MUST match S_seed exactly (currently S_seed={{json.dumps(s_seed)}})
- og_image_fields: ONLY provide headline and headline_en
- applicable/inapplicable_scenarios must each have ≥2 items
- core_keywords must have ≥2 Chinese + ≥2 English real-user queries
"""
        return prompt

    def parse_result(self, args: dict[str, Any], ctx: PhaseContext | None = None) -> PhaseResult:
        """Validate and parse the submit_evaluator_fields tool arguments.

        Validates key rules (SOP §2.4 + §1.3 H-L).

        Fields validated here (LLM-generated):
          1. tier ∈ {standard, verified} (default: standard)
          2. is_flagship=true → parent_flagship_slug=None
          3. is_flagship=false → parent_flagship_slug non-empty
          4. presets non-null → is_flagship=true
          5. presets[].variable_overrides keys ∈ required_inputs[].name
          6. applicable_scenarios 2-6 items
          7. inapplicable_scenarios 2-6 items
          8. model_compatibility ≥1, model unique
          9. core_keywords 5-10 items, ≥2 Chinese + ≥2 English
          10. og_image_fields.headline/headline_en non-empty
          11. placeholder alignment: S_seed == set(required_inputs.name)

        Fields injected by Assembler (NOT validated here):
          - host_adapters       (from Crystal IR)
          - creator_proof       (pass-through from ctx.creator_proof)
          - sample_output       (derived from creator_proof[0])
          - og_image_fields.stat_primary/stat_secondary (computed from constraint counts)
        """

        errors: list[str] = []

        # --- 1. tier ---
        tier = args.get("tier", "")
        if tier not in {"standard", "verified"}:
            errors.append(f"tier must be 'standard' or 'verified', got {tier!r}")

        # --- 2+3. is_flagship / parent_flagship_slug ---
        is_flagship = args.get("is_flagship")
        parent_slug = args.get("parent_flagship_slug")
        if is_flagship is True and parent_slug is not None:
            errors.append("is_flagship=true requires parent_flagship_slug=null")
        if is_flagship is False and not parent_slug:
            errors.append("is_flagship=false requires non-empty parent_flagship_slug")

        # --- 4. presets only allowed when is_flagship=true ---
        presets = args.get("presets")
        if presets and not is_flagship:
            errors.append("presets may only be non-empty when is_flagship=true")

        # --- 5. preset variable_overrides keys must be in required_inputs names ---
        required_inputs = args.get("required_inputs", [])
        input_names = {inp.get("name") for inp in required_inputs if inp.get("name")}
        if presets:
            for i, preset in enumerate(presets):
                overrides = preset.get("variable_overrides", {}) or {}
                for key in overrides:
                    if key not in input_names:
                        errors.append(
                            f"presets[{i}].variable_overrides key '{key}' "
                            f"not in required_inputs names: {sorted(input_names)}"
                        )

        # --- 6. applicable_scenarios 2-6 ---
        applicable = args.get("applicable_scenarios", [])
        if not (2 <= len(applicable) <= 6):
            errors.append(f"applicable_scenarios must have 2-6 items, got {len(applicable)}")

        # --- 7. inapplicable_scenarios 2-6 ---
        inapplicable = args.get("inapplicable_scenarios", [])
        if not (2 <= len(inapplicable) <= 6):
            errors.append(f"inapplicable_scenarios must have 2-6 items, got {len(inapplicable)}")

        # --- 8. model_compatibility ≥1, model unique ---
        model_compat = args.get("model_compatibility", [])
        if len(model_compat) < 1:
            errors.append("model_compatibility must have ≥1 entry")
        compat_models = [m.get("model") for m in model_compat]
        if len(compat_models) != len(set(compat_models)):
            errors.append("model_compatibility model values must be unique")

        # --- 9. core_keywords 5-10 items, ≥2 Chinese + ≥2 English ---
        core_keywords = args.get("core_keywords", [])
        if not (5 <= len(core_keywords) <= 10):
            errors.append(f"core_keywords must have 5-10 items, got {len(core_keywords)}")
        zh_kws = [k for k in core_keywords if any("\u4e00" <= c <= "\u9fff" for c in k)]
        en_kws = [k for k in core_keywords if not any("\u4e00" <= c <= "\u9fff" for c in k)]
        if len(zh_kws) < 2:
            errors.append(f"core_keywords needs ≥2 Chinese items, got {len(zh_kws)}")
        if len(en_kws) < 2:
            errors.append(f"core_keywords needs ≥2 English items, got {len(en_kws)}")

        # --- 10. og_image_fields: headline/headline_en non-empty ---
        # (stat fields are injected by Assembler)
        ogf = args.get("og_image_fields", {}) or {}
        for field in ("headline", "headline_en"):
            val = ogf.get(field, "")
            if not val:
                errors.append(f"og_image_fields.{field} must be non-empty")

        # --- 11. Placeholder alignment: S_seed == set(required_inputs.name) ---
        if ctx is not None and ctx.seed_content:
            parsed = parse_seed_placeholders(ctx.seed_content)
            s_seed = parsed.valid
            s_inputs = input_names
            missing_in_inputs = s_seed - s_inputs
            missing_in_seed = s_inputs - s_seed
            if parsed.invalid or missing_in_inputs or missing_in_seed:
                detail = []
                if missing_in_inputs:
                    detail.append(f"missing_in_inputs={sorted(missing_in_inputs)}")
                if missing_in_seed:
                    detail.append(f"missing_in_seed={sorted(missing_in_seed)}")
                if parsed.invalid:
                    detail.append(f"invalid_placeholders={sorted(parsed.invalid)}")
                errors.append("USER-INPUTS-MATCH: placeholder 不对齐 — " + "; ".join(detail))

        if errors:
            raise PhaseParsingError("evaluator", errors)

        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields=args,
        )

    def run(self, ctx: PhaseContext, adapter: LLMAdapter) -> PhaseResult:
        """Execute evaluator phase: build prompt → tool_use loop → parse_result."""
        logger.info("EvaluatorPhase.run(): blueprint_id=%s", ctx.manifest.blueprint_id)

        user_message = self.build_prompt(ctx)
        tool_def = self._make_tool_definition()

        system_prompt = (
            "You are a precise evaluator and SEO/GEO metadata generator "
            "for Doramagic crystal packages. "
            "Always call the required submit_evaluator_fields tool with exact values. "
            "Follow all format rules strictly. "
            "Do not ask clarifying questions — generate and submit. "
            "Pay special attention to: "
            "(1) required_inputs must exactly match the S_seed placeholder set; "
            "(2) creator_proof must include the stub entry unchanged; "
            "(3) og_image_fields must contain numbers in stat fields; "
            "(4) core_keywords must include ≥2 Chinese and ≥2 English real-user queries."
        )

        model_id = os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed")

        executor = ToolUseExecutor(
            adapter=adapter,
            model_id=model_id,
            system_prompt=system_prompt,
            tools=[tool_def],
            submit_tool_name="submit_evaluator_fields",
            max_iter=5,
            temperature=0.1,
            max_tokens=8192,
        )

        logger.info("EvaluatorPhase.run(): starting tool_use loop (model=%s)", model_id)
        result = executor.run(user_message)

        logger.info(
            "EvaluatorPhase.run(): done (iterations=%d, prompt_tokens=%d, completion_tokens=%d, "
            "client_input_chars=%d, client_output_chars=%d)",
            result.iterations,
            result.llm_response.prompt_tokens,
            result.llm_response.completion_tokens,
            result.client_input_chars,
            result.client_output_chars,
        )

        if result.submitted_args is None:
            from doramagic_web_publisher.errors import ToolUseError

            raise ToolUseError("submit_evaluator_fields tool was never called", result.iterations)

        phase_result = self.parse_result(result.submitted_args, ctx=ctx)
        phase_result.token_usage = {
            "prompt_tokens": result.llm_response.prompt_tokens,
            "completion_tokens": result.llm_response.completion_tokens,
            "client_input_chars": result.client_input_chars,
            "client_output_chars": result.client_output_chars,
        }
        phase_result.iterations = result.iterations
        return phase_result

    def mock_result(self) -> PhaseResult:
        """Return placeholder PhaseResult for --mock mode.

        Note: host_adapters, creator_proof, sample_output are injected by Assembler.
        This mock result only contains LLM-generated fields.
        og_image_fields contains only headline/headline_en; stat fields are computed by Assembler.
        """
        return PhaseResult(
            phase_name=self.name,
            success=True,
            fields={
                "applicable_scenarios": [
                    {
                        "text": "开发调试 web_publisher 流水线时",
                        "text_en": "When developing and debugging the web_publisher pipeline",
                    },
                    {
                        "text": "验证 Package JSON 组装逻辑时",
                        "text_en": "When validating Package JSON assembly logic",
                    },
                ],
                "inapplicable_scenarios": [
                    {
                        "text": "生产环境晶体发布时（需真实 LLM 输出）",
                        "text_en": (
                            "When publishing crystals in production (requires real LLM output)"
                        ),
                    },
                    {
                        "text": "需要真实蓝图内容的场景",
                        "text_en": "When real blueprint content is required",
                    },
                ],
                "required_inputs": [],
                "model_compatibility": [
                    {
                        "model": "claude-sonnet-4-6",
                        "status": "recommended",
                        "note": None,
                        "note_en": None,
                    }
                ],
                "tier": "standard",
                "is_flagship": True,
                "parent_flagship_slug": None,
                "presets": None,
                "core_keywords": [
                    "用 Claude 做模拟任务需要什么？",
                    "如何测试 web_publisher 流水线？",
                    "how to test web publisher pipeline with claude",
                    "mock crystal pipeline test",
                    "doramagic pipeline scaffold debug",
                ],
                "meta_title_suffix": None,
                "og_image_fields": {
                    "headline": "测试流水线骨架",
                    "headline_en": "Test Pipeline Scaffold",
                    # stat_primary/stat_secondary injected by Assembler — not here
                },
            },
        )
