"""知识积木 v2 — 结构化信封 + 自然语言约束。

信封层给系统看（检索、组合、验证），内容层给 LLM 看（生成代码时的约束）。
架构目标：支持 10000+ 积木的高效检索与自动组合。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# 能力类型枚举
CapabilityType = Literal["poll", "filter", "notify", "transform"]

# 数据源枚举（None 表示无外部依赖）
DataSourceType = Literal[
    "stock_api",
    "gmail",
    "rss",
    "github",
    "webhook",
    "telegram",
    "twitter",
    "slack",
    "database",
    "filesystem",
]

# 积木来源
BrickSource = Literal["manual", "auto-extracted", "community"]

# 失败严重程度
FailureSeverity = Literal["HIGH", "MEDIUM", "LOW"]

# 输入参数类型
InputParamType = Literal["string", "float", "integer", "boolean", "enum", "text"]


class InputSpec(BaseModel):
    """输入参数规格定义。

    Args:
        type: 参数类型，支持 string/float/integer/boolean/enum/text
        required: 是否必填，默认为 True
        default: 默认值，required=False 时应提供
        description: 参数用途说明
        validation: Python 表达式字符串，用于运行时校验
        enum_values: type 为 enum 时的合法值列表
    """

    type: InputParamType
    required: bool = True
    default: Any = None
    description: str = ""
    validation: str | None = None
    enum_values: list[str] | None = None


class OutputSpec(BaseModel):
    """输出规格定义。

    Args:
        type: 输出数据类型
        description: 输出内容说明
    """

    type: str
    description: str = ""


class FailurePattern(BaseModel):
    """已知失败模式 — 告知 LLM 需要防御哪些边界情况。

    Args:
        severity: 严重程度，HIGH 阻断性 / MEDIUM 降级 / LOW 告警
        pattern: 触发场景的自然语言描述
        mitigation: 推荐的缓解方案
    """

    severity: FailureSeverity
    pattern: str
    mitigation: str


class BrickV2(BaseModel):
    """知识积木 v2 — 结构化信封 + 自然语言约束。

    设计原则：
    - 信封层（id/category/inputs/outputs 等）给系统看，用于检索、兼容检查、自动组合
    - 内容层（core_capability/constraints/common_failures）给 LLM 看，指导代码生成
    - 同一积木可在多个 skill 中复用，通过 compatible_with 表达已验证的组合

    Args:
        id: 全局唯一标识，格式建议 "<领域>-<功能>-v<主版本>"
        name: 人类可读名称
        version: semver 格式版本号
        category: 分类标签列表，用于粗粒度分类导航
        tags: 搜索关键词标签，用于全文检索
        capability_type: 核心能力类型（poll/filter/notify/transform）
        data_source: 主要数据来源，None 表示无外部依赖
        inputs: 参数输入规格，key 为参数名
        outputs: 输出规格，key 为输出项名称
        requires: 前置依赖的积木 id 列表
        conflicts_with: 互斥积木 id 列表（不可同时使用）
        compatible_with: 已验证可组合的积木 id 列表
        core_capability: 一句话描述核心能力（给 LLM 看）
        constraints: 生成代码时必须遵守的约束列表（最关键）
        common_failures: 已知失败模式列表
        source: 积木来源
        freshness_date: 最后验证日期，格式 YYYY-MM-DD
        quality_score: 质量评分 0-100，越高越可靠
        usage_count: 被 skill 引用次数，用于排序
        evidence_refs: 支撑约束的文档/Issue/PR 引用
    """

    # === 信封层（给系统看）===
    id: str = Field(description="全局唯一标识，如 'stock-alert-v1'")
    name: str = Field(description="人类可读名称")
    version: str = Field(default="1.0.0", description="semver 版本号")
    category: list[str] = Field(description="分类标签，如 ['金融', '监控']")
    tags: list[str] = Field(description="搜索关键词标签")
    capability_type: CapabilityType = Field(description="能力类型：poll/filter/notify/transform")
    data_source: DataSourceType | None = Field(default=None, description="主要数据来源")

    # 输入输出（用于自动组合兼容检查）
    inputs: dict[str, InputSpec] = Field(description="参数定义，key 为参数名")
    outputs: dict[str, OutputSpec] = Field(description="输出定义，key 为输出项名称")

    # 组合约束
    requires: list[str] = Field(default_factory=list, description="前置依赖积木 id")
    conflicts_with: list[str] = Field(default_factory=list, description="互斥积木 id")
    compatible_with: list[str] = Field(default_factory=list, description="已验证可组合积木 id")

    # === 内容层（给 LLM 看）===
    core_capability: str = Field(description="一句话描述核心能力")
    constraints: list[str] = Field(description="生成代码时必须遵守的约束，最关键字段")
    common_failures: list[FailurePattern] = Field(
        default_factory=list, description="已知失败模式，驱动防御性代码生成"
    )

    # === 元数据 ===
    source: BrickSource = Field(default="manual", description="积木来源")
    freshness_date: str | None = Field(default=None, description="最后验证日期 YYYY-MM-DD")
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0, description="质量评分 0-100")
    usage_count: int = Field(default=0, ge=0, description="被 skill 引用次数")
    evidence_refs: list[str] = Field(
        default_factory=list, description="支撑约束的文档/Issue/PR 引用 URL"
    )
