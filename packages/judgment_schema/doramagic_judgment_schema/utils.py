"""LLM 响应 JSON 安全提取工具。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_llm_json(raw_text: str) -> Any:
    """
    从 LLM 响应文本中安全提取 JSON。
    处理：纯 JSON、code fence 包裹、前后多余文字。
    返回解析后的 Python 对象，解析失败抛出 ValueError。
    """
    text = raw_text.strip()

    # 策略1：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略2：提取 code fence 内的 JSON
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略3：找到第一个 [ 或 { 开始的子串
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start_idx = text.find(start_char)
        if start_idx >= 0:
            # 从后往前找对应的闭合括号
            end_idx = text.rfind(end_char)
            if end_idx > start_idx:
                try:
                    return json.loads(text[start_idx : end_idx + 1])
                except json.JSONDecodeError:
                    pass

    raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:200]}...")
