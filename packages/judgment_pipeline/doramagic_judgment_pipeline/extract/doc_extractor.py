"""文档知识/资源层提取器 — 从仓库文档中提取知识层和资源层判断。"""

from __future__ import annotations

import logging

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


DOC_EXTRACTION_SYSTEM_PROMPT = """你是 Doramagic 的知识提取专家。你的任务是从项目文档中提取两类判断：

**知识层判断**（世界如何运转）：
- 领域的客观规律和因果关系
- 不变量（无论用什么工具、什么场景，这条规则都成立）
- 系统/领域的物理约束
- 例：当处理金融数据时，必须使用 Decimal 而非 float 进行金额计算，否则累计误差会在三天内达到 0.8%

**资源层判断**（手里有什么装备）：
- 工具/API/库的真实能力边界
- 资源的限制条件（免费 vs 付费、速率限制、数据范围）
- 选择某个资源就必须接受的约束
- 例：当使用 yfinance 获取行情数据时，禁止将其用于实时交易决策，否则因数据延迟 15-20 分钟导致交易信号失效

每颗判断必须严格遵循三元组格式：
  当 [具体条件] 时，必须/禁止 [具体行为]，否则 [可量化后果]。

约束（违反任何一条你的输出将被代码级拒绝）：
1. [条件] 必须具体到一个工作场景，不能是"使用时"这种泛泛之词
2. [行为] 必须是一个可执行指令，不能是"注意安全"这种建议
3. [后果] 必须包含可量化的影响或具体的失败表现
4. 如果无法量化后果，写明"后果程度未知，需实验验证"并建议 confidence_score < 0.6
5. 一颗判断只说一件事。如果你发现两件事，拆成两颗
6. action 中不允许出现：注意、考虑、适当、合理、尽量、可能需要
7. **layer 必须是 "knowledge" 或 "resource"**，不要写 "experience"（经验层由 Issue 提取器负责）

输出格式：只输出一个 JSON 数组，不要添加任何解释文字。每个元素：
{
  "when": "触发条件",
  "modality": "must" | "must_not" | "should" | "should_not",
  "action": "具体行为",
  "consequence_kind": "bug" | "performance" | "data_corruption" | "service_disruption" | "financial_loss" | "operational_failure" | "compliance" | "safety" | "false_claim",
  "consequence_description": "后果描述",
  "layer": "knowledge" | "resource",
  "severity": "fatal" | "high" | "medium" | "low",
  "confidence_score": 0.0-1.0,
  "crystal_section": "code_skeleton" | "hard_constraints" | "acceptance_criteria",
  "evidence_summary": "引用文档中的具体内容作为证据"
}

crystal_section 选择指南（文档提取专用）：
- "code_skeleton"：领域客观规律、不变量、因果关系 → 将植入代码骨架的 assert/validation
- "hard_constraints"：实践约束、工具边界、迁移规则 → 将成为硬约束表中的行
- "acceptance_criteria"：跨层验证条件 → 将成为验收标准中的条目

如果文档段落没有可提取的判断（纯安装步骤、纯 API 列表等），返回空数组 []。
不要编造文档中没有提到的信息。
最多提取 5 颗判断，优先提取 severity 最高的。"""


DOC_EXTRACTION_FEW_SHOT = """
示例 — 知识层提取（从 README "How it works" 段落）：
{"when": "使用时间序列数据进行量化回测时", "modality": "must", "action": "基于交易日序列计算技术指标，禁止对非交易日插值填充", "consequence_kind": "data_corruption", "consequence_description": "插值会引入虚假数据点，导致均线等指标计算结果偏离真实市场状态，回测收益率虚高 5-15%", "layer": "knowledge", "severity": "high", "confidence_score": 0.9, "crystal_section": "code_skeleton", "evidence_summary": "README Architecture 章节说明：交易日历是非连续的，所有计算必须基于交易日序列"}

示例 — 资源层提取（从 README "Limitations" 段落）：
{"when": "使用 yfinance 获取股票历史数据进行策略研究时", "modality": "must", "action": "在本地建立数据缓存层，避免每次运行都从 API 拉取", "consequence_kind": "service_disruption", "consequence_description": "yfinance 无官方 API key，高频请求会触发 IP 限流，导致数据拉取中断", "layer": "resource", "severity": "medium", "confidence_score": 0.85, "crystal_section": "hard_constraints", "evidence_summary": "README Limitations 章节：yfinance is unofficial, rate limits may apply"}

示例 — 会被拒绝的提取：
{"when": "开发时", "modality": "should", "action": "考虑性能", ...}
↑ 被拒绝原因：when 太笼统、action 包含"考虑"
"""


DOC_EXTRACTION_USER_TEMPLATE = """项目: {project}
文档来源: {source_type}
段落标题: {title}
URL: {url}

文档内容:
{body}

请从以上文档内容中提取知识层和资源层的判断。"""


# 代码专用提取 prompt（断言/验证代码 → 知识层判断）
CODE_EXTRACTION_SYSTEM_PROMPT = """你是 Doramagic 的代码知识提取专家。你的任务是从代码片段中提取隐含的领域知识。

代码中的知识比文档更可靠——断言是被测试验证过的不变量，验证函数是被生产环境校验过的规则。

你需要提取的知识类型：
1. **断言 (assert)** → 不变量："当[条件]时，[某个属性]必须始终成立"
2. **验证 (raise ValueError/TypeError)** → 输入规则："当[操作]时，[输入]必须满足[条件]"
3. **配置常量 (TIMEOUT/RATE_LIMIT)** → 资源边界："当使用[资源]时，[参数]的真实边界是[值]"
4. **类型选择 (Decimal vs float)** → 领域决策："当[场景]时，必须使用[类型A]而非[类型B]"

约束：
1. 只提取代码中**明确表达**的知识，不要推测或编造
2. 三元组格式：当 [具体条件] 时，必须/禁止 [具体行为]，否则 [可量化后果]
3. action 中不允许出现：注意、考虑、适当、合理、尽量、可能需要
4. 如果代码片段只是普通业务逻辑（没有断言、验证或配置），返回空数组 []
5. **layer 必须是 "knowledge" 或 "resource"**

输出格式：只输出一个 JSON 数组。每个元素同文档提取器格式。
最多提取 3 颗判断（代码片段通常信息密度低于文档）。"""


CODE_EXTRACTION_USER_TEMPLATE = """项目: {project}
文件: {title}
代码类别: {code_category}
URL: {url}

代码片段:
{body}

请从以上代码中提取知识层和资源层的判断。如果代码只是普通业务逻辑，返回 []。"""


# source_type 到默认 crystal_section 的映射
SOURCE_TYPE_TO_SECTION: dict[str, CrystalSection] = {
    "github_readme": CrystalSection.CODE_SKELETON,
    "github_doc": CrystalSection.CODE_SKELETON,
    "github_changelog": CrystalSection.HARD_CONSTRAINTS,
    "github_deps": CrystalSection.HARD_CONSTRAINTS,
    "github_code": CrystalSection.CODE_SKELETON,
}

# source_type 到默认 layer 的映射
SOURCE_TYPE_TO_LAYER: dict[str, Layer] = {
    "github_readme": Layer.KNOWLEDGE,
    "github_doc": Layer.KNOWLEDGE,
    "github_changelog": Layer.RESOURCE,
    "github_deps": Layer.RESOURCE,
    "github_code": Layer.KNOWLEDGE,
}


async def extract_doc_judgments(
    record: RawExperienceRecord,
    adapter: LLMAdapter,
    domain: str,
    model: str = "sonnet",
    id_counter: int = 1,
) -> list[Judgment]:
    """从一条文档记录中提取判断。返回通过校验的 Judgment 列表。"""
    source_type = record.signals.get("source_type", "github_doc")
    is_code = source_type == "github_code"

    if is_code:
        user_content = CODE_EXTRACTION_USER_TEMPLATE.format(
            project=record.project_or_community,
            title=record.title,
            code_category=record.signals.get("code_category", "unknown"),
            url=record.source_url,
            body=record.body[:4000],
        )
        system_prompt = CODE_EXTRACTION_SYSTEM_PROMPT
        few_shot = ""
    else:
        user_content = DOC_EXTRACTION_USER_TEMPLATE.format(
            project=record.project_or_community,
            source_type=source_type,
            title=record.title,
            url=record.source_url,
            body=record.body[:4000],
        )
        system_prompt = DOC_EXTRACTION_SYSTEM_PROMPT
        few_shot = DOC_EXTRACTION_FEW_SHOT

    messages_content = f"{few_shot}\n\n{user_content}" if few_shot else user_content
    response = adapter.chat(
        messages=[LLMMessage(role="user", content=messages_content)],
        system=system_prompt,
        temperature=0.0,
        max_tokens=3000,
    )

    try:
        raw_judgments = parse_llm_json(response.text)
    except ValueError as e:
        logger.warning("文档提取 LLM 输出无法解析: %s (record=%s)", e, record.source_id)
        return []

    if not isinstance(raw_judgments, list):
        logger.warning(
            "文档提取 LLM 输出不是数组: type=%s (record=%s)", type(raw_judgments), record.source_id
        )
        return []

    results: list[Judgment] = []
    rejected: list[dict] = []

    default_layer = SOURCE_TYPE_TO_LAYER.get(source_type, Layer.KNOWLEDGE)
    default_section = SOURCE_TYPE_TO_SECTION.get(source_type, CrystalSection.CODE_SKELETON)

    for i, raw_item in enumerate(raw_judgments):
        try:
            # layer: LLM 输出优先，限定为 knowledge 或 resource
            layer_str = raw_item.get("layer", default_layer.value)
            if layer_str == "experience":
                layer_str = default_layer.value
            layer_initial = layer_str[0].upper() if layer_str else "K"

            # crystal_section: LLM 输出优先
            section_str = raw_item.get("crystal_section", "")
            try:
                crystal_section = CrystalSection(section_str)
            except ValueError:
                crystal_section = default_section

            judgment = Judgment(
                id=f"{domain}-{layer_initial}-{id_counter + i:03d}",
                core=JudgmentCore(
                    when=raw_item.get("when", ""),
                    modality=Modality(raw_item.get("modality", "should")),
                    action=raw_item.get("action", ""),
                    consequence=Consequence(
                        kind=ConsequenceKind(raw_item.get("consequence_kind", "bug")),
                        description=raw_item.get("consequence_description", "后果未明确"),
                    ),
                ),
                layer=Layer(layer_str),
                scope=JudgmentScope(
                    level=ScopeLevel.DOMAIN,
                    domains=[domain],
                ),
                confidence=JudgmentConfidence(
                    source=SourceLevel.S1_SINGLE_PROJECT,
                    score=raw_item.get("confidence_score", 0.7),
                    consensus=ConsensusLevel.MIXED,
                    evidence_refs=[
                        EvidenceRef(
                            type=EvidenceRefType.DOC,
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

            validation = validate_judgment(judgment)
            if validation.valid:
                results.append(judgment)
            else:
                logger.info("文档判断校验失败: id=%s errors=%s", judgment.id, validation.errors)
                rejected.append(
                    {
                        "stage": "validate",
                        "judgment_id": judgment.id,
                        "errors": validation.errors,
                        "raw": raw_item,
                    }
                )

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(
                "构造文档 Judgment 失败: %s (record=%s, item=%d)", e, record.source_id, i
            )
            rejected.append(
                {
                    "stage": "construct",
                    "error": str(e),
                    "raw": raw_item,
                }
            )
            continue

    if rejected:
        logger.info("文档提取 rejected %d 条 (record=%s)", len(rejected), record.source_id)

    return results
