"""关系自动建立。用 LLM 识别新判断和已有判断之间的关系。"""

from __future__ import annotations

import logging

from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import Judgment, Relation, RelationType
from doramagic_judgment_schema.utils import parse_llm_json
from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage

logger = logging.getLogger(__name__)


LINKER_SYSTEM_PROMPT = """你是 Doramagic 的知识图谱专家。你需要判断一颗新判断和已有判断之间是否存在关系。

可能的关系类型：
- generates: 新判断成立 → 产生目标判断（因果关系）
- depends_on: 新判断依赖目标判断（前置条件）
- conflicts: 与目标判断互斥（不可同时成立）
- strengthens: 为目标判断提供额外证据
- supersedes: 新判断替代目标判断（版本迭代）
- subsumes: 新判断包含目标判断（上位规则）

对每对判断，输出 JSON：
{"relations": [{"target_id": "xxx", "type": "关系类型", "description": "因果解释"}]}

如果没有关系，返回 {"relations": []}。
不要强行建立关系。没关系就是没关系。"""


async def auto_link(
    new_judgment: Judgment,
    store: JudgmentStore,
    adapter: LLMAdapter,
    model: str = "sonnet",
    max_candidates: int = 20,
) -> list[Relation]:
    """为新判断自动建立和已有判断的关系。只在同域内匹配。"""
    # 找候选判断（同域）
    candidates: list[Judgment] = []
    for domain in new_judgment.scope.domains:
        candidates.extend(store.list_by_domain(domain))

    # 排除自身
    candidates = [c for c in candidates if c.id != new_judgment.id]

    # 限制候选数量
    candidates = candidates[:max_candidates]

    if not candidates:
        return []

    # 构建 LLM 请求
    modality_val = new_judgment.core.modality
    if not isinstance(modality_val, str):
        modality_val = modality_val.value

    candidates_text = "\n".join(
        f"- {c.id}: 当{c.core.when}时，{c.core.modality} {c.core.action}" for c in candidates
    )

    new_text = (
        f"新判断 {new_judgment.id}: "
        f"当{new_judgment.core.when}时，"
        f"{modality_val} {new_judgment.core.action}，"
        f"否则{new_judgment.core.consequence.description}"
    )

    response = adapter.chat(
        messages=[LLMMessage(role="user", content=f"{new_text}\n\n已有判断:\n{candidates_text}")],
        system=LINKER_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=500,
    )

    try:
        result = parse_llm_json(response.content)
        relations = []
        for r in result.get("relations", []):
            relations.append(
                Relation(
                    type=RelationType(r["type"]),
                    target_id=r["target_id"],
                    description=r["description"],
                )
            )
        return relations
    except (ValueError, KeyError, TypeError):
        logger.warning("关系建立失败：LLM 返回格式错误 (judgment=%s)", new_judgment.id)
        return []
