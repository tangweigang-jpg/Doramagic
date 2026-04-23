#!/usr/bin/env python3
"""emit_skill_bundle.py — V6 seed.yaml → agentskills.io 合规 SKILL bundle

对齐 2025-12 Anthropic agentskills.io 开放标准
（Claude Code / Claude.ai / ClawHub / Cursor / VS Code Copilot 均支持）。

输入:
    seed.yaml (V6.1+ Doramagic 晶体)

输出:
    {slug}.skill/{slug}/
    ├── SKILL.md                    # agentskills.io 标准入口
    ├── references/
    │   ├── seed.yaml               # 权威全量
    │   ├── ANTI_PATTERNS.md        # 跨项目反模式
    │   ├── WISDOM.md               # 跨项目精华
    │   ├── CONSTRAINTS.md          # domain + fatal
    │   ├── USE_CASES.md            # 全量 KUC
    │   ├── LOCKS.md                # SL + preconditions
    │   └── COMPONENTS.md           # AST 组件地图
    └── human_summary.md

Skill bundles contain only knowledge files — no install scripts, no executable
artifacts. Dependency info lives in seed.yaml `resources.packages` as
informational metadata; the host AI decides how (and whether) to install deps
in the user's project environment.

Usage:
    python scripts/emit_skill_bundle.py \\
        --seed knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v6.1.seed.yaml \\
        --out _runs/skill_bundles/
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

# ----------------------------------------------------------------------
# Constants (agentskills.io spec)
# ----------------------------------------------------------------------

SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SKILL_NAME_MAX = 64
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
SKILL_MD_MAX_LINES = 200
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def _validate_skill_name(name: str) -> None:
    """agentskills.io 规则：[a-z0-9-], 1-64 chars, 无首尾/连续连字符。"""
    if not (1 <= len(name) <= SKILL_NAME_MAX):
        raise ValueError(f"skill name length out of [1,{SKILL_NAME_MAX}]: {name!r} ({len(name)})")
    if "--" in name:
        raise ValueError(f"skill name has consecutive hyphens: {name!r}")
    if not SKILL_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"skill name violates pattern [a-z0-9-]: {name!r}")


def _validate_description(description: str) -> None:
    if not isinstance(description, str) or not description.strip():
        raise ValueError("description must be a non-empty string")
    if len(description) > DESCRIPTION_MAX:
        raise ValueError(f"description exceeds {DESCRIPTION_MAX} chars: {len(description)}")


def _validate_compatibility(compatibility: str) -> None:
    if not isinstance(compatibility, str) or not compatibility.strip():
        raise ValueError("compatibility must be a non-empty string when provided")
    if len(compatibility) > COMPATIBILITY_MAX:
        raise ValueError(f"compatibility exceeds {COMPATIBILITY_MAX} chars: {len(compatibility)}")


def _validate_skill_md(skill_md_path: Path, expected_name: str) -> None:
    text = skill_md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > SKILL_MD_MAX_LINES:
        raise ValueError(f"SKILL.md exceeds {SKILL_MD_MAX_LINES} lines: {len(lines)}")
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        end_idx = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("SKILL.md frontmatter closing delimiter not found") from exc
    frontmatter = yaml.safe_load("\n".join(lines[1:end_idx])) or {}
    name = frontmatter.get("name")
    if name != expected_name:
        raise ValueError(f"frontmatter name {name!r} must equal parent directory {expected_name!r}")
    _validate_skill_name(name)
    _validate_description(frontmatter.get("description", ""))
    if "compatibility" in frontmatter:
        _validate_compatibility(frontmatter["compatibility"])


def _validate_markdown_links(skill_dir: Path) -> None:
    missing: list[str] = []
    for md_path in skill_dir.rglob("*.md"):
        text = md_path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_PATTERN.findall(text):
            target = raw_target.split("#", 1)[0].split("?", 1)[0].strip()
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (md_path.parent / target).resolve()
            if not resolved.exists():
                rel_md = md_path.relative_to(skill_dir)
                missing.append(f"{rel_md}: {raw_target}")
    if missing:
        details = "\n".join(f"- {item}" for item in missing)
        raise ValueError(f"bundle contains dangling markdown links:\n{details}")


# ----------------------------------------------------------------------
# Seed path parsing
# ----------------------------------------------------------------------


def _derive_slug(seed_path: Path) -> tuple[str, str]:
    """从 seed 路径派生 (blueprint_id, project_slug)。

    例：knowledge/.../finance-bp-009--zvt/xxx.seed.yaml
        → ("finance-bp-009", "zvt")
    """
    parent = seed_path.parent.name
    if not parent:
        raise ValueError(f"cannot derive skill slug from empty parent directory: {seed_path}")
    if "--" in parent:
        bp_id, project_slug = parent.split("--", 1)
    else:
        bp_id = parent
        project_slug = ""
    return _normalize_slug_part(bp_id, "blueprint_id"), _normalize_slug_part(
        project_slug, "project_slug"
    ) if project_slug else ""


def _normalize_slug_part(value: str, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        raise ValueError(f"{label} is empty after normalization: {value!r}")
    return slug


# ----------------------------------------------------------------------
# Description synthesizer
# ----------------------------------------------------------------------

_NOISE_TERMS = {
    # Documentation tooling
    "sphinx",
    "autodoc",
    "numpydoc",
    "sphinx-apidoc",
    "apidoc",
    "documentation",
    "documentations",
    "docs",
    "doc",
    "readthedocs",
    "docstring",
    "readme",
    "changelog",
    "license",
    "contributing",
    # Scaffolding / build / deploy
    "scaffold",
    "scaffolding",
    "template",
    "boilerplate",
    "deploy",
    "deployment",
    "install",
    "installation",
    "setup",
    "config",
    "configuration",
    "build",
    "builds",
    "makefile",
    "dockerfile",
    "pipeline config",
    "ci",
    "github action",
    # Testing
    "test",
    "tests",
    "testing",
    "unit test",
    "integration test",
    "test file",
    "test files",
    "test utilities",
    "testing utilities",
    "test case",
    "test generation",
    "fixture",
    "fixtures",
    "mock",
    "tempdir",
    "validation",
    # Lint / format
    "lint",
    "format",
    "pre-commit",
    "precommit",
    # Generic infra (not business)
    "api service",
    "backend",
    "frontend",
    "server",
    # Chinese equivalents
    "文档",
    "部署",
    "安装",
    "配置",
    "构建",
    "测试",
    "脚手架",
    "模板",
    "API服务",
    "api服务",
    "后端",
    "前端",
    "调度",
}


def _collect_uc_keywords(uc_entries: list[dict] | None, top_n: int = 8) -> list[str]:
    """Extract top-N business-signal triggers from uc_entries, filtering engineering noise.

    Previous impl: took top 6 UCs × first 2 positive_terms = often landed on
    doc/scaffold/test terms (sphinx/documentation/unit test/tempdir) when the
    blueprint's early UCs happened to be boilerplate. Now scans ≥30 UCs and
    blacklists obvious non-business terms.
    """
    if not uc_entries:
        return []
    seen: set[str] = set()
    kws: list[str] = []
    for uc in uc_entries[:30]:
        for t in uc.get("positive_terms") or []:
            if not isinstance(t, str):
                continue
            t_clean = t.strip()
            if not t_clean:
                continue
            t_lower = t_clean.lower()
            if t_lower in seen:
                continue
            # Skip if any noise term ≥3 chars matches (substring) t_lower.
            # This catches "autodoc" (contains doc), "test files" (contains test),
            # "docs build" (contains docs), "numpydoc" (contains doc), etc.
            if t_lower in _NOISE_TERMS or any(n in t_lower for n in _NOISE_TERMS if len(n) >= 3):
                continue
            seen.add(t_lower)
            kws.append(t_clean)
            if len(kws) >= top_n:
                return kws
    # Fallback: if positive_terms were all noise, extract trigger phrases from
    # uc.name (first 3-4 words). Handles blueprints with poor intent_router.
    if not kws:
        for uc in uc_entries[: top_n * 2]:
            name = (uc.get("name") or uc.get("short_description") or "").strip()
            if not name:
                continue
            name_lower = name.lower()
            if any(n in name_lower for n in _NOISE_TERMS if len(n) >= 3):
                continue
            words = [w for w in name.split()[:4] if w.isalnum() or "-" in w]
            if len(words) < 2:
                continue
            phrase = " ".join(words).lower()
            if phrase in seen:
                continue
            seen.add(phrase)
            kws.append(phrase)
            if len(kws) >= top_n:
                break
    return kws


def _build_negative_scope(seed: dict) -> str:
    markets = (seed.get("meta", {}).get("capability_tags", {}) or {}).get("markets") or []
    if markets and "cn-astock" in markets:
        return "non-Chinese A-share markets (US / HK / crypto) or non-quant-backtest workflows"
    return "markets or workflows outside declared capability_tags"


def _build_description(
    seed: dict,
    max_chars: int = DESCRIPTION_MAX,
) -> str:
    # Honor LLM-generated override if present (injected in emit_skill_bundle)
    override = (seed.get("_runtime_opts") or {}).get("description_override")
    if override:
        override = override.strip()
        if len(override) > max_chars:
            override = override[: max_chars - 3].rstrip() + "..."
        _validate_description(override)
        return override
    """Build project-specific description from objective seed fields only.

    Avoids tagline/positioning (which are prone to bp-009 template pollution
    via default values in compile_crystal_skeleton.py). Uses only:
      - meta.blueprint_id        (project identity)
      - meta.capability_tags     (markets + activities)
      - intent_router.uc_entries (top trigger keywords — truly project-specific)
    """
    meta = seed.get("meta", {}) or {}
    bp_id = meta.get("blueprint_id", "unknown")
    tags = meta.get("capability_tags", {}) or {}
    markets = tags.get("markets") or []
    activities = tags.get("activities") or []

    uc_entries = (seed.get("intent_router") or {}).get("uc_entries") or []
    kws = _collect_uc_keywords(uc_entries, top_n=8)

    # Compose a factual, non-templated description.
    acts = ", ".join(activities[:3]) if activities else "analytics"
    mks = "/".join(markets) if markets else "finance"
    parts = [f"Crystal skill compiled from {bp_id} ({acts} on {mks})."]
    if kws:
        parts.append(f"Triggers: {', '.join(kws)}.")

    desc = " ".join(parts)
    if len(desc) > max_chars:
        desc = desc[: max_chars - 3].rstrip() + "..."
    _validate_description(desc)
    return desc


# ----------------------------------------------------------------------
# UC helpers
# ----------------------------------------------------------------------


def _top_ucs(seed: dict, n: int = 3) -> list[dict]:
    pin = seed.get("post_install_notice") or {}
    msg = pin.get("message_template") or {}
    cat = msg.get("capability_catalog") or {}
    groups = cat.get("groups") or []
    flat: list[dict] = []
    for g in groups:
        for uc in g.get("ucs", []) or []:
            flat.append(uc)
            if len(flat) >= n:
                return flat[:n]
    return flat[:n]


# ----------------------------------------------------------------------
# SKILL.md renderer (f-string, no Jinja2)
# ----------------------------------------------------------------------


def render_skill_md(seed: dict, skill_name: str, bp_id: str) -> str:
    meta = seed.get("meta", {}) or {}
    ep = meta.get("execution_protocol", {}) or {}
    hs = seed.get("human_summary", {}) or {}
    what_can = hs.get("what_i_can_do") or {}
    opts = seed.get("_runtime_opts") or {}
    tagline_raw = (
        opts.get("tagline_override") or what_can.get("tagline") or "Doramagic-compiled quant skill"
    )
    # Collapse multi-line tagline (YAML |- keeps internal newlines) to one line
    tagline = " ".join(tagline_raw.split())
    display_name_zh = opts.get("display_name_zh")
    uc_entries = (seed.get("intent_router") or {}).get("uc_entries") or []
    description = _build_description(seed)

    arch = seed.get("architecture") or {}
    pipeline = arch.get("pipeline") or "data → factor → selector → trader"

    top_ucs = _top_ucs(seed, n=3) or uc_entries[:3]
    total_uc = len(uc_entries)

    ap = seed.get("anti_patterns") or []
    total_ap = len(ap)
    top_ap_high = [x for x in ap if x.get("severity") in ("high", "fatal")][:3]

    sls = (seed.get("spec_lock_registry") or {}).get("semantic_locks") or []
    fatal_sls = [s for s in sls if s.get("violation_is") == "fatal"][:8]

    what_ask = (hs.get("what_i_ask_you") or [])[:6]

    eq = seed.get("evidence_quality") or {}
    eq_notice = (
        eq.get("user_disclosure_template", "").strip() if eq.get("user_disclosure_template") else ""
    )

    markets_str = ", ".join((meta.get("capability_tags") or {}).get("markets") or [])
    activities_str = ", ".join((meta.get("capability_tags") or {}).get("activities") or [])
    version = meta.get("version", "v6.1")
    compiled_at = meta.get("compiled_at", "")

    execute_trigger = ep.get("execute_trigger", "user intent matches intent_router + action verb")

    compatibility = (
        "Knowledge-only skill bundle. Host AI consumes it directly from the URL "
        "— no installation required on the user's side."
    )
    _validate_compatibility(compatibility)

    # ---- Frontmatter ----
    fm_lines = [
        "---",
        f"name: {skill_name}",
        "description: |-",
    ]
    for line in description.split("\n"):
        fm_lines.append(f"  {line}")
    fm_lines += [
        "license: Proprietary. See LICENSE.txt in project root.",
        f"compatibility: {compatibility}",
        "metadata:",
        f'  version: "{version}"',
        f'  blueprint_id: "{bp_id}"',
        f'  compiled_at: "{compiled_at}"',
        f'  capability_markets: "{markets_str}"',
        f'  capability_activities: "{activities_str}"',
        f'  sop_version: "{meta.get("sop_version", "crystal-compilation-v6.1")}"',
        "---",
        "",
    ]
    frontmatter = "\n".join(fm_lines)

    # ---- Body ----
    h1 = f"# {display_name_zh} ({skill_name})" if display_name_zh else f"# {skill_name}"
    body = [
        h1,
        "",
        f"> {tagline}",
        "",
        "## Pipeline",
        "",
        f"`{pipeline}`",
        "",
        f"## Top Use Cases ({total_uc} total)",
        "",
    ]
    for uc in top_ucs:
        name = uc.get("name") or uc.get("uc_id", "UC-?")
        uc_id = uc.get("uc_id", "")
        desc = uc.get("short_description") or uc.get("description") or ""
        triggers = uc.get("sample_triggers") or []
        trig_str = ", ".join(triggers[:3]) if triggers else ""
        body.append(f"### {name} (`{uc_id}`)")
        body.append(desc.strip())
        if trig_str:
            body.append(f"**Triggers**: {trig_str}")
        body.append("")
    if total_uc > 3:
        body.append(
            f"For all **{total_uc}** use cases, see "
            "[references/USE_CASES.md](references/USE_CASES.md)."
        )
        body.append("")

    body += [
        f"**Execute trigger**: `{execute_trigger}`",
        "",
    ]

    if what_ask:
        body.append("## What I'll Ask You")
        body.append("")
        for q in what_ask:
            body.append(f"- {q}")
        body.append("")

    if fatal_sls:
        body += [
            "## Semantic Locks (Fatal)",
            "",
            "| ID | Rule | On Violation |",
            "|---|---|---|",
        ]
        for sl in fatal_sls:
            sid = sl.get("id", "?")
            desc = (sl.get("description") or sl.get("rule") or "").strip()
            body.append(f"| `{sid}` | {_oneline(desc)} | halt |")
        body.append("")
        body.append("Full lock definitions: [references/LOCKS.md](references/LOCKS.md)")
        body.append("")

    if top_ap_high:
        body.append(f"## Top Anti-Patterns ({total_ap} total)")
        body.append("")
        for ap_entry in top_ap_high:
            aid = ap_entry.get("id", "?")
            title = ap_entry.get("title") or ap_entry.get("description", "")
            body.append(f"- **`{aid}`**: {_oneline(title)}")
        body.append("")
        body.append(
            f"All {total_ap} anti-patterns: "
            "[references/ANTI_PATTERNS.md](references/ANTI_PATTERNS.md)"
        )
        body.append("")

    if eq_notice:
        body += [
            "## Evidence Quality Notice",
            "",
            f"> {_oneline(eq_notice)}",
            "",
        ]

    body += [
        "## Reference Files",
        "",
        "| File | Contents | When to Load |",
        "|---|---|---|",
        "| [references/seed.yaml](references/seed.yaml) | "
        "V6+ 全量权威 (source-of-truth) | 有行为/决策争议时必读 |",
        f"| [references/ANTI_PATTERNS.md](references/ANTI_PATTERNS.md) | "
        f"{total_ap} 条跨项目反模式 | 开始实现前 |",
        "| [references/WISDOM.md](references/WISDOM.md) | 跨项目精华借鉴 | 架构决策时 |",
        "| [references/CONSTRAINTS.md](references/CONSTRAINTS.md) | "
        "domain + fatal 约束 | 规则冲突时 |",
        "| [references/USE_CASES.md](references/USE_CASES.md) | "
        "全量 KUC-* 业务场景 | 需要完整示例时 |",
        "| [references/LOCKS.md](references/LOCKS.md) | "
        "SL-* + preconditions + hints | 生成回测/交易代码前 |",
        "| [references/COMPONENTS.md](references/COMPONENTS.md) | "
        "AST 组件地图（按 module 拆分）| 查 API 时 |",
        "",
        "---",
        "",
        f"*Compiled by Doramagic {meta.get('sop_version', 'v6.1')} "
        f"from `{bp_id}` blueprint at {compiled_at}.*",
        "*See [human_summary.md](human_summary.md) for non-technical overview.*",
        "",
    ]

    return frontmatter + "\n".join(body)


def _oneline(s: str) -> str:
    return " ".join(s.split())


# ----------------------------------------------------------------------
# references/ renderers
# ----------------------------------------------------------------------


def _write_anti_patterns_md(refs: Path, ap_list: list[dict]) -> None:
    lines = ["# Anti-Patterns (Cross-Project)", "", f"Total: **{len(ap_list)}**", ""]
    groups: dict[str, list[dict]] = {}
    for ap in ap_list:
        proj = ap.get("project_source") or ap.get("source_project") or "other"
        groups.setdefault(proj, []).append(ap)
    for proj, items in sorted(groups.items()):
        lines.append(f"## {proj} ({len(items)})")
        lines.append("")
        for ap in items:
            aid = ap.get("id", "?")
            title = _oneline(ap.get("title", ""))
            sev = ap.get("severity", "")
            lines.append(f"### `{aid}` — {title} <sub>({sev})</sub>")
            lines.append("")
            desc = ap.get("description", "").strip()
            if desc:
                lines.append(desc)
                lines.append("")
            link = ap.get("issue_link") or ap.get("url") or ""
            if link:
                lines.append(f"Source: {link}")
                lines.append("")
    (refs / "ANTI_PATTERNS.md").write_text("\n".join(lines), encoding="utf-8")


def _write_wisdom_md(refs: Path, wisdom_list: list[dict]) -> None:
    lines = ["# Cross-Project Wisdom", "", f"Total: **{len(wisdom_list)}**", ""]
    for w in wisdom_list:
        wid = w.get("wisdom_id") or w.get("id", "?")
        name = w.get("pattern_name") or w.get("name", "")
        src = w.get("source_project", "")
        act = w.get("applicable_to_activity") or w.get("applicable_to", "")
        lines.append(f"## `{wid}` — {name}")
        lines.append(f"**From**: {src} · **Applicable to**: {act}")
        lines.append("")
        desc = (w.get("description") or "").strip()
        if desc:
            lines.append(desc)
            lines.append("")
    (refs / "WISDOM.md").write_text("\n".join(lines), encoding="utf-8")


def _write_constraints_md(refs: Path, seed: dict) -> None:
    lines = ["# Constraints", ""]
    # Fatal (from spec_lock_registry or fatal_constraints or preservation)
    fatal_src = []
    for cand in ("fatal_constraints", "preservation_manifest"):
        v = seed.get(cand)
        if v:
            fatal_src.append((cand, v))
    for name, v in fatal_src:
        lines.append(f"## {name}")
        lines.append("")
        lines.append("```yaml")
        lines.append(yaml.safe_dump(v, allow_unicode=True, sort_keys=False, width=100)[:5000])
        lines.append("```")
        lines.append("")
    # Domain injected
    dci = seed.get("domain_constraints_injected") or []
    if dci:
        lines.append(f"## Domain Constraints Injected ({len(dci)})")
        lines.append("")
        for c in dci:
            cid = c.get("id", "?")
            stmt = _oneline(c.get("statement", ""))
            sev = c.get("severity", "")
            lines.append(f"- **`{cid}`** <sub>({sev})</sub>: {stmt}")
        lines.append("")
    (refs / "CONSTRAINTS.md").write_text("\n".join(lines), encoding="utf-8")


def _write_use_cases_md(refs: Path, kucs: list[dict]) -> None:
    lines = ["# Known Use Cases (KUC)", "", f"Total: **{len(kucs)}**", ""]
    for kuc in kucs:
        kid = kuc.get("kuc_id") or kuc.get("id", "?")
        src = kuc.get("source_file", "")
        problem = (kuc.get("business_problem") or "").strip()
        lines.append(f"## `{kid}`")
        if src:
            lines.append(f"**Source**: `{src}`")
        if problem:
            lines.append("")
            lines.append(problem)
        for key in ("inputs", "components", "parameters", "validation"):
            vs = kuc.get(key)
            if vs:
                lines.append("")
                lines.append(f"**{key.capitalize()}**:")
                if isinstance(vs, list):
                    for v in vs:
                        lines.append(f"- {v}")
                else:
                    lines.append(f"```\n{vs}\n```")
        lines.append("")
    (refs / "USE_CASES.md").write_text("\n".join(lines), encoding="utf-8")


def _write_locks_md(refs: Path, lock_reg: dict, preconditions: list) -> None:
    lines = ["# Semantic Locks + Preconditions", ""]
    sls = (lock_reg or {}).get("semantic_locks", [])
    if sls:
        lines.append(f"## Semantic Locks ({len(sls)})")
        lines.append("")
        for sl in sls:
            sid = sl.get("id", "?")
            viol = sl.get("violation_is", "")
            desc = _oneline(sl.get("description", sl.get("rule", "")))
            lines.append(f"### `{sid}` <sub>(on_violation: {viol})</sub>")
            lines.append(desc)
            hint = sl.get("traceback_hint") or sl.get("hint")
            if hint:
                lines.append(f"**Hint**: {_oneline(hint)}")
            lines.append("")
    if preconditions:
        lines.append(f"## Preconditions ({len(preconditions)})")
        lines.append("")
        for pc in preconditions:
            pid = pc.get("id", "?")
            check = pc.get("check_command") or pc.get("check", "")
            on_fail = pc.get("on_fail", "")
            lines.append(
                f"- **`{pid}`**: `{_oneline(str(check))}` → on_fail: {_oneline(str(on_fail))}"
            )
        lines.append("")
    (refs / "LOCKS.md").write_text("\n".join(lines), encoding="utf-8")


def _write_components_md(refs: Path, ccm: dict) -> None:
    lines = ["# Component Capability Map", ""]
    stats = ccm.get("stats", {})
    if stats:
        lines.append(f"**Project**: {ccm.get('project', '?')}")
        lines.append(f"**Scan date**: {ccm.get('scan_date', '?')}")
        lines.append(f"**Stats**: {stats}")
        lines.append("")
    modules = ccm.get("modules") or {}
    # 大模块拆子文件，避免单文件过大
    mod_dir = refs / "components"
    mod_dir.mkdir(parents=True, exist_ok=True)
    lines.append(f"## Modules ({len(modules)})")
    lines.append("")
    used_names: set[str] = set()
    for mod_name, mod_data in modules.items():
        classes = (mod_data or {}).get("classes") or []
        filename = _component_filename(str(mod_name), used_names)
        sub_path = mod_dir / filename
        # 子文件
        sub_lines = [f"# {mod_name} ({len(classes)} classes)", ""]
        for cls in classes:
            cname = cls.get("name", "?")
            cfile = cls.get("file", "")
            cline = cls.get("line", "")
            doc = _oneline(cls.get("docstring_first", ""))
            sub_lines.append(f"## `{cname}`")
            sub_lines.append(f"`{cfile}:{cline}`")
            if doc:
                sub_lines.append(f"> {doc}")
            sub_lines.append("")
        sub_path.write_text("\n".join(sub_lines), encoding="utf-8")
        lines.append(f"- [{mod_name}](components/{filename}): {len(classes)} classes")
    lines.append("")
    data_flow = ccm.get("data_flow_hints") or []
    if data_flow:
        lines.append(f"## Data Flow Hints ({len(data_flow)})")
        lines.append("")
        for hint in data_flow[:20]:
            lines.append(f"- {hint}")
    (refs / "COMPONENTS.md").write_text("\n".join(lines), encoding="utf-8")


def _component_filename(module_name: str, used_names: set[str]) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", module_name.strip()).strip(".-")
    stem = stem or "module"
    filename = f"{stem}.md"
    if filename not in used_names:
        used_names.add(filename)
        return filename
    idx = 2
    while f"{stem}-{idx}.md" in used_names:
        idx += 1
    filename = f"{stem}-{idx}.md"
    used_names.add(filename)
    return filename


def _package_spec(pkg: Any) -> str | None:
    if isinstance(pkg, str):
        return pkg.strip() or None
    if not isinstance(pkg, dict):
        return None
    name = str(pkg.get("name") or pkg.get("package") or "").strip()
    if not name:
        return None
    version = str(pkg.get("version") or pkg.get("version_pin") or "").strip()
    if not version or version.lower() == "latest" or re.search(r"([<>=!~]=?|@)", name):
        return name
    if re.match(r"^(==|!=|<=|>=|~=|<|>)", version):
        return f"{name}{version}"
    return f"{name}=={version}"


def _write_human_summary_md(skill_dir: Path, hs: dict) -> None:
    lines = ["# Human Summary", ""]
    what_can = hs.get("what_i_can_do") or {}
    if what_can.get("tagline"):
        lines.append(f"> {what_can['tagline']}")
        lines.append("")
    for key in ("what_i_can_do", "what_i_ask_you", "limitations"):
        v = hs.get(key)
        if v:
            lines.append(f"## {key.replace('_', ' ').title()}")
            lines.append("")
            if isinstance(v, dict):
                for k, vv in v.items():
                    lines.append(f"- **{k}**: {vv}")
            elif isinstance(v, list):
                for item in v:
                    lines.append(f"- {item}")
            else:
                lines.append(str(v))
            lines.append("")
    (skill_dir / "human_summary.md").write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------
# Main entry
# ----------------------------------------------------------------------


def emit_skill_bundle(seed_path: Path, out_dir: Path, _opts: dict | None = None) -> Path:
    seed_path = Path(seed_path)
    out_dir = Path(out_dir)

    seed = yaml.safe_load(seed_path.read_text(encoding="utf-8"))

    bp_id, project_slug = _derive_slug(seed_path)
    skill_name = (
        _opts.get("slug_override")
        if _opts and _opts.get("slug_override")
        else (f"{bp_id}-{project_slug}" if project_slug else bp_id)
    )
    _validate_skill_name(skill_name)

    # Load overrides in priority order:
    #   1. skill_metadata.yaml (CTO-locked bilingual) — highest priority
    #   2. descriptions_map.py (LLM-generated Chinese copy) — fallback
    desc_override = None
    tagline_override = None
    display_name_zh = None

    metadata_yaml = Path(__file__).resolve().parent / "skill_metadata.yaml"
    if metadata_yaml.exists():
        with metadata_yaml.open(encoding="utf-8") as f:
            metadata_data = yaml.safe_load(f) or {}
        entry = (metadata_data.get("skills") or {}).get(skill_name)
        if entry:
            desc_override = entry.get("description_zh")
            tagline_override = entry.get("tagline_zh")
            display_name_zh = entry.get("name_zh")

    if desc_override is None:
        try:
            from descriptions_map import FINAL_DESCRIPTIONS  # type: ignore

            desc_override = FINAL_DESCRIPTIONS.get(skill_name)
        except ImportError:
            pass

    opts = seed.setdefault("_runtime_opts", {})
    if desc_override:
        opts["description_override"] = desc_override
    if tagline_override:
        opts["tagline_override"] = tagline_override
    if display_name_zh:
        opts["display_name_zh"] = display_name_zh

    bundle_root = out_dir / f"{skill_name}.skill"
    skill_dir = bundle_root / skill_name
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    # SKILL.md
    skill_md = render_skill_md(seed, skill_name, bp_id)
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(skill_md, encoding="utf-8")

    # references/
    _write_anti_patterns_md(refs_dir, seed.get("anti_patterns") or [])
    _write_wisdom_md(refs_dir, seed.get("cross_project_wisdom") or [])
    _write_constraints_md(refs_dir, seed)
    _write_use_cases_md(refs_dir, seed.get("known_use_cases") or [])
    _write_locks_md(
        refs_dir,
        seed.get("spec_lock_registry") or {},
        seed.get("preconditions") or [],
    )
    _write_components_md(refs_dir, seed.get("component_capability_map") or {})

    # seed.yaml 权威副本
    shutil.copy(seed_path, refs_dir / "seed.yaml")

    # human_summary.md
    _write_human_summary_md(skill_dir, seed.get("human_summary") or {})

    _validate_skill_md(skill_md_path, skill_name)
    _validate_markdown_links(skill_dir)

    print(f"[emit_skill_bundle] Bundle written to: {bundle_root}")
    print(f"  skill_name: {skill_name}")
    print(f"  files in skill_dir: {len(list(skill_dir.rglob('*')))}")
    return bundle_root


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="V6 seed → agentskills.io bundle")
    p.add_argument("--seed", required=True, type=Path, help="V6 seed.yaml path")
    p.add_argument("--out", required=True, type=Path, help="bundle output dir")
    p.add_argument(
        "--slug-override", default=None, help="Override computed skill slug (e.g. 'qlib-ai-quant')"
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        opts = {"slug_override": args.slug_override} if args.slug_override else None
        emit_skill_bundle(args.seed, args.out, opts)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
