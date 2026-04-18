# Phase 3: FAQ Generation Prompt Template

<!-- REPLACE_WITH: Full Phase 3 prompt for generating field group F.

When implementing, this template should be rendered with:
  - crystal_ir: dict (user_intent, stages, context_acquisition)
  - fatal_constraints: list (top 3 fatal constraints from Phase 2 output)
  - host_adapters_preview: list (from crystal_ir.host_adapters, used for question 3)
  - required_inputs_preview: list (from crystal_ir.context_acquisition, for question 4)
  - blueprint_applicability: dict (for domain-specific question 5)
  - slug: str (from Phase 1, for doramagic.ai/r/{slug} CTA)

5 Mandatory FAQ categories (SOP §1.3F):
  1. Core capability: "这个配方能帮我做什么？"
  2. Pitfall value: "使用时有哪些常见失败？" (→ top 3 fatal constraints)
  3. Applicable scope: "这个配方支持哪些 AI 环境？" (→ host_adapters)
  4. Input requirements: "使用这个配方需要准备什么？" (→ required_inputs)
  5. Domain-specific: varies by domain (→ blueprint applicability)

Question format: real user queries as in Perplexity/ChatGPT
  ✅ "用 Claude 做 A 股 MACD 回测需要什么？"
  ❌ "MACD 回测配方的输入参数有哪些？"

Answer rules:
  - Chinese 80-120 chars, English 120-200 chars
  - Conclusion first, then supplement
  - ≥1 specific number per answer
  - LAST answer MUST contain "doramagic.ai" (zero-click protection)
-->

REPLACE_WITH: Phase 3 (faq) prompt template.

This file will contain the full LLM prompt for generating:
- faqs[] (group F): 5-8 bilingual Q&A pairs, 5 mandatory categories,
  user-style questions, CTA in last answer

Reference: SOP §1.3F
