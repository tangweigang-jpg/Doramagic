"""Knowledge source type detector for repository analysis.

Scans a repository to determine what types of knowledge sources it contains:
- code: Python/TypeScript/Go/Rust/Java source files with business logic
- document: SKILL.md, CLAUDE.md, AGENTS.md, skills/ directory
- config: hooks.json, settings.json, YAML/TOML config with behavior rules

A single project can have multiple knowledge source types (spectrum, not binary).
The detection result drives strategy routing in the extraction pipeline:
- code → Step 2a (reverse engineering)
- document → Step 2a-s (structural extraction)
- both → parallel execution, merged with conflict resolution

Design reference: Blueprint extraction SOP v3.6, Step 0a.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "dist",
    "build",
}

# Code source indicators
_CODE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".java", ".kt", ".scala"}

# Document source indicators (file names, case-insensitive)
_DOC_FILENAMES = {
    "skill.md",
    "claude.md",
    "agents.md",
    "gemini.md",
    "cursorrules",
    ".cursorrules",
}

# Document source directories
_DOC_DIRECTORIES = {"skills", ".claude"}

# Config source indicators
_CONFIG_FILENAMES = {"hooks.json", "settings.json", "manifest.json"}
_CONFIG_EXTENSIONS = {".yaml", ".yml", ".toml", ".tf"}

# Eval source indicators
_EVAL_PATTERNS = {"evals.json", "eval", "benchmark"}


def detect_knowledge_sources(repo_path: Path) -> dict:
    """Detect knowledge source types present in a repository.

    Returns:
        {
            "knowledge_sources": ["code", "document", ...],
            "code_files_count": int,
            "document_files": ["skills/debugging/SKILL.md", ...],
            "config_files": ["hooks.json", ...],
            "eval_files": ["evals/evals.json", ...],
            "skill_directories": ["skills/debugging", ...],
        }
    """
    repo_root = repo_path.resolve()
    if not repo_root.is_dir():
        logger.warning("repo_path is not a directory: %s", repo_root)
        return {
            "knowledge_sources": [],
            "code_files_count": 0,
            "document_files": [],
            "config_files": [],
            "eval_files": [],
            "skill_directories": [],
        }

    code_count = 0
    document_files: list[str] = []
    config_files: list[str] = []
    eval_files: list[str] = []
    skill_directories: list[str] = []

    for fpath in repo_root.rglob("*"):
        if not fpath.is_file():
            continue

        # Skip hidden/build dirs
        rel_parts = fpath.relative_to(repo_root).parts
        if any(
            (part.startswith(".") and part not in (".claude", ".cursorrules"))
            or part in _SKIP_DIRS
            or part.endswith(".egg-info")
            for part in rel_parts
        ):
            continue

        rel = str(fpath.relative_to(repo_root))
        name_lower = fpath.name.lower()
        suffix = fpath.suffix.lower()

        # Code detection
        if suffix in _CODE_EXTENSIONS:
            code_count += 1

        # Document detection — specific filenames
        if name_lower in _DOC_FILENAMES:
            document_files.append(rel)

        # Document detection — prompt files
        if suffix in (".md",) and "prompt" in name_lower:
            document_files.append(rel)

        # Config detection — specific filenames
        if name_lower in _CONFIG_FILENAMES:
            config_files.append(rel)

        # Config detection — YAML/TOML with behavior content
        if suffix in _CONFIG_EXTENSIONS and name_lower not in (
            "pyproject.toml",
            "setup.cfg",
            "package.json",
        ):
            config_files.append(rel)

        # Eval detection
        if name_lower == "evals.json" or ("eval" in name_lower and suffix == ".json"):
            eval_files.append(rel)

    # Skill directory detection
    for dir_name in _DOC_DIRECTORIES:
        candidate = repo_root / dir_name
        if candidate.is_dir():
            # Find skill subdirectories (each containing SKILL.md)
            for skill_md in candidate.rglob("SKILL.md"):
                skill_dir = str(skill_md.parent.relative_to(repo_root))
                skill_directories.append(skill_dir)
            # Also check for agent definitions
            for agent_md in candidate.rglob("*.md"):
                if agent_md.name.lower() not in _DOC_FILENAMES:
                    rel = str(agent_md.relative_to(repo_root))
                    if rel not in document_files:
                        document_files.append(rel)

    # Classify knowledge source types
    sources: list[str] = []
    if code_count >= 3:  # At least a few code files with logic
        sources.append("code")
    if document_files or skill_directories:
        sources.append("document")
    if config_files:
        sources.append("config")

    result = {
        "knowledge_sources": sources,
        "code_files_count": code_count,
        "document_files": sorted(document_files)[:50],
        "config_files": sorted(config_files)[:20],
        "eval_files": sorted(eval_files)[:10],
        "skill_directories": sorted(skill_directories)[:50],
    }

    logger.info(
        "Knowledge sources: %s (code=%d, doc=%d, config=%d, skills=%d)",
        sources,
        code_count,
        len(document_files),
        len(config_files),
        len(skill_directories),
    )
    return result
