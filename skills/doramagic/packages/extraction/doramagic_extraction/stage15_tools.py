"""Stage 1.5 tool implementations and formatting helpers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from doramagic_contracts.base import EvidenceRef
from doramagic_contracts.extraction import Stage1Finding, Stage15AgenticInput

from .stage15_config import _MAX_SEARCH_OUTPUT_BYTES, _MAX_SNIPPET_LINES, _MAX_TREE_ENTRIES


def _tool_list_tree(repo_root: Path, tool_input: dict) -> str:
    """List directory tree of the repository."""
    rel_path = tool_input.get("path", ".")
    target = (repo_root / rel_path).resolve()
    # Safety: don't escape the repo root
    try:
        target.relative_to(repo_root)
    except ValueError:
        return "ERROR: path escapes repository root"

    if not target.exists():
        return f"Directory not found: {rel_path}"

    entries: list[str] = []
    try:
        for item in sorted(target.rglob("*")):
            rel = item.relative_to(repo_root)
            if any(part.startswith(".") for part in rel.parts):
                continue  # skip hidden dirs
            if any(
                part in ("node_modules", "__pycache__", ".git", "dist", "build")
                for part in rel.parts
            ):
                continue
            prefix = "  " * (len(rel.parts) - 1)
            suffix = "/" if item.is_dir() else ""
            entries.append(f"{prefix}{item.name}{suffix}")
            if len(entries) >= _MAX_TREE_ENTRIES:
                entries.append("... (truncated)")
                break
    except PermissionError as exc:
        return f"Permission error listing tree: {exc}"

    return "\n".join(entries) if entries else "(empty directory)"


def _tool_search_repo(repo_root: Path, tool_input: dict) -> str:
    """Grep the repository for a pattern."""
    pattern = tool_input.get("pattern", "")
    file_glob = tool_input.get("file_glob") or "*"
    max_results = min(int(tool_input.get("max_results", 10)), 20)

    if not pattern:
        return "ERROR: pattern is required for search_repo"

    if not repo_root.exists():
        # Fallback: can't search a non-existent repo
        return f"Repository not found at: {repo_root}"

    try:
        cmd = [
            "grep",
            "-rn",
            f"--include={file_glob}",
            "-m",
            str(max_results),
            pattern,
            str(repo_root),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout or result.stderr or "(no matches)"
        # Trim absolute path prefix so output is relative
        output = output.replace(str(repo_root) + "/", "")
        return output[:_MAX_SEARCH_OUTPUT_BYTES]
    except subprocess.TimeoutExpired:
        return "ERROR: search timed out"
    except FileNotFoundError:
        # grep not available; try Python fallback
        return _python_grep(repo_root, pattern, file_glob, max_results)
    except Exception as exc:
        return f"ERROR: search failed: {exc}"


def _python_grep(repo_root: Path, pattern: str, file_glob: str, max_results: int) -> str:
    """Python-based grep fallback when system grep is unavailable."""
    results: list[str] = []
    try:
        if len(pattern) > 200:
            return "ERROR: pattern too long (max 200 chars)"
        regex = re.compile(pattern)
    except re.error as exc:
        return f"ERROR: invalid regex pattern: {exc}"

    glob = f"**/{file_glob}" if file_glob != "*" else "**/*"
    try:
        for file_path in sorted(repo_root.rglob(glob.replace("**/", ""))):
            if not file_path.is_file():
                continue
            if any(p.startswith(".") for p in file_path.parts):
                continue
            try:
                lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                for lineno, line in enumerate(lines, 1):
                    if regex.search(line):
                        rel = file_path.relative_to(repo_root)
                        results.append(f"{rel}:{lineno}: {line.rstrip()}")
                        if len(results) >= max_results:
                            return "\n".join(results)
            except (PermissionError, OSError):
                continue
    except Exception:
        pass

    return "\n".join(results) if results else "(no matches)"


def _tool_read_file(repo_root: Path, tool_input: dict) -> tuple[str, EvidenceRef | None]:
    """Read a file or line range from the repository.

    Returns (observation_text, evidence_ref_or_None).
    """
    rel_path = tool_input.get("path")
    if not rel_path:
        return "ERROR: path is required for read_file", None

    target = (repo_root / rel_path).resolve()
    try:
        target.relative_to(repo_root)
    except ValueError:
        return "ERROR: path escapes repository root", None

    if not target.exists():
        return f"File not found: {rel_path}", None

    try:
        all_lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    except (PermissionError, OSError) as exc:
        return f"ERROR reading file: {exc}", None

    start_line = tool_input.get("start_line")
    end_line = tool_input.get("end_line")

    if start_line is not None:
        start_idx = max(0, int(start_line) - 1)
        end_idx = min(len(all_lines), int(end_line) if end_line else start_idx + _MAX_SNIPPET_LINES)
    else:
        start_idx = 0
        end_idx = min(len(all_lines), _MAX_SNIPPET_LINES)

    # Clamp range
    if end_idx - start_idx > _MAX_SNIPPET_LINES:
        end_idx = start_idx + _MAX_SNIPPET_LINES

    snippet_lines = all_lines[start_idx:end_idx]
    snippet = "\n".join(f"{start_idx + i + 1}: {line}" for i, line in enumerate(snippet_lines))
    summary = f"Read {len(snippet_lines)} lines ({start_idx + 1}-{start_idx + len(snippet_lines)}) from {rel_path}:\n{snippet}"

    actual_start = start_idx + 1
    actual_end = start_idx + len(snippet_lines)
    if actual_end < actual_start:
        actual_end = actual_start  # guard against empty range

    evidence = EvidenceRef(
        kind="file_line",
        path=str(rel_path),
        start_line=actual_start,
        end_line=actual_end,
        snippet="\n".join(snippet_lines[:5]),  # keep snippet concise
    )
    return summary, evidence


def _tool_read_artifact(
    findings: list[Stage1Finding],
    tool_input: dict,
) -> str:
    """Return Stage 1 findings as formatted text."""
    related_ids = tool_input.get("related_finding_ids") or []
    if related_ids:
        selected = [f for f in findings if f.finding_id in related_ids]
    else:
        selected = findings

    if not selected:
        return "No Stage 1 findings available for: {0}".format(related_ids or "all")

    parts = []
    for finding in selected:
        parts.append(f"[{finding.knowledge_type}] {finding.finding_id}: {finding.title}")
        parts.append(f"Statement: {finding.statement}")
        parts.append(f"Confidence: {finding.confidence}")
        for ref in finding.evidence_refs:
            if ref.kind == "file_line":
                parts.append(f"Evidence: {ref.path}:{ref.start_line}-{ref.end_line}")
                if ref.snippet:
                    parts.append(f"  Snippet: {ref.snippet[:200]}")
        parts.append("")
    return "\n".join(parts)


def _format_history(steps: list[tuple[str, str, str, str]]) -> str:
    """Format exploration history as a readable string.

    Each tuple is (step_id, tool_name, tool_input_json, observation).
    """
    if not steps:
        return "(no prior steps for this hypothesis)"
    lines = []
    for step_id, tool_name, tool_input_str, observation in steps:
        lines.append(f"Step {step_id}: {tool_name}({tool_input_str[:200]})")
        lines.append(f"  → {observation[:300]}")
    return "\n".join(lines)


def _format_repo_context(input_data: Stage15AgenticInput) -> str:
    facts = input_data.repo_facts
    return (
        "Repo: {repo_id}\n"
        "Languages: {langs}\n"
        "Frameworks: {fw}\n"
        "Entrypoints: {ep}\n"
        "Dependencies: {deps}\n"
        "Summary: {summary}"
    ).format(
        repo_id=input_data.repo.repo_id,
        langs=", ".join(facts.languages),
        fw=", ".join(facts.frameworks),
        ep=", ".join(facts.entrypoints),
        deps=", ".join(facts.dependencies[:10]),
        summary=facts.repo_summary[:300],
    )


def _parse_search_evidence(grep_output: str, repo_root: Path) -> list[EvidenceRef]:
    """Extract file:line evidence from grep output lines."""
    refs: list[EvidenceRef] = []
    pattern = re.compile(r"^(.+?):(\d+):\s*(.*)$")
    seen: set = set()
    for line in grep_output.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        rel_path, lineno_str, snippet = m.group(1), m.group(2), m.group(3)
        try:
            lineno = int(lineno_str)
        except ValueError:
            continue
        key = f"{rel_path}:{lineno}"
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            EvidenceRef(
                kind="file_line",
                path=rel_path,
                start_line=lineno,
                end_line=lineno,
                snippet=snippet.strip()[:200],
            )
        )
        if len(refs) >= 3:
            break
    return refs
