#!/usr/bin/env python3
"""Doramagic S2 deterministic repo fact extraction."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _pkg in ("contracts", "shared_utils", "extraction", "orchestration"):
    _p = str(PROJECT_ROOT / "packages" / _pkg)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from doramagic_extraction.stage0 import extract_repo_facts  # noqa: E402

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    "target",
    ".gradle",
}

FOCUS_FILE_CANDIDATES = [
    "README.md",
    "README.rst",
    "docs/README.md",
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "build.gradle",
    "settings.gradle",
    "app/build.gradle",
    "app/src/main/AndroidManifest.xml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "main.py",
    "app.py",
    "manage.py",
    "src/main.py",
    "src/index.ts",
    "src/index.js",
    "server.py",
    "server.js",
]

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".sh",
}

LINE_COMMENT_PREFIXES = {
    ".py": "#",
    ".rb": "#",
    ".sh": "#",
    ".yml": "#",
    ".yaml": "#",
    ".toml": "#",
    ".js": "//",
    ".jsx": "//",
    ".ts": "//",
    ".tsx": "//",
    ".java": "//",
    ".kt": "//",
    ".go": "//",
    ".rs": "//",
    ".php": "//",
    ".swift": "//",
    ".c": "//",
    ".cc": "//",
    ".cpp": "//",
    ".h": "//",
    ".hpp": "//",
    ".cs": "//",
}

BLOCK_COMMENT_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".php",
    ".swift",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
}


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _readme_excerpt(repo_path: Path, max_lines: int = 30, max_chars: int = 2400) -> str:
    readme = _first_existing(
        [
            repo_path / "README.md",
            repo_path / "README.rst",
            repo_path / "readme.md",
            repo_path / "Readme.md",
        ]
    )
    if readme is None:
        return ""
    try:
        lines = readme.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    excerpt_lines = []
    total_chars = 0
    for line in lines:
        stripped = line.rstrip()
        if not stripped and not excerpt_lines:
            continue
        excerpt_lines.append(stripped)
        total_chars += len(stripped)
        if len(excerpt_lines) >= max_lines or total_chars >= max_chars:
            break
    return "\n".join(excerpt_lines).strip()


def _top_level_entries(repo_path: Path) -> list[str]:
    entries = []
    for entry in sorted(repo_path.iterdir(), key=lambda item: item.name.lower()):
        if entry.name.startswith("."):
            continue
        entries.append(entry.name + ("/" if entry.is_dir() else ""))
    return entries[:40]


def _focus_files(repo_path: Path) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for candidate in FOCUS_FILE_CANDIDATES:
        path = repo_path / candidate
        if path.exists() and path.is_file():
            rel = path.relative_to(repo_path).as_posix()
            found.append(rel)
            seen.add(rel)

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".")]
        rel_root = Path(root).relative_to(repo_path)
        for filename in sorted(files):
            if filename.startswith("."):
                continue
            rel = (rel_root / filename).as_posix()
            if rel in seen:
                continue
            if filename in {"models.py", "views.py", "urls.py", "api.py", "settings.py"}:
                found.append(rel)
                seen.add(rel)
            if filename in {"MainActivity.java", "MainActivity.kt"}:
                if rel not in seen:
                    found.append(rel)
                    seen.add(rel)
            if rel not in seen and filename.endswith(("Activity.java", "Activity.kt", "Fragment.java", "Fragment.kt")):
                found.append(rel)
                seen.add(rel)
            if len(found) >= 24:
                return found
    return found


def _license_files(repo_path: Path) -> list[str]:
    results = []
    for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]:
        path = repo_path / name
        if path.exists() and path.is_file():
            results.append(path.relative_to(repo_path).as_posix())
    return results


def _iter_files(repo_path: Path, extensions: set[str] | None = None) -> Iterable[Path]:
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue
            path = Path(root) / filename
            if extensions is not None and path.suffix.lower() not in extensions:
                continue
            yield path


def _source_stats(repo_path: Path) -> dict[str, int | float]:
    source_file_count = 0
    source_line_count = 0
    comment_line_count = 0

    for path in _iter_files(repo_path, SOURCE_EXTENSIONS):
        source_file_count += 1
        suffix = path.suffix.lower()
        line_prefix = LINE_COMMENT_PREFIXES.get(suffix)
        in_block_comment = False
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for line in lines:
            source_line_count += 1
            stripped = line.strip()
            if not stripped:
                continue
            if suffix in BLOCK_COMMENT_EXTENSIONS:
                if in_block_comment:
                    comment_line_count += 1
                    if "*/" in stripped:
                        in_block_comment = False
                    continue
                if stripped.startswith("/*"):
                    comment_line_count += 1
                    if "*/" not in stripped:
                        in_block_comment = True
                    continue
                if stripped.startswith("*"):
                    comment_line_count += 1
                    continue
            if line_prefix and stripped.startswith(line_prefix):
                comment_line_count += 1

    comment_density = round(comment_line_count / source_line_count, 4) if source_line_count else 0.0
    return {
        "source_file_count": source_file_count,
        "source_line_count": source_line_count,
        "comment_line_count": comment_line_count,
        "comment_density": comment_density,
    }


def _rationale_artifacts(repo_path: Path) -> dict[str, object]:
    readme_files: list[str] = []
    adr_files: list[str] = []
    changelog_files: list[str] = []
    decision_docs: list[str] = []
    why_hint_files: list[str] = []

    why_pattern = re.compile(r"\b(why|motivation|philosophy|rationale|trade[- ]off|by design|won't implement)\b", re.I)

    for path in _iter_files(repo_path):
        rel = path.relative_to(repo_path).as_posix()
        name = path.name.lower()
        rel_lower = rel.lower()

        if name.startswith("readme"):
            readme_files.append(rel)
        if "adr" in rel_lower or name.startswith("adr-") or "/decisions/" in rel_lower:
            adr_files.append(rel)
        if name.startswith("changelog") or name.startswith("history") or name.startswith("releases"):
            changelog_files.append(rel)
        if "decision" in rel_lower or "architecture" in rel_lower or "design" in rel_lower:
            decision_docs.append(rel)

        if path.suffix.lower() in {".md", ".rst", ".txt"} and (
            name.startswith("readme") or "docs/" in rel_lower or name.startswith("changelog")
        ):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if why_pattern.search(text):
                why_hint_files.append(rel)

    return {
        "readme_files": sorted(readme_files)[:10],
        "adr_files": sorted(adr_files)[:20],
        "changelog_files": sorted(changelog_files)[:10],
        "decision_docs": sorted(set(decision_docs))[:20],
        "why_hint_files": sorted(set(why_hint_files))[:20],
        "has_readme": bool(readme_files),
        "has_adr": bool(adr_files),
        "has_changelog": bool(changelog_files),
        "has_explicit_why_hint": bool(why_hint_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract deterministic repo facts for Doramagic S2")
    parser.add_argument("--repo-path", required=True, help="Path to extracted repository")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--repo-id", default="", help="Optional repo_id override")
    parser.add_argument("--repo-full-name", default="", help="Optional full_name override, e.g. owner/repo")
    parser.add_argument("--repo-url", default="", help="Optional GitHub URL override")
    parser.add_argument("--default-branch", default="", help="Optional default branch override")
    parser.add_argument("--commit-sha", default="", help="Optional commit SHA override")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        print("repo path not found: {0}".format(repo_path), file=sys.stderr)
        return 1

    repo_facts = extract_repo_facts(str(repo_path))
    payload = repo_facts.model_dump() if hasattr(repo_facts, "model_dump") else repo_facts.dict()

    repo_payload = dict(payload["repo"])
    if args.repo_id:
        repo_payload["repo_id"] = args.repo_id
    if args.repo_full_name:
        repo_payload["full_name"] = args.repo_full_name
    if args.repo_url:
        repo_payload["url"] = args.repo_url
    if args.default_branch:
        repo_payload["default_branch"] = args.default_branch
    if args.commit_sha:
        repo_payload["commit_sha"] = args.commit_sha
    payload["repo"] = repo_payload

    result = {
        "schema_version": "dm.s2.repo-facts-bundle.v2",
        "repo_facts": payload,
        "top_level_entries": _top_level_entries(repo_path),
        "focus_files": _focus_files(repo_path),
        "readme_excerpt": _readme_excerpt(repo_path),
        "license_files": _license_files(repo_path),
        "source_stats": _source_stats(repo_path),
        "rationale_artifacts": _rationale_artifacts(repo_path),
    }

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("facts={0}".format(output_path))
    print("languages={0}".format(", ".join(result["repo_facts"]["languages"][:5])))
    print("focus_files={0}".format(len(result["focus_files"])))
    print("comment_density={0}".format(result["source_stats"]["comment_density"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
