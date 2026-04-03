"""检索模块。直接匹配 + 1跳图谱 + 排序。"""

from __future__ import annotations

from dataclasses import dataclass

from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import Judgment, LifecycleStatus


@dataclass
class RetrievalResult:
    judgments: list[tuple[Judgment, float]]  # (judgment, weight)
    coverage_gaps: list[str]  # 识别到的缺口


def retrieve(
    store: JudgmentStore,
    domain: str,
    task_type: str | None = None,
    resources: list[str] | None = None,
) -> RetrievalResult:
    """
    根据领域和任务类型检索相关判断。
    Step 1: 直接匹配（domain + scope 过滤）→ P1 (权重 1.0)
    Step 2: 图谱扩展（1跳）→ P2 (权重 0.8)
    Step 3: 排序
    """
    # Step 1: 直接匹配
    p1: list[tuple[Judgment, float]] = []
    all_domain = store.list_by_domain(domain)
    active_statuses = (LifecycleStatus.ACTIVE, LifecycleStatus.DRAFT)
    for j in all_domain:
        if j.version.status not in active_statuses:
            continue
        # scope 过滤
        if j.scope.context_requires:
            if (
                task_type
                and j.scope.context_requires.task_types
                and task_type not in j.scope.context_requires.task_types
            ):
                continue
            if (
                resources
                and j.scope.context_requires.resources
                and not set(resources) & set(j.scope.context_requires.resources)
            ):
                continue
        p1.append((j, 1.0))

    # 加入 universal 判断
    for j in store.list_by_domain("universal"):
        if j.version.status in active_statuses:
            p1.append((j, 0.9))

    # Step 2: 图谱扩展（1跳）
    p2: list[tuple[Judgment, float]] = []
    seen_ids = {j.id for j, _ in p1}
    for j, _ in p1:
        related = store.get_relations(j.id, max_hops=1)
        for rel_j in related:
            if rel_j.id not in seen_ids:
                seen_ids.add(rel_j.id)
                p2.append((rel_j, 0.8))

    # Step 3: 排序
    all_results = p1 + p2
    severity_order = {"fatal": 4, "high": 3, "medium": 2, "low": 1}
    all_results.sort(
        key=lambda x: (
            x[1] * severity_order.get(x[0].compilation.severity, 1) * x[0].confidence.score
        ),
        reverse=True,
    )

    # 简单缺口检测
    coverage_gaps = _detect_gaps(domain, task_type, all_results)

    return RetrievalResult(judgments=all_results, coverage_gaps=coverage_gaps)


def _detect_gaps(
    domain: str,
    task_type: str | None,
    results: list[tuple[Judgment, float]],
) -> list[str]:
    """简单的缺口检测。检查关键领域是否有覆盖。"""
    gaps: list[str] = []
    layers_covered = {j.layer for j, _ in results}

    if "knowledge" not in layers_covered:
        gaps.append(f"{domain} 领域缺少 knowledge 层判断（跨项目共性规则）")
    if "resource" not in layers_covered:
        gaps.append(f"{domain} 领域缺少 resource 层判断（工具边界约束）")
    if "experience" not in layers_covered:
        gaps.append(f"{domain} 领域缺少 experience 层判断（社区踩坑经验）")

    if len(results) < 10:
        gaps.append(f"判断数量不足（{len(results)} 颗），晶体覆盖可能不完整")

    return gaps
