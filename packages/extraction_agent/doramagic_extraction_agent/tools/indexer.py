"""AST-based structural index for repository exploration.

Builds a pre-computed index of every Python file in a repository:
- Class/method signatures with docstrings and line numbers
- Import dependencies (who imports whom)
- File type classification (model/util/test/example/config)
- Math-related file detection (scipy, sklearn, statsmodels, etc.)

The index is built once (pure Python, no LLM) and then exposed via four
query tools that the extraction agent can call during agentic phases.

Design reference: Agentless (ICLR 2025) skeleton representation,
ArchAgent (2026) File Summarizer.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from doramagic_extraction_agent.core.tool_registry import ToolDef

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
    "dist",
    "build",
}

_MATH_IMPORTS = frozenset(
    {
        "scipy",
        "sklearn",
        "statsmodels",
        "torch",
        "tensorflow",
        "tf",
        "optbinning",
        "cvxpy",
        "sympy",
    }
)

_MATH_QUALNAMES = frozenset(
    {
        "numpy.linalg",
        "numpy.random",
        "numpy.fft",
        "scipy.optimize",
        "scipy.stats",
        "scipy.linalg",
        "scipy.signal",
        "sklearn.linear_model",
        "sklearn.ensemble",
        "sklearn.pipeline",
        "sklearn.preprocessing",
        "sklearn.cluster",
        "sklearn.metrics",
        "statsmodels.api",
        "statsmodels.tsa",
        "statsmodels.regression",
        "torch.nn",
        "torch.optim",
    }
)

# Broader keyword patterns that signal math/quant logic in source.
# Two tiers: strong (1 hit = math) and weak (need 2+ hits).
_MATH_KEYWORDS_STRONG = frozenset(
    {
        # Explicit math/stats operations (avoid ambiguous terms like bare "regression")
        "linear_regression",
        "logistic_regression",
        "ridge_regression",
        "gradient_descent",
        "backprop",
        "loss_function",
        "linear_model",
        "decision_tree",
        "random_forest",
        "cross_entropy",
        "mean_squared_error",
        "r_squared",
        "eigenvalue",
        "matrix_inverse",
        "cholesky",
        "monte_carlo",
        "confidence_interval",
        "scipy.optimize",
        "scipy.stats",
        "sklearn.",
        # Quant finance specific
        "sharpe_ratio",
        "max_drawdown",
        "covariance_matrix",
        "black_scholes",
        "greeks",
        "var_calc",
        "value_at_risk",
    }
)
_MATH_KEYWORDS_WEAK = frozenset(
    {
        # Pandas/numpy quant operations (common in factor/trading code)
        ".rolling(",
        ".ewm(",
        ".pct_change(",
        "cumsum(",
        "cumprod(",
        ".corr(",
        ".cov(",
        ".std(",
        ".var(",
        # Trading/simulation signals
        "buy_cost",
        "sell_cost",
        "slippage",
        "commission",
        "position_size",
        "fill_price",
        "pnl",
        # Factor computation signals
        "moving_average",
        "exponential_moving",
        "macd",
        "bollinger",
        "rsi",
        "atr",
        "volatility",
    }
)


# ---------------------------------------------------------------------------
# AST parsing
# ---------------------------------------------------------------------------


_TEST_SEGMENTS = frozenset({"test", "tests", "testing"})
_EXAMPLE_SEGMENTS = frozenset(
    {
        "example",
        "examples",
        "tutorial",
        "tutorials",
        "notebook",
        "notebooks",
        "demo",
        "demos",
        "sample",
        "samples",
    }
)


def _classify_file(rel_path: str, has_classes: bool) -> str:
    """Classify a Python file by its path segments and content."""
    path_parts = Path(rel_path).parts
    segments = frozenset(p.lower() for p in path_parts)
    fname = path_parts[-1].lower()

    # Test: directory segment or filename pattern
    is_test = (
        segments & _TEST_SEGMENTS
        or fname.startswith("test_")
        or fname.endswith("_test.py")
        or fname == "conftest.py"
    )
    if is_test:
        return "test"
    # Example: directory segment
    if segments & _EXAMPLE_SEGMENTS:
        return "example"
    if fname in (
        "setup.py",
        "pyproject.toml",
        "setup.cfg",
        "conf.py",
        "settings.py",
        "config.py",
        "manage.py",
        "__main__.py",
    ):
        return "config"
    if has_classes:
        return "model"
    return "util"


def _is_math_related(imports: list[str], source_text: str) -> bool:
    """Detect whether a file involves mathematical/quantitative logic.

    Strict criteria to avoid false positives from data-only files:
    - Direct import of a math library (scipy, sklearn, statsmodels, torch)
    - Qualified import of a math submodule (numpy.linalg, scipy.optimize)
    - numpy/pandas combined with math keywords in source
    """
    has_numpy = False
    for imp in imports:
        top = imp.split(".")[0]
        if top in _MATH_IMPORTS:
            return True
        if imp in _MATH_QUALNAMES:
            return True
        if top in ("numpy", "np"):
            has_numpy = True

    snippet = source_text[:8000].lower()

    # Strong keyword: 1 hit is enough
    if any(kw in snippet for kw in _MATH_KEYWORDS_STRONG):
        return True

    # numpy + weak keyword = math
    weak_hits = sum(1 for kw in _MATH_KEYWORDS_WEAK if kw in snippet)
    if has_numpy and weak_hits >= 1:
        return True

    # Multiple weak keywords without numpy = still math (e.g. pandas quant code)
    return weak_hits >= 2


def _parse_file(filepath: Path, repo_root: Path) -> dict[str, Any] | None:
    """Parse a single Python file and return its structural summary."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return None

    rel = str(filepath.relative_to(repo_root))

    # Module docstring
    module_doc = ast.get_docstring(tree) or ""

    # Imports
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    # Top-level classes
    classes: list[dict[str, Any]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(ast.unparse(base))
            methods: list[dict[str, Any]] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = ast.unparse(item.args) if hasattr(ast, "unparse") else ""
                    methods.append(
                        {
                            "name": item.name,
                            "signature": f"({sig})",
                            "line": item.lineno,
                            "docstring": (ast.get_docstring(item) or "")[:200],
                        }
                    )
            classes.append(
                {
                    "name": node.name,
                    "bases": bases,
                    "methods": methods,
                    "line": node.lineno,
                    "docstring": (ast.get_docstring(node) or "")[:200],
                }
            )

    # Top-level functions (not inside classes)
    functions: list[dict[str, Any]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = ast.unparse(node.args) if hasattr(ast, "unparse") else ""
            functions.append(
                {
                    "name": node.name,
                    "signature": f"({sig})",
                    "line": node.lineno,
                    "docstring": (ast.get_docstring(node) or "")[:200],
                }
            )

    file_type = _classify_file(rel, bool(classes))
    math_related = _is_math_related(imports, source)

    return {
        "type": file_type,
        "classes": classes,
        "functions": functions,
        "imports": imports,
        "module_docstring": module_doc[:300],
        "math_related": math_related,
        "lines": len(source.splitlines()),
    }


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------


def _scan_document_sources(repo_root: Path) -> dict[str, Any]:
    """Scan non-code knowledge sources: SKILL.md, CLAUDE.md, agent defs.

    Returns a dict with keys: skill_files, claude_md, agent_files.
    Each skill_file entry contains frontmatter metadata and heading structure.
    """
    import re as _re

    import yaml as _yaml

    skill_files: list[dict[str, Any]] = []
    claude_md: list[dict[str, Any]] = []
    agent_files: list[dict[str, Any]] = []

    _doc_names = {"skill.md", "claude.md", "agents.md", "gemini.md"}
    _frontmatter_re = _re.compile(r"^---\s*\n(.*?)\n---\s*\n", _re.DOTALL)
    _heading_re = _re.compile(r"^(#{1,4})\s+(.+)$", _re.MULTILINE)

    for fpath in repo_root.rglob("*.md"):
        rel_parts = fpath.relative_to(repo_root).parts
        if any(
            (part.startswith(".") and part != ".claude") or part in _SKIP_DIRS for part in rel_parts
        ):
            continue

        name_lower = fpath.name.lower()
        if name_lower not in _doc_names:
            # Check if inside skills/ or .claude/agents/ directory
            rel_str = str(fpath.relative_to(repo_root))
            if not any(
                seg in rel_str.lower()
                for seg in ("skills/", ".claude/agents/", ".claude/commands/")
            ):
                continue

        rel = str(fpath.relative_to(repo_root))
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Parse YAML frontmatter
        frontmatter: dict[str, Any] = {}
        fm_match = _frontmatter_re.match(content)
        if fm_match:
            import contextlib

            with contextlib.suppress(_yaml.YAMLError):
                frontmatter = _yaml.safe_load(fm_match.group(1)) or {}

        # Parse heading structure
        headings: list[dict[str, str]] = []
        for m in _heading_re.finditer(content):
            headings.append(
                {
                    "level": len(m.group(1)),
                    "title": m.group(2).strip(),
                }
            )

        entry = {
            "path": rel,
            "frontmatter": frontmatter,
            "headings": headings[:30],  # Cap to avoid bloat
            "size_bytes": len(content.encode("utf-8")),
        }

        if name_lower == "skill.md":
            skill_files.append(entry)
        elif name_lower == "claude.md":
            claude_md.append(entry)
        elif "agents/" in rel.lower() or "agent" in name_lower:
            agent_files.append(entry)
        else:
            # Generic document in skills/ or commands/
            skill_files.append(entry)

    result = {
        "skill_files": sorted(skill_files, key=lambda x: x["path"]),
        "claude_md": sorted(claude_md, key=lambda x: x["path"]),
        "agent_files": sorted(agent_files, key=lambda x: x["path"]),
    }

    if skill_files or claude_md or agent_files:
        logger.info(
            "Document sources: %d skills, %d CLAUDE.md, %d agents",
            len(skill_files),
            len(claude_md),
            len(agent_files),
        )
    return result


def build_structural_index(repo_path: Path) -> dict[str, Any]:
    """Build a complete structural index for all .py files in a repository.

    Returns a dict with keys: files, dependency_graph, entry_points, stats,
    document_sources.
    """
    repo_root = repo_path.resolve()
    files: dict[str, Any] = {}
    dep_graph: dict[str, list[str]] = {}

    # Collect all .py files
    py_files: list[Path] = []
    for fpath in repo_root.rglob("*.py"):
        # Skip hidden/build dirs
        rel_parts = fpath.relative_to(repo_root).parts
        if any(
            part.startswith(".") or part in _SKIP_DIRS or part.endswith(".egg-info")
            for part in rel_parts
        ):
            continue
        py_files.append(fpath)

    logger.info("Indexing %d Python files in %s", len(py_files), repo_root)

    # Build module name → file path mappings for dependency resolution.
    # Supports common layouts: flat (pkg/foo.py), src (src/pkg/foo.py).
    # For src/ layouts, register both "src.pkg.foo" and "pkg.foo" as aliases.
    module_to_path: dict[str, str] = {}
    internal_top_modules: set[str] = set()  # for external import detection

    for fpath in py_files:
        rel = str(fpath.relative_to(repo_root))
        mod = rel.replace("/", ".").replace("\\", ".").removesuffix(".py")
        if mod.endswith(".__init__"):
            mod = mod.removesuffix(".__init__")
        module_to_path[mod] = rel
        internal_top_modules.add(mod.split(".")[0])

        # Alias: strip common source roots (src/, lib/)
        parts = mod.split(".")
        if parts[0] in ("src", "lib") and len(parts) > 1:
            alias = ".".join(parts[1:])
            if alias not in module_to_path:
                module_to_path[alias] = rel
            internal_top_modules.add(parts[1])

    def _resolve_import(imp: str, current_rel: str) -> str | None:
        """Resolve an import string to a repo-relative file path.

        Uses longest prefix match against module_to_path for O(k) lookup
        where k is the number of dotted segments in the import.
        """
        # Try progressively shorter prefixes: a.b.c → a.b → a
        parts = imp.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            path = module_to_path.get(candidate)
            if path and path != current_rel:
                return path
        return None

    for fpath in py_files:
        rel = str(fpath.relative_to(repo_root))
        info = _parse_file(fpath, repo_root)
        if info is None:
            continue
        files[rel] = info

        # Build dependency edges (only internal imports)
        deps: list[str] = []
        for imp in info["imports"]:
            resolved = _resolve_import(imp, rel)
            if resolved:
                deps.append(resolved)
        if deps:
            dep_graph[rel] = sorted(set(deps))

    # Detect entry points: __init__.py that re-export, __main__.py, cli scripts
    entry_points: list[str] = []
    for rel, info in files.items():
        parts = Path(rel).parts
        fname = parts[-1]
        if fname == "__main__.py":
            entry_points.append(rel)
        elif fname == "__init__.py":
            # Package init with imports: depth ≤ 3 (covers src/pkg/__init__.py)
            # Skip test packages
            if len(parts) <= 3 and info["imports"] and info["type"] != "test":
                entry_points.append(rel)
        elif fname in ("cli.py", "app.py", "main.py", "run.py"):
            entry_points.append(rel)

    # Examples (non-.py files)
    examples: list[str] = []
    for pattern in ("**/*.ipynb", "**/*.md"):
        for fpath in repo_root.rglob(pattern.split("/")[-1]):
            rel_parts = fpath.relative_to(repo_root).parts
            if any(part.startswith(".") or part in _SKIP_DIRS for part in rel_parts):
                continue
            rel = str(fpath.relative_to(repo_root))
            if any(
                kw in rel.lower() for kw in ("example", "tutorial", "notebook", "demo", "guide")
            ):
                examples.append(rel)
    examples.sort()

    # Stats
    type_counts: dict[str, int] = {}
    math_count = 0
    total_classes = 0
    total_functions = 0
    for info in files.values():
        ft = info["type"]
        type_counts[ft] = type_counts.get(ft, 0) + 1
        if info.get("math_related"):
            math_count += 1
        total_classes += len(info.get("classes", []))
        total_functions += len(info.get("functions", []))

    # v7: Scan document knowledge sources (SKILL.md, CLAUDE.md, etc.)
    doc_index = _scan_document_sources(repo_root)

    index = {
        "files": files,
        "dependency_graph": dep_graph,
        "_internal_top_modules": sorted(internal_top_modules),
        "entry_points": entry_points,
        "examples": examples[:50],
        "document_sources": doc_index,  # v7: non-code knowledge source index
        "stats": {
            "total_py_files": len(files),
            "total_classes": total_classes,
            "total_functions": total_functions,
            "math_related_files": math_count,
            "document_source_files": len(doc_index.get("skill_files", []))
            + len(doc_index.get("claude_md", [])),
            "by_type": type_counts,
        },
    }

    logger.info(
        "Index built: %d files, %d classes, %d functions, %d math, %d doc sources",
        len(files),
        total_classes,
        total_functions,
        math_count,
        index["stats"]["document_source_files"],
    )
    return index


# ---------------------------------------------------------------------------
# Summary builder (for injection into phase messages)
# ---------------------------------------------------------------------------


def build_index_summary(index: dict[str, Any], max_lines: int = 200) -> str:
    """Build a human-readable summary of the structural index.

    Used to inject into agentic phase initial_messages so the LLM has a
    repo map from the start.
    """
    lines: list[str] = []
    stats = index.get("stats", {})

    lines.append("## Repository Structural Index")
    lines.append(f"- Python files: {stats.get('total_py_files', 0)}")
    lines.append(f"- Classes: {stats.get('total_classes', 0)}")
    lines.append(f"- Functions: {stats.get('total_functions', 0)}")
    lines.append(f"- Math-related files: {stats.get('math_related_files', 0)}")
    by_type = stats.get("by_type", {})
    if by_type:
        lines.append(f"- By type: {by_type}")

    # Entry points
    entry_points = index.get("entry_points", [])
    if entry_points:
        lines.append(f"\n### Entry Points ({len(entry_points)})")
        for ep in entry_points[:10]:
            lines.append(f"  - {ep}")

    # Math-related files (critical for M-type BD detection)
    math_files = [
        (path, info) for path, info in index.get("files", {}).items() if info.get("math_related")
    ]
    if math_files:
        lines.append(f"\n### Math-Related Files ({len(math_files)})")
        for path, info in sorted(math_files):
            classes = [c["name"] for c in info.get("classes", [])]
            imports = [
                i
                for i in info.get("imports", [])
                if i.split(".")[0] in _MATH_IMPORTS or i in _MATH_QUALNAMES
            ]
            desc = ""
            if classes:
                desc += f" classes=[{', '.join(classes)}]"
            if imports:
                desc += f" imports=[{', '.join(imports[:5])}]"
            lines.append(f"  - {path}{desc}")

    # Model files skeleton (non-test, non-example, with classes)
    model_files = [
        (path, info) for path, info in index.get("files", {}).items() if info.get("type") == "model"
    ]
    if model_files:
        lines.append(f"\n### Model Files ({len(model_files)}) — Class Skeleton")
        for path, info in sorted(model_files):
            if len(lines) >= max_lines - 5:
                lines.append(f"  ... and {len(model_files) - model_files.index((path, info))} more")
                break
            classes = info.get("classes", [])
            for cls in classes:
                methods = [m["name"] for m in cls.get("methods", [])]
                bases = cls.get("bases", [])
                base_str = f"({', '.join(bases)})" if bases else ""
                lines.append(f"  - {path}: class {cls['name']}{base_str}")
                if methods:
                    lines.append(f"    methods: {', '.join(methods)}")

    # Examples
    examples = index.get("examples", [])
    if examples:
        lines.append(f"\n### Examples/Tutorials ({len(examples)})")
        for ex in examples[:10]:
            lines.append(f"  - {ex}")

    return "\n".join(lines[:max_lines])


def build_math_files_summary(index: dict[str, Any], max_files: int = 30) -> str:
    """Build a focused summary of math-related files for R1/R3 injection.

    Caps output to max_files entries to avoid oversized prompts.
    Prioritizes non-test, non-example files (model > util > config).
    """
    math_files = [
        (path, info) for path, info in index.get("files", {}).items() if info.get("math_related")
    ]
    if not math_files:
        return ""

    # Prioritize: model > util > example > test > config
    type_priority = {"model": 0, "util": 1, "example": 2, "config": 3, "test": 4}
    math_files.sort(key=lambda x: (type_priority.get(x[1].get("type", ""), 5), x[0]))

    shown = math_files[:max_files]
    remaining = len(math_files) - len(shown)

    lines = [f"## Math-Related Files ({len(math_files)})"]
    lines.append(
        "These files contain mathematical/quantitative logic. "
        "Each likely represents one or more M-type business decisions."
    )
    if remaining > 0:
        lines.append(f"Showing top {max_files}; use list_by_type('math') for the full list.")
    lines.append("")

    for path, info in shown:
        math_imports = [
            i
            for i in info.get("imports", [])
            if i.split(".")[0] in _MATH_IMPORTS or i in _MATH_QUALNAMES
        ]

        lines.append(f"### {path}")
        if info.get("module_docstring"):
            lines.append(f"  > {info['module_docstring'][:150]}")
        if math_imports:
            lines.append(f"  Math imports: {', '.join(math_imports)}")
        for cls in info.get("classes", []):
            methods = [f"{m['name']}() L{m['line']}" for m in cls.get("methods", [])]
            lines.append(f"  class {cls['name']}: {', '.join(methods[:8])}")
        for fn in info.get("functions", [])[:5]:
            lines.append(f"  def {fn['name']}{fn['signature']} L{fn['line']}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Query tools (for agentic phases)
# ---------------------------------------------------------------------------


def create_index_tools(index: dict[str, Any]) -> list[ToolDef]:
    """Create 4 query tools backed by a pre-built structural index.

    Tools:
        get_skeleton(file_path) — class/method signatures for a file
        get_dependencies(file_path) — imports and reverse imports
        get_file_type(file_path) — classification + math flag
        list_by_type(file_type) — all files of a given type
    """

    files = index.get("files", {})
    dep_graph = index.get("dependency_graph", {})
    internal_modules = index.get("_internal_top_modules", set())

    # Build reverse dependency map
    reverse_deps: dict[str, list[str]] = {}
    for src, targets in dep_graph.items():
        for tgt in targets:
            reverse_deps.setdefault(tgt, []).append(src)

    # -----------------------------------------------------------------------
    # Tool 1: get_skeleton
    # -----------------------------------------------------------------------

    async def _get_skeleton(file_path: str) -> str:
        """Return the class/method skeleton of a file."""
        info = files.get(file_path)
        if info is None:
            # Try fuzzy match
            candidates = [p for p in files if p.endswith(file_path) or file_path in p]
            if candidates:
                return (
                    f"File '{file_path}' not found in index. "
                    f"Did you mean: {', '.join(candidates[:5])}?"
                )
            return f"File '{file_path}' not found in index."

        parts = [
            f"# {file_path} ({info['lines']} lines, type={info['type']}"
            f"{', math-related' if info.get('math_related') else ''})"
        ]

        if info.get("module_docstring"):
            parts.append(f'"""{info["module_docstring"]}"""')

        if info.get("imports"):
            parts.append(f"\nImports: {', '.join(info['imports'][:15])}")

        for cls in info.get("classes", []):
            bases = f"({', '.join(cls['bases'])})" if cls.get("bases") else ""
            parts.append(f"\nclass {cls['name']}{bases}:  # L{cls['line']}")
            if cls.get("docstring"):
                parts.append(f'    """{cls["docstring"]}"""')
            for m in cls.get("methods", []):
                doc = f"  # {m['docstring'][:80]}" if m.get("docstring") else ""
                parts.append(f"    def {m['name']}{m['signature']}  # L{m['line']}{doc}")

        for fn in info.get("functions", []):
            doc = f"  # {fn['docstring'][:80]}" if fn.get("docstring") else ""
            parts.append(f"\ndef {fn['name']}{fn['signature']}  # L{fn['line']}{doc}")

        return "\n".join(parts)

    get_skeleton_tool = ToolDef(
        name="get_skeleton",
        description=(
            "Return the class/method skeleton (signatures, docstrings, line numbers) "
            "of a Python file from the pre-built structural index. Much faster than "
            "reading the full file — use this first to understand a file's structure, "
            "then read_file for specific line ranges."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root (e.g. 'src/main.py').",
                },
            },
            "required": ["file_path"],
        },
        handler=_get_skeleton,
    )

    # -----------------------------------------------------------------------
    # Tool 2: get_dependencies
    # -----------------------------------------------------------------------

    async def _get_dependencies(file_path: str) -> str:
        """Return what a file imports and what imports it."""
        info = files.get(file_path)
        if info is None:
            candidates = [p for p in files if p.endswith(file_path) or file_path in p]
            if candidates:
                return f"File '{file_path}' not found. Did you mean: {', '.join(candidates[:5])}?"
            return f"File '{file_path}' not found in index."

        parts = [f"# Dependencies for {file_path}"]

        # External imports: not matching any known internal top-level module
        internal_set = (
            set(internal_modules) if not isinstance(internal_modules, set) else internal_modules
        )
        ext_imports = [i for i in info.get("imports", []) if i.split(".")[0] not in internal_set]
        if ext_imports:
            parts.append(f"\nExternal imports: {', '.join(ext_imports)}")

        # Internal: this file imports
        forward = dep_graph.get(file_path, [])
        if forward:
            parts.append(f"\nImports from repo ({len(forward)}):")
            for dep in forward:
                parts.append(f"  → {dep}")

        # Internal: imported by
        reverse = reverse_deps.get(file_path, [])
        if reverse:
            parts.append(f"\nImported by ({len(reverse)}):")
            for src in sorted(reverse):
                parts.append(f"  ← {src}")

        if not forward and not reverse:
            parts.append("\nNo internal dependencies found.")

        return "\n".join(parts)

    get_dependencies_tool = ToolDef(
        name="get_dependencies",
        description=(
            "Show what a file imports (forward dependencies) and what other files "
            "import it (reverse dependencies). Helps trace data flow and understand "
            "module coupling."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root.",
                },
            },
            "required": ["file_path"],
        },
        handler=_get_dependencies,
    )

    # -----------------------------------------------------------------------
    # Tool 3: get_file_type
    # -----------------------------------------------------------------------

    async def _get_file_type(file_path: str) -> str:
        """Return the classification and flags for a file."""
        info = files.get(file_path)
        if info is None:
            candidates = [p for p in files if p.endswith(file_path) or file_path in p]
            if candidates:
                return f"File '{file_path}' not found. Did you mean: {', '.join(candidates[:5])}?"
            return f"File '{file_path}' not found in index."

        return (
            f"File: {file_path}\n"
            f"Type: {info['type']}\n"
            f"Math-related: {info.get('math_related', False)}\n"
            f"Lines: {info['lines']}\n"
            f"Classes: {len(info.get('classes', []))}\n"
            f"Functions: {len(info.get('functions', []))}"
        )

    get_file_type_tool = ToolDef(
        name="get_file_type",
        description=(
            "Return the classification (model/util/test/example/config), math flag, "
            "and basic stats for a Python file."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root.",
                },
            },
            "required": ["file_path"],
        },
        handler=_get_file_type,
    )

    # -----------------------------------------------------------------------
    # Tool 4: list_by_type
    # -----------------------------------------------------------------------

    async def _list_by_type(file_type: str) -> str:
        """List all files of a given type."""
        valid_types = {"model", "util", "test", "example", "config", "math"}
        if file_type not in valid_types:
            return f"Invalid type '{file_type}'. Valid types: {sorted(valid_types)}"

        if file_type == "math":
            matched = [(p, i) for p, i in files.items() if i.get("math_related")]
        else:
            matched = [(p, i) for p, i in files.items() if i.get("type") == file_type]

        if not matched:
            return f"No files of type '{file_type}' found."

        parts = [f"# Files of type '{file_type}' ({len(matched)})"]
        for path, info in sorted(matched):
            classes = [c["name"] for c in info.get("classes", [])]
            suffix = f"  [{', '.join(classes)}]" if classes else ""
            math = " (math)" if info.get("math_related") and file_type != "math" else ""
            parts.append(f"  {path} ({info['lines']} lines){suffix}{math}")

        return "\n".join(parts)

    list_by_type_tool = ToolDef(
        name="list_by_type",
        description=(
            "List all Python files of a given type: model, util, test, example, "
            "config, or 'math' (special: files with mathematical/quantitative logic). "
            "Returns file paths with class names and line counts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_type": {
                    "type": "string",
                    "description": (
                        "File type to list. One of: model, util, test, example, config, math."
                    ),
                },
            },
            "required": ["file_type"],
        },
        handler=_list_by_type,
    )

    return [get_skeleton_tool, get_dependencies_tool, get_file_type_tool, list_by_type_tool]
