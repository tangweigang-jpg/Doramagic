"""种子晶体编译器 — 将判断集编译为三段式配方（代码骨架 + 硬约束表 + 验收标准）。

晶体是配方/蓝图，消费者是用户的 AI 工具。
参考实现：docs/research/judgment-system/multi-agent-orchestration.seed.md
"""

from __future__ import annotations

from datetime import UTC, datetime

from doramagic_judgment_schema.types import (
    Judgment,
)

from .retrieve import RetrievalResult


def compile_crystal(
    retrieval: RetrievalResult,
    domain: str,
    task_description: str,
    version: str = "0.1.0",
    max_tokens: int | None = None,
) -> str:
    """
    将检索结果编译为种子晶体 — 三段式配方格式。

    输出结构：
    1. 代码骨架（最小可运行样本，知识层 judgment 植入为 assert/validation）
    2. 硬约束表（经验层 + 资源层 judgment，表格形式）
    3. 验收标准（三层交叉碰撞，编号列表）
    4. context_acquisition 指令块
    """
    # ── 分拣判断到三段 ──
    skeleton_judgments: list[tuple[Judgment, float]] = []
    constraint_rows: list[tuple[Judgment, float]] = []
    acceptance_judgments: list[tuple[Judgment, float]] = []

    for judgment, weight in retrieval.judgments:
        layer = judgment.layer
        if not isinstance(layer, str):
            layer = layer.value

        if layer == "knowledge":
            skeleton_judgments.append((judgment, weight))
        elif layer in ("experience", "resource"):
            constraint_rows.append((judgment, weight))
        else:
            constraint_rows.append((judgment, weight))

    # 从三层碰撞中提取验收标准候选
    knowledge_whens = {j.core.when for j, _ in skeleton_judgments}
    experience_whens = {j.core.when for j, _ in constraint_rows}
    cross_layer_whens = knowledge_whens & experience_whens

    remaining_constraints: list[tuple[Judgment, float]] = []
    for judgment, weight in constraint_rows:
        if judgment.core.when in cross_layer_whens:
            acceptance_judgments.append((judgment, weight))
        else:
            remaining_constraints.append((judgment, weight))
    constraint_rows = remaining_constraints

    # severity = FATAL 也进入验收标准
    final_constraints: list[tuple[Judgment, float]] = []
    for judgment, weight in constraint_rows:
        sev = judgment.compilation.severity
        if not isinstance(sev, str):
            sev = sev.value
        if sev == "fatal":
            acceptance_judgments.append((judgment, weight))
        else:
            final_constraints.append((judgment, weight))
    constraint_rows = final_constraints

    # ── 渲染四段 ──
    section_1 = _render_code_skeleton(skeleton_judgments, domain, task_description)
    section_2 = _render_hard_constraints_table(constraint_rows)
    section_3 = _render_acceptance_criteria(acceptance_judgments)
    section_4 = _render_context_acquisition(domain)
    coverage = _render_coverage_gaps(retrieval.coverage_gaps)

    compiled_at = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")

    crystal = f"""# 种子晶体：{domain} — {task_description}

> 来源：Doramagic 知识引擎 | 基于 {len(retrieval.judgments)} 颗判断编译
> 知识库版本: {version} | 编译时间: {compiled_at}
> 适用场景：{task_description}

---

{section_4}

---

## 一、最小可运行样本

{section_1}

---

## 二、硬约束（违反必出 bug）

{section_2}

---

## 三、验收标准

{section_3}

---

{coverage}

---

*生成自 Doramagic 知识引擎*
"""

    if max_tokens:
        max_chars = max_tokens * 4
        if len(crystal) > max_chars:
            crystal = _trim_to_budget(crystal, max_chars)

    return crystal


def _render_code_skeleton(
    judgments: list[tuple[Judgment, float]],
    domain: str,
    task_description: str,
) -> str:
    if not judgments:
        return f'```python\n"""{domain}: {task_description} — 最小可运行骨架"""\n\n# 知识库中暂无知识层判断，骨架待填充\npass\n```'

    lines = [f'"""{domain}: {task_description} — 最小可运行骨架"""', ""]
    for judgment, _ in judgments:
        lines.append(f"# 领域规则：当{judgment.core.when}时")
        lines.append(f"# → {judgment.core.action}")
        lines.append(f"assert True  # 待实现: {judgment.core.action}")
        lines.append(f"# 违反后果: {judgment.core.consequence.description}")
        lines.append("")
    return "```python\n" + "\n".join(lines) + "\n```"


def _render_hard_constraints_table(
    judgments: list[tuple[Judgment, float]],
) -> str:
    if not judgments:
        return "| # | 约束 | 原因 | 违反后果 |\n|---|------|------|---------|"

    rows = ["| # | 约束 | 原因 | 违反后果 |", "|---|------|------|---------|"]
    for i, (judgment, _) in enumerate(judgments, 1):
        modality_map = {"must": "必须", "must_not": "禁止", "should": "应当", "should_not": "不应"}
        mod = judgment.core.modality
        if not isinstance(mod, str):
            mod = mod.value
        prefix = modality_map.get(mod, "")
        constraint = f"**{prefix}**：当{judgment.core.when}时，{judgment.core.action}"
        reason = _get_evidence_summary(judgment)
        consequence = judgment.core.consequence.description
        rows.append(f"| C{i} | {constraint} | {reason} | {consequence} |")
    return "\n".join(rows)


def _render_acceptance_criteria(
    judgments: list[tuple[Judgment, float]],
) -> str:
    if not judgments:
        return "（暂无验收标准 — 需要更多三层交叉判断）"

    lines = ["一个合格的 skill 必须通过以下检验：", ""]
    for i, (judgment, _) in enumerate(judgments, 1):
        lines.append(
            f"{i}. **{judgment.core.action}**：当{judgment.core.when}时，"
            f"违反将导致 {judgment.core.consequence.description}"
        )
    return "\n".join(lines)


def _render_context_acquisition(domain: str) -> str:
    return f"""## context_acquisition

> **以下指令面向消费本晶体的宿主 AI 系统（Claude Code / Codex / Antigravity 等）。**

在按本配方构建 skill 之前，你（宿主 AI）必须先获取用户的个性化上下文：

1. **查阅用户历史会话**：翻阅当前用户之前的对话记录，提取：
   - 用户的项目背景和技术栈
   - 用户过往的偏好和约束（如特定框架版本、部署环境）
   - 用户在 {domain} 领域的经验水平

2. **补充采集缺失信息**：如果历史会话中缺少以下关键信息，向用户提问：
   - 具体使用的框架和版本？
   - 目标部署环境（本地 / 云 / 边缘）？
   - 性能/成本/可维护性的优先级排序？
   - 是否有特殊约束（合规要求、网络隔离等）？

3. **基于用户上下文 + 本晶体的代码骨架 + 硬约束 + 验收标准，现场构建定制 skill。**
   同一颗晶体在不同用户手里产出不同的 skill，因为每个用户的上下文不同。"""


def _render_coverage_gaps(gaps: list[str]) -> str:
    if not gaps:
        return "## 已知缺口\n\n无已知缺口。"
    lines = ["## 已知缺口", ""]
    for g in gaps:
        lines.append(f"- {g}")
    return "\n".join(lines)


def _get_evidence_summary(judgment: Judgment) -> str:
    if judgment.confidence.evidence_refs:
        ref = judgment.confidence.evidence_refs[0]
        return ref.summary if hasattr(ref, "summary") and ref.summary else ref.source
    return "社区实践经验"


def _trim_to_budget(crystal: str, max_chars: int) -> str:
    """代码骨架和验收标准永不截断，从硬约束表末尾行截断。"""
    table_start = crystal.find("## 二、硬约束")
    table_end = crystal.find("---", table_start + 10) if table_start >= 0 else -1
    if table_start < 0 or table_end < 0:
        return crystal[:max_chars]

    before_table = crystal[:table_start]
    table_section = crystal[table_start:table_end]
    after_table = crystal[table_end:]
    non_table_size = len(before_table) + len(after_table)
    table_budget = max_chars - non_table_size

    if table_budget <= 0:
        return crystal[:max_chars]

    table_lines = table_section.split("\n")
    trimmed_lines: list[str] = []
    used = 0
    for line in table_lines:
        if used + len(line) + 1 > table_budget:
            trimmed_lines.append("| ... | （因 token 预算限制，部分约束被省略） | | |")
            break
        trimmed_lines.append(line)
        used += len(line) + 1
    return before_table + "\n".join(trimmed_lines) + after_table
