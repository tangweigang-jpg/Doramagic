# Codex Improvement Report for Doramagic

Date: 2026-03-27

Repository reviewed:
- `/Users/tangsir/Documents/openclaw/Doramagic`

Key files reviewed first:
- `scripts/doramagic_singleshot.py`
- `packages/extraction/doramagic_extraction/llm_stage_runner.py`
- `packages/extraction/doramagic_extraction/brick_injection.py`
- `packages/community/doramagic_community/github_search.py`

Competitor repos cloned and reviewed on the mini:
- `https://github.com/danielmiessler/fabric`
- `https://github.com/yamadashy/repomix`
- `https://github.com/contextpilot-dev/contextpilot`

## Executive Summary

The current Doramagic singleshot pipeline has four structural quality problems:

1. The compile step is a single large LLM call with a 60 second timeout and no retry. When it fails, Doramagic falls directly to `_compile_skill_template()`. This is the main driver of the template fallback rate.
2. Domain brick selection is split across two different implementations. `brick_injection.py` uses framework mapping, but `scripts/doramagic_singleshot.py` has its own fuzzy keyword matcher at `load_matching_bricks()` (`scripts/doramagic_singleshot.py:119-169`). That duplicate logic is the real source of PKM contamination.
3. There is no output quality gate before delivery. Validation only checks presence of frontmatter, minimum sections, and a few domain disclaimers (`scripts/doramagic_singleshot.py:1112-1161`).
4. Cross-project contamination is possible both before and after synthesis:
   - `synthesize(souls, intent)` receives the full mixed soul list, including ClawHub and local skills, not just repo souls (`scripts/doramagic_singleshot.py:870-879`).
   - compile validation never checks whether project/tool names in the generated SKILL actually belong to the analyzed source set.

My recommendation is to make one architectural change instead of four isolated hacks:

- Move all brick matching into `packages/extraction/doramagic_extraction/brick_injection.py`.
- Add a deterministic quality and entity guard package under `packages/extraction/doramagic_extraction/`.
- Replace single-shot compile with sectioned compile + retry, and only fall back to template as the last resort.

That keeps the main fixes deterministic and testable, and it avoids pushing more responsibility onto one fragile LLM call.

## Evidence From Current Code

### 1. Compile timeout and fallback

- `call_llm(... timeout=60)` is hard-coded in `scripts/doramagic_singleshot.py:330-370`.
- `compile_skill()` does one large compile call and, on exception, immediately returns `_compile_skill_template(...)` at `scripts/doramagic_singleshot.py:1226-1255`.
- The compile prompt is explicitly truncated to `max_chars=16000` in `_build_compile_prompt(...)` at `scripts/doramagic_singleshot.py:989-1096`.
- The repair pass is another single large call at `scripts/doramagic_singleshot.py:1265-1300`.

### 2. Domain contamination

- `brick_injection.py` maps frameworks to brick files deterministically at `packages/extraction/doramagic_extraction/brick_injection.py:48-171`, but it does not perform semantic validation.
- Singleshot does not use `brick_injection.py` for its domain brick loading path.
- Instead, singleshot uses its own keyword/domain matcher at `scripts/doramagic_singleshot.py:119-169`.
- That matcher includes risky generic triggers such as `"knowledge" -> domain_pkm`, `"note" -> domain_pkm`, `"wiki" -> domain_pkm`.

This means GraphRAG-style intents can pick up PKM bricks simply because the domain string contains “knowledge”.

### 3. No quality scoring before delivery

- Validation only checks frontmatter, minimum H2 count, minimum line count, and domain disclaimers in `_validate_skill_md(...)` at `scripts/doramagic_singleshot.py:1112-1161`.
- There is no scoring rubric, no contamination check, no minimum source traceability check, and no artifact like `quality_score.json`.

### 4. Cross-project contamination

- `synthesize()` receives the entire `souls` list and serializes all of it into the LLM prompt (`scripts/doramagic_singleshot.py:870-879`).
- That `souls` list contains:
  - repo souls,
  - ClawHub skills,
  - local skills,
  because they are all appended before synthesis at `scripts/doramagic_singleshot.py:1632-1668`.
- There is no post-processor that verifies whether named projects/tools in the output belong to the analyzed sources.

## 1. Template Fallback Fix

### Root cause

The compile stage is currently doing too much in one shot:

- reference skill
- synthesis results
- repo soul details
- up to 20 bricks
- reference tools
- full SKILL synthesis

That is exactly the wrong place to use a single non-retried 60-second call.

### Design change

Replace the current single compile call with:

1. A retry wrapper for transient LLM failures.
2. A sectioned compiler that makes 4 smaller calls instead of 1 giant call.
3. A quality repair pass only if the assembled result scores below the acceptance bar.
4. Keep `_compile_skill_template()` as the last fallback, not the first fallback.

### Why this is better

- Smaller prompts reduce timeout risk directly.
- Section-by-section compile localizes failure. If one section fails, you retry just that section.
- A repair pass becomes targeted instead of “re-generate the whole world”.

### Proposed patch

#### Patch A: add retry wrapper and sectioned compile to `scripts/doramagic_singleshot.py`

```diff
--- a/scripts/doramagic_singleshot.py
+++ b/scripts/doramagic_singleshot.py
@@
 import argparse
 import json
 import os
 import re
 import subprocess
 import sys
 import time
 from datetime import datetime
 from pathlib import Path
 
 SCRIPT_DIR = Path(__file__).resolve().parent
+
+for _candidate in [
+    SCRIPT_DIR.parent / "packages" / "extraction",
+    SCRIPT_DIR.parent / "skills" / "doramagic" / "packages" / "extraction",
+]:
+    if _candidate.exists() and str(_candidate) not in sys.path:
+        sys.path.insert(0, str(_candidate))
+
+try:
+    from doramagic_extraction.brick_injection import load_and_inject_bricks
+    from doramagic_extraction.entity_guard import (
+        build_allowed_source_names,
+        find_unknown_entities,
+    )
+    from doramagic_extraction.output_quality import score_skill_md
+except Exception:
+    load_and_inject_bricks = None
+    build_allowed_source_names = None
+    find_unknown_entities = None
+    score_skill_md = None
@@
 def call_llm(system_prompt, user_prompt, max_tokens=4096, stage_name=None, timeout=60):
@@
     return text
+
+
+_RETRYABLE_LLM_MARKERS = (
+    "timeout",
+    "timed out",
+    "connection reset",
+    "temporarily unavailable",
+    "502",
+    "503",
+    "504",
+)
+
+
+def _is_retryable_llm_error(exc: Exception) -> bool:
+    text = str(exc).lower()
+    return any(marker in text for marker in _RETRYABLE_LLM_MARKERS)
+
+
+def call_llm_with_retry(
+    system_prompt,
+    user_prompt,
+    *,
+    max_tokens=4096,
+    stage_name=None,
+    timeout=60,
+    attempts=3,
+    base_backoff_seconds=2.0,
+):
+    last_exc = None
+    for attempt in range(1, attempts + 1):
+        stage_label = stage_name if attempt == 1 else f"{stage_name}_retry_{attempt}"
+        try:
+            return call_llm(
+                system_prompt,
+                user_prompt,
+                max_tokens=max_tokens,
+                stage_name=stage_label,
+                timeout=timeout,
+            )
+        except Exception as exc:
+            last_exc = exc
+            if attempt >= attempts or not _is_retryable_llm_error(exc):
+                raise
+            sleep_s = base_backoff_seconds * (2 ** (attempt - 1))
+            _log(
+                "Retryable LLM failure during %s: %s; retrying in %.1fs (%d/%d)"
+                % (stage_name or "llm_call", exc, sleep_s, attempt, attempts)
+            )
+            time.sleep(sleep_s)
+    raise last_exc
@@
-def load_matching_bricks(domain, keywords=None, bricks_dir=None):
-    """Load bricks matching the domain and/or detected frameworks.
-
-    Returns list of brick dicts with statement, knowledge_type, confidence, tags.
-    """
-    if bricks_dir is None:
-        # Auto-resolve: check SCRIPT_DIR/../bricks/ or DORAMAGIC_ROOT/bricks/
-        candidates = [
-            SCRIPT_DIR.parent / "bricks",
-            SCRIPT_DIR.parent.parent / "bricks",
-            Path(os.environ.get("DORAMAGIC_ROOT", "")) / "bricks",
-        ]
-        for c in candidates:
-            if c.exists():
-                bricks_dir = c
-                break
-    if bricks_dir is None:
-        return []
-
-    bricks_dir = Path(bricks_dir)
-    matched_files = set()
-
-    # Match by domain
-    domain_lower = (domain or "").lower()
-    for keyword, brick_file in _DOMAIN_BRICK_MAP.items():
-        if keyword in domain_lower:
-            matched_files.add(brick_file)
-
-    # Match by keywords (framework detection)
-    for kw in (keywords or []):
-        kw_lower = kw.lower()
-        if kw_lower in _FRAMEWORK_BRICK_MAP:
-            matched_files.add(_FRAMEWORK_BRICK_MAP[kw_lower])
-
-    # Load bricks from matched files
-    all_bricks = []
-    for brick_file in matched_files:
-        jsonl_path = bricks_dir / ("%s.jsonl" % brick_file)
-        if not jsonl_path.exists():
-            continue
-        try:
-            with open(jsonl_path) as f:
-                for line in f:
-                    line = line.strip()
-                    if line:
-                        brick = json.loads(line)
-                        all_bricks.append(brick)
-        except Exception:
-            pass
-
-    return all_bricks
+def load_matching_bricks(domain, keywords=None, bricks_dir=None, project_context=""):
+    """Load bricks through the shared brick_injection module.
+
+    This removes the duplicate keyword matcher from singleshot and lets the
+    semantic validation gate live in one place.
+    """
+    if load_and_inject_bricks is None:
+        return []
+
+    hints = []
+    if domain:
+        hints.append(domain)
+    for kw in (keywords or []):
+        if kw and kw not in hints:
+            hints.append(kw)
+
+    result = load_and_inject_bricks(
+        frameworks=hints,
+        bricks_dir=str(bricks_dir) if bricks_dir else None,
+        output_dir=None,
+        project_context=project_context,
+    )
+    return result.raw_bricks
@@
+_SECTIONED_COMPILE_SPECS = [
+    {
+        "name": "scaffold",
+        "max_tokens": 1400,
+        "instructions": (
+            "Return ONLY these sections in markdown: YAML frontmatter, # Title, "
+            "## Role, ## When to Use. Do not include any other section."
+        ),
+    },
+    {
+        "name": "knowledge",
+        "max_tokens": 2200,
+        "instructions": (
+            "Return ONLY the ## Domain Knowledge section. Use cited bullets only. "
+            "Every bullet must cite a project name or brick id."
+        ),
+    },
+    {
+        "name": "decisions_workflow",
+        "max_tokens": 2200,
+        "instructions": (
+            "Return ONLY the ## Decision Framework and ## Recommended Workflow sections. "
+            "Decision Framework must contain concrete trade-offs. Workflow must contain at least 5 actionable steps."
+        ),
+    },
+    {
+        "name": "warnings_safety",
+        "max_tokens": 2200,
+        "instructions": (
+            "Return ONLY the ## Anti-patterns & UNSAID Warnings, ## Safety Boundaries, "
+            "and ## Capabilities sections. Anti-patterns must include severity labels."
+        ),
+    },
+]
+
+
+def _build_source_projects_section(souls):
+    lines = ["## Source Projects"]
+    for soul in souls:
+        project_name = soul.get("project_name", "unknown")
+        source_kind = soul.get("source", "repo")
+        if source_kind == "clawhub":
+            contribution = "market context only"
+        elif source_kind == "local":
+            contribution = "local reference context"
+        else:
+            why_count = len(soul.get("why_decisions", []))
+            trap_count = len(soul.get("unsaid_traps", []))
+            contribution = "%d WHY decisions, %d traps" % (why_count, trap_count)
+        lines.append("- %s — %s" % (project_name, contribution))
+    return "\n".join(lines)
+
+
+def _build_section_prompt(section_name, synthesis, souls, profile, bricks, reference_content):
+    repo_souls = [s for s in souls if s.get("source") not in ("clawhub", "local", "clawhub_ref")]
+    parts = [
+        "## User Context",
+        "- Domain: %s" % profile.get("domain", "general"),
+        "- Intent: %s" % profile.get("intent", ""),
+        "- Intent (English): %s" % profile.get("intent_en", ""),
+        "- User type: %s" % profile.get("user_type", "unknown"),
+        "",
+    ]
+
+    if reference_content:
+        parts.extend([
+            "## Reference Style",
+            reference_content,
+            "",
+        ])
+
+    if section_name in ("scaffold", "knowledge", "decisions_workflow", "warnings_safety"):
+        contract = synthesis.get("skill_contract", {}) if synthesis else {}
+        parts.extend([
+            "## Skill Contract",
+            "- Purpose: %s" % contract.get("purpose", ""),
+            "- Capabilities: %s" % ", ".join(contract.get("capabilities", [])),
+            "- Recommendation: %s" % (synthesis.get("recommendation", "") if synthesis else ""),
+            "",
+        ])
+
+    if section_name in ("knowledge", "decisions_workflow", "warnings_safety"):
+        parts.append("## Real Repo Souls")
+        for soul in repo_souls:
+            parts.append("### %s" % soul.get("project_name", "unknown"))
+            if soul.get("design_philosophy"):
+                parts.append("- Philosophy: %s" % soul.get("design_philosophy"))
+            if soul.get("mental_model"):
+                parts.append("- Mental Model: %s" % soul.get("mental_model"))
+            for d in soul.get("why_decisions", [])[:5]:
+                parts.append("- WHY: %s (evidence: %s)" % (d.get("decision", ""), d.get("evidence", "")))
+            for t in soul.get("unsaid_traps", [])[:5]:
+                parts.append("- UNSAID: [%s] %s" % (t.get("severity", "medium").upper(), t.get("trap", "")))
+            parts.append("")
+
+    if section_name in ("knowledge", "warnings_safety") and bricks:
+        parts.append("## Domain Bricks")
+        for brick in bricks[:10]:
+            parts.append(
+                "- [%s] (id: %s) %s"
+                % (
+                    brick.get("knowledge_type", "fact").upper(),
+                    brick.get("brick_id", ""),
+                    brick.get("statement", ""),
+                )
+            )
+        parts.append("")
+
+    if section_name in ("knowledge", "decisions_workflow"):
+        parts.append("## Synthesis")
+        for c in (synthesis or {}).get("consensus_whys", [])[:6]:
+            parts.append("- Consensus: %s (from: %s)" % (c.get("statement", ""), ", ".join(c.get("sources", []))))
+        for d in (synthesis or {}).get("divergent_whys", [])[:4]:
+            parts.append("- Divergence: %s" % json.dumps(d, ensure_ascii=False))
+        for t in (synthesis or {}).get("combined_traps", [])[:8]:
+            parts.append("- Trap: [%s] %s (source: %s)" % (
+                t.get("severity", "medium").upper(),
+                t.get("trap", ""),
+                t.get("source", ""),
+            ))
+        parts.append("")
+
+    return "\n".join(parts)
+
+
+def _compile_skill_by_sections(synthesis, souls, profile, bricks, reference_content):
+    rendered_sections = []
+    for spec in _SECTIONED_COMPILE_SPECS:
+        user_prompt = _build_section_prompt(
+            spec["name"],
+            synthesis,
+            souls,
+            profile,
+            bricks,
+            reference_content,
+        )
+        section_system = SKILL_ARCHITECT_SYSTEM + "\n\n" + spec["instructions"]
+        section_md = call_llm_with_retry(
+            section_system,
+            user_prompt,
+            max_tokens=spec["max_tokens"],
+            stage_name="compile_%s" % spec["name"],
+            timeout=90,
+            attempts=3,
+        )
+        rendered_sections.append(_strip_code_fences(section_md).strip())
+
+    rendered_sections.append(_build_source_projects_section(souls))
+    return "\n\n".join(section for section in rendered_sections if section.strip())
@@
 def compile_skill(synthesis, souls, profile, bricks=None):
@@
     # 2. Build compile prompt
     prompt = _build_compile_prompt(synthesis, souls, profile, bricks, ref_content)
+
+    allowed_sources = set()
+    if build_allowed_source_names is not None:
+        allowed_sources = build_allowed_source_names(souls)
 
-    # 3. Round 1: LLM compile
+    # 3. Preferred path: sectioned compile with retry
     try:
-        skill_md = call_llm(
-            SKILL_ARCHITECT_SYSTEM, prompt,
-            max_tokens=6000, stage_name="compile_skill",
-        )
-        skill_md = _strip_code_fences(skill_md)
+        skill_md = _compile_skill_by_sections(synthesis, souls, profile, bricks, ref_content)
     except Exception as e:
-        _log("Skill Architect LLM failed: %s — falling back to template" % e)
-        if _debug_logger is not None:
-            _debug_logger.detail("compile LLM FAILED: %s — using template fallback" % e)
-        return _compile_skill_template(synthesis, souls, profile, bricks)
+        _log("Sectioned compile failed: %s — trying legacy single-shot compile" % e)
+        try:
+            skill_md = call_llm_with_retry(
+                SKILL_ARCHITECT_SYSTEM,
+                prompt,
+                max_tokens=6000,
+                stage_name="compile_skill",
+                timeout=120,
+                attempts=2,
+            )
+            skill_md = _strip_code_fences(skill_md)
+        except Exception as legacy_exc:
+            _log("Skill Architect LLM failed: %s — falling back to template" % legacy_exc)
+            if _debug_logger is not None:
+                _debug_logger.detail(
+                    "compile LLM FAILED after sectioned+legacy attempts: %s — using template fallback"
+                    % legacy_exc
+                )
+            return _compile_skill_template(synthesis, souls, profile, bricks)
 
     # 4. Validate
     issues = _validate_skill_md(skill_md, domain)
+
+    if allowed_sources and find_unknown_entities is not None:
+        unknown_entities = find_unknown_entities(skill_md, allowed_sources)
+        if unknown_entities:
+            issues.append(
+                "Unknown project/tool names found in output: %s"
+                % ", ".join(unknown_entities[:10])
+            )
+
+    if score_skill_md is not None:
+        quality = score_skill_md(
+            skill_md,
+            domain=domain,
+            allowed_sources=allowed_sources,
+        )
+        if quality.total < 60:
+            issues.append("Quality score below shipping bar: %d/100" % quality.total)
+            issues.extend(quality.issues[:6])
@@
-            skill_md_fixed = call_llm(
+            skill_md_fixed = call_llm_with_retry(
                 SKILL_ARCHITECT_SYSTEM, fix_prompt,
-                max_tokens=6000, stage_name="compile_skill_fix",
+                max_tokens=6000, stage_name="compile_skill_fix", timeout=90, attempts=2,
             )
             skill_md_fixed = _strip_code_fences(skill_md_fixed)
@@
     return skill_md
@@
-    extraction_bricks = load_matching_bricks(
-        profile.get("domain", ""),
-        profile.get("keywords", []),
-    )
-    if extraction_bricks and _debug_logger is not None:
-        _debug_logger.detail("extraction bricks: %d loaded for soul extraction prompts" % len(extraction_bricks))
-
     t0 = time.time()
     souls = []
     for repo in repos:
         name = repo.get("name", "unknown")
         local_dir = repo.get("local_dir") or repo.get("local_path", "")
         facts = repo.get("facts", {})
+        repo_context = " ".join(
+            part for part in [
+                name,
+                profile.get("domain", ""),
+                profile.get("intent", ""),
+                facts.get("repo_summary", ""),
+                facts.get("project_narrative", ""),
+            ] if part
+        )
+        repo_bricks = load_matching_bricks(
+            profile.get("domain", ""),
+            profile.get("keywords", []),
+            project_context=repo_context,
+        )
 
         _log("Extracting soul: %s" % name)
-        soul = extract_soul(name, local_dir, facts, bricks=extraction_bricks)
+        soul = extract_soul(name, local_dir, facts, bricks=repo_bricks)
@@
-    else:
+    else:
+        repo_souls_only = [s for s in souls if s.get("source") not in ("clawhub", "local", "clawhub_ref")]
         _log("Synthesizing via LLM...")
-        syn = synthesize(souls, profile["intent"])
+        syn = synthesize(repo_souls_only, profile["intent"])
@@
-    domain_bricks = load_matching_bricks(
-        profile.get("domain", ""),
-        profile.get("keywords", []),
-    )
+    combined_context = "\n".join(
+        "%s %s %s" % (
+            s.get("project_name", ""),
+            s.get("design_philosophy", ""),
+            s.get("mental_model", ""),
+        )
+        for s in souls
+    )
+    domain_bricks = load_matching_bricks(
+        profile.get("domain", ""),
+        profile.get("keywords", []),
+        project_context=combined_context,
+    )
@@
     delivery = rd / "delivery"
     delivery.mkdir(parents=True, exist_ok=True)
     with open(delivery / "SKILL.md", "w") as f:
         f.write(skill_md)
+
+    if score_skill_md is not None:
+        allowed_sources = build_allowed_source_names(souls) if build_allowed_source_names else set()
+        quality = score_skill_md(skill_md, domain=profile.get("domain", ""), allowed_sources=allowed_sources)
+        with open(delivery / "quality_score.json", "w") as f:
+            json.dump(quality.to_dict(), f, ensure_ascii=False, indent=2)
```

### Notes on this patch

- This is intentionally conservative. It keeps the current compile prompt builder and legacy compile path as a fallback.
- The highest leverage change is `_compile_skill_by_sections()`, not the retry helper. Retry alone will help, but it will not solve prompt bloat.
- The synthesis path is also tightened so only real repo souls participate in cross-project synthesis.

## 2. Domain Contamination Fix

### Root cause

The bug is not only in `brick_injection.py`. The actual contamination path in singleshot is the duplicate brick matcher at `scripts/doramagic_singleshot.py:119-169`.

That means there are two brick-selection systems:

- `packages/extraction/doramagic_extraction/brick_injection.py`
- `scripts/doramagic_singleshot.py::load_matching_bricks()`

As long as that duplication exists, fixing only `brick_injection.py` will not stop contamination in the main v12 singleshot path.

### Design change

1. Move all brick selection logic into `brick_injection.py`.
2. Add a deterministic semantic similarity gate there.
3. Make singleshot call the shared module instead of its own keyword matcher.

### Proposed semantic gate

No new external embedding dependency is required. A deterministic TF-cosine gate is good enough for the first pass:

- Build a project context string from:
  - repo name
  - profile domain
  - profile intent
  - repo summary
  - project narrative
- Build a brick profile string from:
  - brick filename
  - brick aliases
  - `domain_id`
  - first N brick statements
- Compute cosine similarity over normalized tokens.
- Reject domain brick files below threshold.

This is not “true embedding semantics”, but it is already much better than substring keyword matching, deterministic, testable, and dependency-free.

### Proposed patch

#### Patch B: centralize brick selection in `packages/extraction/doramagic_extraction/brick_injection.py`

```diff
--- a/packages/extraction/doramagic_extraction/brick_injection.py
+++ b/packages/extraction/doramagic_extraction/brick_injection.py
@@
 import json
+import math
 import os
+import re
 import sys
+from collections import Counter
 from dataclasses import dataclass
 from pathlib import Path
 from typing import Optional
@@
+_DOMAIN_HINT_TO_BRICK_FILE: dict[str, str] = {
+    "health": "domain_health",
+    "medical": "domain_health",
+    "fitness": "domain_health",
+    "wellness": "domain_health",
+    "finance": "domain_finance",
+    "investment": "domain_finance",
+    "trading": "domain_finance",
+    "obsidian": "domain_pkm",
+    "logseq": "domain_pkm",
+    "zettelkasten": "domain_pkm",
+    "note taking": "domain_pkm",
+    "self-hosted": "domain_private_cloud",
+    "homelab": "domain_private_cloud",
+    "rss": "domain_info_ingestion",
+    "feed": "domain_info_ingestion",
+    "home assistant": "home_assistant",
+}
+
+
+_BRICK_PROFILE_ALIASES: dict[str, list[str]] = {
+    "domain_pkm": ["note taking", "personal knowledge management", "backlinks", "obsidian", "logseq"],
+    "domain_finance": ["budget", "investment", "trading", "portfolio", "expense tracking"],
+    "domain_health": ["symptoms", "diagnosis", "wellness", "medical", "triage"],
+    "domain_private_cloud": ["self hosted", "homelab", "nas", "server", "private cloud"],
+    "domain_info_ingestion": ["rss", "scraping", "feed reader", "crawler", "information ingestion"],
+}
+
+
+_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+./-]{1,}", re.IGNORECASE)
+_SIMILARITY_STOPWORDS = {
+    "the", "and", "for", "with", "this", "that", "from", "into", "your", "project",
+    "tool", "repo", "repository", "system", "using", "used", "based", "data",
+    "code", "software", "domain", "general", "assistant",
+}
@@
 class BrickInjectionResult:
@@
     raw_bricks: list[dict]
     """所有已加载积木的原始字典（未经 pydantic 验证）。"""
+
+    rejected_candidates: list[str] | None = None
+    """被语义闸门拒绝的 brick file 候选。"""
@@
+def _tokenize_similarity_text(text: str) -> list[str]:
+    tokens = []
+    for match in _TOKEN_RE.findall((text or "").lower()):
+        token = match.replace("_", " ").replace("-", " ").strip()
+        for part in token.split():
+            if len(part) >= 3 and part not in _SIMILARITY_STOPWORDS:
+                tokens.append(part)
+    return tokens
+
+
+def _cosine_similarity(left: str, right: str) -> float:
+    left_counts = Counter(_tokenize_similarity_text(left))
+    right_counts = Counter(_tokenize_similarity_text(right))
+    if not left_counts or not right_counts:
+        return 0.0
+
+    shared = set(left_counts) & set(right_counts)
+    numerator = sum(left_counts[t] * right_counts[t] for t in shared)
+    left_norm = math.sqrt(sum(v * v for v in left_counts.values()))
+    right_norm = math.sqrt(sum(v * v for v in right_counts.values()))
+    if not left_norm or not right_norm:
+        return 0.0
+    return numerator / (left_norm * right_norm)
+
+
+def _build_brick_profile_text(brick_filename: str, bricks: list[dict]) -> str:
+    aliases = _BRICK_PROFILE_ALIASES.get(brick_filename, [])
+    domain_ids = " ".join(b.get("domain_id", "") for b in bricks[:8])
+    statements = " ".join(b.get("statement", "") for b in bricks[:12])
+    return " ".join(
+        [brick_filename.replace("_", " "), domain_ids, " ".join(aliases), statements]
+    )
+
+
+def _passes_semantic_gate(
+    brick_filename: str,
+    bricks: list[dict],
+    project_context: str,
+    *,
+    threshold: float = 0.16,
+) -> bool:
+    if not project_context.strip():
+        return True
+    profile = _build_brick_profile_text(brick_filename, bricks)
+    score = _cosine_similarity(project_context, profile)
+
+    # Be stricter for broad domain packs than for exact framework packs.
+    if brick_filename.startswith("domain_"):
+        return score >= threshold
+    return score >= (threshold * 0.50)
+
+
+def _resolve_domain_hint_files(hints: list[str]) -> list[str]:
+    resolved: list[str] = []
+    for hint in hints:
+        normalized = _normalize_framework_name(hint)
+        for phrase, brick_file in _DOMAIN_HINT_TO_BRICK_FILE.items():
+            if phrase in normalized and brick_file not in resolved:
+                resolved.append(brick_file)
+    return resolved
@@
 def load_and_inject_bricks(
     frameworks: list[str],
     bricks_dir: Optional[str] = None,
     output_dir: Optional[str] = None,
+    project_context: str = "",
 ) -> BrickInjectionResult:
@@
     all_bricks: list[dict] = []
     frameworks_matched: list[str] = []
     frameworks_not_matched: list[str] = []
+    rejected_candidates: list[str] = []
     # 用 set 避免重复加载同一文件（如 FastAPI + Flask 都映射到 fastapi_flask.jsonl）
     loaded_files: set[str] = set()
+
+    candidate_files: list[tuple[str, str]] = []
+    for framework in frameworks:
+        candidate_files.append((framework, _resolve_brick_filename(framework)))
+    for brick_file in _resolve_domain_hint_files(frameworks):
+        candidate_files.append((brick_file, brick_file))
 
-    for framework in frameworks:
-        brick_filename = _resolve_brick_filename(framework)
+    for framework, brick_filename in candidate_files:
         jsonl_path = bricks_path_obj / f"{brick_filename}.jsonl"
@@
         bricks = _load_bricks_from_file(jsonl_path)
 
-        if bricks:
+        if bricks and _passes_semantic_gate(brick_filename, bricks, project_context):
             all_bricks.extend(bricks)
             frameworks_matched.append(framework)
             loaded_files.add(str(jsonl_path))
+        elif bricks:
+            rejected_candidates.append(brick_filename)
+            frameworks_not_matched.append(framework)
         else:
             frameworks_not_matched.append(framework)
@@
     return BrickInjectionResult(
         bricks_loaded=len(all_bricks),
         frameworks_matched=frameworks_matched,
         frameworks_not_matched=frameworks_not_matched,
         injection_text=injection_text,
         bricks_path=bricks_file_path,
         raw_bricks=all_bricks,
+        rejected_candidates=rejected_candidates,
     )
```

#### Patch C: pass project context from orchestration

```diff
--- a/packages/orchestration/doramagic_orchestration/phase_runner.py
+++ b/packages/orchestration/doramagic_orchestration/phase_runner.py
@@
     try:
+        project_context = " ".join(
+            part for part in [
+                repo_facts.get("repo_summary", ""),
+                repo_facts.get("project_narrative", ""),
+                " ".join(repo_facts.get("frameworks", [])),
+                " ".join(repo_facts.get("languages", [])),
+            ] if part
+        )
         result = load_and_inject_bricks(
             frameworks=frameworks,
             bricks_dir=bricks_dir,
             output_dir=output_dir,
+            project_context=project_context,
         )
```

### Tests to add

```diff
--- a/packages/extraction/tests/test_brick_injection.py
+++ b/packages/extraction/tests/test_brick_injection.py
@@
 class TestLoadAndInjectBricks:
+    def test_semantic_gate_rejects_pkm_for_graphrag_context(self, tmp_bricks_dir: Path):
+        result = load_and_inject_bricks(
+            frameworks=["knowledge graph", "rag"],
+            bricks_dir=str(tmp_bricks_dir),
+            project_context="GraphRAG extracts entities, relations, and communities from documents for retrieval-augmented generation.",
+        )
+        assert result.bricks_loaded == 0
+
+    def test_semantic_gate_keeps_pkm_for_obsidian_context(self, tmp_bricks_dir: Path):
+        # Add a domain_pkm fixture file in tmp_bricks_dir for this test in the real implementation.
+        result = load_and_inject_bricks(
+            frameworks=["obsidian", "note taking"],
+            bricks_dir=str(tmp_bricks_dir),
+            project_context="An Obsidian plugin for backlinks, note graphs, and personal knowledge management workflows.",
+        )
+        assert "obsidian" in [f.lower() for f in result.frameworks_matched]
```

## 3. Output Quality Scoring

### Goal

Before writing `delivery/SKILL.md`, Doramagic should score the output on a 0-100 scale and produce a machine-readable artifact such as `delivery/quality_score.json`.

### Acceptance bar

- `>= 80`: strong output
- `60-79`: acceptable
- `< 60`: incomplete, must trigger repair pass or be marked incomplete

### Rubric

I recommend a 100-point rubric derived from the actual failure modes in this repo:

- Mandatory sections: 40
  - YAML frontmatter: 5
  - Role + When to Use: 5
  - Domain Knowledge quality bar: 10
  - Decision Framework: 10
  - Anti-patterns / warnings: 10
- Quality dimensions: 30
  - Source traceability: 10
  - No contamination: 10
  - Actionability: 10
- Completeness bonus: 30
  - Workflow: 10
  - Safety Boundaries: 5
  - Capabilities: 5
  - Source Projects: 5
  - Community signals: 5

This matches the actual shape of Doramagic’s output and gives you a clear `60+` shipping bar.

### Proposed module

Create a new file:

- `packages/extraction/doramagic_extraction/output_quality.py`

### Proposed patch

```diff
*** /dev/null
--- a/packages/extraction/doramagic_extraction/output_quality.py
@@
+from __future__ import annotations
+
+import re
+from dataclasses import dataclass, field
+
+
+_REQUIRED_H2 = [
+    "## Role",
+    "## When to Use",
+    "## Domain Knowledge",
+    "## Decision Framework",
+    "## Recommended Workflow",
+    "## Anti-patterns",
+    "## Safety Boundaries",
+    "## Capabilities",
+    "## Source Projects",
+]
+
+_CITATION_MARKERS = ("(from:", "source:", "evidence:", "id:")
+_SEVERITY_MARKERS = ("[HIGH]", "[MEDIUM]", "[LOW]")
+_COMMUNITY_MARKERS = ("issue #", "pull request", "community issue", "comments:")
+
+
+@dataclass
+class QualityScoreResult:
+    total: int
+    mandatory_sections: int
+    quality_dimensions: int
+    completeness_bonus: int
+    issues: list[str] = field(default_factory=list)
+
+    def to_dict(self) -> dict:
+        return {
+            "total": self.total,
+            "mandatory_sections": self.mandatory_sections,
+            "quality_dimensions": self.quality_dimensions,
+            "completeness_bonus": self.completeness_bonus,
+            "issues": self.issues,
+        }
+
+
+def _section_text(skill_md: str, header: str) -> str:
+    lines = skill_md.splitlines()
+    start = None
+    for idx, line in enumerate(lines):
+        if line.strip() == header:
+            start = idx + 1
+            break
+    if start is None:
+        return ""
+    end = len(lines)
+    for idx in range(start, len(lines)):
+        if lines[idx].startswith("## "):
+            end = idx
+            break
+    return "\n".join(lines[start:end]).strip()
+
+
+def _bullet_lines(text: str) -> list[str]:
+    return [
+        line.strip()
+        for line in text.splitlines()
+        if re.match(r"^(- |\* |\d+\.)", line.strip())
+    ]
+
+
+def _has_decision_table(text: str) -> bool:
+    return "|" in text and "choose" in text.lower()
+
+
+def _actionability_ratio(lines: list[str]) -> float:
+    if not lines:
+        return 0.0
+    imperative_markers = (
+        "use ", "prefer ", "avoid ", "check ", "compare ", "verify ",
+        "run ", "inspect ", "collect ", "document ", "choose ", "escalate ",
+    )
+    actionable = sum(
+        1 for line in lines
+        if any(marker in line.lower() for marker in imperative_markers)
+    )
+    return actionable / len(lines)
+
+
+def _source_traceability_score(skill_md: str) -> tuple[int, list[str]]:
+    issues = []
+    knowledge = _bullet_lines(_section_text(skill_md, "## Domain Knowledge"))
+    if not knowledge:
+        return 0, ["Domain Knowledge has no bullets"]
+    cited = sum(1 for line in knowledge if any(marker in line.lower() for marker in _CITATION_MARKERS))
+    ratio = cited / len(knowledge)
+    if ratio >= 0.8:
+        return 10, []
+    if ratio >= 0.5:
+        return 7, []
+    issues.append("Less than 50% of Domain Knowledge bullets have explicit source markers")
+    return 3, issues
+
+
+def _contamination_score(skill_md: str, allowed_sources: set[str]) -> tuple[int, list[str]]:
+    if not allowed_sources:
+        return 10, []
+    from doramagic_extraction.entity_guard import find_unknown_entities
+
+    unknown = find_unknown_entities(skill_md, allowed_sources)
+    if not unknown:
+        return 10, []
+    if len(unknown) <= 2:
+        return 5, ["Potential contamination: %s" % ", ".join(unknown)]
+    return 0, ["Cross-project contamination: %s" % ", ".join(unknown[:10])]
+
+
+def score_skill_md(skill_md: str, *, domain: str = "", allowed_sources: set[str] | None = None) -> QualityScoreResult:
+    issues: list[str] = []
+
+    mandatory = 0
+    quality = 0
+    completeness = 0
+
+    # Mandatory sections (40)
+    if skill_md.strip().startswith("---"):
+        mandatory += 5
+    else:
+        issues.append("Missing YAML frontmatter")
+
+    if "## Role" in skill_md and "## When to Use" in skill_md:
+        mandatory += 5
+    else:
+        issues.append("Missing Role or When to Use")
+
+    domain_knowledge = _section_text(skill_md, "## Domain Knowledge")
+    domain_bullets = _bullet_lines(domain_knowledge)
+    if len(domain_bullets) >= 5:
+        mandatory += 10
+    else:
+        issues.append("Domain Knowledge has fewer than 5 bullets")
+
+    decision_framework = _section_text(skill_md, "## Decision Framework")
+    if _has_decision_table(decision_framework) or decision_framework.lower().count("choose") >= 2:
+        mandatory += 10
+    else:
+        issues.append("Decision Framework lacks concrete trade-off structure")
+
+    anti_patterns = _section_text(skill_md, "## Anti-patterns & UNSAID Warnings")
+    anti_lines = _bullet_lines(anti_patterns)
+    severity_count = sum(1 for line in anti_lines if any(marker in line for marker in _SEVERITY_MARKERS))
+    if len(anti_lines) >= 3 and severity_count >= 3:
+        mandatory += 10
+    else:
+        issues.append("Anti-patterns section needs 3+ severity-tagged warnings")
+
+    # Quality dimensions (30)
+    trace_score, trace_issues = _source_traceability_score(skill_md)
+    quality += trace_score
+    issues.extend(trace_issues)
+
+    contam_score, contam_issues = _contamination_score(skill_md, allowed_sources or set())
+    quality += contam_score
+    issues.extend(contam_issues)
+
+    workflow_lines = _bullet_lines(_section_text(skill_md, "## Recommended Workflow"))
+    capability_lines = _bullet_lines(_section_text(skill_md, "## Capabilities"))
+    actionable_pool = workflow_lines + capability_lines
+    ratio = _actionability_ratio(actionable_pool)
+    if ratio >= 0.8:
+        quality += 10
+    elif ratio >= 0.5:
+        quality += 6
+    else:
+        quality += 2
+        issues.append("Workflow and capabilities are too generic / not actionable enough")
+
+    # Completeness bonus (30)
+    if len(workflow_lines) >= 5:
+        completeness += 10
+    else:
+        issues.append("Workflow has fewer than 5 steps")
+
+    if "## Safety Boundaries" in skill_md:
+        completeness += 5
+    else:
+        issues.append("Missing Safety Boundaries")
+
+    if 5 <= len(capability_lines) <= 8:
+        completeness += 5
+    elif capability_lines:
+        completeness += 2
+        issues.append("Capabilities count should ideally be between 5 and 8")
+    else:
+        issues.append("Missing Capabilities bullets")
+
+    source_projects = _section_text(skill_md, "## Source Projects")
+    source_lines = _bullet_lines(source_projects)
+    if source_lines:
+        completeness += 5
+    else:
+        issues.append("Missing Source Projects bullets")
+
+    lower = skill_md.lower()
+    if any(marker in lower for marker in _COMMUNITY_MARKERS):
+        completeness += 5
+
+    total = mandatory + quality + completeness
+    return QualityScoreResult(
+        total=total,
+        mandatory_sections=mandatory,
+        quality_dimensions=quality,
+        completeness_bonus=completeness,
+        issues=issues,
+    )
```

### Tests to add

```diff
*** /dev/null
--- a/packages/extraction/tests/test_output_quality.py
@@
+from pathlib import Path
+import sys
+
+sys.path.insert(0, str(Path(__file__).parent.parent))
+
+from doramagic_extraction.output_quality import score_skill_md
+
+
+def test_quality_score_rewards_complete_skill():
+    skill_md = """---
+name: graphrag-advisor
+description: Use when analyzing knowledge-graph based RAG systems.
+---
+
+# GraphRAG Advisor
+
+## Role
+- Become a senior GraphRAG reviewer.
+
+## When to Use
+- Use when evaluating entity-relation extraction pipelines.
+- Use when comparing graph construction strategies.
+- Use when debugging retrieval drift.
+
+## Domain Knowledge
+- WHY: Build graph communities before retrieval expansion (from: microsoft/graphrag)
+- WHY: Tune chunking for entity density, not just token count (from: microsoft/graphrag)
+- UNSAID: Community summaries drift if the graph is stale (from: microsoft/graphrag)
+- WHY: Bricks should never override repo evidence (from: brick:graph-rag-core)
+- WHY: Explicit provenance beats hidden synthesis (from: microsoft/graphrag)
+
+## Decision Framework
+| Choose | When |
+|---|---|
+| pre-computed communities | when queries are repeated |
+| on-demand expansion | when the corpus changes frequently |
+
+## Recommended Workflow
+1. Inspect entity extraction quality before retrieval.
+2. Compare graph coverage against query intent.
+3. Verify provenance for every generated summary.
+4. Check community freshness before ranking.
+5. Escalate if source evidence is missing.
+
+## Anti-patterns & UNSAID Warnings
+- [HIGH] Do not inject PKM bricks into GraphRAG outputs. (source: microsoft/graphrag)
+- [MEDIUM] Avoid hiding provenance under generic summaries. (source: microsoft/graphrag)
+- [LOW] Do not treat graph density as quality by itself. (source: microsoft/graphrag)
+
+## Safety Boundaries
+- Do not fabricate unsupported sources.
+
+## Capabilities
+- Compare graph construction strategies.
+- Review provenance structure.
+- Flag retrieval drift.
+- Audit knowledge-source mapping.
+- Suggest safer compile prompts.
+
+## Source Projects
+- microsoft/graphrag — graph-first RAG design
+"""
+    result = score_skill_md(skill_md, domain="graph rag", allowed_sources={"microsoft/graphrag", "graphrag"})
+    assert result.total >= 60
+
+
+def test_quality_score_penalizes_missing_citations():
+    skill_md = """---
+name: weak-skill
+description: weak
+---
+# Weak
+## Role
+x
+## When to Use
+- use it
+## Domain Knowledge
+- generic bullet
+## Decision Framework
+none
+## Anti-patterns & UNSAID Warnings
+- warning
+"""
+    result = score_skill_md(skill_md, domain="general", allowed_sources={"repo-a"})
+    assert result.total < 60
+    assert any("source" in issue.lower() for issue in result.issues)
```

## 4. Cross-Project Contamination Detection

### Root cause

There are two contamination points:

1. Upstream contamination: `synthesize()` is fed mixed repo/ClawHub/local souls.
2. Downstream contamination: compile output is never checked against the allowed source set.

### Design change

Add a deterministic entity guard:

- Build an allowlist from analyzed sources.
- Extract project-like entities from the generated skill.
- Fail or repair if any project/tool name appears that is not in the allowlist.

This should run:

- after synthesis,
- after compile,
- and as part of the quality score.

### Proposed module

Create:

- `packages/extraction/doramagic_extraction/entity_guard.py`

### Proposed patch

```diff
*** /dev/null
--- a/packages/extraction/doramagic_extraction/entity_guard.py
@@
+from __future__ import annotations
+
+import re
+
+_REPO_PATTERN = re.compile(r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\b")
+_PROJECT_PATTERN = re.compile(r"\b(?:[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*|[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)+)\b")
+
+_GENERIC_ALLOWLIST = {
+    "github",
+    "git",
+    "python",
+    "json",
+    "yaml",
+    "readme",
+    "api",
+    "llm",
+    "openclaw",
+    "clawhub",
+    "doramagic",
+    "claude",
+    "claude code",
+}
+
+
+def _normalize_name(name: str) -> str:
+    name = (name or "").strip().lower()
+    if name.startswith("clawhub:"):
+        name = name.split(":", 1)[1]
+    if name.startswith("local:"):
+        name = name.split(":", 1)[1]
+    return name
+
+
+def build_allowed_source_names(souls: list[dict]) -> set[str]:
+    allowed: set[str] = set(_GENERIC_ALLOWLIST)
+    for soul in souls:
+        project_name = soul.get("project_name", "")
+        if not project_name:
+            continue
+        normalized = _normalize_name(project_name)
+        if normalized:
+            allowed.add(normalized)
+
+        if "/" in normalized:
+            owner, repo = normalized.split("/", 1)
+            allowed.add(owner)
+            allowed.add(repo)
+
+        alias = normalized.replace("-", " ").replace("_", " ")
+        if alias:
+            allowed.add(alias)
+    return allowed
+
+
+def extract_project_like_entities(markdown: str) -> set[str]:
+    candidates: set[str] = set()
+    for match in _REPO_PATTERN.findall(markdown or ""):
+        candidates.add(match)
+    for match in _PROJECT_PATTERN.findall(markdown or ""):
+        if len(match) >= 4:
+            candidates.add(match)
+    return candidates
+
+
+def find_unknown_entities(markdown: str, allowed_sources: set[str]) -> list[str]:
+    unknown = []
+    for entity in sorted(extract_project_like_entities(markdown)):
+        normalized = _normalize_name(entity)
+        if not normalized:
+            continue
+        if normalized in allowed_sources:
+            continue
+        if normalized.replace("-", " ") in allowed_sources:
+            continue
+        unknown.append(entity)
+    return unknown
```

### Integration points

- Only repo souls should go into `synthesize()`.
- `compile_skill()` should append unknown entities to the validation issue list.
- `quality_score.json` should deduct points for unknown entities.

### Optional synthesis hardening

Add an explicit allowlist to the synthesis prompt:

```diff
--- a/scripts/doramagic_singleshot.py
+++ b/scripts/doramagic_singleshot.py
@@
 def synthesize(souls, intent):
     """Cross-repo synthesis via LLM API."""
     try:
+        source_names = [s.get("project_name", "") for s in souls if s.get("project_name")]
         result = call_llm_json(
-            SYNTHESIS_SYSTEM,
-            "User intent: %s\n\nProject souls:\n%s"
-            % (intent, json.dumps(souls, ensure_ascii=False, indent=2)),
+            SYNTHESIS_SYSTEM + (
+                "\n\nOnly cite or mention projects from this explicit source list: %s. "
+                "If a name is not in this list, do not mention it."
+                % ", ".join(source_names)
+            ),
+            "User intent: %s\n\nProject souls:\n%s"
+            % (intent, json.dumps(souls, ensure_ascii=False, indent=2)),
             max_tokens=3000,
             stage_name="synthesis",
         )
```

## 5. Compare With Competitors

## 5.1 Fabric

Code reviewed:
- `fabric/data/patterns/extract_wisdom/system.md`
- `fabric/data/patterns/extract_wisdom/README.md`

### What Fabric does well

Fabric’s `extract_wisdom` pattern is very rigid about output shape:

- named sections
- minimum counts
- explicit output rules
- “extract first, distill second” workflow

That matters because it reduces omission. It is less “creative”, but much more reliable.

### Technique Doramagic should adopt

Adopt Fabric’s section-first contract for compile:

- do not ask the model for the full polished skill in one call
- ask for one section at a time with explicit constraints
- stitch deterministically

This is exactly what the sectioned compile patch above does.

### Concrete code Doramagic can adopt

The `_SECTIONED_COMPILE_SPECS` design in Patch A is the direct Fabric-style adoption.

If you want an even more Fabric-like internal plan object, add this helper:

```python
def _compile_contract():
    return {
        "scaffold": {"required_headers": ["# Title", "## Role", "## When to Use"]},
        "knowledge": {"required_headers": ["## Domain Knowledge"], "min_bullets": 5},
        "decisions_workflow": {
            "required_headers": ["## Decision Framework", "## Recommended Workflow"],
            "min_workflow_steps": 5,
        },
        "warnings_safety": {
            "required_headers": ["## Anti-patterns & UNSAID Warnings", "## Safety Boundaries", "## Capabilities"],
            "min_warnings": 3,
        },
    }
```

That gives you a deterministic contract that can be shared by:

- compile,
- validation,
- scoring.

## 5.2 Repomix

Code reviewed:
- `repomix/src/core/treeSitter/parseFile.ts`
- `repomix/src/core/treeSitter/loadLanguage.ts`
- `repomix/src/core/skill/skillTechStack.ts`
- `repomix/src/core/skill/packSkill.ts`
- `repomix/src/mcp/tools/generateSkillTool.ts`

### What Repomix does well

Repomix reduces code before it reaches the model:

- Tree-sitter/WASM parsing for code structure extraction
- language-specific parsing strategies
- deterministic tech-stack detection
- split output into references rather than stuffing everything into one prompt

The biggest lesson for Doramagic is not “use Tree-sitter because it is fashionable”. The lesson is:

- do structural pre-processing before LLM,
- and give the LLM compressed signatures, not raw files.

### Technique Doramagic should adopt

Add an AST digest step before LLM extraction:

- extract class names
- function signatures
- import graph
- public API surface
- config file dependencies

This can feed:

- `extract_soul()`
- `synthesize()`
- `llm_stage_runner._load_repo_code()`

### Concrete code Doramagic can adopt

Add a small Python AST digest module:

```diff
*** /dev/null
--- a/packages/extraction/doramagic_extraction/ast_digest.py
@@
+from __future__ import annotations
+
+from pathlib import Path
+import ast
+
+
+def extract_python_digest(repo_path: str, focus_files: list[str], max_items: int = 100) -> str:
+    repo = Path(repo_path)
+    rows: list[str] = []
+
+    for rel_path in focus_files[:20]:
+        path = repo / rel_path
+        if not path.exists() or path.suffix != ".py":
+            continue
+        try:
+            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
+        except Exception:
+            continue
+
+        for node in ast.walk(tree):
+            if isinstance(node, ast.ClassDef):
+                rows.append(f"{rel_path}: class {node.name}")
+            elif isinstance(node, ast.FunctionDef):
+                arg_names = [arg.arg for arg in node.args.args]
+                rows.append(f"{rel_path}: def {node.name}({', '.join(arg_names)})")
+            if len(rows) >= max_items:
+                break
+        if len(rows) >= max_items:
+            break
+
+    if not rows:
+        return ""
+    return "## AST Digest\\n" + "\\n".join(f"- {row}" for row in rows)
```

Then use it in `llm_stage_runner.py`:

```diff
--- a/packages/extraction/doramagic_extraction/llm_stage_runner.py
+++ b/packages/extraction/doramagic_extraction/llm_stage_runner.py
@@
+from doramagic_extraction.ast_digest import extract_python_digest
@@
 def _load_repo_code(repo_path: str, output_dir: str, max_chars: int = 100_000) -> str:
@@
     if facts_path.exists():
         try:
             facts = json.loads(facts_path.read_text(encoding="utf-8"))
             focus = facts.get("focus_files", [])
+            ast_digest = extract_python_digest(repo_path, focus)
+            if ast_digest:
+                return ast_digest + "\n\n" + _read_files(repo_path, focus, max_chars=max_chars - len(ast_digest) - 4)
             if focus:
                 return _read_files(repo_path, focus, max_chars)
```

This is intentionally lightweight. It does not require immediately bringing in Tree-sitter Python bindings. But structurally it moves Doramagic toward the Repomix idea: compress code before sending it to the LLM.

## 5.3 ContextPilot

Code reviewed:
- `contextpilot/internal/generator/generator.go`
- `contextpilot/cmd/score.go`
- `contextpilot/internal/decisions/decisions.go`
- `contextpilot/CLAUDE.md`

### What ContextPilot does well

ContextPilot separates:

- deterministic template rendering,
- context quality scoring,
- decision logging.

That split makes the system much easier to debug than a one-shot generator.

### Technique Doramagic should adopt

Adopt the same split:

1. deterministic artifact generation for source manifests / quality metadata,
2. a first-class score artifact,
3. a simple decision ledger if you want long-term advisor-pack evolution.

The direct Doramagic analog is:

- `delivery/SKILL.md`
- `delivery/quality_score.json`
- `delivery/source_manifest.json`

### Concrete code Doramagic can adopt

Add a deterministic source manifest writer:

```python
def write_source_manifest(delivery_dir: Path, souls: list[dict], quality_result) -> None:
    manifest = {
        "repo_sources": [],
        "reference_sources": [],
        "quality_score": quality_result.total,
    }
    for soul in souls:
        row = {
            "project_name": soul.get("project_name", ""),
            "source": soul.get("source", "repo"),
            "why_count": len(soul.get("why_decisions", [])),
            "trap_count": len(soul.get("unsaid_traps", [])),
        }
        if row["source"] == "repo":
            manifest["repo_sources"].append(row)
        else:
            manifest["reference_sources"].append(row)

    (delivery_dir / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

Then call it right after writing `quality_score.json`.

This is a direct ContextPilot-style move:

- generate the human artifact,
- generate the machine-readable artifact beside it,
- make both inspectable.

## Recommended Implementation Order

Do the work in this order:

1. Implement `entity_guard.py`.
2. Implement `output_quality.py`.
3. Patch singleshot compile to use sectioned compile + retry.
4. Centralize brick matching into `brick_injection.py`.
5. Remove singleshot’s duplicate `load_matching_bricks()` logic.
6. Add AST digest as a follow-up, not in the same PR.

Reason:

- The first four changes directly attack the observed quality failures.
- The AST digest is valuable, but it is an optimization and grounding upgrade, not the first blocker.

## Risks and Tradeoffs

### Sectioned compile

Pros:
- fewer timeouts
- easier debugging
- easier repair

Cons:
- more total tokens across all calls
- more assembly logic

Recommendation:
- accept the extra tokens; the quality gain is worth it

### Deterministic similarity gate

Pros:
- no new dependency
- testable
- explains why a brick was or was not injected

Cons:
- weaker than embedding-based semantic similarity

Recommendation:
- ship deterministic cosine gate first; move to embedding gate only if necessary

### Entity guard

Pros:
- directly targets cross-project leakage
- cheap
- easy to test

Cons:
- can produce a few false positives if the allowlist is too strict

Recommendation:
- treat unknown entities as repair triggers first, not hard failures

## Final Recommendation

If I were implementing this immediately, I would ship one PR with:

- `entity_guard.py`
- `output_quality.py`
- sectioned compile + retry in singleshot
- synthesis narrowed to repo souls only
- centralized brick loading through `brick_injection.py`

And I would leave AST digest / deeper Tree-sitter integration for the next PR.

That first PR is already enough to materially reduce:

- compile fallback rate
- domain contamination
- cross-project leakage
- silent low-quality deliveries

## File-Level Summary

Files that should change first:

- `scripts/doramagic_singleshot.py`
- `packages/extraction/doramagic_extraction/brick_injection.py`
- `packages/orchestration/doramagic_orchestration/phase_runner.py`

New files to add:

- `packages/extraction/doramagic_extraction/output_quality.py`
- `packages/extraction/doramagic_extraction/entity_guard.py`
- `packages/extraction/tests/test_output_quality.py`

Optional next-step file:

- `packages/extraction/doramagic_extraction/ast_digest.py`

