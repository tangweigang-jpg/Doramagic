"""con_extract_resources phase handler — deterministic scan + Instructor enrichment.

Implements the resource extraction phase for SOP v2.2:
  Step A: deterministic scan of repo dependency declarations (no LLM)
  Step B: build resource context from blueprint replaceable_points + scanned deps
  Step C: Instructor structured call → ResourceExtractionResult
           with RawFallback graceful degradation to scan-only result
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..core.agent_loop import PhaseResult

if TYPE_CHECKING:
    from ..core.agent_loop import ExtractionAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt (kept here — tightly coupled with this handler's logic)
# ---------------------------------------------------------------------------

CON_RESOURCE_V2_SYSTEM = """\
你是资源提取专家。你的任务是从项目依赖声明和蓝图中提取「资源」信息。

## 资源定义
资源 = 让晶体成为可运行 skill 所需的 API、工具、依赖库等一切非 LLM 要素。
描述"是什么 + 能做什么 + 有什么限制"（陈述性）。

## 输出要求
对 external_services：
- install: 可直接执行的安装命令
- api_example: 最小可运行代码片段（5-15 行，从项目代码中提取真实用法）
- known_issues: 具体的坑（来源标注：文档/Issue/源码）
- fit_for/not_fit_for: 从蓝图 replaceable_points 继承

对 dependencies：
- critical=true: 缺失则核心功能完全不可用
- version: 从依赖声明中提取

对 infrastructure：
- 存储路径、缓存路径（从源码配置中推断）

不要虚构不存在的限制或功能。

## CRITICAL 规则
- 蓝图的每个 replaceable_point 的每个 option 都必须有对应的 external_service 条目。不能遗漏任何 option，包括非默认选项（如 QMT、其他数据源等）。
- api_example 不能为空字符串 — 如果无法从代码中提取示例，请写一个最小可运行的 5 行代码片段展示该服务的核心调用方式。
"""

# ---------------------------------------------------------------------------
# Step A: deterministic repo dependency scan
# ---------------------------------------------------------------------------

_DEP_LINE_RE = re.compile(
    r"^(?P<pkg>[A-Za-z0-9_.\-]+)"  # package name (with extras stripped below)
    r"(?:\[[^\]]*\])?"  # optional [extra]
    r"\s*(?P<ver>[><=!~^][^\s;#]*)?"  # optional version specifier
)


def _parse_requirements_txt(path: Path) -> list[dict[str, str]]:
    """Parse requirements.txt into a list of {package, version} dicts."""
    deps: list[dict[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r ") or line.startswith("--requirement "):
            # Include-reference — recurse into referenced file
            ref_file = line.split(None, 1)[1].strip()
            ref_path = path.parent / ref_file
            if ref_path.exists():
                deps.extend(_parse_requirements_txt(ref_path))
            else:
                logger.debug(
                    "requirements.txt includes -r %s but file not found at %s",
                    ref_file,
                    ref_path,
                )
            continue
        if line.startswith("-"):
            # Other pip flags (-e, --index-url, …)
            continue
        # Strip inline comment
        line = line.split("#")[0].strip()
        m = _DEP_LINE_RE.match(line)
        if m:
            deps.append(
                {
                    "package": m.group("pkg"),
                    "version": (m.group("ver") or "").strip(),
                }
            )
    return deps


def _parse_pyproject_toml(path: Path) -> list[dict[str, str]]:
    """Parse pyproject.toml [project].dependencies or [tool.poetry.dependencies]."""
    text = path.read_text(encoding="utf-8", errors="replace")

    # Try stdlib tomllib first (Python 3.11+), fall back to regex
    try:
        import tomllib  # type: ignore[import]

        data: dict[str, Any] = tomllib.loads(text)
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import]

            data = tomllib.loads(text)
        except ImportError:
            data = {}

    deps: list[dict[str, str]] = []

    if data:
        # PEP 517 / PEP 621
        pep621_deps: list[str] = data.get("project", {}).get("dependencies", [])
        for dep_str in pep621_deps:
            m = _DEP_LINE_RE.match(dep_str.strip())
            if m:
                deps.append(
                    {
                        "package": m.group("pkg"),
                        "version": (m.group("ver") or "").strip(),
                    }
                )

        # Poetry
        poetry_deps: dict[str, Any] = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for pkg, ver_val in poetry_deps.items():
            if pkg.lower() == "python":
                continue
            if isinstance(ver_val, str):
                ver_str = ver_val
            elif isinstance(ver_val, dict):
                ver_str = ver_val.get("version", "")
            else:
                ver_str = ""
            deps.append({"package": pkg, "version": ver_str})

    if not deps:
        # Regex fallback: look for [project] dependencies = [...] or [tool.poetry.dependencies]
        pep_block = re.search(
            r"\[project\].*?dependencies\s*=\s*\[(.*?)\]",
            text,
            re.DOTALL,
        )
        if pep_block:
            for item in re.findall(r'"([^"]+)"|\'([^\']+)\'', pep_block.group(1)):
                raw = (item[0] or item[1]).strip()
                m = _DEP_LINE_RE.match(raw)
                if m:
                    deps.append(
                        {
                            "package": m.group("pkg"),
                            "version": (m.group("ver") or "").strip(),
                        }
                    )

    return deps


def _parse_setup_py(path: Path) -> list[dict[str, str]]:
    """Extract install_requires entries from setup.py via regex (no exec)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    block = re.search(
        r"install_requires\s*=\s*\[(.*?)\]",
        text,
        re.DOTALL,
    )
    if not block:
        return []
    deps: list[dict[str, str]] = []
    for item in re.findall(r'"([^"]+)"|\'([^\']+)\'', block.group(1)):
        raw = (item[0] or item[1]).strip()
        m = _DEP_LINE_RE.match(raw)
        if m:
            deps.append(
                {
                    "package": m.group("pkg"),
                    "version": (m.group("ver") or "").strip(),
                }
            )
    return deps


def _parse_setup_cfg(path: Path) -> list[dict[str, str]]:
    """Extract install_requires from [options] section in setup.cfg."""
    import configparser

    cfg = configparser.ConfigParser()
    cfg.read_string(path.read_text(encoding="utf-8", errors="replace"))
    raw = cfg.get("options", "install_requires", fallback="")
    deps: list[dict[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _DEP_LINE_RE.match(line)
        if m:
            deps.append(
                {
                    "package": m.group("pkg"),
                    "version": (m.group("ver") or "").strip(),
                }
            )
    return deps


def scan_repo_dependencies(repo_path: Path) -> dict[str, Any]:
    """Scan repo for dependency declarations. Returns raw dependency data.

    Checks all candidate files in priority order and accumulates results.
    Empty results (e.g. a requirements.txt that only contains -r references
    whose targets have now been recursed into) no longer cause early exit.
    Returns: {"dependencies": [...], "source_file": "<filename or filenames>"}
    """
    candidates: list[tuple[str, Path]] = [
        ("requirements.txt", repo_path / "requirements.txt"),
        ("pyproject.toml", repo_path / "pyproject.toml"),
        ("setup.py", repo_path / "setup.py"),
        ("setup.cfg", repo_path / "setup.cfg"),
    ]

    all_deps: list[dict[str, str]] = []
    source_files: list[str] = []

    for source_name, candidate_path in candidates:
        if not candidate_path.exists():
            continue
        try:
            if source_name == "requirements.txt":
                deps = _parse_requirements_txt(candidate_path)
            elif source_name == "pyproject.toml":
                deps = _parse_pyproject_toml(candidate_path)
            elif source_name == "setup.py":
                deps = _parse_setup_py(candidate_path)
            else:
                deps = _parse_setup_cfg(candidate_path)

            logger.info(
                "scan_repo_dependencies: parsed %s (%d packages)",
                source_name,
                len(deps),
            )
            if deps:
                all_deps.extend(deps)
                source_files.append(source_name)

        except Exception as exc:
            logger.warning(
                "scan_repo_dependencies: failed to parse %s — %s",
                candidate_path,
                exc,
            )
            continue

    # Deduplicate by package name (case-insensitive), preserving first-seen order
    seen: set[str] = set()
    unique_deps: list[dict[str, str]] = []
    for d in all_deps:
        pkg_key = d.get("package", "").lower()
        if pkg_key and pkg_key not in seen:
            seen.add(pkg_key)
            unique_deps.append(d)

    if unique_deps:
        source_label = ", ".join(source_files)
        logger.info(
            "scan_repo_dependencies: total %d unique packages from [%s]",
            len(unique_deps),
            source_label,
        )
        return {"dependencies": unique_deps, "source_file": source_label}

    logger.info("scan_repo_dependencies: no dependency file found in %s", repo_path)
    return {"dependencies": [], "source_file": None}


# ---------------------------------------------------------------------------
# Step B: build resource context for Instructor call
# ---------------------------------------------------------------------------


def build_resource_context(
    blueprint: dict[str, Any],
    manifest: dict[str, Any],
    scanned_deps: dict[str, Any],
) -> str:
    """Build user message for Instructor call with all resource context.

    Assembles:
    1. Blueprint replaceable_points options (name / traits / fit_for / not_fit_for)
    2. Scanned dependency list
    3. Blueprint applicability.prerequisites (if any)
    4. Blueprint source.projects (repo names)
    """
    parts: list[str] = []

    # -- 1. replaceable_points from all stages --
    stages: list[dict[str, Any]] = blueprint.get("stages", [])
    rp_blocks: list[str] = []
    for stage in stages:
        stage_id = stage.get("id", "?")
        rps = stage.get("replaceable_points", [])
        if not rps:
            continue
        for rp in rps:
            if not isinstance(rp, dict):
                continue
            rp_name = rp.get("name", "")
            options = rp.get("options", [])
            options_text = yaml.dump(options, allow_unicode=True, default_flow_style=False).strip()
            rp_blocks.append(
                f"### replaceable_point: {rp_name} (stage={stage_id})\n"
                f"description: {rp.get('description', '')}\n"
                f"default: {rp.get('default', '')}\n"
                f"options:\n{options_text}\n"
                f"selection_criteria: {rp.get('selection_criteria', '')}"
            )

    if rp_blocks:
        parts.append("## Blueprint Replaceable Points\n\n" + "\n\n".join(rp_blocks))

    # -- 1b. Explicit option coverage checklist --
    # Build a flat list of every option across all replaceable_points so the
    # LLM knows exactly which external_service entries it must produce.
    option_checklist: list[str] = []
    for stage in stages:
        stage_id = stage.get("id", "?")
        for rp in stage.get("replaceable_points", []):
            if not isinstance(rp, dict):
                continue
            rp_name = rp.get("name", "")
            for opt in rp.get("options", []):
                if isinstance(opt, dict):
                    opt_name = opt.get("name") or opt.get("value") or str(opt)
                elif isinstance(opt, str):
                    opt_name = opt
                else:
                    opt_name = str(opt)
                option_checklist.append(
                    f"  - replaceable_point={rp_name} / option={opt_name} (stage={stage_id})"
                    " → 必须生成对应的 external_service 条目"
                )

    if option_checklist:
        parts.append(
            "## REQUIRED external_service 覆盖清单\n\n"
            "以下每个 option 都必须在 external_services 中有对应条目：\n"
            + "\n".join(option_checklist)
        )

    # -- 2. Scanned dependencies --
    dep_list: list[dict[str, str]] = scanned_deps.get("dependencies", [])
    source_file: str | None = scanned_deps.get("source_file")
    if dep_list:
        dep_lines = "\n".join(
            f"  - {d['package']}{' ' + d['version'] if d.get('version') else ''}" for d in dep_list
        )
        parts.append(f"## Scanned Dependencies (from {source_file})\n\n{dep_lines}")
    else:
        parts.append("## Scanned Dependencies\n\n(none found)")

    # -- 3. applicability.prerequisites --
    applicability: dict[str, Any] = blueprint.get("applicability", {})
    prerequisites = applicability.get("prerequisites", [])
    if prerequisites:
        prereq_text = "\n".join(f"  - {p}" for p in prerequisites)
        parts.append(f"## Blueprint Prerequisites\n\n{prereq_text}")

    # -- 4. source.projects --
    source: dict[str, Any] = blueprint.get("source", {})
    projects = source.get("projects", [])
    if projects:
        proj_text = "\n".join(
            f"  - {p}" if isinstance(p, str) else f"  - {p.get('name', p)}" for p in projects
        )
        parts.append(f"## Source Projects (repos)\n\n{proj_text}")

    # -- Instructions --
    bp_id = blueprint.get("id", "unknown")
    parts.append(
        f"## Instructions\n\n"
        f"Blueprint ID: {bp_id}\n"
        "Extract a ResourceExtractionResult covering:\n"
        "- external_services: EVERY option listed in 'REQUIRED external_service 覆盖清单' above must\n"
        "  have a corresponding entry. Do not skip any option, including non-default ones.\n"
        "- dependencies: critical Python packages (mark critical=true if system fails without them)\n"
        "- infrastructure: storage/cache paths inferred from source\n"
        "- optional: tools needed only in specific scenarios\n"
        "Derive fit_for/not_fit_for from the replaceable_points options above.\n"
        "api_example must never be an empty string — write at minimum a 5-line runnable snippet.\n"
        "Do not fabricate information not present in the context."
    )

    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Step C: fallback builder (scan-only, no LLM)
# ---------------------------------------------------------------------------


def _build_fallback_result(scanned_deps: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal ResourceExtractionResult from scan data only."""
    from .constraint_schemas_v2 import Dependency, ResourceExtractionResult

    dep_list: list[dict[str, str]] = scanned_deps.get("dependencies", [])
    source_file: str | None = scanned_deps.get("source_file")

    pydantic_deps = [
        Dependency(
            package=d["package"],
            version=d.get("version", ""),
            usage="",
            install=f"pip install {d['package']}",
            critical=False,
        )
        for d in dep_list
    ]

    result = ResourceExtractionResult(
        external_services=[],
        dependencies=pydantic_deps,
        infrastructure=[],
        optional=[],
    )
    logger.info(
        "Fallback resource result built from %s: %d dependencies",
        source_file or "no file",
        len(pydantic_deps),
    )
    return result.model_dump()


# ---------------------------------------------------------------------------
# Main phase handler
# ---------------------------------------------------------------------------


async def extract_resources(
    agent: ExtractionAgent,
    blueprint: dict[str, Any],
    manifest: dict[str, Any],
    repo_path: Path,
    artifacts_dir: Path,
) -> PhaseResult:
    """con_extract_resources phase — deterministic scan + Instructor enrichment.

    Args:
        agent: The running ExtractionAgent (provides run_structured_call).
        blueprint: Parsed blueprint dict (from blueprint YAML).
        manifest: Coverage manifest produced by con_build_manifest.
        repo_path: Root directory of the target repository.
        artifacts_dir: Directory to write artifacts (resources.json, etc.).

    Returns:
        PhaseResult with status "completed" or "error".
    """
    phase_name = "con_extract_resources"

    # -- Step A: deterministic scan --
    logger.info("%s: scanning repo dependencies in %s", phase_name, repo_path)
    scanned_deps = scan_repo_dependencies(repo_path)
    logger.info(
        "%s: scan result — source=%s deps=%d",
        phase_name,
        scanned_deps.get("source_file"),
        len(scanned_deps.get("dependencies", [])),
    )

    # -- Step B: build Instructor context --
    user_msg = build_resource_context(blueprint, manifest, scanned_deps)

    # -- Step C: Instructor call --
    from .constraint_schemas_v2 import RawFallback, ResourceExtractionResult

    result_dict: dict[str, Any]
    total_tokens: int = 0
    instructor_ok = False

    try:
        result, tokens = await agent.run_structured_call(
            CON_RESOURCE_V2_SYSTEM,
            user_msg,
            ResourceExtractionResult,
        )
        total_tokens = tokens

        if isinstance(result, RawFallback):
            logger.warning(
                "%s: Instructor L3 fallback (stage=%s) — using scan-only result",
                phase_name,
                result.stage,
            )
            # Save raw text for debugging
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            (artifacts_dir / "resources_raw_fallback.txt").write_text(
                result.text,
                encoding="utf-8",
            )
            result_dict = _build_fallback_result(scanned_deps)
        else:
            result_dict = result.model_dump()
            instructor_ok = True
            logger.info(
                "%s: Instructor succeeded — external_services=%d deps=%d infra=%d optional=%d",
                phase_name,
                len(result.external_services),
                len(result.dependencies),
                len(result.infrastructure),
                len(result.optional),
            )

    except Exception as exc:
        logger.warning(
            "%s: Instructor call raised %s — falling back to scan-only",
            phase_name,
            exc,
        )
        result_dict = _build_fallback_result(scanned_deps)

    # -- Write artifact --
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifacts_dir / "resources.json"
    output_path.write_text(
        json.dumps(result_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("%s: wrote %s", phase_name, output_path)

    n_services = len(result_dict.get("external_services", []))
    n_deps = len(result_dict.get("dependencies", []))
    n_infra = len(result_dict.get("infrastructure", []))
    summary = (
        f"external_services={n_services} "
        f"dependencies={n_deps} "
        f"infrastructure={n_infra} "
        f"instructor={'ok' if instructor_ok else 'fallback'} "
        f"tokens={total_tokens}"
    )

    return PhaseResult(
        phase_name=phase_name,
        status="completed",
        final_text=summary,
        total_tokens=total_tokens,
    )
