"""将判断规范化为可比较的签名，用于确定性去重。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .types import Judgment

# 词汇归一化字典
VOCABULARY_MAP: dict[str, str] = {
    # 浮点数相关
    "float": "binary_float",
    "double": "binary_float",
    "ieee 754": "binary_float",
    "浮点": "binary_float",
    "浮点数": "binary_float",
    # 精确数值
    "decimal": "exact_decimal",
    "bigdecimal": "exact_decimal",
    # 金融概念
    "pnl": "profit_and_loss",
    "p&l": "profit_and_loss",
    "盈亏": "profit_and_loss",
    "收益": "profit_and_loss",
    # 数据获取
    "yfinance": "yfinance_api",
    "yahoo finance": "yfinance_api",
    # 交易类型
    "实盘": "live_trading",
    "live trading": "live_trading",
    "回测": "backtest",
    "backtesting": "backtest",
    # 时间频率
    "日线": "daily_bar",
    "eod": "daily_bar",
    "end of day": "daily_bar",
    "实时": "realtime",
    "real-time": "realtime",
    "real time": "realtime",
}


def normalize_text(text: str) -> str:
    """对文本做词汇归一化。"""
    result = text.lower().strip()
    # 按长度降序替换（避免短词误替换长词的一部分）
    for original, normalized in sorted(VOCABULARY_MAP.items(), key=lambda x: -len(x[0])):
        result = result.replace(original.lower(), normalized)
    # 去除多余空格
    result = re.sub(r"\s+", " ", result)
    return result


@dataclass
class CanonicalSignature:
    scope_sig: str  # 归一化的 domains + resources + task_types
    rule_sig: str  # 归一化的 modality + action 核心动词/对象
    cause_sig: str  # 归一化的 consequence.kind + 关键实体


def compute_signature(judgment: Judgment) -> CanonicalSignature:
    """计算一颗判断的 canonical signature，用于确定性去重。"""

    # scope_sig: 领域 + 资源 + 任务类型
    scope_parts: list[str] = []
    scope_parts.extend(sorted(judgment.scope.domains))
    if judgment.scope.context_requires:
        scope_parts.extend(sorted(judgment.scope.context_requires.resources))
        scope_parts.extend(sorted(judgment.scope.context_requires.task_types))
    scope_sig = normalize_text("|".join(scope_parts))

    # rule_sig: modality + action 关键内容
    modality_val = judgment.core.modality
    if not isinstance(modality_val, str):
        modality_val = modality_val.value
    rule_sig = normalize_text(f"{modality_val}|{judgment.core.action}")

    # cause_sig: consequence 类型 + 描述中的关键实体
    kind_val = judgment.core.consequence.kind
    if not isinstance(kind_val, str):
        kind_val = kind_val.value
    cause_sig = normalize_text(f"{kind_val}|{judgment.core.consequence.description}")

    return CanonicalSignature(
        scope_sig=scope_sig,
        rule_sig=rule_sig,
        cause_sig=cause_sig,
    )
