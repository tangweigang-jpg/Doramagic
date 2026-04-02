"""Quality gate -- 6-dimension scoring for skill quality assessment.

Dimensions (100-point scale):
  Coverage     (27%) -- required sections present, workflow depth, anti-pattern depth
  Evidence     (23%) -- evidence markers, attribution in knowledge section
  DSD Health   (18%) -- specific vs generic language ratio
  Code Health  (12%) -- Python syntax validity, runtime trap detection
  WHY Density  (12%) -- ratio of sentences containing causal reasoning
  Substance    (8%)  -- vocabulary richness, minimum length

Pass threshold: 60 points.

v13.2 changes (2026-04-01):
  - Added Code Health dimension (P0-1 of Eval-Driven Quality Improvement)
  - Adjusted weights to accommodate new dimension
"""

from __future__ import annotations

import ast as _ast
import re

_REQUIRED_HEADINGS = [
    "Role",
    "Domain Knowledge",
    "Decision Framework",
    "Recommended Workflow",
    "Anti-Patterns",
]
_WHY_RE = re.compile(
    r"\b(because|why|rather than|instead of|trade[- ]?off|constraint|rationale)\b", re.I
)
_GENERIC_RE = re.compile(
    r"\b(best practice|industry standard|scalable solution|robust system)\b", re.I
)

# --- Code Health helpers ---
_SKIP_MARKERS = frozenset({"# pseudocode", "# example", "# conceptual", "# 伪代码", "# 示例"})


def _check_code_health(skill_md: str) -> tuple[float, list[str]]:
    """Parse all ```python code blocks in SKILL.md and return (score 0-100, error_list).

    Rules:
    - No python blocks → (100.0, [])  (don't penalise pure-doc skills)
    - Blocks starting with a skip marker comment are skipped
    - Each SyntaxError: -25 points (min 0)
    - Common runtime traps detected via heuristics: -10 points each
    """
    code_blocks = re.findall(r"```python\n(.*?)```", skill_md, re.DOTALL)
    if not code_blocks:
        return 100.0, []

    errors: list[str] = []
    warnings: list[str] = []

    for i, block in enumerate(code_blocks):
        first_line = block.strip().split("\n")[0].strip().lower() if block.strip() else ""
        if first_line in _SKIP_MARKERS:
            continue

        # 1. AST syntax check
        try:
            _ast.parse(block)
        except SyntaxError as e:
            errors.append(f"block_{i + 1}:L{e.lineno}: SyntaxError: {e.msg}")
            continue

        # 2. Common runtime trap heuristics
        if re.search(r"\.replace\(\s*day\s*=\s*\w+\.day\s*\+\s*1\s*\)", block):
            warnings.append(f"block_{i + 1}: month-end date overflow risk (day+1 crashes on 31st)")
        if re.search(r"market_close\s*=\s*(2[4-9]|[3-9]\d)", block):
            warnings.append(f"block_{i + 1}: market-hours constant exceeds 23 (max hour value)")
        if re.search(r"timezone\s*=\s*timezone\.utc", block) and re.search(
            r"(?:HOUR|hour|Hour)\s*=\s*[5-9]\b", block
        ):
            warnings.append(
                f"block_{i + 1}: UTC timezone with local-time hour reference — may need conversion"
            )

    penalty = len(errors) * 25.0 + len(warnings) * 15.0
    score = max(0.0, 100.0 - penalty)
    return score, errors + [f"[warn] {w}" for w in warnings]


def score_quality(skill_md: str) -> dict:
    """Score SKILL.md on 5 dimensions (100-point scale).

    Returns dict with total, passed, blockers, and per-dimension scores.
    """
    lines = skill_md.strip().splitlines()
    blockers: list[str] = []

    # Extract H2 sections
    sections: dict[str, str] = {}
    h2_lines = [(i, line[3:].strip()) for i, line in enumerate(lines) if line.startswith("## ")]
    for idx, (line_no, heading) in enumerate(h2_lines):
        end = h2_lines[idx + 1][0] if idx + 1 < len(h2_lines) else len(lines)
        sections[heading] = "\n".join(lines[line_no + 1 : end])

    # --- Coverage (30%) ---
    present = sum(1 for h in _REQUIRED_HEADINGS if any(h.lower() in sh.lower() for sh in sections))
    cov_raw = (present / len(_REQUIRED_HEADINGS)) * 100.0
    if not skill_md.strip().startswith("---"):
        cov_raw -= 12
        blockers.append("missing_yaml_frontmatter")
    workflow_text = next((v for k, v in sections.items() if "workflow" in k.lower()), "")
    anti_text = next((v for k, v in sections.items() if "anti-pattern" in k.lower()), "")
    wf_bullets = sum(
        1
        for line in workflow_text.splitlines()
        if line.strip().startswith(("-", "*", "1", "2", "3", "4", "5"))
    )
    ap_bullets = sum(1 for line in anti_text.splitlines() if line.strip().startswith(("-", "*")))
    if wf_bullets < 4:
        cov_raw -= 10
    if ap_bullets < 2:
        cov_raw -= 8
    cov_raw = max(0, min(100, cov_raw))

    # --- Evidence Quality (25%) ---
    knowledge_text = next((v for k, v in sections.items() if "knowledge" in k.lower()), "")
    evidence_markers = len(
        re.findall(
            r"\[(CODE|CATALOG|BASELINE)\]|github\.com|source:|README|from:|"
            r"\(from:|\(source:|\(evidence:|\bfile:|\bcommit\b",
            knowledge_text,
            re.I,
        )
    )
    attributed = len(re.findall(r"[-*]\s+.+\(.+\)", knowledge_text))
    evidence_hits = evidence_markers + attributed
    kb_bullets = max(
        1, sum(1 for line in knowledge_text.splitlines() if line.strip().startswith(("-", "*")))
    )
    ev_raw = min(100, (evidence_hits / kb_bullets) * 100)
    ev_raw = max(0, min(100, ev_raw))

    # --- DSD Health (20%) ---
    combined = " ".join(
        sections.get(k, "")
        for k in sections
        if any(w in k.lower() for w in ("knowledge", "framework", "anti-pattern", "safety"))
    )
    specific = len(
        re.findall(
            r"\b(prefer|avoid|unless|except|trade[- ]?off|failure|trap|constraint)\b",
            combined,
            re.I,
        )
    )
    generic = len(_GENERIC_RE.findall(combined))
    dsd_raw = min(100, specific * 9.0) - min(25, generic * 5.0)
    dsd_raw = max(0, dsd_raw)

    # --- WHY Density (15%) ---
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", skill_md) if s.strip()]
    why_hits = sum(1 for s in sentences if _WHY_RE.search(s))
    why_ratio = why_hits / max(1, len(sentences))
    why_raw = min(100, why_ratio * 220)

    # --- Substance (10%) ---
    tokens = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", skill_md)
    unique_ratio = len(set(tokens)) / max(1, len(tokens))
    sub_raw = min(100, len(tokens) / 12.0) + min(25, unique_ratio * 40)
    if len(tokens) < 220:
        sub_raw -= 20
    sub_raw = max(0, min(100, sub_raw))

    # --- Code Health (12%) ---
    code_raw, code_errors = _check_code_health(skill_md)

    # --- Total (6 dimensions) ---
    total = round(
        cov_raw * 0.27
        + ev_raw * 0.23
        + dsd_raw * 0.18
        + code_raw * 0.12
        + why_raw * 0.12
        + sub_raw * 0.08,
        1,
    )

    if present < 3:
        blockers.append("fewer_than_3_required_sections")

    # Find weakest section for targeted repair
    dimension_scores = {
        "coverage": round(cov_raw, 1),
        "evidence": round(ev_raw, 1),
        "dsd_health": round(dsd_raw, 1),
        "code_health": round(code_raw, 1),
        "why_density": round(why_raw, 1),
        "substance": round(sub_raw, 1),
    }
    weakest_section = _map_weakest_to_section(dimension_scores)

    passed = total >= 60.0 and not blockers
    repair_plan = []
    if not passed and weakest_section:
        repair_plan = [weakest_section]
    repairable = bool(repair_plan) and not blockers

    return {
        "total": total,
        "quality_score": total,
        "passed": passed,
        "blockers": blockers,
        "weakest_section": weakest_section,
        "weakest_dimension": min(dimension_scores, key=dimension_scores.get),
        "repair_plan": repair_plan,
        "repairable": repairable,
        "code_errors": code_errors,
        **dimension_scores,
    }


def _map_weakest_to_section(scores: dict[str, float]) -> str | None:
    """Map weakest quality dimension to a compilable section key.

    Returns the section key that should be re-compiled to address
    the weakest quality dimension.
    """
    dim_to_section = {
        "coverage": "workflow",
        "evidence": "knowledge",
        "dsd_health": "role",
        "code_health": "workflow",
        "why_density": "knowledge",
        "substance": "knowledge",
    }
    weakest_dim = min(scores, key=scores.get)
    return dim_to_section.get(weakest_dim)
