"""用轻量 LLM 对通过过滤的记录做精细分类。"""

from __future__ import annotations

import logging

from doramagic_judgment_schema.utils import parse_llm_json
from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage

from ..source_adapters.base import RawExperienceRecord

logger = logging.getLogger(__name__)

CLASSIFICATION_SYSTEM_PROMPT = """你是一个 GitHub Issue 分类专家。根据 Issue 的标题、正文和评论，将它分为以下类别之一：

- bug_confirmed: 被代码修复证实的 bug（有关联的 merged PR 或明确的修复方案）
- design_boundary: 框架设计边界/已知限制（维护者明确表示"这是预期行为"或"不会修复"）
- incident: 生产事故或严重故障报告
- workaround: 社区提出的绕过方案（不是官方修复，是用户自己的应对策略）
- anti_pattern: 社区警告不要这么做的实践
- low_value: 不包含可操作经验的讨论（纯功能请求、重复问题、信息不足）

你只需要返回一个 JSON 对象：{"category": "类别名", "reason": "一句话理由"}
不要返回其他内容。"""


CLASSIFICATION_USER_TEMPLATE = """Issue #{source_id}: {title}

正文:
{body_truncated}

评论摘要（前3条）:
{replies_truncated}

信号: has_code_fix={has_code_fix}, is_design_boundary={is_design_boundary}, reply_count={reply_count}
"""

VALID_CATEGORIES = {
    "bug_confirmed",
    "design_boundary",
    "incident",
    "workaround",
    "anti_pattern",
    "low_value",
}


async def classify_record(
    record: RawExperienceRecord,
    adapter: LLMAdapter,
    model: str = "haiku",
) -> tuple[str, str]:
    """
    分类一条记录。返回 (category, reason)。
    category 是上述 6 种之一。
    """
    body_truncated = record.body[:1500] if len(record.body) > 1500 else record.body
    replies_truncated = "\n---\n".join(r[:500] for r in record.replies[:3])

    user_content = CLASSIFICATION_USER_TEMPLATE.format(
        source_id=record.source_id,
        title=record.title,
        body_truncated=body_truncated,
        replies_truncated=replies_truncated,
        has_code_fix=record.signals.get("has_code_fix", False),
        is_design_boundary=record.signals.get("is_design_boundary", False),
        reply_count=record.signals.get("reply_count", 0),
    )

    response = adapter.chat(
        messages=[LLMMessage(role="user", content=user_content)],
        system=CLASSIFICATION_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=200,
    )

    try:
        result = parse_llm_json(response.content)
        category = result.get("category", "low_value")
        if category not in VALID_CATEGORIES:
            category = "low_value"
        return category, result.get("reason", "")
    except (ValueError, AttributeError):
        logger.warning("分类失败：LLM 返回格式错误 (record=%s)", record.source_id)
        return "low_value", "分类失败：LLM 返回格式错误"
