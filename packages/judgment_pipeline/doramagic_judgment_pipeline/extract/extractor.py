"""从分类后的记录中提取判断三元组。核心环节。"""

from __future__ import annotations

import logging
import time

from doramagic_judgment_schema.types import (
    ConsensusLevel,
    Consequence,
    ConsequenceKind,
    CrystalSection,
    EvidenceRef,
    EvidenceRefType,
    Freshness,
    Judgment,
    JudgmentCompilation,
    JudgmentConfidence,
    JudgmentCore,
    JudgmentScope,
    JudgmentVersion,
    Layer,
    LifecycleStatus,
    Modality,
    ScopeLevel,
    Severity,
    SourceLevel,
)
from doramagic_judgment_schema.utils import parse_llm_json
from doramagic_judgment_schema.validators import validate_judgment
from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage

from ..source_adapters.base import RawExperienceRecord

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM_PROMPT = """你是 Doramagic 的判断提取专家。你的任务是从 GitHub Issue 讨论中提取可操作的判断（Judgment）。

每颗判断必须严格遵循三元组格式：
  当 [具体条件] 时，必须/禁止 [具体行为]，否则 [可量化后果]。

约束（违反任何一条你的输出将被代码级拒绝）：
1. [条件] 必须具体到一个工作场景，不能是"开发时"这种泛泛之词
2. [行为] 必须是一个可执行指令，不能是"注意安全"这种建议
3. [后果] 必须包含可量化的影响或具体的失败表现
4. 如果无法量化后果，写明"后果程度未知，需实验验证"并建议 confidence_score < 0.6
5. 一颗判断只说一件事。如果你发现两件事，拆成两颗
6. action 中不允许出现：注意、考虑、适当、合理、尽量、可能需要
7. 区分"这个项目特有的坑"（experience 层）和"这个领域通用的坑"（knowledge 层）

输出格式：只输出一个 JSON 数组，不要添加任何解释文字。每个元素：
{
  "when": "触发条件",
  "modality": "must" | "must_not" | "should" | "should_not",
  "action": "具体行为",
  "consequence_kind": "bug" | "performance" | "data_corruption" | "service_disruption" | "financial_loss" | "operational_failure" | "compliance" | "safety" | "false_claim",
  "consequence_description": "后果描述",
  "layer": "knowledge" | "resource" | "experience",
  "severity": "fatal" | "high" | "medium" | "low",
  "confidence_score": 0.0-1.0,
  "crystal_section": "constraints" | "world_model" | "resource_profile" | "architecture" | "protocols" | "evidence",
  "evidence_summary": "引用 Issue 中的具体证据"
}

如果 Issue 中没有可提取的判断，返回空数组 []。
不要编造 Issue 中没有提到的信息。
最多提取 5 颗判断，优先提取 severity 最高的。"""


EXTRACTION_FEW_SHOT = """
示例 — 好的提取（会通过校验）：
{"when": "使用 yfinance 获取 A 股日线数据进行回测时", "modality": "must_not", "action": "直接使用 close 字段作为真实收盘价，必须使用 adj_close 字段", "consequence_kind": "data_corruption", "consequence_description": "未复权价格会导致回测收益率偏差超过 30%，在长周期策略中表现为虚假盈利", "layer": "knowledge", "severity": "high", "confidence_score": 0.85, "crystal_section": "constraints", "evidence_summary": "Issue #142 中用户展示了 3 年回测中未复权与复权价格的收益率对比图"}

示例 — 会被拒绝的提取（模糊词 + 不可量化）：
{"when": "开发时", "modality": "should", "action": "注意数据质量", "consequence_kind": "bug", "consequence_description": "可能出问题", ...}
↑ 被拒绝原因：when 太笼统、action 包含"注意"、后果不具体
"""


EXTRACTION_USER_TEMPLATE = """Issue #{source_id}: {title}
项目: {project}
分类: {category}（分类信号，供你参考判断提取方向）
URL: {url}

正文:
{body}

评论（按时间排序）:
{replies}

请从以上讨论中提取判断。"""


# 分类到 scope_level 的映射
CATEGORY_TO_SCOPE: dict[str, ScopeLevel] = {
    "bug_confirmed": ScopeLevel.CONTEXT,
    "design_boundary": ScopeLevel.DOMAIN,
    "incident": ScopeLevel.CONTEXT,
    "workaround": ScopeLevel.CONTEXT,
    "anti_pattern": ScopeLevel.DOMAIN,
}

# 分类到 crystal_section 的默认映射（LLM 输出优先）
CATEGORY_TO_SECTION: dict[str, CrystalSection] = {
    "bug_confirmed": CrystalSection.CONSTRAINTS,
    "design_boundary": CrystalSection.WORLD_MODEL,
    "incident": CrystalSection.EVIDENCE,
    "workaround": CrystalSection.PROTOCOLS,
    "anti_pattern": CrystalSection.CONSTRAINTS,
}


async def extract_judgments(
    record: RawExperienceRecord,
    category: str,
    adapter: LLMAdapter,
    domain: str,
    model: str = "sonnet",
    id_counter: int = 1,
) -> list[Judgment]:
    """
    从一条记录中提取判断。
    返回通过校验的 Judgment 列表。
    """
    user_content = EXTRACTION_USER_TEMPLATE.format(
        source_id=record.source_id,
        title=record.title,
        project=record.project_or_community,
        category=category,
        url=record.source_url,
        body=record.body[:3000],
        replies="\n---\n".join(record.replies[:10]),
    )

    response = adapter.chat(
        messages=[LLMMessage(role="user", content=EXTRACTION_FEW_SHOT + "\n\n" + user_content)],
        system=EXTRACTION_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=3000,
    )

    try:
        raw_judgments = parse_llm_json(response.content)
    except ValueError as e:
        logger.warning("LLM 输出无法解析为 JSON: %s (record=%s)", e, record.source_id)
        return []

    if not isinstance(raw_judgments, list):
        logger.warning(
            "LLM 输出不是数组: type=%s (record=%s)", type(raw_judgments), record.source_id
        )
        return []

    results: list[Judgment] = []

    for i, raw_item in enumerate(raw_judgments):
        try:
            layer_str = raw_item.get("layer", "experience")
            layer_initial = layer_str[0].upper() if layer_str else "E"

            # crystal_section: LLM 输出优先，否则用分类映射
            section_str = raw_item.get("crystal_section", "")
            try:
                crystal_section = CrystalSection(section_str)
            except ValueError:
                crystal_section = CATEGORY_TO_SECTION.get(category, CrystalSection.CONSTRAINTS)

            scope_level = CATEGORY_TO_SCOPE.get(category, ScopeLevel.DOMAIN)

            # 用时间戳前缀避免跨运行 ID 碰撞
            run_ts = int(time.time()) % 100000
            judgment = Judgment(
                id=f"{domain}-{layer_initial}-{run_ts}{id_counter + i:03d}",
                core=JudgmentCore(
                    when=raw_item.get("when", ""),
                    modality=Modality(raw_item.get("modality", "should")),
                    action=raw_item.get("action", ""),
                    consequence=Consequence(
                        kind=ConsequenceKind(raw_item.get("consequence_kind", "bug")),
                        description=raw_item.get(
                            "consequence_description", "后果未明确，需进一步验证"
                        ),
                    ),
                ),
                layer=Layer(layer_str),
                scope=JudgmentScope(
                    level=scope_level,
                    domains=[domain],
                ),
                confidence=JudgmentConfidence(
                    source=SourceLevel.S3_COMMUNITY,
                    score=raw_item.get("confidence_score", 0.7),
                    consensus=ConsensusLevel.MIXED,
                    evidence_refs=[
                        EvidenceRef(
                            type=EvidenceRefType.ISSUE,
                            source=record.project_or_community,
                            locator=record.source_url,
                            summary=raw_item.get("evidence_summary", record.title),
                        ),
                    ],
                ),
                compilation=JudgmentCompilation(
                    severity=Severity(raw_item.get("severity", "medium")),
                    crystal_section=crystal_section,
                    freshness=Freshness.SEMI_STABLE,
                    query_tags=[domain],
                ),
                version=JudgmentVersion(status=LifecycleStatus.DRAFT),
            )

            # 代码级校验
            validation = validate_judgment(judgment)
            if validation.valid:
                results.append(judgment)
            else:
                logger.info("判断校验失败: id=%s errors=%s", judgment.id, validation.errors)

        except (KeyError, ValueError, TypeError) as e:
            logger.warning("构造 Judgment 失败: %s (record=%s, item=%d)", e, record.source_id, i)
            continue

    return results
