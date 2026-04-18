# Phase 2: Constraints Generation Prompt Template

<!-- REPLACE_WITH: Full Phase 2 prompt for generating field group D.

When implementing, this template should be rendered with:
  - constraints_jsonl: list[dict] (raw constraint entries, pre-filtered to fatal/critical/high)
  - blueprint_commit: str (40-char hash for evidence_url construction)
  - blueprint_source: str (owner/repo for GitHub permalink base)
  - cross_project_constraints: list (from crystal_ir.cross_project_constraints.items)

Key instructions to include in the final prompt:
1. Filter rule: only severity in {fatal, critical, high} with evidence_refs
2. evidence_url construction (SOP §1.3D):
   locator format: "src/path/file.py:L89"
   template: https://github.com/{owner}/{repo}/blob/{full_commit_hash}/{path}#L{line}
   if locator cannot be parsed → set evidence_url = null
3. summary_en format (≤160 chars):
   "If {simplified trigger}, {simplified consequence}. Correct approach: {simplified action}."
4. summary (Chinese, ≤80 chars):
   "如果{简化的触发条件}，{简化的后果}。正确做法：{简化的行为}。"
5. Cross-project constraints: set is_cross_project=true, source_blueprint_id from attribution
6. Call submit_constraints_fields with ALL constraints
-->

REPLACE_WITH: Phase 2 (constraints) prompt template.

This file will contain the full LLM prompt for generating:
- constraints[] (group D): bilingual summaries, evidence_url construction,
  cross-project attribution, confidence scores

Reference: SOP §1.3D
