"""
Deceptive Source Detection (DSD) — 8 deterministic checks.

Pure Python, zero LLM calls.

Integration point:
    from deceptive_source_detection import run_dsd_checks, DSDReport, DSDCheck

Public API matches BRIEF.md:
    run_dsd_checks(cards, repo_facts, community_signals) -> DSDReport

Each check returns a DSDCheck with:
    check_id   : str   — e.g. "DSD-1"
    name       : str
    score      : float — 0..1  (0 = no problem, 1 = maximum problem)
    triggered  : bool  — True when threshold exceeded
    detail     : str
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Data models (dataclasses — no pydantic dependency needed here)
# ---------------------------------------------------------------------------


@dataclass
class DSDCheck:
    check_id: str
    name: str
    score: float          # 0..1
    triggered: bool
    detail: str


@dataclass
class DSDReport:
    checks: list[DSDCheck] = field(default_factory=list)
    overall_status: Literal["CLEAN", "WARNING", "SUSPICIOUS"] = "CLEAN"

    def to_dict(self) -> dict:
        return {
            "checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "score": round(c.score, 4),
                    "triggered": c.triggered,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
            "overall_status": self.overall_status,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INFERENCE_WORDS = re.compile(
    r"\b(inferred?|infers?|inference|推测|推断|likely|probably|possibly|"
    r"assumed?|assumption|unclear|unknown|uncertain|guessed?|speculated?|"
    r"appears? to|seems? to)\b",
    re.IGNORECASE,
)

_WORKAROUND_WORDS = re.compile(
    r"\b(workaround|work-around|edge[- ]?case|hack|kludge|临时|绕过|"
    r"monkey[- ]?patch|patch|fix-up|fixup|band-aid|bandaid|"
    r"undocumented|gotcha|footgun|pitfall)\b",
    re.IGNORECASE,
)

_CLOSED_SOURCE_KEYWORDS = re.compile(
    r"\b(api[_\s]?key|paid[_\s]plan|proprietary|closed[_\s]source|"
    r"enterprise[_\s]only|license[_\s]required|saas|third[_\s]party[_\s]service|"
    r"external[_\s]service|vendor[_\s]lock|商用|闭源|付费|外部服务)\b",
    re.IGNORECASE,
)

_VERSION_RE = re.compile(r"\bv?(\d+)\.(\d+)", re.IGNORECASE)


def _card_text(card: dict) -> str:
    """Concatenate all string values in a card for full-text analysis."""
    parts = []
    for v in card.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " ".join(parts)


def _is_rationale_card(card: dict) -> bool:
    """Heuristic: Q2 (rationale) cards and cards with knowledge_type=rationale."""
    q_key = card.get("question_key", "")
    k_type = card.get("knowledge_type", "")
    card_type = card.get("card_type", "")
    # Stage1Finding uses question_key Q2 for rationale
    # KnowledgeAtom uses knowledge_type="rationale"
    return q_key == "Q2" or k_type == "rationale" or "rationale" in card_type.lower()


def _extract_major_versions(refs: list[dict]) -> set[int]:
    """Extract distinct major version numbers from evidence_ref paths/snippets."""
    versions: set[int] = set()
    for ref in refs:
        text = " ".join(
            str(ref.get(f, "")) for f in ("path", "snippet", "source_url", "artifact_name")
        )
        for m in _VERSION_RE.finditer(text):
            versions.add(int(m.group(1)))
    return versions


# ---------------------------------------------------------------------------
# Individual DSD checks
# ---------------------------------------------------------------------------


def check_dsd1_rationale_support_ratio(cards: list[dict]) -> DSDCheck:
    """
    DSD-1: Rationale Support Ratio
    WHY cards backed by CODE/DOC/COMMUNITY evidence vs total WHY cards.
    Threshold: < 0.3 → WARNING
    """
    rationale_cards = [c for c in cards if _is_rationale_card(c)]
    total = len(rationale_cards)

    if total == 0:
        return DSDCheck(
            check_id="DSD-1",
            name="Rationale Support Ratio",
            score=0.0,
            triggered=False,
            detail="No rationale cards found — check skipped.",
        )

    supported = 0
    for card in rationale_cards:
        tags = card.get("evidence_tags", [])
        if any(t in ("CODE", "DOC", "COMMUNITY") for t in tags):
            supported += 1

    ratio = supported / total
    # Score = inverse of support ratio (high score = bad)
    score = max(0.0, 1.0 - ratio)
    triggered = ratio < 0.3

    return DSDCheck(
        check_id="DSD-1",
        name="Rationale Support Ratio",
        score=score,
        triggered=triggered,
        detail=(
            f"{supported}/{total} rationale cards have real evidence "
            f"(ratio={ratio:.2f}, threshold=0.30). "
            + ("WARNING: insufficient evidence for WHY claims." if triggered else "OK")
        ),
    )


def check_dsd2_temporal_conflict(cards: list[dict]) -> DSDCheck:
    """
    DSD-2: Temporal Conflict Score
    Same subject has cards referencing evidence from 2+ major versions apart.
    Threshold: any subject with version gap ≥ 2 → WARNING
    """
    subject_versions: dict[str, set[int]] = {}

    for card in cards:
        subject = card.get("subject", card.get("title", ""))
        if not subject:
            continue
        refs = card.get("evidence_refs", [])
        versions = _extract_major_versions(refs)
        if versions:
            subject_versions.setdefault(subject, set()).update(versions)

    conflicts = []
    for subj, versions in subject_versions.items():
        if len(versions) >= 2:
            gap = max(versions) - min(versions)
            if gap >= 2:
                conflicts.append((subj, sorted(versions)))

    triggered = len(conflicts) > 0
    score = min(1.0, len(conflicts) / max(1, len(subject_versions))) if subject_versions else 0.0

    detail_parts = []
    for subj, versions in conflicts[:3]:  # cap output length
        detail_parts.append(f"'{subj}' spans v{versions[0]}..v{versions[-1]}")
    detail = (
        f"{len(conflicts)} subject(s) have temporal version conflicts. "
        + ("; ".join(detail_parts) if detail_parts else "")
        + (" WARNING: stale evidence may mislead." if triggered else " OK")
    )

    return DSDCheck(
        check_id="DSD-2",
        name="Temporal Conflict Score",
        score=round(score, 4),
        triggered=triggered,
        detail=detail,
    )


def check_dsd3_exception_dominance(cards: list[dict], community_signals: str) -> DSDCheck:
    """
    DSD-3: Exception Dominance Ratio
    Workarounds / edge-cases as fraction of community_signals lines.
    Threshold: > 0.6 → WARNING
    """
    if not community_signals:
        return DSDCheck(
            check_id="DSD-3",
            name="Exception Dominance Ratio",
            score=0.0,
            triggered=False,
            detail="No community_signals provided — check skipped.",
        )

    lines = [ln for ln in community_signals.split("\n") if ln.strip()]
    total_lines = len(lines)
    if total_lines == 0:
        return DSDCheck(
            check_id="DSD-3",
            name="Exception Dominance Ratio",
            score=0.0,
            triggered=False,
            detail="community_signals is empty — check skipped.",
        )

    workaround_lines = sum(1 for ln in lines if _WORKAROUND_WORDS.search(ln))
    ratio = workaround_lines / total_lines
    triggered = ratio > 0.6

    return DSDCheck(
        check_id="DSD-3",
        name="Exception Dominance Ratio",
        score=round(ratio, 4),
        triggered=triggered,
        detail=(
            f"{workaround_lines}/{total_lines} community signal lines contain "
            f"workaround/edge-case language (ratio={ratio:.2f}, threshold=0.60). "
            + ("WARNING: project may be held together by workarounds." if triggered else "OK")
        ),
    )


def check_dsd4_support_desk_share(community_signals: str) -> DSDCheck:
    """
    DSD-4: Support-Desk Share
    Maintainer replies as fraction of total replies detected in community_signals.
    Proxy: lines containing "[maintainer]", "closed by", "@author", "core team" etc.
    Threshold: > 0.8 → WARNING
    """
    _MAINTAINER_RE = re.compile(
        r"\[maintainer\]|closed by|merged by|@(author|core|team|owner|admin)|"
        r"maintainer|core[_\s]team|project[_\s]owner|repo[_\s]owner",
        re.IGNORECASE,
    )
    _REPLY_MARKER = re.compile(
        r"\[reply\]|\breply\b|\bcomment\b|\bresponse\b|\banswer\b|回复|评论",
        re.IGNORECASE,
    )

    if not community_signals:
        return DSDCheck(
            check_id="DSD-4",
            name="Support-Desk Share",
            score=0.0,
            triggered=False,
            detail="No community_signals provided — check skipped.",
        )

    lines = community_signals.split("\n")
    total_replies = sum(1 for ln in lines if _REPLY_MARKER.search(ln))
    maintainer_replies = sum(1 for ln in lines if _MAINTAINER_RE.search(ln))

    if total_replies == 0:
        return DSDCheck(
            check_id="DSD-4",
            name="Support-Desk Share",
            score=0.0,
            triggered=False,
            detail="No reply markers found in community_signals — check skipped.",
        )

    ratio = maintainer_replies / total_replies
    triggered = ratio > 0.8

    return DSDCheck(
        check_id="DSD-4",
        name="Support-Desk Share",
        score=round(ratio, 4),
        triggered=triggered,
        detail=(
            f"{maintainer_replies}/{total_replies} replies are from maintainers "
            f"(ratio={ratio:.2f}, threshold=0.80). "
            + (
                "WARNING: community discussion is one-sided (support-desk pattern)."
                if triggered
                else "OK"
            )
        ),
    )


def check_dsd5_public_context_completeness(cards: list[dict]) -> DSDCheck:
    """
    DSD-5: Public Context Completeness
    Fraction of words in all card texts that are inference/speculation markers.
    Threshold: > 0.4 → WARNING

    Score is computed per-card and averaged to avoid long-document bias.
    """
    if not cards:
        return DSDCheck(
            check_id="DSD-5",
            name="Public Context Completeness",
            score=0.0,
            triggered=False,
            detail="No cards provided — check skipped.",
        )

    card_ratios = []
    for card in cards:
        text = _card_text(card)
        words = text.split()
        total_words = len(words)
        if total_words == 0:
            continue
        inference_hits = len(_INFERENCE_WORDS.findall(text))
        card_ratios.append(inference_hits / total_words)

    if not card_ratios:
        return DSDCheck(
            check_id="DSD-5",
            name="Public Context Completeness",
            score=0.0,
            triggered=False,
            detail="Could not compute word ratios — check skipped.",
        )

    avg_ratio = sum(card_ratios) / len(card_ratios)
    triggered = avg_ratio > 0.4

    return DSDCheck(
        check_id="DSD-5",
        name="Public Context Completeness",
        score=round(avg_ratio, 4),
        triggered=triggered,
        detail=(
            f"Average inference-word density across {len(card_ratios)} cards = "
            f"{avg_ratio:.3f} (threshold=0.40). "
            + (
                "WARNING: cards contain excessive speculation language."
                if triggered
                else "OK"
            )
        ),
    )


def check_dsd6_persona_divergence(cards: list[dict]) -> DSDCheck:
    """
    DSD-6: Persona Divergence Score
    Detect contradictory environment assumptions across different sources within
    the same card set.

    Proxy: Check if cards reference mutually exclusive runtime environments.
    E.g., one card says "requires Python 2" while another says "requires Python 3".

    Approach:
    - Extract (subject, env_claim) pairs from card texts.
    - Flag when the same subject has contradictory claims.
    """
    _ENV_PATTERNS = {
        "python_version": re.compile(r"python\s*([23])[\s\.]", re.IGNORECASE),
        "node_version": re.compile(r"node(?:\.js)?\s*v?(\d+)", re.IGNORECASE),
        "os": re.compile(r"\b(linux|windows|macos|darwin|ubuntu|debian|centos)\b", re.IGNORECASE),
        "container": re.compile(r"\b(docker|podman|kubernetes|k8s|containerd)\b", re.IGNORECASE),
    }

    # Collect env assumptions per (subject, env_type) → set of claimed values
    env_claims: dict[tuple[str, str], set[str]] = {}

    for card in cards:
        subject = card.get("subject", card.get("title", "unnamed"))
        text = _card_text(card)
        for env_type, pattern in _ENV_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                key = (subject, env_type)
                env_claims.setdefault(key, set()).update(m.lower() for m in matches)

    contradictions = []
    for (subject, env_type), values in env_claims.items():
        if env_type == "python_version" and "2" in values and "3" in values:
            contradictions.append(f"'{subject}' claims both Python 2 and 3")
        elif env_type == "os" and len(values) >= 3:
            # Three+ OS mentions under same subject is suspicious
            contradictions.append(
                f"'{subject}' references {len(values)} OS environments: {', '.join(sorted(values))}"
            )
        # For other env types: divergence of 2+ distinct values is a conflict
        elif env_type not in ("python_version", "os") and len(values) >= 2:
            contradictions.append(
                f"'{subject}' has {env_type} divergence: {', '.join(sorted(values))}"
            )

    triggered = len(contradictions) > 0
    score = min(1.0, len(contradictions) / max(1, len(cards)))

    return DSDCheck(
        check_id="DSD-6",
        name="Persona Divergence Score",
        score=round(score, 4),
        triggered=triggered,
        detail=(
            f"{len(contradictions)} environment contradiction(s) detected. "
            + ("; ".join(contradictions[:3]) if contradictions else "")
            + (" WARNING: conflicting environment assumptions." if triggered else " OK")
        ),
    )


def check_dsd7_dependency_dominance(cards: list[dict], repo_facts: dict) -> DSDCheck:
    """
    DSD-7: Dependency Dominance Index
    Fraction of core-function cards that depend on external closed-source services.
    Threshold: > 0.5 → WARNING
    """
    # Also scan repo_facts dependencies for closed-source indicators
    repo_deps: list[str] = []
    if repo_facts:
        repo_deps = repo_facts.get("dependencies", [])

    # Count cards that reference closed-source dependencies
    core_cards = [
        c for c in cards
        if c.get("knowledge_type") in ("capability", "interface", "assembly_pattern")
        or c.get("question_key") in ("Q1", "Q3", "Q5")
    ]

    if not core_cards and not repo_deps:
        return DSDCheck(
            check_id="DSD-7",
            name="Dependency Dominance Index",
            score=0.0,
            triggered=False,
            detail="No core-function cards or repo dependencies found — check skipped.",
        )

    # Check repo_facts dependencies
    closed_deps = [d for d in repo_deps if _CLOSED_SOURCE_KEYWORDS.search(d)]
    repo_closed_ratio = len(closed_deps) / max(1, len(repo_deps)) if repo_deps else 0.0

    # Check cards
    closed_card_count = sum(
        1 for c in core_cards if _CLOSED_SOURCE_KEYWORDS.search(_card_text(c))
    )
    card_closed_ratio = closed_card_count / max(1, len(core_cards)) if core_cards else 0.0

    # Combined score: weighted average (repo_facts is ground truth, cards are context)
    if repo_deps and core_cards:
        score = 0.6 * repo_closed_ratio + 0.4 * card_closed_ratio
    elif repo_deps:
        score = repo_closed_ratio
    else:
        score = card_closed_ratio

    triggered = score > 0.5

    return DSDCheck(
        check_id="DSD-7",
        name="Dependency Dominance Index",
        score=round(score, 4),
        triggered=triggered,
        detail=(
            f"Closed-source dependency ratio: repo={repo_closed_ratio:.2f} "
            f"({len(closed_deps)}/{len(repo_deps)} deps), "
            f"cards={card_closed_ratio:.2f} "
            f"({closed_card_count}/{len(core_cards)} core cards). "
            f"Combined score={score:.2f} (threshold=0.50). "
            + ("WARNING: core functionality depends heavily on closed-source services." if triggered else "OK")
        ),
    )


def check_dsd8_narrative_evidence_tension(cards: list[dict]) -> DSDCheck:
    """
    DSD-8: Narrative-Evidence Tension
    Fraction of narrative assertions in cards that lack supporting evidence.

    "Narrative assertion" heuristic: sentences that contain strong modal
    verbs (should, must, always, never, is the) without a matching evidence_ref
    in the same card.

    Threshold: unsupported assertions > 30% of total assertions → WARNING
    """
    _ASSERTION_RE = re.compile(
        r"[^.!?]*\b(should|must|always|never|is\s+the|are\s+the|"
        r"recommended|required|best\s+practice|anti[- ]?pattern|"
        r"必须|应该|建议|推荐|最佳实践)\b[^.!?]*[.!?]",
        re.IGNORECASE,
    )

    total_assertions = 0
    unsupported_assertions = 0

    for card in cards:
        text = _card_text(card)
        assertions = _ASSERTION_RE.findall(text)
        has_evidence = bool(card.get("evidence_refs"))
        card_assertions = len(assertions)
        total_assertions += card_assertions

        if card_assertions > 0 and not has_evidence:
            unsupported_assertions += card_assertions

    if total_assertions == 0:
        return DSDCheck(
            check_id="DSD-8",
            name="Narrative-Evidence Tension",
            score=0.0,
            triggered=False,
            detail="No narrative assertions detected — check skipped.",
        )

    ratio = unsupported_assertions / total_assertions
    triggered = ratio > 0.3

    return DSDCheck(
        check_id="DSD-8",
        name="Narrative-Evidence Tension",
        score=round(ratio, 4),
        triggered=triggered,
        detail=(
            f"{unsupported_assertions}/{total_assertions} narrative assertions "
            f"lack evidence refs (ratio={ratio:.2f}, threshold=0.30). "
            + ("WARNING: strong claims without traceability." if triggered else "OK")
        ),
    )


# ---------------------------------------------------------------------------
# Overall status computation
# ---------------------------------------------------------------------------


def compute_overall_status(checks: list[DSDCheck]) -> Literal["CLEAN", "WARNING", "SUSPICIOUS"]:
    """
    CLEAN     = 0 checks triggered
    WARNING   = 1-3 checks triggered
    SUSPICIOUS = 4+ checks triggered
    """
    triggered_count = sum(1 for c in checks if c.triggered)
    if triggered_count == 0:
        return "CLEAN"
    if triggered_count <= 3:
        return "WARNING"
    return "SUSPICIOUS"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_dsd_checks(
    cards: list[dict],
    repo_facts: dict | None = None,
    community_signals: str | None = None,
) -> DSDReport:
    """
    Run all 8 DSD checks and return a DSDReport.

    Args:
        cards: List of card dicts (already processed by run_evidence_tagging
               so that evidence_tags fields are populated).
        repo_facts: Optional dict from repo_facts.json (Stage 0 output).
        community_signals: Optional string content of community_signals.md.

    Returns:
        DSDReport with all 8 checks and overall_status.
    """
    repo_facts = repo_facts or {}
    community_signals = community_signals or ""

    checks = [
        check_dsd1_rationale_support_ratio(cards),
        check_dsd2_temporal_conflict(cards),
        check_dsd3_exception_dominance(cards, community_signals),
        check_dsd4_support_desk_share(community_signals),
        check_dsd5_public_context_completeness(cards),
        check_dsd6_persona_divergence(cards),
        check_dsd7_dependency_dominance(cards, repo_facts),
        check_dsd8_narrative_evidence_tension(cards),
    ]

    overall_status = compute_overall_status(checks)

    return DSDReport(checks=checks, overall_status=overall_status)
