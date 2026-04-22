# 三方挑战 Prompt — 直接复制粘贴给 GPT-4o 和 Gemini

> 把以下全部内容复制粘贴给 GPT-4o（或 Gemini），不需要修改。两个模型用同一份 prompt。

---

## 开始复制 ↓↓↓

你是一位资深后端架构师和代码审查专家。以下是一份即将交给 Claude Code CLI **全自动执行**（bypass permission on，不暂停确认）的 Python 开发规格文档。你的任务是**严格审查这份文档中的错误、遗漏、矛盾和执行风险**。

### 背景
- 项目名：Doramagic，一个从 GitHub Issue 讨论中提取结构化"判断"（Judgment）的知识系统
- 判断的核心三元组：当[条件]时，必须/禁止[行为]，否则[后果]
- 运行环境：macOS Mac Mini，Python 3.12，uv 包管理
- LLM 调用通过统一的 LLMAdapter（支持 Anthropic/OpenAI/Google，同步方法 chat() 返回 LLMResponse.text）
- **LLMAdapter 没有 JSON mode**，需要手动 json.loads() + code fence 剥离
- 全自动执行意味着：任何 spec 中的错误都会不经确认地传播到代码中

### 审查要求

请从以下 5 个维度严格审查，每个维度给出"通过/警告/致命"评级和具体意见：

**维度 1：代码可编译性**
- 所有 import 路径是否正确？
- Pydantic v2 的 API 用法是否准确（Field, model_post_init, field_validator 等）？
- 枚举值在不同文件之间是否一致？
- 有没有用到不存在的方法或参数？

**维度 2：LLM Prompt 工程质量**
- 3 个 system prompt（分类、提取、关系建立）是否清晰无歧义？
- 输出格式要求是否与代码端的解析逻辑匹配？
- 有没有 prompt 漏洞（会导致 LLM 输出无法 parse 的格式）？
- 温度/max_tokens 设置是否合理？

**维度 3：三轨过滤器逻辑**
- 权重分配（repro_steps=2.5, expert_reply=2.0 等）是否合理？
- 阈值（bug=3.0, discussion=4.5, 默认=5.0）会不会过滤掉有价值的内容？
- 减分逻辑（feature_request=-2.0）是否会误伤？
- 轨道优先级设计（代码共证 > 边界 > 打分）是否正确？

**维度 4：数据流一致性**
- 从 GitHub API 获取 → 过滤 → 分类 → 提取 → 去重 → 存储，数据模型的转换是否有断裂？
- RawExperienceRecord 的字段是否覆盖了下游所有需求？
- Judgment 对象从 LLM 输出到 Pydantic 构造是否有字段遗漏或类型不匹配？
- 去重的 signature 计算是否能正确识别语义重复？

**维度 5：自动执行安全性**
- 哪些地方如果出错，会导致静默失败（数据丢失但不报错）？
- 异常处理是否充分？ bare except 或者过宽的 try-except 会吞掉什么？
- 文件系统操作（JSONL 读写）有没有并发安全问题？
- 环境变量缺失时的行为是否明确？

---

### 文档内容

#### PART 1：Pydantic Models（types.py）

```python
"""Doramagic Judgment Schema v1.0 — Pydantic 实现"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── 枚举 ──

class Layer(str, Enum):
    KNOWLEDGE = "knowledge"
    RESOURCE = "resource"
    EXPERIENCE = "experience"

class Modality(str, Enum):
    MUST = "must"
    MUST_NOT = "must_not"
    SHOULD = "should"
    SHOULD_NOT = "should_not"

class Severity(str, Enum):
    FATAL = "fatal"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ScopeLevel(str, Enum):
    UNIVERSAL = "universal"
    DOMAIN = "domain"
    CONTEXT = "context"

class Freshness(str, Enum):
    STABLE = "stable"
    SEMI_STABLE = "semi_stable"
    VOLATILE = "volatile"

class LifecycleStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"

class ConsequenceKind(str, Enum):
    BUG = "bug"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    SAFETY = "safety"
    FINANCIAL_LOSS = "financial_loss"
    FALSE_CLAIM = "false_claim"
    OPERATIONAL_FAILURE = "operational_failure"
    DATA_CORRUPTION = "data_corruption"
    SERVICE_DISRUPTION = "service_disruption"

class SourceLevel(str, Enum):
    S1_SINGLE_PROJECT = "S1_single_project"
    S2_CROSS_PROJECT = "S2_cross_project"
    S3_COMMUNITY = "S3_community"
    S4_REASONING = "S4_reasoning"

class ConsensusLevel(str, Enum):
    UNIVERSAL = "universal"
    STRONG = "strong"
    MIXED = "mixed"
    CONTESTED = "contested"

class CrystalSection(str, Enum):
    WORLD_MODEL = "world_model"
    CONSTRAINTS = "constraints"
    RESOURCE_PROFILE = "resource_profile"
    ARCHITECTURE = "architecture"
    PROTOCOLS = "protocols"
    EVIDENCE = "evidence"

class RelationType(str, Enum):
    GENERATES = "generates"
    DEPENDS_ON = "depends_on"
    CONFLICTS = "conflicts"
    STRENGTHENS = "strengthens"
    SUPERSEDES = "supersedes"
    SUBSUMES = "subsumes"

class EvidenceRefType(str, Enum):
    SOURCE_CODE = "source_code"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    DISCUSSION = "discussion"
    BENCHMARK = "benchmark"
    PAPER = "paper"
    DOC = "doc"
    USER_FEEDBACK = "user_feedback"


# ── 子模型 ──

class Consequence(BaseModel):
    kind: ConsequenceKind
    description: str = Field(min_length=10)

class JudgmentCore(BaseModel):
    when: str = Field(min_length=5, description="触发条件")
    modality: Modality
    action: str = Field(min_length=5, description="具体行为")
    consequence: Consequence

class ContextRequires(BaseModel):
    resources: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    target_versions: dict[str, str] = Field(default_factory=dict)

class JudgmentScope(BaseModel):
    level: ScopeLevel
    domains: list[str] = Field(min_length=1)
    context_requires: Optional[ContextRequires] = None

class EvidenceRef(BaseModel):
    type: EvidenceRefType
    source: str
    locator: Optional[str] = None
    summary: str

class JudgmentConfidence(BaseModel):
    source: SourceLevel
    score: float = Field(ge=0.0, le=1.0)
    consensus: ConsensusLevel
    verified_by: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)

class JudgmentCompilation(BaseModel):
    severity: Severity
    crystal_section: CrystalSection
    freshness: Freshness
    freshness_note: Optional[str] = None
    emit_as_hard_constraint: bool = False
    machine_checkable: bool = False
    validator_template: Optional[str] = None
    degradation_action: Optional[str] = None
    query_tags: list[str] = Field(default_factory=list)

class Relation(BaseModel):
    type: RelationType
    target_id: str
    description: str = Field(min_length=5, description="给编译器 LLM 的因果解释")

class JudgmentVersion(BaseModel):
    status: LifecycleStatus = LifecycleStatus.DRAFT
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    review_after_days: Optional[int] = None
    superseded_by: Optional[str] = None
    schema_version: str = "1.0"

class JudgmentExamples(BaseModel):
    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)


# ── 主模型 ──

class Judgment(BaseModel):
    id: str = Field(pattern=r"^[a-z]+-[KRE]-\d{3,}$")
    hash: str = ""
    core: JudgmentCore
    layer: Layer
    scope: JudgmentScope
    confidence: JudgmentConfidence
    compilation: JudgmentCompilation
    relations: list[Relation] = Field(default_factory=list)
    version: JudgmentVersion = Field(default_factory=JudgmentVersion)
    examples: Optional[JudgmentExamples] = None
    notes: Optional[str] = None

    def model_post_init(self, __context: object) -> None:
        """自动计算 content hash。"""
        if not self.hash:
            content = json.dumps(
                {"core": self.core.model_dump(), "scope": self.scope.model_dump()},
                sort_keys=True,
                ensure_ascii=False,
            )
            self.hash = hashlib.sha256(content.encode()).hexdigest()[:16]
```

#### PART 2：Validators（validators.py）

```python
"""判断质量的代码级强制校验。不依赖 LLM，纯确定性。"""

from __future__ import annotations
from dataclasses import dataclass
from .types import Judgment, SourceLevel

VAGUE_WORDS_ZH = ["注意", "考虑", "适当", "合理", "尽量", "可能需要", "建议", "参考"]
VAGUE_WORDS_EN = [
    "consider", "be careful", "try to", "might need", "possibly",
    "appropriate", "reasonable", "should consider",
]
VAGUE_WORDS = VAGUE_WORDS_ZH + VAGUE_WORDS_EN

NON_ATOMIC_MARKERS_ZH = ["以及", "同时", "并且", "此外", "另外"]
NON_ATOMIC_MARKERS_EN = ["and also", "as well as", "in addition", "furthermore", "additionally"]
NON_ATOMIC_MARKERS = NON_ATOMIC_MARKERS_ZH + NON_ATOMIC_MARKERS_EN

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]

def validate_judgment(judgment: Judgment) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not judgment.core.when.strip():
        errors.append("core.when 为空")
    if not judgment.core.action.strip():
        errors.append("core.action 为空")
    if not judgment.core.consequence.description.strip():
        errors.append("core.consequence.description 为空")

    action = judgment.core.action.lower()
    for word in VAGUE_WORDS:
        if word.lower() in action:
            errors.append(f"core.action 包含模糊词 '{word}'，需要更具体的行为描述")
            break

    when_and_action = judgment.core.when + " " + judgment.core.action
    for marker in NON_ATOMIC_MARKERS:
        if marker in when_and_action:
            warnings.append(f"疑似非原子判断：'{marker}' 出现在 when/action 中。考虑拆分为多颗判断。")
            break

    if judgment.confidence.source != SourceLevel.S4_REASONING:
        if not judgment.confidence.evidence_refs:
            errors.append("非 S4_reasoning 来源的判断必须有 evidence_refs。")
    else:
        if judgment.confidence.score >= 0.6:
            warnings.append(f"S4_reasoning 来源的判断 confidence.score 应 < 0.6。当前值: {judgment.confidence.score}")

    if len(judgment.core.when) > 100:
        warnings.append(f"core.when 过长（{len(judgment.core.when)} 字符），可能太复杂。")

    if len(judgment.core.action) < 10:
        warnings.append(f"core.action 过短（{len(judgment.core.action)} 字符），可能太模糊。")

    if judgment.scope.level.value == "context" and not judgment.scope.context_requires:
        errors.append("scope.level 为 context 但缺少 context_requires")

    if judgment.layer.value == "knowledge" and judgment.confidence.source == SourceLevel.S1_SINGLE_PROJECT:
        warnings.append("knowledge 层判断通常不应来自单个项目。")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
```

#### PART 3：三轨过滤器（filter.py）

```python
"""三轨预过滤器。确定性，不用 LLM。"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from ..source_adapters.base import RawExperienceRecord

class FilterTrack(str, Enum):
    TRACK_1_CODE_EVIDENCE = "track_1"
    TRACK_2_DESIGN_BOUNDARY = "track_2"
    TRACK_3_SIGNAL_SCORE = "track_3"
    REJECTED = "rejected"

@dataclass
class FilterResult:
    record: RawExperienceRecord
    track: FilterTrack
    score: float
    reason: str

def filter_records(records: list[RawExperienceRecord]) -> list[FilterResult]:
    results: list[FilterResult] = []
    for record in records:
        signals = record.signals

        # 轨道一：代码共证（最高优先，零门槛）
        if signals.get("has_code_fix"):
            results.append(FilterResult(record=record, track=FilterTrack.TRACK_1_CODE_EVIDENCE, score=0, reason="Issue 已关闭且关联了 merged PR"))
            continue

        # 轨道二：边界妥协
        if signals.get("is_design_boundary") and signals.get("body_length", 0) >= 50:
            results.append(FilterResult(record=record, track=FilterTrack.TRACK_2_DESIGN_BOUNDARY, score=0, reason=f"设计边界标签 + body_length={signals.get('body_length', 0)}"))
            continue

        # 轨道三：信号打分
        score = _compute_signal_score(signals)
        threshold = _get_threshold(record, signals)
        if score >= threshold:
            results.append(FilterResult(record=record, track=FilterTrack.TRACK_3_SIGNAL_SCORE, score=score, reason=f"信号得分 {score:.1f} >= 阈值 {threshold}"))
        else:
            results.append(FilterResult(record=record, track=FilterTrack.REJECTED, score=score, reason=f"信号得分 {score:.1f} < 阈值 {threshold}"))
    return results

def _compute_signal_score(signals: dict) -> float:
    score = 0.0
    if signals.get("has_repro_steps"): score += 2.5
    if signals.get("expert_reply"): score += 2.0
    if signals.get("has_logs_or_evidence"): score += 1.5

    labels = {l.lower() for l in signals.get("labels", [])}
    if labels & {"bug", "regression", "incident", "data-issue"}: score += 1.5
    if signals.get("approval_score", 0) >= 3: score += 1.0
    if signals.get("reply_count", 0) >= 3: score += 0.5
    if signals.get("body_length", 0) >= 120: score += 0.5

    # 减分
    if labels & {"feature", "enhancement", "feature-request"} and not signals.get("has_logs_or_evidence"): score -= 2.0
    if labels & {"question"} and not signals.get("has_repro_steps"): score -= 1.5

    return score

def _get_threshold(record: RawExperienceRecord, signals: dict) -> float:
    labels = {l.lower() for l in signals.get("labels", [])}
    if labels & {"bug", "regression", "incident"}: return 3.0
    if record.pre_category == "bug": return 3.0
    if labels & {"discussion"}: return 4.5
    return 5.0
```

#### PART 4：LLM 分类 Prompt（classifier.py）

```python
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
```

代码端解析：
```python
response = adapter.chat(messages=[...], system=CLASSIFICATION_SYSTEM_PROMPT, temperature=0.0, max_tokens=200)
raw = response.text.strip()
if raw.startswith("```"):
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
result = json.loads(raw)
return result.get("category", "low_value"), result.get("reason", "")
```

#### PART 5：LLM 提取 Prompt（extractor.py）

```python
EXTRACTION_SYSTEM_PROMPT = """你是 Doramagic 的判断提取专家。你的任务是从 GitHub Issue 讨论中提取可操作的判断（Judgment）。

每颗判断必须严格遵循三元组格式：
  当 [具体条件] 时，必须/禁止 [具体行为]，否则 [可量化后果]。

约束（违反任何一条你的输出将被代码级拒绝）：
1. [条件] 必须具体到一个工作场景，不能是"开发时"这种泛泛之词
2. [行为] 必须是一个可执行指令，不能是"注意安全"这种建议
3. [后果] 必须包含可量化的影响或具体的失败表现
4. 如果无法量化后果，写明"后果程度未知，需实验验证"并建议 confidence score < 0.6
5. 一颗判断只说一件事。如果你发现两件事，拆成两颗
6. action 中不允许出现：注意、考虑、适当、合理、尽量、可能需要
7. 区分"这个项目特有的坑"（experience 层）和"这个领域通用的坑"（knowledge 层）

输出格式：JSON 数组，每个元素包含：
{
  "when": "触发条件",
  "modality": "must" | "must_not" | "should" | "should_not",
  "action": "具体行为",
  "consequence_kind": "bug" | "performance" | "data_corruption" | "service_disruption" | "financial_loss" | "operational_failure",
  "consequence_description": "后果描述",
  "layer": "knowledge" | "resource" | "experience",
  "severity": "fatal" | "high" | "medium" | "low",
  "confidence_score": 0.0-1.0,
  "evidence_summary": "引用 Issue 中的具体证据"
}

如果 Issue 中没有可提取的判断，返回空数组 []。
不要编造 Issue 中没有提到的信息。"""
```

代码端将 LLM 输出构造为 Judgment 对象：
```python
judgment = Judgment(
    id=f"{domain}-{layer_initial}-{id_counter + i:03d}",
    core=JudgmentCore(
        when=raw["when"],
        modality=Modality(raw["modality"]),
        action=raw["action"],
        consequence=Consequence(
            kind=ConsequenceKind(raw["consequence_kind"]),
            description=raw["consequence_description"],
        ),
    ),
    layer=Layer(raw.get("layer", "experience")),
    scope=JudgmentScope(
        level=ScopeLevel.DOMAIN,
        domains=[domain],
    ),
    confidence=JudgmentConfidence(
        source=SourceLevel.S3_COMMUNITY,
        score=raw.get("confidence_score", 0.7),
        consensus=ConsensusLevel.MIXED,
        evidence_refs=[
            EvidenceRef(
                type=EvidenceRefType.ISSUE,
                source=record.project_or_community,
                locator=record.source_url,
                summary=raw.get("evidence_summary", record.title),
            ),
        ],
    ),
    compilation=JudgmentCompilation(
        severity=Severity(raw.get("severity", "medium")),
        crystal_section=CrystalSection.CONSTRAINTS,
        freshness=Freshness.SEMI_STABLE,
        query_tags=[domain],
    ),
    version=JudgmentVersion(status=LifecycleStatus.DRAFT),
)
validation = validate_judgment(judgment)
if validation.valid:
    results.append(judgment)
```

#### PART 6：LLM 关系建立 Prompt（linker.py）

```python
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
```

#### PART 7：去重逻辑（dedup.py）

```python
def dedup_judgments(judgments: list[Judgment]) -> DedupResult:
    # Step 1: 计算 canonical signature
    sigs: dict[str, CanonicalSignature] = {}
    for j in judgments:
        sigs[j.id] = compute_signature(j)

    # Step 2: 按 scope_sig 分桶
    buckets: dict[str, list[Judgment]] = {}
    for j in judgments:
        bucket_key = sigs[j.id].scope_sig
        buckets.setdefault(bucket_key, []).append(j)

    # Step 3: 桶内强重复匹配
    unique: list[Judgment] = []
    duplicates: list[tuple[str, str, str]] = []
    seen_rule_sigs: dict[str, str] = {}

    for bucket_key, bucket_judgments in buckets.items():
        for j in bucket_judgments:
            sig = sigs[j.id]
            composite_key = f"{bucket_key}||{sig.rule_sig}"

            if composite_key in seen_rule_sigs:
                duplicates.append((seen_rule_sigs[composite_key], j.id, f"强重复：rule_sig 一致"))
            else:
                cause_key = f"{bucket_key}||{sig.cause_sig}"
                if cause_key in seen_rule_sigs:
                    duplicates.append((seen_rule_sigs[cause_key], j.id, f"根因重复：cause_sig 一致"))
                else:
                    seen_rule_sigs[composite_key] = j.id
                    seen_rule_sigs[f"{bucket_key}||{sig.cause_sig}"] = j.id
                    unique.append(j)

    return DedupResult(unique=unique, duplicates=duplicates)
```

#### PART 8：环境与集成约束

- 运行环境：macOS Mac Mini，Python 3.12，.venv/ 由 uv 管理
- 项目不是 uv workspace，通过 PYTHONPATH 注入包路径
- LLMAdapter 三个方法：chat()（同步）、generate()（异步）、generate_with_tools()（本项目不用）
- LLMAdapter 返回 LLMResponse，字段是 `.text`（不是 `.content`）
- LLMAdapter 没有 JSON mode，必须手动 json.loads + code fence 剥离
- 新增 3 个包需注册到 Makefile 的 PACKAGES_PATH 和根 pyproject.toml 的 wheel 包列表
- knowledge/judgments/ 是新目录，与现有 knowledge/bricks/ 物理隔离互不干涉
- 所有新包需注册到 mypy 配置（disallow_untyped_defs = true）
- JudgmentStore 必须满足 Protocol（store/get/list_by_domain/get_relations/count），为未来 PostgreSQL 迁移预留

---

### 输出格式

请按以下格式输出你的审查结果：

```
## 维度 1：代码可编译性 — [通过/警告/致命]
[具体意见]

## 维度 2：LLM Prompt 工程质量 — [通过/警告/致命]
[具体意见]

## 维度 3：三轨过滤器逻辑 — [通过/警告/致命]
[具体意见]

## 维度 4：数据流一致性 — [通过/警告/致命]
[具体意见]

## 维度 5：自动执行安全性 — [通过/警告/致命]
[具体意见]

## 综合评级：[可直接执行 / 需修改后执行 / 不可执行]
[一段话总结]
```

请严格审查。宁可误报，不可漏报。这份代码将全自动执行，没有人类审查环节。

## 结束复制 ↑↑↑
