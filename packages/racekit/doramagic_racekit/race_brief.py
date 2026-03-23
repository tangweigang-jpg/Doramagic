"""Generate racer-facing briefs from the module spec document."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .race_config import RacerName, canonical_module_name, module_branch_slug, normalize_identifier
from .race_workspace import _resolve_output_root, _resolve_repo_root


def _extract_module_section(spec_text: str, module_name: str) -> str:
    target = normalize_identifier(canonical_module_name(module_name))
    lines = spec_text.splitlines()
    start_index = None
    end_index = len(lines)

    for index, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        if target in normalize_identifier(line):
            start_index = index
            break

    if start_index is None:
        raise ValueError("Module spec not found: {0}".format(module_name))

    for index in range(start_index + 1, len(lines)):
        if lines[index].startswith("## "):
            end_index = index
            break

    return "\n".join(lines[start_index:end_index]).strip()


def _split_subsections(section_text: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current_title = ""

    for line in section_text.splitlines():
        match = re.match(r"^###\s+\d+\.\s+(.+)$", line)
        if match:
            current_title = match.group(1).strip()
            sections[current_title] = []
            continue

        if current_title:
            sections[current_title].append(line)

    return {
        title: "\n".join(content).strip()
        for title, content in sections.items()
    }


def _fixture_paths(repo_root: Path) -> List[str]:
    fixtures_root = repo_root / "data" / "fixtures"
    if not fixtures_root.exists():
        return ["data/fixtures/"]

    return [
        str(path.relative_to(repo_root))
        for path in sorted(fixtures_root.rglob("*"))
        if path.is_file()
    ]


def generate_brief(round_num: int, module_name: str, racer_name: str, spec_path: str) -> Path:
    """Generate a brief file for one racer and module pairing."""

    spec_file = Path(spec_path).expanduser().resolve()
    spec_text = spec_file.read_text(encoding="utf-8")
    canonical_module = canonical_module_name(module_name)
    racer = RacerName.coerce(racer_name)
    repo_root = _resolve_repo_root(spec_file.parent)
    output_root = _resolve_output_root(repo_root)
    output_path = (
        output_root
        / "r{0:02d}".format(round_num)
        / module_branch_slug(canonical_module)
        / racer.value
        / "BRIEF.md"
    )

    module_section = _extract_module_section(spec_text, canonical_module)
    subsections = _split_subsections(module_section)
    fixture_lines = "\n".join("- `{0}`".format(item) for item in _fixture_paths(repo_root))

    content = """# Doramagic Race Brief

- Round: {round_num}
- Module: `{module_name}`
- Racer: {racer_name} ({racer_slug})
- Source Spec: `{spec_path}`

## 模块职责

{responsibility}

## 输入 Schema

{input_schema}

## 输出 Schema

{output_schema}

## 验收标准

{acceptance}

## 设计自由度

{freedom}

## Fixture 路径

{fixture_lines}

## 交付清单

1. 模块代码
2. 单元测试
3. 至少 1 条基于 Sim2 或等价 fixture 的集成测试
4. `README.md`
5. `DECISIONS.md`
""".format(
        round_num=round_num,
        module_name=canonical_module,
        racer_name=racer.display_name,
        racer_slug=racer.value,
        spec_path=str(spec_file),
        responsibility=subsections.get("模块名称与职责", "见规格文档。"),
        input_schema=subsections.get("输入契约", "见规格文档。"),
        output_schema=subsections.get("输出契约", "见规格文档。"),
        acceptance=subsections.get("验收标准", "见规格文档。"),
        freedom=subsections.get("设计自由度", "见规格文档。"),
        fixture_lines=fixture_lines,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
