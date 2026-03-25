"""Stage 0 确定性提取 — 从本地仓库路径提取机器可读的 RepoFacts。

设计原则：代码说事实，AI 说故事。
Stage 0 只做确定性提取，绝不调用 LLM。所有输出都是可重现的。

实际生产中此模块会调用 prepare-repo.sh 和 repomix，
当前实现为骨架版本，用于 Round 1 前置依赖建立。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# 引用 contracts 包
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "packages" / "contracts"))

from doramagic_contracts.base import RepoRef  # noqa: E402
from doramagic_contracts.extraction import RepoFacts  # noqa: E402

# ---------------------------------------------------------------------------
# 语言检测规则：文件扩展名 → 语言名
# ---------------------------------------------------------------------------

_EXT_TO_LANG: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".sh": "Shell",
}

# ---------------------------------------------------------------------------
# 框架检测规则：文件/目录名或关键依赖 → 框架名
# ---------------------------------------------------------------------------

_FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    # (indicator_filename_or_dir, framework_name)
    ("next.config.js", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("nuxt.config.ts", "Nuxt.js"),
    ("nuxt.config.js", "Nuxt.js"),
    ("vite.config.ts", "Vite"),
    ("vite.config.js", "Vite"),
    ("angular.json", "Angular"),
    ("svelte.config.js", "Svelte"),
    ("gatsby-config.js", "Gatsby"),
    ("astro.config.mjs", "Astro"),
    ("manage.py", "Django"),
    ("app.py", "Flask"),  # heuristic; may collide with FastAPI
    ("pyproject.toml", "_check_pyproject"),  # requires secondary check
    ("requirements.txt", "_check_requirements"),
    ("Cargo.toml", "Rust/Cargo"),
    ("go.mod", "Go module"),
    ("pom.xml", "Maven/Java"),
    ("build.gradle", "Gradle/Java"),
]

_PYPROJECT_FRAMEWORK_KEYWORDS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "starlette": "Starlette",
    "litestar": "Litestar",
    "tornado": "Tornado",
}

_REQUIREMENTS_FRAMEWORK_KEYWORDS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "starlette": "Starlette",
}

# ---------------------------------------------------------------------------
# 进入点检测：常见 entrypoint 文件名（按优先级）
# ---------------------------------------------------------------------------

_ENTRYPOINT_CANDIDATES: list[str] = [
    # Next.js / Remix
    "src/app/api/chat/route.ts",
    "src/app/layout.tsx",
    "src/pages/index.tsx",
    "src/pages/index.js",
    "pages/index.tsx",
    "pages/index.js",
    # Node
    "src/index.ts",
    "src/index.js",
    "index.ts",
    "index.js",
    "server.ts",
    "server.js",
    # Python
    "main.py",
    "app.py",
    "manage.py",
    "run.py",
    "src/main.py",
    # Go
    "main.go",
    "cmd/main.go",
]

# ---------------------------------------------------------------------------
# 命令检测：从 package.json scripts 或 Makefile 提取
# ---------------------------------------------------------------------------


def _detect_languages(repo_path: Path) -> list[str]:
    """统计仓库中各语言的文件数，返回按数量降序的语言列表。"""
    lang_counts: dict[str, int] = {}
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", ".next", ".nuxt", "coverage",
    }

    for root, dirs, files in os.walk(repo_path):
        # 跳过无关目录（in-place 修改 dirs 以避免递归进入）
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            lang = _EXT_TO_LANG.get(ext)
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

    # 按文件数降序，返回语言名列表
    return [lang for lang, _ in sorted(lang_counts.items(), key=lambda x: -x[1])]


def _detect_frameworks(repo_path: Path) -> list[str]:
    """通过特征文件检测框架，返回去重后的框架列表。"""
    frameworks: list[str] = []
    seen: set[str] = set()

    root_files = {f.name for f in repo_path.iterdir() if f.is_file()}

    for indicator, framework in _FRAMEWORK_INDICATORS:
        if indicator not in root_files:
            continue

        if framework == "_check_pyproject":
            # 读取 pyproject.toml，检查 [project.dependencies] 或 [tool.poetry.dependencies]
            try:
                content = (repo_path / "pyproject.toml").read_text(encoding="utf-8").lower()
                for keyword, fw_name in _PYPROJECT_FRAMEWORK_KEYWORDS.items():
                    if keyword in content and fw_name not in seen:
                        frameworks.append(fw_name)
                        seen.add(fw_name)
            except OSError:
                pass
        elif framework == "_check_requirements":
            try:
                content = (repo_path / "requirements.txt").read_text(encoding="utf-8").lower()
                for keyword, fw_name in _REQUIREMENTS_FRAMEWORK_KEYWORDS.items():
                    if keyword in content and fw_name not in seen:
                        frameworks.append(fw_name)
                        seen.add(fw_name)
            except OSError:
                pass
        else:
            if framework not in seen:
                frameworks.append(framework)
                seen.add(framework)

    return frameworks


def _detect_entrypoints(repo_path: Path) -> list[str]:
    """按优先级列表检测实际存在的 entrypoint 文件。"""
    found: list[str] = []
    for candidate in _ENTRYPOINT_CANDIDATES:
        if (repo_path / candidate).exists():
            found.append(candidate)
    return found


def _detect_commands(repo_path: Path) -> list[str]:
    """从 package.json scripts 或 Makefile 提取常用命令。"""
    commands: list[str] = []

    # 尝试 package.json
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            for script_name in ["dev", "start", "build", "test", "lint"]:
                if script_name in scripts:
                    commands.append(f"npm run {script_name}")
        except (OSError, ValueError):
            pass

    # 尝试 Makefile
    makefile = repo_path / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and line.endswith(":"):
                    target = line.rstrip(":")
                    if target and not target.startswith("."):
                        commands.append(f"make {target}")
        except OSError:
            pass

    # 尝试 pyproject.toml scripts
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            # 简单文本搜索，不依赖 tomllib（3.9 兼容）
            if "[tool.pytest" in content:
                commands.append("pytest")
            if "ruff" in content:
                commands.append("ruff check .")
            if "mypy" in content:
                commands.append("mypy .")
        except OSError:
            pass

    return commands


def _detect_storage_paths(repo_path: Path) -> list[str]:
    """检测常见存储/数据目录。"""
    storage_candidates = ["data/", "storage/", "db/", "database/", "uploads/", "files/", "cache/"]
    found: list[str] = []
    for candidate in storage_candidates:
        if (repo_path / candidate.rstrip("/")).exists():
            found.append(candidate)
    return found


def _detect_dependencies(repo_path: Path) -> list[str]:
    """提取顶层依赖名称列表（不含版本号）。"""
    deps: list[str] = []

    # package.json dependencies
    pkg_json = repo_path / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            for section in ["dependencies", "devDependencies"]:
                deps.extend(data.get(section, {}).keys())
        except (OSError, ValueError):
            pass

    # requirements.txt
    requirements = repo_path / "requirements.txt"
    if requirements.exists():
        try:
            for line in requirements.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # 去掉版本约束
                    pkg = line.split(">=")[0].split("==")[0].split("<=")[0].split("[")[0].strip()
                    if pkg:
                        deps.append(pkg)
        except OSError:
            pass

    return deps


def _build_repo_summary(
    repo_path: Path,
    languages: list[str],
    frameworks: list[str],
    entrypoints: list[str],
    config: Optional[dict],
) -> str:
    """生成简短的仓库摘要（纯确定性，不调用 LLM）。"""
    parts: list[str] = []
    repo_name = repo_path.name

    lang_str = ", ".join(languages[:3]) if languages else "unknown"
    parts.append(f"Repository '{repo_name}' written in {lang_str}.")

    if frameworks:
        parts.append(f"Detected frameworks: {', '.join(frameworks)}.")

    if entrypoints:
        parts.append(f"Primary entrypoint: {entrypoints[0]}.")
    else:
        parts.append("No standard entrypoint detected.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------


def extract_repo_facts(
    repo_path: str,
    config: Optional[dict] = None,
) -> RepoFacts:
    """从本地仓库路径提取 RepoFacts（Stage 0 确定性提取）。

    Args:
        repo_path: 仓库在本地文件系统的绝对路径。
        config: 可选配置字典，当前版本保留供后续扩展（如 exclude_dirs）。

    Returns:
        符合 dm.repo-facts.v1 schema 的 RepoFacts 实例。

    Raises:
        ValueError: repo_path 不存在或不是目录。
    """
    path = Path(repo_path).resolve()
    if not path.exists():
        raise ValueError(f"repo_path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"repo_path is not a directory: {path}")

    # --- 确定性提取 ---
    languages = _detect_languages(path)
    frameworks = _detect_frameworks(path)
    entrypoints = _detect_entrypoints(path)
    commands = _detect_commands(path)
    storage_paths = _detect_storage_paths(path)
    dependencies = _detect_dependencies(path)

    # --- 构建 RepoRef（骨架版本：sha 和 url 为占位值）---
    # url 使用 https://localhost 占位，因为 RepoRef.url 是 HttpUrl 类型，
    # 不接受 file:// 协议。实际集成 prepare-repo.sh 时会填入真实 GitHub URL。
    repo_ref = RepoRef(
        repo_id=path.name,
        full_name=f"local/{path.name}",
        url=f"https://localhost/local/{path.name}",
        default_branch="main",
        commit_sha="0000000000000000000000000000000000000000",
        local_path=str(path),
    )

    # --- 生成摘要 ---
    repo_summary = _build_repo_summary(path, languages, frameworks, entrypoints, config)

    return RepoFacts(
        repo=repo_ref,
        languages=languages,
        frameworks=frameworks,
        entrypoints=entrypoints,
        commands=commands,
        storage_paths=storage_paths,
        dependencies=dependencies,
        repo_summary=repo_summary,
    )
