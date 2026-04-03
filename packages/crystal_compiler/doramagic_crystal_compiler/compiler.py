"""种子晶体编译器。将判断集按 crystal_section 组装成约束文本。"""

from __future__ import annotations

from datetime import datetime

from doramagic_judgment_schema.types import (
    CrystalSection,
    Judgment,
    Severity,
)

from .retrieve import RetrievalResult

CRYSTAL_TEMPLATE = """# 种子晶体：{domain} — {task_description}

> 本晶体由 Doramagic 知识系统编译，基于 {judgment_count} 颗判断。
> 知识库版本: {version} | 编译时间: {compiled_at}

{personalization_prompt}

---

## 硬约束（违反将导致严重后果）

{hard_constraints}

## 软约束（强烈建议遵守）

{soft_constraints}

## 资源边界

{resource_profile}

## 已知缺口

{coverage_gaps}
"""


def compile_crystal(
    retrieval: RetrievalResult,
    domain: str,
    task_description: str,
    version: str = "0.1.0",
) -> str:
    """将检索结果编译为种子晶体文本。"""
    hard_constraints: list[str] = []
    soft_constraints: list[str] = []
    resource_profile: list[str] = []

    for judgment, _weight in retrieval.judgments:
        line = _format_judgment(judgment)

        if judgment.compilation.severity in (
            Severity.FATAL,
            Severity.HIGH,
        ):
            modality = judgment.core.modality
            if not isinstance(modality, str):
                modality = modality.value
            if modality in ("must", "must_not"):
                hard_constraints.append(line)
            else:
                soft_constraints.append(line)
        elif judgment.compilation.crystal_section == CrystalSection.RESOURCE_PROFILE:
            resource_profile.append(line)
        else:
            soft_constraints.append(line)

    personalization_prompt = (
        "> **个性化提示**：为了让本晶体更精准地约束你的工作，"
        "请告诉我：\n"
        "> 1. 你使用的具体框架和版本？\n"
        "> 2. 你的目标市场？\n"
        "> 3. 你的经验水平（新手/中级/专家）？\n"
        "> 4. 你的具体任务？"
    )

    gaps_text = (
        "\n".join(f"- {g}" for g in retrieval.coverage_gaps)
        if retrieval.coverage_gaps
        else "无已知缺口。"
    )

    return CRYSTAL_TEMPLATE.format(
        domain=domain,
        task_description=task_description,
        judgment_count=len(retrieval.judgments),
        version=version,
        compiled_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        personalization_prompt=personalization_prompt,
        hard_constraints=("\n\n".join(hard_constraints) if hard_constraints else "（暂无硬约束）"),
        soft_constraints=("\n\n".join(soft_constraints) if soft_constraints else "（暂无软约束）"),
        resource_profile=(
            "\n\n".join(resource_profile) if resource_profile else "（暂无资源边界信息）"
        ),
        coverage_gaps=gaps_text,
    )


def _format_judgment(j: Judgment) -> str:
    """将一颗判断格式化为晶体中的约束文本。"""
    modality_val = j.core.modality
    if not isinstance(modality_val, str):
        modality_val = modality_val.value

    modality_prefix = {
        "must": "必须",
        "must_not": "禁止",
        "should": "应当",
        "should_not": "不应",
    }
    prefix = modality_prefix.get(modality_val, "")

    evidence = ""
    if j.confidence.evidence_refs:
        ref = j.confidence.evidence_refs[0]
        evidence = f"（{ref.source}: {ref.summary}）"

    return (
        f"{prefix}：当{j.core.when}时，{j.core.action}。\n"
        f"  → 否则：{j.core.consequence.description}\n"
        f"  {evidence}"
    )
