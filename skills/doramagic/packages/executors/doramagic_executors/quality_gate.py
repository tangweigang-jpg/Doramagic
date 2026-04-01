"""Quality gate -- 5-dimension scoring 5-dimension scoring for skill quality assessment.

Dimensions (100-point scale):
  Coverage    (30%) -- required sections present, workflow depth, anti-pattern depth
  Evidence    (25%) -- evidence markers, attribution in knowledge section
  DSD Health  (20%) -- specific vs generic language ratio
  WHY Density (15%) -- ratio of sentences containing causal reasoning
  Substance   (10%) -- vocabulary richness, minimum length

Pass threshold: 60 points.
"""

from __future__ import annotations

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

    # --- Total ---
    total = round(
        cov_raw * 0.30 + ev_raw * 0.25 + dsd_raw * 0.20 + why_raw * 0.15 + sub_raw * 0.10, 1
    )

    if present < 3:
        blockers.append("fewer_than_3_required_sections")

    # Find weakest section for targeted repair
    dimension_scores = {
        "coverage": round(cov_raw, 1),
        "evidence": round(ev_raw, 1),
        "dsd_health": round(dsd_raw, 1),
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
        "why_density": "knowledge",
        "substance": "knowledge",
    }
    weakest_dim = min(scores, key=scores.get)
    return dim_to_section.get(weakest_dim)
