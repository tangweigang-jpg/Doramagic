"""
Confidence System: Evidence-Chain Tagging + Deterministic Verdict

Subsystem 1 of the confidence pipeline.  Pure deterministic — zero LLM calls.

Integration point:
    from confidence_system import run_evidence_tagging, tag_evidence_refs, compute_verdict

Public API matches the interface defined in BRIEF.md:
    run_evidence_tagging(cards: list[dict]) -> list[dict]
"""

from __future__ import annotations

import re
from typing import Literal

# ---------------------------------------------------------------------------
# Types (mirror contracts without requiring the package at import time)
# ---------------------------------------------------------------------------

EvidenceTag = Literal["CODE", "DOC", "COMMUNITY", "INFERENCE"]
Verdict = Literal["SUPPORTED", "CONTESTED", "WEAK", "REJECTED"]
PolicyAction = Literal["ALLOW_CORE", "ALLOW_STORY", "QUARANTINE"]

# ---------------------------------------------------------------------------
# Path-keyword sets for DOC detection
# ---------------------------------------------------------------------------

# Artifact paths that indicate documentation (matched case-insensitively)
_DOC_PATH_KEYWORDS = frozenset(
    {
        "readme",
        "doc",
        "docs",
        "guide",
        "contributing",
        "changelog",
        "howto",
        "tutorial",
        "manual",
        "wiki",
        "faq",
        "architecture",
        "design",
    }
)

# File extensions that are always documentation regardless of path segment
_DOC_EXTENSIONS = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
        ".adoc",
        ".asciidoc",
        ".html",
        ".htm",
        ".pdf",
    }
)


def _path_contains_doc_keyword(path: str) -> bool:
    """Return True if *path* contains any DOC-indicator segment or extension."""
    lower = path.lower()
    # Check extension first (fast path)
    for ext in _DOC_EXTENSIONS:
        if lower.endswith(ext):
            return True
    # Split by common separators and check each segment
    segments = re.split(r"[/\\._-]", lower)
    return bool(_DOC_PATH_KEYWORDS & set(segments))


# ---------------------------------------------------------------------------
# Evidence tagging
# ---------------------------------------------------------------------------


def tag_single_ref(kind: str, path: str) -> EvidenceTag:
    """
    Tag one evidence_ref according to the rules in BRIEF.md.

        file_line  → CODE  (always)
        community_ref → COMMUNITY  (always)
        artifact_ref:
            path contains readme/doc/guide/contributing → DOC
            otherwise                                   → CODE
    """
    kind = (kind or "").lower()

    if kind == "file_line":
        return "CODE"

    if kind == "community_ref":
        return "COMMUNITY"

    if kind == "artifact_ref":
        if _path_contains_doc_keyword(path or ""):
            return "DOC"
        return "CODE"

    # Unknown / missing kind — treat as INFERENCE (caller must handle)
    return "INFERENCE"


def tag_evidence_refs(evidence_refs: list[dict]) -> list[EvidenceTag]:
    """
    Convert a list of evidence_ref dicts to a list of EvidenceTag strings.
    Empty list → ["INFERENCE"].
    """
    if not evidence_refs:
        return ["INFERENCE"]
    return [tag_single_ref(ref.get("kind", ""), ref.get("path", "")) for ref in evidence_refs]


# ---------------------------------------------------------------------------
# Verdict computation
# ---------------------------------------------------------------------------


def compute_verdict(tags: list[EvidenceTag]) -> tuple[Verdict, PolicyAction]:
    """
    Deterministic Boolean-algebra verdict from a list of evidence tags.

    Rules (BRIEF.md table, evaluated in priority order):

    1. CODE + DOC                    → SUPPORTED / ALLOW_CORE
    2. CODE + COMMUNITY              → SUPPORTED / ALLOW_CORE
    3. DOC + COMMUNITY (no CODE)     → SUPPORTED / ALLOW_STORY
    4. CODE only                     → SUPPORTED / ALLOW_CORE
    5. COMMUNITY only (no CODE, DOC) → CONTESTED / ALLOW_STORY
    6. INFERENCE + any 1 corroboration → WEAK / ALLOW_STORY
    7. INFERENCE only                → REJECTED / QUARANTINE
    8. Contradictory evidence        → CONTESTED / ALLOW_STORY

    "Contradictory evidence" is defined as CODE and COMMUNITY present but
    producing mutually exclusive recommendations (a heuristic: we detect this
    when the tag set contains BOTH CODE and COMMUNITY but the evidence_refs
    carry conflicting normalized_force signals — since we operate only on tags
    here, contradiction is flagged when we have CODE and COMMUNITY but also an
    explicit INFERENCE tag mixed in with other tags, suggesting the LLM
    couldn't reconcile them).
    """
    tag_set = set(tags)

    has_code = "CODE" in tag_set
    has_doc = "DOC" in tag_set
    has_community = "COMMUNITY" in tag_set
    has_inference = "INFERENCE" in tag_set

    # Count non-inference distinct tag types
    corroborating = tag_set - {"INFERENCE"}
    corroboration_count = len(corroborating)

    # --- Detect contradictory evidence ---
    # Contradiction: CODE + COMMUNITY + INFERENCE mixed together.
    # The INFERENCE tag alongside real evidence implies the extractor
    # found conflicting signals and fell back to inference for some refs.
    if has_inference and corroboration_count >= 2:
        return "CONTESTED", "ALLOW_STORY"

    # --- INFERENCE only ---
    if has_inference and corroboration_count == 0:
        return "REJECTED", "QUARANTINE"

    # --- INFERENCE + 1 corroborating tag ---
    if has_inference and corroboration_count == 1:
        return "WEAK", "ALLOW_STORY"

    # --- No INFERENCE below this line ---

    # Rule 1: CODE + DOC (COMMUNITY presence is a bonus, doesn't downgrade)
    if has_code and has_doc:
        return "SUPPORTED", "ALLOW_CORE"

    # Rule 2: CODE + COMMUNITY
    if has_code and has_community:
        return "SUPPORTED", "ALLOW_CORE"

    # Rule 3: DOC + COMMUNITY (no CODE)
    if has_doc and has_community:
        return "SUPPORTED", "ALLOW_STORY"

    # Rule 4: CODE only
    if has_code:
        return "SUPPORTED", "ALLOW_CORE"

    # Rule 5: COMMUNITY only
    if has_community:
        return "CONTESTED", "ALLOW_STORY"

    # Fallback (empty tags after stripping INFERENCE — shouldn't happen)
    return "REJECTED", "QUARANTINE"


# ---------------------------------------------------------------------------
# Card-level processing
# ---------------------------------------------------------------------------


def process_card(card: dict) -> dict:
    """
    Annotate a single card dict with evidence_tags, verdict, and policy_action.

    Operates on the 'evidence_refs' list inside the card.  The card dict is
    modified in-place AND returned for convenience.

    Card shape (minimal):
        {
            "card_id": "...",
            "evidence_refs": [{"kind": "file_line", "path": "src/foo.py", ...}, ...]
            # optional other fields
        }
    """
    refs = card.get("evidence_refs") or []
    tags = tag_evidence_refs(refs)
    verdict, policy_action = compute_verdict(tags)

    card["evidence_tags"] = tags
    card["verdict"] = verdict
    card["policy_action"] = policy_action
    return card


# ---------------------------------------------------------------------------
# Public integration API
# ---------------------------------------------------------------------------


def run_evidence_tagging(cards: list[dict]) -> list[dict]:
    """
    Tag every card with evidence_tags, verdict, and policy_action.

    Args:
        cards: List of card dicts, each optionally containing 'evidence_refs'.

    Returns:
        The same list with each card mutated in place to include the three
        new fields.  Order is preserved.
    """
    for card in cards:
        process_card(card)
    return cards


# ---------------------------------------------------------------------------
# YAML frontmatter integration helper
# ---------------------------------------------------------------------------


def inject_verdict_into_frontmatter(frontmatter_text: str, card: dict) -> str:
    """
    Inject or replace evidence_tags / verdict / policy_action lines inside an
    existing YAML frontmatter block (between leading --- markers).

    This is a text-level operation so it works without a full YAML parser.

    Args:
        frontmatter_text: The complete card file text (including --- markers).
        card: A card dict that has already been processed by process_card().

    Returns:
        Updated file text with the three fields injected just before the
        closing '---' marker.
    """
    tags_yaml = "[" + ", ".join(card["evidence_tags"]) + "]"
    verdict_line = f"verdict: {card['verdict']}"
    policy_line = f"policy_action: {card['policy_action']}"
    tags_line = f"evidence_tags: {tags_yaml}"

    # Remove any existing occurrences of these keys
    lines = frontmatter_text.split("\n")
    filtered = [
        ln for ln in lines if not re.match(r"^(evidence_tags|verdict|policy_action)\s*:", ln)
    ]

    # Find the closing --- (second occurrence) and inject before it
    # The first --- is at index 0, the closing one comes after frontmatter body
    close_idx = None
    fm_start = False
    for i, ln in enumerate(filtered):
        if ln.strip() == "---":
            if not fm_start:
                fm_start = True
                continue
            close_idx = i
            break

    if close_idx is not None:
        filtered.insert(close_idx, tags_line)
        filtered.insert(close_idx + 1, verdict_line)
        filtered.insert(close_idx + 2, policy_line)
    else:
        # No closing --- found; append at end of frontmatter as best effort
        filtered.extend([tags_line, verdict_line, policy_line])

    return "\n".join(filtered)
