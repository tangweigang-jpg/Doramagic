#!/usr/bin/env python3
"""Doramagic Engine — deterministic orchestrator for the discovery-to-facts pipeline.

This script chains github_search.py and extract_facts.py into a single end-to-end
workflow:

  1. Read a need_profile.json (keywords + domain + intent)
  2. Search GitHub for matching repos via github_search.py
  3. Filter candidates: stars > 30, prefer recently updated, keep top N
  4. Download each selected repo via github_search.py --download
  5. Verify extraction safety (Zip Slip prevention)
  6. Extract deterministic facts for each repo via extract_facts.py
  7. Aggregate results and write summary.json to the output directory
  8. Print summary JSON to stdout (the LLM reads this)

Usage:
    python3 doramagic_engine.py --need /path/to/need_profile.json \\
                                 --output /path/to/run_dir/ \\
                                 [--top 5] [--timeout 60]

need_profile.json format:
    {
      "keywords": ["记账", "bookkeeping", "expense tracker"],
      "domain": "finance",
      "intent": "帮我做一个记账 app"
    }

Progress messages go to stderr; the final JSON goes to stdout.
Total wall-clock timeout: 5 minutes hard cap, overridable via --timeout.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
GITHUB_SEARCH_SCRIPT = SCRIPT_DIR / "github_search.py"
EXTRACT_FACTS_SCRIPT = SCRIPT_DIR / "extract_facts.py"

MIN_STARS = 0          # repos with fewer stars are discarded
DEFAULT_TOP = 5         # how many repos to analyse when --top is not given
HARD_TIMEOUT_SECS = 300 # 5-minute wall-clock cap
RETRY_DELAY_SECS = 10   # pause before retrying a 403/429 from GitHub


# ---------------------------------------------------------------------------
# Logging helpers (stderr only so stdout stays clean for JSON)
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Print a progress message to stderr."""
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
    """Return True only if every file under target_dir resolves within it.

    Prevents Zip Slip attacks where a crafted archive escapes the target
    directory via path-traversal components (e.g. ../../etc/passwd).
    """
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
# Step 1 — search GitHub
# ---------------------------------------------------------------------------

def _search_repos(
    keywords: list[str],
    discovery_path: Path,
    top_k: int,
    per_step_timeout: int,
) -> list[dict]:
    """Call github_search.py to populate discovery_path, return parsed repo list.

    Retries once on HTTP 403/429 after RETRY_DELAY_SECS.
    """
    discovery_path.parent.mkdir(parents=True, exist_ok=True)

    # 只用前 3 个关键词搜索——太多关键词 GitHub 要求全部匹配，命中率暴跌
    search_keywords = keywords[:3]
    cmd = (
        [sys.executable, str(GITHUB_SEARCH_SCRIPT)]
        + search_keywords
        + ["--top", str(top_k * 2),   # fetch extra so filtering has room
           "--output", str(discovery_path)]
    )

    for attempt in range(2):
        _log(f"Searching GitHub (attempt {attempt + 1}): {' '.join(keywords[:3])}...")
        try:
            result = _run(cmd, timeout=per_step_timeout, capture_stderr=True)
        except subprocess.TimeoutExpired:
            _log("Search timed out.")
            return []

        # github_search.py prints the error code to stderr on HTTP errors
        stderr_lower = (result.stderr or "").lower()
        if "403" in stderr_lower or "429" in stderr_lower:
            if attempt == 0:
                _log(f"Rate-limited by GitHub API, retrying in {RETRY_DELAY_SECS}s…")
                time.sleep(RETRY_DELAY_SECS)
                continue
            else:
                _log("Still rate-limited after retry, giving up on search.")
                return []
        break  # success path

    if not discovery_path.exists():
        _log("discovery.json was not created by github_search.py")
        return []

    try:
        repos = json.loads(discovery_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"Failed to parse discovery.json: {exc}")
        return []

    if not isinstance(repos, list):
        _log("Unexpected discovery.json format (expected a list).")
        return []

    _log(f"Search returned {len(repos)} raw candidates.")
    return repos


# ---------------------------------------------------------------------------
# Step 2 — filter repos
# ---------------------------------------------------------------------------

def _filter_repos(repos: list[dict], top_n: int) -> list[dict]:
    """Keep repos with stars > MIN_STARS, sorted by stars desc, capped at top_n."""
    filtered = [r for r in repos if r.get("stars", 0) > MIN_STARS]
    # secondary sort by updated_at descending (ISO-8601 strings sort correctly)
    filtered.sort(key=lambda r: (r.get("stars", 0), r.get("updated_at", "")), reverse=True)
    selected = filtered[:top_n]
    _log(
        f"Filtered {len(repos)} → {len(filtered)} (stars>{MIN_STARS}), "
        f"selected top {len(selected)}."
    )
    return selected


# ---------------------------------------------------------------------------
# Step 3 — download repos
# ---------------------------------------------------------------------------

def _sanitize_name(full_name: str) -> str:
    """Convert 'owner/repo' to 'owner-repo' for safe filesystem use."""
    return full_name.replace("/", "-").replace(" ", "_")


def _download_repo(
    repo: dict,
    repos_base_dir: Path,
    per_step_timeout: int,
) -> str | None:
    """Download a repo via github_search.py --download.

    Returns the local extracted directory path, or None on failure.
    Retries once on 403/429.
    """
    full_name: str = repo["name"]
    branch: str = repo.get("default_branch", "main")
    safe_name = _sanitize_name(full_name)
    dest_dir = repos_base_dir / safe_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(GITHUB_SEARCH_SCRIPT),
        "--download", full_name,
        "--branch", branch,
        "--output", str(dest_dir),
    ]

    for attempt in range(2):
        _log(f"Downloading {full_name} (attempt {attempt + 1})…")
        try:
            result = _run(cmd, timeout=per_step_timeout, capture_stderr=True)
        except subprocess.TimeoutExpired:
            _log(f"Download of {full_name} timed out.")
            return None

        stderr_lower = (result.stderr or "").lower()
        stdout_text = (result.stdout or "").strip()

        if "403" in stderr_lower or "429" in stderr_lower:
            if attempt == 0:
                _log(f"Rate-limited while downloading {full_name}, retrying in {RETRY_DELAY_SECS}s…")
                time.sleep(RETRY_DELAY_SECS)
                continue
            else:
                _log(f"Still rate-limited for {full_name}, skipping.")
                return None

        # github_search.py prints {"status": "ok", "repo_dir": "..."} to stdout
        try:
            data = json.loads(stdout_text)
            if data.get("status") == "ok" and data.get("repo_dir"):
                repo_dir = data["repo_dir"]
                break
            else:
                _log(f"Unexpected download response for {full_name}: {stdout_text[:200]}")
                return None
        except (json.JSONDecodeError, TypeError):
            _log(f"Could not parse download response for {full_name}: {stdout_text[:200]}")
            return None
    else:
        return None

    # Safety: verify no Zip Slip escape
    extracted_path = Path(repo_dir)
    if not extracted_path.exists():
        _log(f"Extracted path does not exist: {repo_dir}")
        return None

    if not _verify_safe_extraction(extracted_path):
        _log(f"SECURITY: Zip Slip detected in {full_name}, skipping repo.")
        return None

    _log(f"Downloaded {full_name} → {repo_dir}")
    return repo_dir


# ---------------------------------------------------------------------------
# Step 4 — extract facts
# ---------------------------------------------------------------------------

def _extract_facts(
    repo: dict,
    local_path: str,
    extractions_dir: Path,
    per_step_timeout: int,
) -> dict | None:
    """Call extract_facts.py for a downloaded repo.

    Returns the parsed facts dict, or None on failure.
    """
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

    # Build the compact facts block expected by the output schema.
    source_stats: dict = raw.get("source_stats", {})
    rationale: dict = raw.get("rationale_artifacts", {})
    repo_facts_inner: dict = raw.get("repo_facts", {})

    # languages come from extract_facts's repo_facts payload
    languages: list[str] = repo_facts_inner.get("languages", [])
    # frameworks may also live there
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
        """Seconds left before the hard timeout fires. Returns 0 when exhausted."""
        left = timeout_secs - int(time.monotonic() - wall_start)
        return max(0, left)

    # ------------------------------------------------------------------
    # 0. Load need_profile.json
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Prepare directory layout
    # ------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    repos_dir = output_dir / "repos"
    extractions_dir = output_dir / "extractions"
    # Clean stale artifacts from previous runs to avoid nondeterministic results
    for stale_dir in (repos_dir, extractions_dir):
        if stale_dir.exists():
            import shutil
            shutil.rmtree(stale_dir)
    repos_dir.mkdir(parents=True, exist_ok=True)
    extractions_dir.mkdir(parents=True, exist_ok=True)
    discovery_path = output_dir / "discovery.json"
    if discovery_path.exists():
        discovery_path.unlink()

    # ------------------------------------------------------------------
    # 1. Search
    # ------------------------------------------------------------------
    all_repos = _search_repos(keywords, discovery_path, top_n, _remaining())
    if not all_repos:
        _error_exit("github_search.py returned 0 results. Try different keywords.")

    # ------------------------------------------------------------------
    # 2. Filter
    # ------------------------------------------------------------------
    selected = _filter_repos(all_repos, top_n)
    if not selected:
        _error_exit(
            f"All {len(all_repos)} candidate repos were filtered out "
            f"(stars ≤ {MIN_STARS}). Try broader keywords."
        )

    # ------------------------------------------------------------------
    # 3+4. Download and extract, collecting results
    # ------------------------------------------------------------------
    repos_summary: list[dict] = []
    facts_summary: dict[str, dict] = {}
    warnings: list[str] = []

    for repo in selected:
        if _remaining() < 15:
            warnings.append(
                f"Hard timeout reached; skipped remaining repos after "
                f"{len(repos_summary)} completed."
            )
            _log(warnings[-1])
            break

        full_name: str = repo["name"]
        safe_name = _sanitize_name(full_name)

        # Download
        local_path = _download_repo(repo, repos_dir, _remaining())
        if local_path is None:
            warnings.append(f"Download failed: {full_name}")
            continue

        # Extract facts
        facts = _extract_facts(repo, local_path, extractions_dir, _remaining())
        if facts is None:
            warnings.append(f"Fact extraction failed: {full_name}")
            # Still record the repo with empty facts so the caller knows we tried
            repos_summary.append({
                "name": full_name,
                "stars": repo.get("stars", 0),
                "url": repo.get("url", ""),
                "local_path": local_path,
                "language": repo.get("language", ""),
                "description": repo.get("description", ""),
            })
            continue

        repos_summary.append({
            "name": full_name,
            "stars": repo.get("stars", 0),
            "url": repo.get("url", ""),
            "local_path": local_path,
            "language": repo.get("language", ""),
            "description": repo.get("description", ""),
        })
        facts_summary[safe_name] = facts

    # ------------------------------------------------------------------
    # Check viability of results
    # ------------------------------------------------------------------
    if not repos_summary:
        _error_exit("All repo downloads failed.", warnings)

    if not facts_summary:
        _error_exit("All fact extractions failed.", warnings)

    # ------------------------------------------------------------------
    # 5. Assemble summary
    # ------------------------------------------------------------------
    summary: dict[str, Any] = {
        "status": "ok",
        "repos_analyzed": len(facts_summary),
        "repos": repos_summary,
        "facts": facts_summary,
        "artifacts_dir": str(extractions_dir),
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

    # ------------------------------------------------------------------
    # 6. Print summary JSON to stdout for the LLM
    # ------------------------------------------------------------------
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    elapsed = int(time.monotonic() - wall_start)
    _log(f"Done in {elapsed}s. Analysed {len(facts_summary)} repo(s).")
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Doramagic Engine: discover → download → extract facts",
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
