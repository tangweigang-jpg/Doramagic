# Phase 1: Content Generation Prompt Template

<!-- REPLACE_WITH: Full Phase 1 prompt for generating field groups A, E, G.

When implementing, this template should be rendered with:
  - crystal_ir: dict (user_intent, stages, context_acquisition, crystal_name, references)
  - blueprint: dict (applicability, business_decisions, known_gaps)
  - constraint_count: int (total constraints)
  - fatal_count: int (fatal constraints)
  - manifest: PublishManifest (blueprint_id, blueprint_source, blueprint_commit)

Key instructions to include in the final prompt:
1. slug rules (SOP §1.3A): action-object-context, 3-6 words, lowercase hyphens, ≤60 chars,
   must NOT contain 'bp-\d+' pattern, must NOT have pure numeric segments
2. name rules: Chinese 10-25 chars with '配方', English ≤60 chars no 'Recipe'
3. definition rules (GEO §1.3A):
   Template: '{配方名} 是一个帮你 {动作} 的 AI 任务配方，覆盖 {N} 条防坑规则，适用于 {场景}。'
   Chinese 40-80 chars, English 80-160 chars, must contain specific number
4. description rules: Chinese 300-800 chars, English 500-1200 chars,
   4-section Markdown structure, must end with 'doramagic.ai' or '完整配方请访问'
5. known_gaps: extract from blueprint business_decisions where known_gap=true,
   only severity critical/high, ≤10, user-facing language
6. changelog: first publish format, include constraint count and host list
7. Call submit_content_fields with ALL fields filled
-->

REPLACE_WITH: Phase 1 (content) prompt template.

This file will contain the full LLM prompt for generating:
- slug / name / name_en (group A identification)
- definition / definition_en (group A, GEO first priority)  
- description / description_en (group A, detailed Markdown)
- category_slug / tags / version (group A metadata)
- known_gaps (group E, from business_decisions)
- changelog / changelog_en / contributors (group G)

Reference: SOP §1.3A, §1.3E, §1.3G
