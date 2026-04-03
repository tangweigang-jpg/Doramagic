"""判断质量的代码级强制校验。不依赖 LLM，纯确定性。"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Judgment, SourceLevel

# 中英文模糊词
VAGUE_WORDS_ZH = ["注意", "考虑", "适当", "合理", "尽量", "可能需要", "建议", "参考"]
VAGUE_WORDS_EN = [
    "consider",
    "be careful",
    "try to",
    "might need",
    "possibly",
    "appropriate",
    "reasonable",
    "should consider",
]
VAGUE_WORDS = VAGUE_WORDS_ZH + VAGUE_WORDS_EN

# 非原子性标志词
NON_ATOMIC_MARKERS_ZH = ["以及", "同时", "并且", "此外", "另外"]
NON_ATOMIC_MARKERS_EN = [
    "and also",
    "as well as",
    "in addition",
    "furthermore",
    "additionally",
]
NON_ATOMIC_MARKERS = NON_ATOMIC_MARKERS_ZH + NON_ATOMIC_MARKERS_EN


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]  # 致命问题，必须修复
    warnings: list[str]  # 建议修复


def validate_judgment(judgment: Judgment) -> ValidationResult:
    """完整校验一颗判断。返回结构化结果。"""
    errors: list[str] = []
    warnings: list[str] = []

    # === 三元组完整性 ===
    if not judgment.core.when.strip():
        errors.append("core.when 为空")
    if not judgment.core.action.strip():
        errors.append("core.action 为空")
    if not judgment.core.consequence.description.strip():
        errors.append("core.consequence.description 为空")

    # === 模糊词检测 ===
    action = judgment.core.action.lower()
    for word in VAGUE_WORDS:
        if word.lower() in action:
            errors.append(f"core.action 包含模糊词 {word}，需要更具体的行为描述")
            break

    # === 原子性检测 ===
    when_and_action = judgment.core.when + " " + judgment.core.action
    for marker in NON_ATOMIC_MARKERS:
        if marker in when_and_action:
            warnings.append(f"疑似非原子判断：{marker} 出现在 when/action 中。考虑拆分为多颗判断。")
            break

    # === 证据强制 ===
    if judgment.confidence.source != SourceLevel.S4_REASONING:
        if not judgment.confidence.evidence_refs:
            errors.append(
                "非 S4_reasoning 来源的判断必须有 evidence_refs。"
                "如果确实无法提供证据，请将 source 设为 S4_reasoning 并将 score 设为 < 0.6。"
            )
    else:
        if judgment.confidence.score >= 0.6:
            warnings.append(
                "S4_reasoning 来源的判断 confidence.score 应 < 0.6。"
                f"当前值: {judgment.confidence.score}"
            )

    # === when 复杂度 ===
    if len(judgment.core.when) > 100:
        warnings.append(
            f"core.when 过长（{len(judgment.core.when)} 字符），可能太复杂。"
            "考虑拆分或精简条件描述。"
        )

    # === action 具体性 ===
    if len(judgment.core.action) < 10:
        warnings.append(f"core.action 过短（{len(judgment.core.action)} 字符），可能太模糊。")

    # === scope 一致性 ===
    if judgment.scope.level == "context" and not judgment.scope.context_requires:
        errors.append("scope.level 为 context 但缺少 context_requires")

    # === layer 与 source 一致性 ===
    if (
        judgment.layer == "knowledge"
        and judgment.confidence.source == SourceLevel.S1_SINGLE_PROJECT
    ):
        warnings.append("knowledge 层判断通常不应来自单个项目。考虑验证是否有跨项目佐证。")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
