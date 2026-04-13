"""Multi-source knowledge miner for non-code repository artifacts.

Reads README, docs/, CHANGELOG, pyproject.toml/setup.py, and recent git
commits to produce a structured ``source_context.md`` that supplements
the AST structural index with human-written context.

Design reference: CoMRAT (MSR 2025) — commit message design rationale.
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Size limits to keep source_context.md within a reasonable token budget.
# All limits are INCLUSIVE of any truncation markers or wrapper text.
# ---------------------------------------------------------------------------

_README_MAX_CHARS = 3000
_CHANGELOG_MAX_CHARS = 3000
_DOC_FILE_MAX_CHARS = 1000
_DOC_TOTAL_MAX_CHARS = 5000
_MAX_DOC_FILES = 8
_GIT_LOG_MAX_ENTRIES = 20
_DEPS_MAX_ENTRIES = 30
_FILE_READ_LIMIT = 50_000  # max bytes to read from any single file


# ---------------------------------------------------------------------------
# Safe file reading helper
# ---------------------------------------------------------------------------


def _safe_read(filepath: Path, repo_root: Path, max_chars: int) -> str | None:
    """Read a text file safely within the repo root.

    Returns file content (truncated to max_chars) or None if the file
    should be skipped (symlink escape, binary, permission error, too large).
    """
    try:
        resolved = filepath.resolve(strict=True)
    except OSError:
        return None

    # Reject symlinks that escape the repo root
    if not resolved.is_relative_to(repo_root):
        logger.warning("Skipping symlink escape: %s -> %s", filepath, resolved)
        return None

    if not resolved.is_file():
        return None

    try:
        # Size-limited read: only read what we need + 1 char for truncation detection
        with resolved.open(encoding="utf-8", errors="ignore") as fh:
            content = fh.read(max_chars + 1)
    except OSError:
        return None

    if len(content) > max_chars:
        return content[:max_chars]
    return content


# ---------------------------------------------------------------------------
# Individual source miners
# ---------------------------------------------------------------------------


def _mine_readme(repo_root: Path) -> str:
    """Extract content from README files."""
    candidates = [
        "README.md", "README.rst", "README.txt", "README",
        "README-en.md", "readme.md",
    ]
    for name in candidates:
        readme = repo_root / name
        if readme.exists():
            content = _safe_read(readme, repo_root, _README_MAX_CHARS)
            if content is None:
                continue
            truncated = len(content) >= _README_MAX_CHARS
            suffix = "\n\n... (truncated)" if truncated else ""
            return f"## Project Overview (from {name})\n\n{content}{suffix}"
    return ""


def _mine_docs(repo_root: Path) -> str:
    """Extract summaries from docs/ directory."""
    docs_dir = repo_root / "docs"
    if not docs_dir.is_dir():
        docs_dir = repo_root / "doc"
        if not docs_dir.is_dir():
            return ""

    md_files: list[Path] = []
    for ext in ("*.md", "*.rst", "*.txt"):
        md_files.extend(docs_dir.rglob(ext))

    # Filter out build artifacts, hidden files, and symlink escapes
    safe_files: list[Path] = []
    for f in md_files:
        try:
            rel_parts = f.relative_to(docs_dir).parts
        except ValueError:
            continue
        if any(p.startswith(".") or p in ("_build", "build")
               for p in rel_parts):
            continue
        safe_files.append(f)

    # Sort by size (largest first) to prioritize substantial docs
    try:
        safe_files.sort(key=lambda f: f.stat().st_size, reverse=True)
    except OSError:
        safe_files.sort()

    if not safe_files:
        return ""

    sections: list[str] = []
    sections.append(f"## Documentation (from docs/, {len(safe_files)} files)")

    total_chars = 0
    included = 0
    for doc_file in safe_files[:_MAX_DOC_FILES]:
        remaining_budget = _DOC_TOTAL_MAX_CHARS - total_chars
        if remaining_budget <= 100:
            break
        read_limit = min(_DOC_FILE_MAX_CHARS, remaining_budget)
        content = _safe_read(doc_file, repo_root, read_limit)
        if content is None:
            continue
        try:
            rel = doc_file.relative_to(repo_root)
        except ValueError:
            continue
        truncated = len(content) >= read_limit
        suffix = "\n... (truncated)" if truncated else ""
        sections.append(f"\n### {rel}\n\n{content}{suffix}")
        total_chars += len(content)
        included += 1

    if len(safe_files) > included:
        remaining = [
            str(f.relative_to(repo_root))
            for f in safe_files[included:]
            if f.is_relative_to(repo_root)
        ]
        if remaining:
            sections.append(
                f"\n### Other doc files ({len(remaining)})\n"
                + "\n".join(f"- {r}" for r in remaining[:20])
            )

    return "\n".join(sections)


def _mine_changelog(repo_root: Path) -> str:
    """Extract evolution history from CHANGELOG."""
    candidates = [
        "CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG.txt",
        "CHANGELOG", "CHANGES.md", "CHANGES.rst", "HISTORY.md",
        "RELEASES.md", "NEWS.md",
    ]
    for name in candidates:
        changelog = repo_root / name
        if changelog.exists():
            content = _safe_read(changelog, repo_root, _CHANGELOG_MAX_CHARS)
            if content is None:
                continue
            truncated = len(content) >= _CHANGELOG_MAX_CHARS
            suffix = "\n\n... (truncated)" if truncated else ""
            return f"## Evolution History (from {name})\n\n{content}{suffix}"
    return ""


def _mine_dependencies(repo_root: Path) -> str:
    """Extract dependency declarations from pyproject.toml or setup.py."""
    sections: list[str] = []

    # Try tomllib first (Python 3.11+), fall back to regex
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        content = _safe_read(pyproject, repo_root, _FILE_READ_LIMIT)
        if content:
            deps = _parse_toml_deps(content)
            if deps:
                sections.append("## Dependencies (from pyproject.toml)")
                for d in deps[:_DEPS_MAX_ENTRIES]:
                    sections.append(f"- {d}")
                if len(deps) > _DEPS_MAX_ENTRIES:
                    sections.append(
                        f"- ... and {len(deps) - _DEPS_MAX_ENTRIES} more"
                    )

    # setup.py fallback
    if not sections:
        setup_py = repo_root / "setup.py"
        if setup_py.exists():
            content = _safe_read(setup_py, repo_root, _FILE_READ_LIMIT)
            if content:
                match = re.search(
                    r'install_requires\s*=\s*\[(.*?)\]',
                    content, re.DOTALL,
                )
                if match:
                    deps = re.findall(
                        r'["\']([^"\']+)["\']', match.group(1),
                    )
                    if deps:
                        sections.append("## Dependencies (from setup.py)")
                        for d in deps[:_DEPS_MAX_ENTRIES]:
                            sections.append(f"- {d}")

    return "\n".join(sections)


def _parse_toml_deps(content: str) -> list[str]:
    """Parse dependencies from pyproject.toml content.

    Tries tomllib (Python 3.11+) first, falls back to regex.
    """
    try:
        import tomllib
        data = tomllib.loads(content)
        return list(data.get("project", {}).get("dependencies", []))
    except (ImportError, Exception):
        pass

    # Regex fallback: extract dependencies = [...] block
    deps: list[str] = []
    in_deps = False
    for line in content.splitlines():
        if re.match(r'\s*dependencies\s*=\s*\[', line):
            in_deps = True
            # Check if closing bracket is on the same line
            inline = re.findall(r'["\']([^"\']+)["\']', line)
            deps.extend(inline)
            if "]" in line:
                in_deps = False
            continue
        if in_deps:
            if "]" in line:
                inline = re.findall(r'["\']([^"\']+)["\']', line)
                deps.extend(inline)
                in_deps = False
            else:
                dep = re.findall(r'["\']([^"\']+)["\']', line)
                deps.extend(dep)
    return deps


def _mine_git_log(repo_root: Path) -> str:
    """Extract recent commit messages for design rationale context."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={_GIT_LOG_MAX_ENTRIES}",
             "--format=%h %s"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""

    lines = result.stdout.strip().splitlines()
    if not lines:
        return ""

    sections = [f"## Recent Commits ({len(lines)} entries)"]
    for line in lines:
        sections.append(f"- {line}")
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def mine_source_context(repo_path: Path) -> str:
    """Mine all non-code sources and produce a structured source_context.md.

    Returns the full Markdown content ready to be saved as an artifact.
    """
    repo_root = repo_path.resolve()
    parts: list[str] = []

    parts.append("# Source Context — Non-Code Knowledge\n")
    parts.append(
        "> Auto-generated from README, docs, CHANGELOG, dependencies, "
        "and git history.\n"
        "> Use this context to understand project intent, evolution, "
        "and constraints.\n"
    )

    miners = [
        _mine_readme,
        _mine_docs,
        _mine_changelog,
        _mine_dependencies,
        _mine_git_log,
    ]

    for miner in miners:
        try:
            section = miner(repo_root)
            if section:
                parts.append(section)
                parts.append("")  # blank line between sections
        except Exception as exc:
            logger.warning("Source miner %s failed: %s", miner.__name__, exc)

    content = "\n".join(parts)
    logger.info(
        "Source context mined: %d chars, %d sections",
        len(content),
        sum(1 for p in parts if p.startswith("## ")),
    )
    return content
