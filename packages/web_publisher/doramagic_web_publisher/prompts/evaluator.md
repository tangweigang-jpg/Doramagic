# Phase 4: Evaluator Generation Prompt Template

<!-- REPLACE_WITH: Full Phase 4 prompt for generating field groups H, I, J, K, L.

When implementing, this template should be rendered with:
  - content_fields: dict (slug, name, definition, description from Phase 1)
  - constraints_fields: dict (constraints[] from Phase 2)
  - faq_fields: dict (faqs[] from Phase 3)
  - crystal_ir: dict (host_adapters, context_acquisition, output_validator, sample_run)
  - seed_content: str (full PRODUCTION.seed.md for placeholder extraction)
  - creator_proof: list (from QA manifest, loaded into ctx before pipeline)
  - blueprint_applicability: dict (for applicable/inapplicable scenarios)
  - blueprint_out_of_scope: dict (for inapplicable scenarios)

Group H — Consumer evaluation data:
  - sample_output: prefer trace_url from creator_proof[0], fallback to text_preview
  - applicable_scenarios: ≥2 from blueprint applicability, user-persona lead
  - inapplicable_scenarios: ≥2 from out_of_scope (MANDATORY, honest boundary)
  - host_adapters: direct from crystal_ir.host_adapters, omit unsupported hosts

Group I — Variable injection:
  - required_inputs: MUST match {{placeholders}} in seed.md EXACTLY
  - Parse seed.md with regex /\{\{\s*([a-z][a-z0-9_]{0,31})\s*\}\}/g
  - Exclude placeholders in code blocks, inline code, HTML comments, frontmatter
  - name format: lowercase snake_case only

Group J — Trust data:
  - creator_proof: passthrough from ctx.creator_proof (loaded from QA manifest)
  - model_compatibility: derive from creator_proof, mark recommended model
  - tier: default "standard"; use "verified" only if ≥3 proofs + ≥2 hosts

Group K — Discovery metadata:
  - tier: agent MUST NOT submit "battle_tested" (TIER-VALID gate)
  - is_flagship: first crystal for a blueprint is true; presets only on flagship
  - parent_flagship_slug: null for flagship, required for non-flagship

Group L — SEO/GEO:
  - core_keywords: 5-10 real user queries, ≥2 Chinese, ≥2 English
    Format: actual search queries, not keyword phrases
    ✅ "用 Claude 做 A 股 MACD 回测需要什么？"
    ❌ "MACD 回测 A 股"
  - og_image_fields: headline starts with action verb, both stats contain numbers
    stat_primary: "{constraintCount} 条防坑规则"
    stat_secondary: "{fatalCount} 条 FATAL · {sourceFileCount} 处源码"
-->

REPLACE_WITH: Phase 4 (evaluator) prompt template.

This file will contain the full LLM prompt for generating:
- sample_output, applicable_scenarios, inapplicable_scenarios, host_adapters (group H)
- required_inputs[] matched to seed.md placeholders (group I)
- creator_proof[], model_compatibility[] (group J)
- tier, is_flagship, parent_flagship_slug, presets (group K)
- core_keywords, meta_title_suffix, og_image_fields (group L)

Reference: SOP §1.3H, §1.3I, §1.3J, §1.3K, §1.3L
