"""Read-only filesystem tools for repo exploration.

Provides four tools that let the extraction agent inspect a source-code
repository:

- ``read_file``    — read a file (or a line-range slice) with ``cat -n`` style
                     line-number prefixes.
- ``list_dir``     — list directory contents; optionally recursive with
                     configurable depth.
- ``grep_codebase`` — regex search across files, returning ``file:line:content``
                      matches.
- ``search_codebase`` — convenience wrapper: grep + file pattern listing.

All tools are bound to a single ``repo_path`` at construction time.  Every
path argument is resolved and checked against ``repo_path`` before any IO
occurs; attempts to escape the repo root are rejected with an error string.
"""

from __future__ import annotations

import fnmatch
import os
import re
import signal
import time
from pathlib import Path
from typing import Any

from doramagic_extraction_agent.core.tool_registry import ToolDef

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".mypy_cache", ".ruff_cache"}
_MAX_READ_LINES = 500
_MAX_LIST_ENTRIES = 200
_GREP_TIMEOUT_SECONDS = 10


def _guard(repo_root: Path, raw_path: str) -> Path | str:
    """Resolve *raw_path* relative to *repo_root* and verify it stays inside.

    Returns the resolved :class:`Path` on success, or an error string if the
    path escapes the repo root or is otherwise invalid.
    """
    try:
        candidate = (repo_root / raw_path).resolve()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: invalid path {raw_path!r}: {exc}"

    if not candidate.is_relative_to(repo_root.resolve()):
        return f"ERROR: path {raw_path!r} is outside the repository root"
    return candidate


def _is_binary(path: Path) -> bool:
    """Heuristic binary-file check: peek at the first 8 KB for null bytes."""
    try:
        with path.open("rb") as fh:
            chunk = fh.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def _read_text(path: Path) -> str | None:
    """Read *path* as UTF-8 text; return ``None`` on encoding errors."""
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return None


def _prefix_lines(lines: list[str], start: int) -> str:
    """Return lines joined with 1-based ``cat -n`` style line-number prefixes.

    ``start`` is the 1-based line number of ``lines[0]``.
    """
    parts: list[str] = []
    for i, line in enumerate(lines, start=start):
        parts.append(f"{i:6}\t{line}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_filesystem_tools(repo_path: Path) -> list[ToolDef]:
    """Create filesystem tools bound to *repo_path*.

    Args:
        repo_path: Absolute path to the repository root.  All path arguments
            supplied to the returned tools are resolved relative to this
            directory, and attempts to escape it are rejected.

    Returns:
        A list of four :class:`ToolDef` instances ready for registration with
        a :class:`~doramagic_extraction_agent.core.tool_registry.ToolRegistry`.
    """

    repo_root = repo_path.resolve()

    # -----------------------------------------------------------------------
    # Tool 1: read_file
    # -----------------------------------------------------------------------

    async def _read_file(
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """Read a file, optionally returning a specific line range."""
        result = _guard(repo_root, path)
        if isinstance(result, str):
            return result
        resolved = result

        if not resolved.exists():
            return f"ERROR: file not found: {path!r}"
        if not resolved.is_file():
            return f"ERROR: {path!r} is not a file"
        if _is_binary(resolved):
            return f"ERROR: {path!r} appears to be a binary file; skipping"

        text = _read_text(resolved)
        if text is None:
            return f"ERROR: {path!r} could not be decoded as UTF-8"

        all_lines = text.splitlines(keepends=True)
        total = len(all_lines)

        # Normalise 1-based line numbers
        lo = max(1, start_line) if start_line is not None else 1
        hi = min(total, end_line) if end_line is not None else total

        # Enforce hard cap
        if (hi - lo + 1) > _MAX_READ_LINES:
            hi = lo + _MAX_READ_LINES - 1

        selected = all_lines[lo - 1 : hi]
        header = f"# {resolved.relative_to(repo_root)}  (lines {lo}–{hi} of {total})\n"
        return header + _prefix_lines(selected, lo)

    read_file_tool = ToolDef(
        name="read_file",
        description=(
            "Read the content of a file in the repository. "
            "If start_line and/or end_line are given, only that range is returned. "
            "Returns at most 500 lines per call. Line numbers are prefixed (cat -n style)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to the file, relative to the repository root "
                        "(e.g. 'src/main.py' or 'README.md')."
                    ),
                },
                "start_line": {
                    "type": "integer",
                    "description": "1-based line number to start reading from (inclusive).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "1-based line number to stop reading at (inclusive).",
                },
            },
            "required": ["path"],
        },
        handler=_read_file,
    )

    # -----------------------------------------------------------------------
    # Tool 2: list_dir
    # -----------------------------------------------------------------------

    async def _list_dir(
        path: str,
        recursive: bool = False,
        max_depth: int = 3,
    ) -> str:
        """List directory contents, optionally recursively."""
        result = _guard(repo_root, path)
        if isinstance(result, str):
            return result
        resolved = result

        if not resolved.exists():
            return f"ERROR: path not found: {path!r}"
        if not resolved.is_dir():
            return f"ERROR: {path!r} is not a directory"

        lines: list[str] = []
        truncated = False

        def _format_entry(p: Path, indent: int) -> str:
            prefix = "  " * indent
            if p.is_dir():
                return f"{prefix}{p.name}/  [dir]"
            try:
                size = p.stat().st_size
            except OSError:
                size = -1
            size_str = f"{size:,} B" if size >= 0 else "? B"
            return f"{prefix}{p.name}  [file, {size_str}]"

        def _walk(directory: Path, depth: int) -> None:
            nonlocal truncated
            if len(lines) >= _MAX_LIST_ENTRIES:
                truncated = True
                return
            try:
                entries = sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name))
            except PermissionError:
                lines.append(f"  [permission denied: {directory}]")
                return
            for entry in entries:
                if len(lines) >= _MAX_LIST_ENTRIES:
                    truncated = True
                    return
                indent_level = depth - (max_depth - (max_depth if not recursive else depth))
                # Compute indent relative to the starting dir
                rel = entry.relative_to(resolved)
                indent = len(rel.parts) - 1
                lines.append(_format_entry(entry, indent))
                if recursive and entry.is_dir() and depth < max_depth:
                    _walk(entry, depth + 1)

        _walk(resolved, 1)

        header = f"# {resolved.relative_to(repo_root) if resolved != repo_root else '.'}/\n"
        body = "\n".join(lines)
        suffix = (
            f"\n\n[Truncated: showing first {_MAX_LIST_ENTRIES} entries]"
            if truncated
            else ""
        )
        return header + body + suffix

    list_dir_tool = ToolDef(
        name="list_dir",
        description=(
            "List the contents of a directory in the repository. "
            "Each entry shows its name, type (file/dir), and size in bytes. "
            "Set recursive=true to traverse subdirectories up to max_depth levels. "
            "Returns at most 200 entries."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Directory path relative to the repository root "
                        "(use '.' or '' for the root itself)."
                    ),
                },
                "recursive": {
                    "type": "boolean",
                    "description": "If true, recurse into subdirectories. Default: false.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": (
                        "Maximum recursion depth when recursive=true. Default: 3."
                    ),
                },
            },
            "required": ["path"],
        },
        handler=_list_dir,
    )

    # -----------------------------------------------------------------------
    # Tool 3: grep_codebase
    # -----------------------------------------------------------------------

    async def _grep_codebase(
        pattern: str,
        path: str | None = None,
        include: str | None = None,
        max_results: int = 50,
    ) -> str:
        """Regex search across files in the repo."""
        search_root_raw = path if path is not None else "."
        result = _guard(repo_root, search_root_raw)
        if isinstance(result, str):
            return result
        search_root = result

        if not search_root.exists():
            return f"ERROR: path not found: {search_root_raw!r}"

        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return f"ERROR: invalid regex {pattern!r}: {exc}"

        matches: list[str] = []
        partial = False
        deadline = time.monotonic() + _GREP_TIMEOUT_SECONDS

        def _should_include(p: Path) -> bool:
            if include:
                return fnmatch.fnmatch(p.name, include)
            return True

        for dirpath, dirnames, filenames in os.walk(search_root):
            # Prune skipped dirs in-place so os.walk doesn't descend into them
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

            for fname in filenames:
                if time.monotonic() > deadline:
                    partial = True
                    break
                if len(matches) >= max_results:
                    partial = True
                    break

                fpath = Path(dirpath) / fname
                if not _should_include(fpath):
                    continue
                if _is_binary(fpath):
                    continue

                text = _read_text(fpath)
                if text is None:
                    continue

                try:
                    rel = fpath.relative_to(repo_root)
                except ValueError:
                    rel = fpath

                for lineno, line in enumerate(text.splitlines(), start=1):
                    if len(matches) >= max_results:
                        partial = True
                        break
                    if compiled.search(line):
                        matches.append(f"{rel}:{lineno}:{line}")

            if partial:
                break

        if not matches:
            return f"No matches found for pattern {pattern!r}"

        header = f"# grep {pattern!r} — {len(matches)} match(es)"
        if partial:
            header += f" (partial results; limit={max_results} or timeout={_GREP_TIMEOUT_SECONDS}s reached)"
        return header + "\n" + "\n".join(matches)

    grep_codebase_tool = ToolDef(
        name="grep_codebase",
        description=(
            "Search the codebase using a Python regex pattern. "
            "Returns matches in 'file:line:content' format. "
            "Skips binary files, __pycache__, .git, and node_modules. "
            "Stops after max_results matches or 10 seconds, whichever comes first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Python regex pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Directory or file to search within, relative to the repo root. "
                        "Defaults to the entire repository."
                    ),
                },
                "include": {
                    "type": "string",
                    "description": (
                        "Shell glob pattern to filter files by name "
                        "(e.g. '*.py', '*.ts').  Omit to search all files."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matching lines to return. Default: 50.",
                },
            },
            "required": ["pattern"],
        },
        handler=_grep_codebase,
    )

    # -----------------------------------------------------------------------
    # Tool 4: search_codebase
    # -----------------------------------------------------------------------

    async def _search_codebase(
        query: str,
        file_pattern: str | None = None,
    ) -> str:
        """Higher-level search: grep + matching file listing combined."""
        parts: list[str] = []

        # 1. Grep for the query string across the whole repo
        grep_result = await _grep_codebase(
            pattern=re.escape(query),
            path=None,
            include=file_pattern,
            max_results=50,
        )
        parts.append("## Text matches\n" + grep_result)

        # 2. If a file_pattern was given, also list files matching it
        if file_pattern:
            matched_files: list[str] = []
            for dirpath, dirnames, filenames in os.walk(repo_root):
                dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
                for fname in filenames:
                    if fnmatch.fnmatch(fname, file_pattern):
                        fpath = Path(dirpath) / fname
                        try:
                            rel = fpath.relative_to(repo_root)
                        except ValueError:
                            rel = fpath
                        matched_files.append(str(rel))
                        if len(matched_files) >= _MAX_LIST_ENTRIES:
                            break
                if len(matched_files) >= _MAX_LIST_ENTRIES:
                    break

            if matched_files:
                truncation = (
                    f"\n[Showing first {_MAX_LIST_ENTRIES} files]"
                    if len(matched_files) >= _MAX_LIST_ENTRIES
                    else ""
                )
                parts.append(
                    f"## Files matching '{file_pattern}'\n"
                    + "\n".join(matched_files)
                    + truncation
                )
            else:
                parts.append(f"## Files matching '{file_pattern}'\nNo files found.")

        return "\n\n".join(parts)

    search_codebase_tool = ToolDef(
        name="search_codebase",
        description=(
            "Higher-level search that combines regex text search with optional file listing. "
            "Greps the codebase for 'query' (literal match) and, if file_pattern is given, "
            "also lists all files whose names match that glob pattern. "
            "Use this when you want both text matches and a file inventory in one call."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Literal text to search for across the codebase.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": (
                        "Optional shell glob to filter by filename "
                        "(e.g. '*.py', '*.yaml').  "
                        "If given, files matching this pattern are also listed."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=_search_codebase,
    )

    return [read_file_tool, list_dir_tool, grep_codebase_tool, search_codebase_tool]
