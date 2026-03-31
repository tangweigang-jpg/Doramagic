"""Local knowledge accumulator -- v12.1.1 minimal version.

Writes extraction learnings to ~/.doramagic/accumulated/{domain}.jsonl
after each successful run. Next same-domain extraction loads accumulated
knowledge as additional context.

Hard constraint: NO data upload. Everything stays local.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


ACCUMULATED_DIR = Path.home() / ".doramagic" / "accumulated"


def accumulate_knowledge(
    domain: str,
    source_repo: str,
    statements: list[dict],
    source_commit: str = "",
) -> int:
    """Append knowledge statements to domain-specific JSONL file.

    Each statement is a dict with at least 'statement' and 'confidence'.
    Returns number of statements written.
    """
    ACCUMULATED_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize domain name for filename
    safe_domain = "".join(c if c.isalnum() or c in "-_" else "_" for c in domain)
    if not safe_domain:
        safe_domain = "general"
    domain_file = ACCUMULATED_DIR / f"{safe_domain}.jsonl"

    now = datetime.now().isoformat()
    written = 0

    with open(domain_file, "a", encoding="utf-8") as f:
        for stmt in statements:
            if not isinstance(stmt, dict) or not stmt.get("statement"):
                continue
            entry = {
                "statement": stmt["statement"],
                "created_at": now,
                "source_repo": source_repo,
                "source_commit": source_commit,
                "confidence": stmt.get("confidence", "medium"),
                "knowledge_type": stmt.get("knowledge_type", "fact"),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += 1

    return written


def load_accumulated(domain: str, max_items: int = 50) -> list[dict]:
    """Load accumulated knowledge for a domain.

    Returns list of knowledge entries, most recent first.
    Only loads metadata first (deferred loading pattern).
    """
    safe_domain = "".join(c if c.isalnum() or c in "-_" else "_" for c in domain)
    domain_file = ACCUMULATED_DIR / f"{safe_domain}.jsonl"

    if not domain_file.exists():
        return []

    entries = []
    try:
        for line in domain_file.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []

    # Most recent first, cap at max_items
    entries.reverse()
    return entries[:max_items]


def accumulate_from_envelopes(
    domain: str,
    envelopes: list[dict],
) -> int:
    """Convenience: accumulate knowledge from RepoExtractionEnvelopes."""
    total = 0
    for env in envelopes:
        repo_name = env.get("repo_name", "unknown")
        statements = []

        # Design philosophy
        phil = env.get("design_philosophy", "")
        if phil:
            statements.append({
                "statement": phil,
                "confidence": "high",
                "knowledge_type": "rationale",
            })

        # WHY decisions
        for d in env.get("why_decisions", []):
            stmt = d.get("decision", "") if isinstance(d, dict) else str(d)
            if stmt:
                statements.append({
                    "statement": stmt,
                    "confidence": d.get("confidence", "medium") if isinstance(d, dict) else "medium",
                    "knowledge_type": "rationale",
                })

        # Unsaid traps
        for t in env.get("unsaid_traps", []):
            trap = t.get("trap", "") if isinstance(t, dict) else str(t)
            if trap:
                statements.append({
                    "statement": f"[TRAP] {trap}",
                    "confidence": "medium",
                    "knowledge_type": "failure",
                })

        total += accumulate_knowledge(domain, repo_name, statements)

    return total
