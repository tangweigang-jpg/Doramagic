"""Blueprint schema 组件 — 蓝图 YAML 的通用结构化模型。

设计原则：schema 定义结构，领域 SOP 定义词汇。
这些模型定义所有领域共享的通用组件。领域特有字段（如金融的
applicable_markets）由各领域 SOP 规定，不在此处约束。

v1.0: 初始版本，支持非代码项目蓝图提取。
向后兼容：所有新字段均为 Optional，现有金融蓝图无需修改。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Activation Profile — 蓝图激活语义（applicability 子结构）
# ---------------------------------------------------------------------------
class ActivationProfile(BaseModel):
    """蓝图的激活语义 — 告诉宿主 AI 什么时候该使用此蓝图。

    代码蓝图由用户/编译器显式选中，不需要此字段。
    非代码 skill 蓝图需要被宿主 AI 自动路由，此字段提供路由信号。
    放在 applicability.activation 下，编译时流入 Crystal.intent_router。
    """

    triggers: list[str] = Field(
        default_factory=list,
        description="什么信号应该触发此蓝图（如 '测试失败', '生产 bug'）",
    )
    emphasis: list[str] = Field(
        default_factory=list,
        description="这些情况下尤其应该使用（如 '时间压力下', '已尝试多次修复'）",
    )
    anti_skip: list[str] = Field(
        default_factory=list,
        description="别因为这些理由跳过（如 '问题看起来简单', '时间紧迫'）",
    )


# ---------------------------------------------------------------------------
# 2. Blueprint Resource — 蓝图关联资源
# ---------------------------------------------------------------------------
class BlueprintResource(BaseModel):
    """蓝图关联资源 — 产品宪法 §1.3: 好的晶体 = 好的蓝图 + 好的资源 + 好的约束。

    资源是三大组成之一，但此前蓝图 schema 没有为其建模。
    代码蓝图的资源隐含在 evidence 和 stage 描述中；
    非代码蓝图的资源（子技术文档、工具脚本、代码示例）是一等知识。

    type 字段的枚举值由领域 SOP 定义，不在此硬编码。常见值：
    - 代码项目: external_service, package_dependency, config_template
    - AI skill: technique_document, tool_script, code_example, reference_doc
    """

    id: str = Field(description="资源唯一标识（蓝图内唯一）")
    type: str = Field(description="资源类型（领域 SOP 定义枚举）")
    name: str = Field(description="资源名称")
    path: str | None = Field(default=None, description="资源路径（相对于源项目根目录）")
    description: str = Field(default="", description="资源用途描述")
    used_in_stages: list[str] = Field(
        default_factory=list,
        description="使用此资源的 stage ID 列表",
    )


# ---------------------------------------------------------------------------
# 3. Blueprint Relation — 蓝图间关系
# ---------------------------------------------------------------------------
RelationType = Literal[
    # 现有（知识关系）
    "alternative_to",  # A 可替代 B
    "specializes",  # A 是 B 的特化
    "generalizes",  # A 是 B 的泛化
    # 新增（执行关系）
    "depends_on",  # A 的某阶段调用 B
    "complementary",  # A 和 B 互补使用
    "contains",  # A 包含 B 作为子技术/子模块
]


class BlueprintRelation(BaseModel):
    """蓝图间关系。

    现有关系类型（alternative_to/specializes/generalizes）描述知识层面的关系。
    新增关系类型（depends_on/complementary/contains）描述执行层面的关系，
    在 AI skill 项目中尤为常见（skill 间互相引用和编排）。
    """

    type: RelationType
    target: str = Field(description="目标蓝图 ID 或资源路径")
    description: str = Field(default="", description="关系描述")
    evidence: str = Field(default="", description="证据引用")


# ---------------------------------------------------------------------------
# 4. Execution Mode — 执行范式（泛化后）
# ---------------------------------------------------------------------------
class ExecutionMode(BaseModel):
    """执行模式 — execution_paradigm 的通用表示。

    替代原有的 {live: str, backtest: str} 金融硬编码结构。
    领域 SOP 定义期望的 mode id（金融: live/backtest，AI skill: mandatory_sequential）。
    """

    id: str = Field(description="模式标识（领域 SOP 定义）")
    description: str = Field(default="", description="模式描述")


# ---------------------------------------------------------------------------
# 5. Extraction Method — 提取策略枚举
# ---------------------------------------------------------------------------
# 一个蓝图可以使用多种策略（混合项目）。
# source.extraction_methods: list[ExtractionMethod]
ExtractionMethod = Literal[
    "semi_auto",  # 代码知识源：源码逆向 + agent 辅助
    "manual",  # 人工提取
    "structural_extraction",  # 文档知识源：SKILL.md/CLAUDE.md 结构化萃取
    "config_parsing",  # 配置知识源：hooks.json/settings.yaml 解析
]
