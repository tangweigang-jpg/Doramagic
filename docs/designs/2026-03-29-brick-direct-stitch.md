# 知识积木直缝路径
日期: 2026-03-29

## 背景与目标

Doramagic 当前只有一条路径：找项目 → 分析代码 → 提取知识 → 编译 skill。耗时 2-5 分钟，依赖能找到好的 GitHub 项目。

但多数 OpenClaw 用户没有特定项目要分析，他们只是想要一个能干活的 skill。而知识积木库（1076 条，49 领域）本身已经包含了缝合 skill 所需的知识。

目标：新增"积木直缝"路径，用户描述需求后秒级产出 skill。

## 不在范围内

- 不做积木 API（后续阶段）
- 不做 Cross-project GCD 自增长（后续阶段）
- 不改现有提取路径（两条路径共存）
- 不做积木过期/版本机制（v2 再做）

## 方案设计

### 路径选择逻辑

FlowController 的 InputRouter 已有 4 条路径：
- DIRECT_URL → 项目提取
- NAMED_PROJECT → 项目提取
- DOMAIN_EXPLORE → 搜索项目再提取
- LOW_CONFIDENCE → 降级

新增第 5 条：
- **BRICK_STITCH** → 积木直缝（当 DOMAIN_EXPLORE 且积木覆盖率高时触发）

判断条件：用 1 次 LLM 调用分析用户意图，匹配积木类别。如果匹配到 3+ 个类别且总积木 ≥ 30 条，走直缝路径。否则走现有 DOMAIN_EXPLORE。

### 三个组件

**1. BrickMatcher — 语义匹配积木类别**

输入：用户意图（NeedProfile.intent + domain）
输出：匹配的积木类别列表 + 每类别相关度评分

实现：1 次 LLM 调用，提供 49 个积木类别的 domain_id + 描述，让 LLM 选出 Top 5。

**2. BrickSelector — 质量排序选取**

输入：匹配的类别列表
输出：排序后的 30-50 条最佳积木

质量权重：
- knowledge_type 权重：failure(3) > rationale(2) > constraint(2) > assembly_pattern(1.5) > capability(1) > interface(1)
- L1 积木权重 × 1.5
- confidence=high × 1.2

**3. BrickStitcher — 缝合成 skill**

输入：选中的积木 + 用户意图
输出：完整的 skill 包（SKILL.md + README.md + PROVENANCE.md + LIMITATIONS.md）

实现：1 次 LLM 调用，prompt 结构：
```
用户需求：{intent}
可用知识积木（按相关度排序）：
{selected_bricks_formatted}

请基于以上知识积木，缝合成一个完整的 AI skill。
要求：
1. 整合多个领域的知识（不是简单罗列）
2. 标注每条知识的来源积木 ID
3. 突出 failure 类型积木（陷阱/反模式）作为警告
4. 生成 SKILL.md 格式输出
```

### 与现有管道的集成

复用现有的 Validator 和 DeliveryPackager — 直缝产出的 skill 也需要经过质量验证和打包。

流程：
```
InputRouter → BRICK_STITCH
  → BrickMatcher（1 次 LLM）
  → BrickSelector（纯确定性）
  → BrickStitcher（1 次 LLM）
  → Validator（复用）
  → DeliveryPackager（复用）
```

总计 2 次 LLM 调用，秒级完成。

## 验证标准

1. `make check` 全通过
2. 测试：构造"Telegram 监控加密货币"意图 → 验证匹配到 messaging + financial + skill_arch 类别
3. 测试：验证 BrickSelector 按质量权重正确排序
4. 测试：验证直缝路径产出包含 SKILL.md 且通过 Validator

## 风险与权衡

- 直缝 skill 没有项目代码作为证据 → PROVENANCE.md 标注"基于知识积木库缝合，非特定项目提取"
- 积木可能过时 → v2 加版本标记，当前可接受
- 语义匹配可能不准 → 匹配结果经过 LLM 判断，准确率应 >90%
