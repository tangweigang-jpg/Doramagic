#!/usr/bin/env python3
"""Doramagic Engine — deterministic orchestrator for the discovery-to-facts pipeline.

This script chains github_search.py and extract_facts.py into a single end-to-end
workflow:

  1. Read a need_profile.json (keywords + domain + intent)
  2. Search GitHub for matching repos via github_search.py
  3. Rank candidates using metadata relevance instead of stars-only
  4. Fetch README + a few core files to build a lightweight snapshot
  5. Fallback to full archive download only when README fetch fails
  6. Extract deterministic facts for each repo via extract_facts.py
  7. Aggregate results and write summary.json to the output directory
  8. Print summary JSON to stdout (the LLM reads this)

Usage:
    python3 doramagic_engine.py --need /path/to/need_profile.json \
                                 --output /path/to/run_dir/ \
                                 [--top 5] [--timeout 60]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from github_search import (  # noqa: E402
    download_repo,
    fetch_repo_file,
    fetch_repo_readme,
    fetch_repo_tree,
    search_github,
)

EXTRACT_FACTS_SCRIPT = SCRIPT_DIR / "extract_facts.py"

MIN_STARS = 30         # drop very low-signal repos before ranking
DEFAULT_TOP = 5        # how many repos to analyse when --top is not given
HARD_TIMEOUT_SECS = 300  # 5-minute wall-clock cap
RETRY_DELAY_SECS = 10  # pause before retrying a failed archive download
MAX_CORE_FILES = 5
LOG_LOCK = threading.Lock()

BUILD_FILE_CANDIDATES = [
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
    "Pipfile",
    "composer.json",
]
ENTRYPOINT_PATTERNS = (
    "main.",
    "app.",
    "cli.",
    "index.",
)
TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
STOPWORDS = {"a", "an", "and", "for", "in", "of", "the", "to", "with"}


# ---------------------------------------------------------------------------
# Logging helpers (stderr only so stdout stays clean for JSON)
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Print a progress message to stderr."""
    with LOG_LOCK:
        print(f"[doramagic_engine] {msg}", file=sys.stderr, flush=True)


def _error_exit(message: str, warnings: list[str] | None = None) -> None:
    """Print an error JSON to stdout and exit with code 1."""
    payload: dict[str, Any] = {"status": "error", "message": message}
    if warnings:
        payload["warnings"] = warnings
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Safety: Zip Slip prevention
# ---------------------------------------------------------------------------

def _verify_safe_extraction(target_dir: Path) -> bool:
    """Return True only if every file under target_dir resolves within it."""
    resolved_target = target_dir.resolve()
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            p = Path(root, f).resolve()
            if not p.is_relative_to(resolved_target):
                return False
    return True


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _run(
    cmd: list[str],
    timeout: int,
    capture_stdout: bool = True,
    capture_stderr: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, letting stderr flow through unless capture_stderr=True."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture_stdout else None,
        stderr=subprocess.PIPE if capture_stderr else None,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Keyword / scoring helpers
# ---------------------------------------------------------------------------

def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().strip().split())


def _tokenize(values: list[str] | tuple[str, ...] | set[str] | str) -> list[str]:
    if isinstance(values, str):
        raw_values = [values]
    else:
        raw_values = list(values)
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        text = _normalize_text(raw)
        for token in TOKEN_SPLIT_RE.split(text):
            if len(token) < 2:
                continue
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _build_query_terms(profile: dict) -> list[str]:
    candidates: list[str] = []
    for key in ("github_queries", "keywords", "relevance_terms"):
        value = profile.get(key, [])
        if isinstance(value, str):
            value = [value]
        for item in value:
            text = (item or "").strip()
            if text:
                candidates.append(text)
    domain = (profile.get("domain") or "").strip()
    if domain:
        candidates.append(domain)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped[:6]


def _build_search_batches(profile: dict) -> list[list[str]]:
    batches: list[list[str]] = []
    github_queries = profile.get("github_queries", [])
    if isinstance(github_queries, str):
        github_queries = [github_queries]
    for query in github_queries:
        text = (query or "").strip()
        if text:
            batches.append([text])
            break

    keyword_terms = []
    for raw in profile.get("keywords", []):
        term = (raw or "").strip()
        if len(term) < 2 or term.lower() in STOPWORDS:
            continue
        keyword_terms.append(term)
    if keyword_terms:
        batches.append(keyword_terms[:4])

    relevance_terms = []
    for raw in profile.get("relevance_terms", []):
        term = (raw or "").strip()
        if len(term) < 2 or term.lower() in STOPWORDS:
            continue
        relevance_terms.append(term)
    if relevance_terms and relevance_terms[:4] != keyword_terms[:4]:
        batches.append(relevance_terms[:4])

    domain = (profile.get("domain") or "").strip()
    if domain:
        batches.append([domain])

    deduped_batches: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for batch in batches:
        key = tuple(term.lower() for term in batch)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_batches.append(batch)
    return deduped_batches[:4]


def _keyword_pool(profile: dict) -> list[str]:
    pool = _build_query_terms(profile)
    if not pool:
        pool = profile.get("keywords", [])
    return _tokenize(pool)


def _parse_updated_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _phrase_match_score(text: str, phrases: list[str]) -> float:
    normalized = _normalize_text(text)
    if not normalized:
        return 0.0
    for phrase in phrases:
        cleaned = _normalize_text(phrase)
        if len(cleaned) >= 4 and cleaned in normalized:
            return 1.0
    return 0.0


def _token_overlap_score(text: str, tokens: list[str]) -> float:
    haystack = set(_tokenize(text))
    if not haystack or not tokens:
        return 0.0
    overlap = len(haystack.intersection(tokens))
    if overlap == 0:
        return 0.0
    return min(1.0, overlap / max(2, min(len(tokens), 4)))


def _score_repo(repo: dict, profile: dict) -> float:
    """Return a 0-1 relevance score using metadata only."""
    keywords = _keyword_pool(profile)
    phrases = _build_query_terms(profile)
    full_name = repo.get("name", "")
    repo_name = full_name.split("/")[-1]
    description = repo.get("description", "") or ""
    topics = [str(topic) for topic in repo.get("topics", [])]

    name_match = max(
        _phrase_match_score(repo_name, phrases),
        min(1.0, 0.65 * _token_overlap_score(repo_name, keywords)),
    )
    desc_match = max(
        _phrase_match_score(description, phrases),
        _token_overlap_score(description, keywords),
    )

    topic_tokens = set(_tokenize(topics))
    keyword_tokens = set(keywords)
    topic_overlap = len(topic_tokens.intersection(keyword_tokens))
    topic_match = min(1.0, topic_overlap / 2.0) if topic_tokens and keyword_tokens else 0.0

    stars = max(0, int(repo.get("stars", 0) or 0))
    stars_score = min(1.0, math.log(stars + 1) / math.log(50000 + 1))

    freshness = 0.2
    updated_at = _parse_updated_at(repo.get("updated_at", ""))
    if updated_at is not None:
        age_days = max(0.0, (datetime.now(timezone.utc) - updated_at).days)
        if age_days <= 365:
            freshness = 1.0
        elif age_days <= 1095:
            freshness = 1.0 - ((age_days - 365) / 730.0) * 0.5
        else:
            freshness = max(0.0, 0.5 - min((age_days - 1095) / 1825.0, 1.0) * 0.5)

    breakdown = {
        "name_match": round(name_match, 4),
        "desc_match": round(desc_match, 4),
        "topic_match": round(topic_match, 4),
        "stars_score": round(stars_score, 4),
        "freshness": round(freshness, 4),
    }
    score = (
        breakdown["name_match"] * 0.30
        + breakdown["desc_match"] * 0.30
        + breakdown["topic_match"] * 0.15
        + breakdown["stars_score"] * 0.15
        + breakdown["freshness"] * 0.10
    )
    repo["score_breakdown"] = breakdown
    repo["relevance_score"] = round(min(max(score, 0.0), 1.0), 4)
    return repo["relevance_score"]


# ---------------------------------------------------------------------------
# Step 1 — search GitHub
# ---------------------------------------------------------------------------

def _search_repos(
    profile: dict,
    discovery_path: Path,
    top_k: int,
    per_step_timeout: int,
) -> list[dict]:
    """Search GitHub and persist enriched discovery results."""
    del per_step_timeout  # network timeouts are enforced in github_search.py helpers
    discovery_path.parent.mkdir(parents=True, exist_ok=True)

    search_batches = _build_search_batches(profile)
    if not search_batches:
        return []

    language = (profile.get("language") or profile.get("preferred_language") or "").strip()
    repos: list[dict] = []
    seen: set[str] = set()
    for batch in search_batches:
        _log(f"Searching GitHub: {' | '.join(batch)}")
        for repo in search_github(
            batch,
            top_k=max(top_k * 2, top_k),
            language=language,
            min_stars=MIN_STARS,
        ):
            if repo["name"] in seen:
                continue
            seen.add(repo["name"])
            repos.append(repo)
        if len(repos) >= max(top_k * 3, top_k):
            break
    try:
        discovery_path.write_text(
            json.dumps(repos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        _log(f"Warning: could not write discovery.json: {exc}")

    _log(f"Search returned {len(repos)} raw candidates.")
    return repos


# ---------------------------------------------------------------------------
# Step 2 — rank repos
# ---------------------------------------------------------------------------

def _rank_and_select_repos(repos: list[dict], profile: dict, top_n: int) -> list[dict]:
    """Rank repos by weighted relevance score and return the top N."""
    filtered = [dict(repo) for repo in repos if int(repo.get("stars", 0) or 0) >= MIN_STARS]
    for repo in filtered:
        _score_repo(repo, profile)

    filtered.sort(
        key=lambda repo: (
            repo.get("relevance_score", 0.0),
            repo.get("stars", 0),
            repo.get("updated_at", ""),
        ),
        reverse=True,
    )
    selected = filtered[:top_n]

    _log(
        f"Ranked {len(repos)} → {len(filtered)} (stars>={MIN_STARS}), "
        f"selected top {len(selected)}."
    )
    for repo in selected:
        _log(
            "score={score:.3f} name={name} breakdown={breakdown}".format(
                score=repo.get("relevance_score", 0.0),
                name=repo.get("name", "?"),
                breakdown=json.dumps(repo.get("score_breakdown", {}), ensure_ascii=False, sort_keys=True),
            )
        )
    return selected


# ---------------------------------------------------------------------------
# Step 3 — materialize repo content
# ---------------------------------------------------------------------------

def _sanitize_name(full_name: str) -> str:
    """Convert 'owner/repo' to 'owner-repo' for safe filesystem use."""
    return full_name.replace("/", "-").replace(" ", "_")


def _download_repo(
    repo: dict,
    repos_base_dir: Path,
    per_step_timeout: int,
) -> str | None:
    """Download a repo archive as a fallback path."""
    full_name: str = repo["name"]
    branch: str = repo.get("default_branch", "main")
    safe_name = _sanitize_name(full_name)
    dest_dir = repos_base_dir / safe_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(2):
        _log(f"Downloading {full_name} (attempt {attempt + 1})…")
        try:
            repo_dir = download_repo(full_name, branch, str(dest_dir))
        except Exception as exc:  # pragma: no cover - network failure guard
            _log(f"Archive download failed for {full_name}: {exc}")
            repo_dir = ""

        if repo_dir:
            extracted_path = Path(repo_dir)
            if extracted_path.exists() and _verify_safe_extraction(extracted_path):
                _log(f"Downloaded {full_name} → {repo_dir}")
                return repo_dir
            _log(f"SECURITY: Zip Slip detected in {full_name}, skipping repo.")
            return None

        if attempt == 0 and per_step_timeout > RETRY_DELAY_SECS:
            time.sleep(RETRY_DELAY_SECS)
    return None


def _select_core_files(tree: list[dict], profile: dict) -> list[str]:
    """Choose a few high-signal files from the repository tree."""
    paths = [item.get("path", "") for item in tree if item.get("path")]
    keyword_tokens = set(_keyword_pool(profile))
    selected: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        if not path or path in seen:
            return
        seen.add(path)
        selected.append(path)

    path_set = set(paths)
    for candidate in BUILD_FILE_CANDIDATES:
        if candidate in path_set:
            _add(candidate)
        if len(selected) >= MAX_CORE_FILES:
            return selected

    for path in paths:
        filename = Path(path).name.lower()
        stem = Path(path).stem.lower()
        if filename.startswith("readme"):
            continue
        if keyword_tokens and any(token in filename or token in stem for token in keyword_tokens):
            _add(path)
        if len(selected) >= MAX_CORE_FILES:
            return selected

    for path in paths:
        filename = Path(path).name.lower()
        if filename.startswith(ENTRYPOINT_PATTERNS):
            _add(path)
        if len(selected) >= MAX_CORE_FILES:
            return selected

    src_files = [path for path in paths if path.startswith("src/")]
    for path in src_files[:2]:
        _add(path)
        if len(selected) >= MAX_CORE_FILES:
            return selected

    return selected[:MAX_CORE_FILES]


def _write_snapshot_file(base_dir: Path, relative_path: str, content: str) -> None:
    target = base_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _materialize_repo_snapshot(
    repo: dict,
    profile: dict,
    repos_base_dir: Path,
    per_step_timeout: int,
) -> tuple[str | None, dict[str, float], str]:
    """Build a lightweight snapshot; fallback to full archive if README is missing."""
    full_name = repo["name"]
    safe_name = _sanitize_name(full_name)
    snapshot_dir = repos_base_dir / safe_name
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    _write_snapshot_file(
        snapshot_dir,
        "metadata.json",
        json.dumps(repo, ensure_ascii=False, indent=2),
    )

    timings = {"readme_fetch": 0.0, "snapshot_fetch": 0.0}
    readme_t0 = time.monotonic()
    readme = fetch_repo_readme(full_name)
    timings["readme_fetch"] = time.monotonic() - readme_t0

    if not readme:
        _log(f"README fetch failed for {full_name}; falling back to archive download.")
        fallback_t0 = time.monotonic()
        local_path = _download_repo(repo, repos_base_dir, per_step_timeout)
        timings["snapshot_fetch"] = time.monotonic() - fallback_t0
        return local_path, timings, "archive"

    _write_snapshot_file(snapshot_dir, "README.md", readme)

    tree_t0 = time.monotonic()
    tree = fetch_repo_tree(full_name)
    selected_files = _select_core_files(tree, profile)
    for relative_path in selected_files:
        content = fetch_repo_file(full_name, relative_path)
        if not content:
            continue
        _write_snapshot_file(snapshot_dir, relative_path, content)
    timings["snapshot_fetch"] = time.monotonic() - tree_t0
    repo["snapshot_files"] = selected_files
    return str(snapshot_dir), timings, "snapshot"


# ---------------------------------------------------------------------------
# Step 4 — extract facts
# ---------------------------------------------------------------------------

def _extract_facts(
    repo: dict,
    local_path: str,
    extractions_dir: Path,
    per_step_timeout: int,
) -> dict | None:
    """Call extract_facts.py for a local repo path or lightweight snapshot."""
    full_name: str = repo["name"]
    safe_name = _sanitize_name(full_name)
    output_dir = extractions_dir / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)
    facts_json_path = output_dir / "repo_facts.json"

    cmd = [
        sys.executable, str(EXTRACT_FACTS_SCRIPT),
        "--repo-path", local_path,
        "--output", str(facts_json_path),
        "--repo-id", safe_name,
        "--repo-url", repo.get("url", ""),
        "--repo-full-name", full_name,
    ]
    branch = repo.get("default_branch", "")
    if branch:
        cmd += ["--default-branch", branch]

    _log(f"Extracting facts for {full_name}…")
    try:
        result = _run(cmd, timeout=per_step_timeout, capture_stderr=False)
    except subprocess.TimeoutExpired:
        _log(f"extract_facts.py timed out for {full_name}.")
        return None

    if result.returncode != 0:
        _log(f"extract_facts.py failed for {full_name} (exit {result.returncode}).")
        return None

    if not facts_json_path.exists():
        _log(f"repo_facts.json not created for {full_name}.")
        return None

    try:
        raw = json.loads(facts_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"Could not parse repo_facts.json for {full_name}: {exc}")
        return None

    source_stats: dict = raw.get("source_stats", {})
    rationale: dict = raw.get("rationale_artifacts", {})
    repo_facts_inner: dict = raw.get("repo_facts", {})
    languages: list[str] = repo_facts_inner.get("languages", [])
    frameworks: list[str] = repo_facts_inner.get("frameworks", [])

    facts: dict[str, Any] = {
        "languages": languages,
        "frameworks": frameworks,
        "source_file_count": source_stats.get("source_file_count", 0),
        "source_line_count": source_stats.get("source_line_count", 0),
        "comment_density": source_stats.get("comment_density", 0.0),
        "readme_excerpt": raw.get("readme_excerpt", ""),
        "focus_files": raw.get("focus_files", []),
        "has_changelog": rationale.get("has_changelog", False),
        "has_adr": rationale.get("has_adr", False),
    }

    _log(
        f"Facts extracted for {full_name}: "
        f"{facts['source_file_count']} files, "
        f"{facts['source_line_count']} lines."
    )
    return facts


def _process_repo(
    repo: dict,
    profile: dict,
    repos_dir: Path,
    extractions_dir: Path,
    per_step_timeout: int,
) -> dict[str, Any]:
    full_name = repo["name"]
    safe_name = _sanitize_name(full_name)
    warnings: list[str] = []

    local_path, fetch_timings, source_mode = _materialize_repo_snapshot(
        repo, profile, repos_dir, per_step_timeout
    )
    if local_path is None:
        return {
            "repo": {
                "name": full_name,
                "stars": repo.get("stars", 0),
                "url": repo.get("url", ""),
                "language": repo.get("language", ""),
                "description": repo.get("description", ""),
                "relevance_score": repo.get("relevance_score", 0.0),
                "score_breakdown": repo.get("score_breakdown", {}),
                "source_mode": source_mode,
            },
            "facts": None,
            "safe_name": safe_name,
            "warnings": [f"Snapshot/download failed: {full_name}"],
            "timings": {"readme_fetch": fetch_timings["readme_fetch"], "snapshot_fetch": fetch_timings["snapshot_fetch"], "extraction": 0.0},
        }

    extract_t0 = time.monotonic()
    facts = _extract_facts(repo, local_path, extractions_dir, per_step_timeout)
    extraction_time = time.monotonic() - extract_t0

    repo_summary = {
        "name": full_name,
        "stars": repo.get("stars", 0),
        "url": repo.get("url", ""),
        "local_path": local_path,
        "language": repo.get("language", ""),
        "description": repo.get("description", ""),
        "relevance_score": repo.get("relevance_score", 0.0),
        "score_breakdown": repo.get("score_breakdown", {}),
        "source_mode": source_mode,
        "snapshot_files": repo.get("snapshot_files", []),
    }

    if facts is None:
        warnings.append(f"Fact extraction failed: {full_name}")

    return {
        "repo": repo_summary,
        "facts": facts,
        "safe_name": safe_name,
        "warnings": warnings,
        "timings": {
            "readme_fetch": fetch_timings["readme_fetch"],
            "snapshot_fetch": fetch_timings["snapshot_fetch"],
            "extraction": extraction_time,
        },
    }


# ---------------------------------------------------------------------------
# Main orchestration logic
# ---------------------------------------------------------------------------

def run(
    need_profile_path: Path,
    output_dir: Path,
    top_n: int,
    timeout_secs: int,
) -> int:
    """Orchestrate the full pipeline. Returns an OS exit code (0=ok, 1=error)."""
    wall_start = time.monotonic()

    def _remaining() -> int:
        left = timeout_secs - int(time.monotonic() - wall_start)
        return max(0, left)

    _log(f"Loading need profile from {need_profile_path}")
    if not need_profile_path.exists():
        _error_exit(f"need_profile.json not found: {need_profile_path}")

    try:
        profile: dict = json.loads(need_profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _error_exit(f"Could not parse need_profile.json: {exc}")

    keywords: list[str] = profile.get("keywords", [])
    if not keywords:
        _error_exit("need_profile.json must contain at least one keyword.")

    _log(f"Keywords: {keywords}  |  domain: {profile.get('domain', '')}  |  top_n: {top_n}")

    output_dir.mkdir(parents=True, exist_ok=True)
    repos_dir = output_dir / "repos"
    extractions_dir = output_dir / "extractions"
    for stale_dir in (repos_dir, extractions_dir):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
    repos_dir.mkdir(parents=True, exist_ok=True)
    extractions_dir.mkdir(parents=True, exist_ok=True)
    discovery_path = output_dir / "discovery.json"
    if discovery_path.exists():
        discovery_path.unlink()

    timings: dict[str, float] = {
        "search": 0.0,
        "ranking": 0.0,
        "readme_fetch": 0.0,
        "snapshot_fetch": 0.0,
        "extraction": 0.0,
    }

    search_t0 = time.monotonic()
    all_repos = _search_repos(profile, discovery_path, top_n, _remaining())
    timings["search"] = round(time.monotonic() - search_t0, 3)
    if not all_repos:
        _error_exit("github_search.py returned 0 results. Try different keywords.")

    rank_t0 = time.monotonic()
    selected = _rank_and_select_repos(all_repos, profile, top_n)
    timings["ranking"] = round(time.monotonic() - rank_t0, 3)
    if not selected:
        _error_exit(
            f"All {len(all_repos)} candidate repos were filtered out "
            f"(stars < {MIN_STARS}). Try broader keywords."
        )

    repos_summary: list[dict] = []
    facts_summary: dict[str, dict] = {}
    warnings: list[str] = []
    order = {repo["name"]: index for index, repo in enumerate(selected)}

    process_t0 = time.monotonic()
    max_workers = min(2, len(selected)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for repo in selected:
            if _remaining() < 15:
                warnings.append(
                    f"Hard timeout reached before processing all repos; "
                    f"submitted {len(futures)} tasks."
                )
                _log(warnings[-1])
                break
            per_repo_timeout = max(20, _remaining())
            future = executor.submit(
                _process_repo,
                repo,
                profile,
                repos_dir,
                extractions_dir,
                per_repo_timeout,
            )
            futures[future] = repo["name"]

        for future in as_completed(futures):
            repo_name = futures[future]
            try:
                result = future.result(timeout=max(20, _remaining()))
            except Exception as exc:  # pragma: no cover - defensive aggregation
                warnings.append(f"Repo processing failed: {repo_name} ({exc})")
                _log(warnings[-1])
                continue

            timings["readme_fetch"] += result["timings"]["readme_fetch"]
            timings["snapshot_fetch"] += result["timings"]["snapshot_fetch"]
            timings["extraction"] += result["timings"]["extraction"]
            warnings.extend(result["warnings"])
            repos_summary.append(result["repo"])
            if result["facts"] is not None:
                facts_summary[result["safe_name"]] = result["facts"]

    total_process_elapsed = time.monotonic() - process_t0
    _log(f"Processed {len(repos_summary)} repo(s) in {total_process_elapsed:.1f}s.")

    if not repos_summary:
        _error_exit("All repo snapshots/downloads failed.", warnings)

    if not facts_summary:
        _error_exit("All fact extractions failed.", warnings)

    repos_summary.sort(key=lambda repo: order.get(repo["name"], 9999))
    summary: dict[str, Any] = {
        "status": "ok",
        "repos_analyzed": len(facts_summary),
        "repos": repos_summary,
        "facts": facts_summary,
        "artifacts_dir": str(extractions_dir),
        "timings": {key: round(value, 3) for key, value in timings.items()},
        "search_mode": "api",
    }
    if warnings:
        summary["warnings"] = warnings

    summary_json_path = output_dir / "summary.json"
    try:
        summary_json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _log(f"Summary written to {summary_json_path}")
    except OSError as exc:
        _log(f"Warning: could not write summary.json: {exc}")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    elapsed = int(time.monotonic() - wall_start)
    _log(f"Done in {elapsed}s. Analysed {len(facts_summary)} repo(s).")
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Doramagic Engine: discover → snapshot/download → extract facts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--need",
        required=True,
        metavar="PATH",
        help="Path to need_profile.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="DIR",
        help="Directory where all artifacts will be written",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        metavar="N",
        help=f"Max repos to analyse (default: {DEFAULT_TOP})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=HARD_TIMEOUT_SECS,
        metavar="SECS",
        help=f"Total wall-clock timeout in seconds (default: {HARD_TIMEOUT_SECS})",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return run(
        need_profile_path=Path(args.need).expanduser().resolve(),
        output_dir=Path(args.output).expanduser().resolve(),
        top_n=args.top,
        timeout_secs=min(args.timeout, HARD_TIMEOUT_SECS),
    )


if __name__ == "__main__":
    raise SystemExit(main())
