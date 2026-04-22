# 约束采集方案 — 四方综合

> 综合 Claude / GPT / Grok / Gemini 四方独立研究
> 日期：2026-04-04
> 状态：待评审

---

## 一、约束的价值本质（四方全票共识）

四方从不同角度表述了同一个核心洞察：

| 模型 | 表述 | 关键词 |
|------|------|--------|
| Claude | 约束编码负空间——"不能怎么做" | 负空间、隐性失败模式显性化 |
| GPT | 把蓝图从"可搭"变成"可对" | 正确性、边界、验证 |
| Grok | 生产级禁忌知识 | 负知识、安全网 |
| Gemini | 抵御大模型高熵坍塌的抗体 | 负向摩擦力、未知之未知 |

**综合结论**：

蓝图描述正空间（系统该有什么结构），约束描述负空间（在这个结构里哪些坑会死人）。没有约束的种子晶体 = "结构正确但实现灾难"的配方。约束提供四种不可替代的价值：

1. **失败预防**：把散落在 Issues/代码注释/防御性断言中的痛苦经验凝聚为可查询的规则
2. **跨阶段不变式**：承载不属于任何单一 stage 但对系统正确性至关重要的规则（如信号延迟）
3. **能力声明边界**：告诉用户"这个系统不能宣称什么"——比代码 bug 更危险的是过度承诺
4. **验收可计算化**：约束直接派生 acceptance checks，使质量可衡量

---

## 二、约束来源分类（四方共识 + 综合映射）

### 来源 → constraint_kind 系统映射

| 来源 | 具体位置 | 主要产出 kind | 提取难度 | 信噪比 |
|------|---------|---------------|----------|--------|
| **源码防御逻辑** | assert、raise、if-guard、shift、类型强制 | domain_rule, architecture_guardrail | 低（grep+AST） | 高 |
| **架构接口约定** | @abstractmethod、执行顺序、全局常量 | architecture_guardrail | 低 | 高 |
| **数据模型/字段语义** | dataclass、enum、schema、转换函数 | domain_rule, architecture_guardrail | 中 | 高 |
| **官方文档** | FAQ、Warning/Note 区块、Limitations | resource_boundary, claim_boundary | 低 | 中 |
| **Issue/PR/Changelog** | bug 报告、破坏性变更、维护者讨论 | operational_lesson, resource_boundary | 中 | 中 |
| **跨项目对比** | 三个项目对同一问题的不同处理方式 | domain_rule, claim_boundary | 高（需合成） | 极高 |

### 关键洞察（Claude 独有，其他三方未显式提出）

**claim_boundary 是最重要但最难提取的一类**。源码中几乎没有直接证据，更多来自文档 disclaimer、License、FAQ 中的 "does not guarantee" 措辞、以及领域常识（如"历史收益不代表未来"）。如果不特别关注，最终产出会严重偏向 domain_rule 和 architecture_guardrail，而 claim_boundary 接近于零。但对用户而言，claim_boundary 可能是最有护城河价值的。

**应对策略**：为 claim_boundary 设计专门的提取轮次，允许 `source_type: expert_reasoning`，不强制要求代码行号级证据。

---

## 三、蓝图驱动采集流程（综合方案）

### 前置步骤（Claude 独有洞察，采纳）

**P0：迁移旧约束**
- `finance.jsonl` 中已有 3 条 v1.0 格式旧约束
- 先用 Schema v0.2 §6 的迁移映射转为 v2.0 格式
- 补充 `applies_to` 字段
- 写入新路径 `knowledge/constraints/domains/finance.jsonl`
- **理由**：去重合并器不能面对两种格式

**P1：global_contracts 转化**
- 三份蓝图各有 6-7 条 `global_contracts`
- 每条逐一转化为正式 Constraint 记录
- `applies_to.target_scope = global, blueprint_ids = [该蓝图ID]`
- **理由**：蓝图中已有的知识不能遗漏（Claude 盲点 2）

### 主流程（六步）

```
Step 1: Clone & Load
  ├─ git clone --depth 1 目标项目（记录 commit hash）
  ├─ 加载蓝图 YAML
  └─ 解析 stages, edges, global_contracts, evidence 引用

Step 2: 上下文组装（per stage）
  ├─ 蓝图侧：stage 的 responsibility, interface, design_decisions, pseudocode, acceptance_hints
  ├─ 源码侧：按蓝图 evidence 字段定位关键文件 + grep 相关类名/函数名
  ├─ 文档侧：README/FAQ/CHANGELOG 中与该阶段相关的章节
  └─ 输出：{stage_id: ExtractionContext}

Step 3: LLM 约束提取（per stage × 5 kinds）
  ├─ 对每个 stage，按 5 种 constraint_kind 分 5 轮提取
  ├─ 每轮聚焦一种 kind + few-shot 示例
  ├─ applies_to 自动填充：target_scope=stage, stage_ids=[当前stage]
  ├─ 强制要求 evidence_refs（文件:行号 或 文档URL）
  └─ 无证据的标 source_type=expert_reasoning, score≤0.7

Step 4: Edge + Global 约束提取
  ├─ 对每条 edge：检查两端数据契约的隐含约束
  ├─ 对 global：领域通用规律 + 跨阶段不变式
  ├─ claim_boundary 专项提取轮次（输入含 README disclaimer + FAQ + 领域常识）
  └─ applies_to 按实际判断填充 edge/global

Step 5: 格式校验
  ├─ Schema v0.2 合规性（必填字段、枚举值、最小长度）
  ├─ hash 计算：sha256(core + scope)[:16]
  ├─ applies_to 一致性：stage_ids/edge_ids 在蓝图中存在
  ├─ 原子性检查：一条约束只有一个 consequence
  └─ acceptance_hints 反向验证：蓝图 hints 是否都有对应约束

Step 6: 入库
  ├─ 分配 ID（finance-C-001, 002, ...）
  ├─ 全部以 status=draft 入库
  └─ 写入 knowledge/constraints/domains/finance.jsonl
```

### 跨蓝图去重（三个蓝图全部采集完后执行）

```
Step 7: 跨项目去重与合并
  ├─ 按 constraint_kind + target_scope 分组
  ├─ 组内 LLM 语义相似度判断（成对比较）
  ├─ 判"同一条"标准：when + action 语义等价 + consequence.kind 相同
  │
  ├─ 同一条 → 合并：
  │   ├─ core triple 取最通用表述
  │   ├─ evidence_refs 全部保留
  │   ├─ confidence 提升（单项目 0.85 / 双项目 0.90 / 三项目 0.95）
  │   ├─ consensus 提升（mixed → strong → universal）
  │   ├─ source_type 改为 cross_project
  │   └─ blueprint_ids：2 个项目 → 列表；3 个项目 → null（领域通用）
  │
  ├─ 相似但有实质差异 → 独立保留，relations 标注 related_to
  │
  └─ 冲突检测（Claude 盲点 5）：
      ├─ 对所有 blueprint_ids=null 的约束，LLM 成对冲突检查
      └─ 发现冲突 → 收窄 blueprint_ids 或标记 conflicts_with
```

### 执行顺序

```
Phase 0: 迁移旧约束 + global_contracts 转化
Phase 1: finance-bp-001 (freqtrade) — 人工深度参与，校准质量
Phase 2: finance-bp-002 (zipline) — 提升自动化比例
Phase 3: finance-bp-003 (vnpy) — 高度自动化
Phase 4: 跨项目去重与合并
Phase 5: 人工审阅，draft → active
```

---

## 四、约束粒度标准（四方全票共识 + 综合规则）

### 核心原则

**一条约束 = 一个可独立违反、可独立验证的规则**（Claude 的表述最精准，其他三方表述等价）

### 必须拆分的情况

当一条规则中存在：
- 两个独立的失败模式（违反 A 不一定违反 B）
- 两个不同的后果（consequence）
- 两个不同的触发条件（when）

```
✗ "回测中信号必须延迟一根K线，且以open价执行"
✓ C1: 信号必须 shift(1) 延迟 → 否则 look-ahead bias
✓ C2: 以下一根K线 open 价成交 → 否则价格偏差
（用户可能做了 shift(1) 但用 close 价，两个错误独立发生）
```

### 应合并的情况

当两条规则是同一件事的正反表述：
```
✗ "date 不能是 DatetimeIndex" + "date 必须是普通列"
✓ 合为一条：date 作为普通列（非 DatetimeIndex），类型 datetime64[ns, UTC]
```

### 粒度边界

- **下限**：不细到 if 语句级别。多行代码服务同一条逻辑规则时，合为一条约束
- **上限**：不泛到原则级别。"代码应该健壮" 不是约束；必须有具体的 when / action / consequence

---

## 五、跨项目约束处理（综合策略）

### 判断"同一条"的标准

1. `core.when` 语义等价（不要求字面相同）
2. `core.action` 语义等价
3. `core.consequence.kind` 相同或可归并
4. 底层因果机制相同（GPT/Gemini 强调）

```
freqtrade shift(1)  ≠  zipline 执行顺序  ≠  vnpy cross_order
→ 这三条不是"同一条约束"（实现机制不同）
→ 但可以上卷为一条通用约束："bar级回测必须隔离信号生成与成交时点"
→ 结果：1 条通用约束(null) + 3 条蓝图特异约束
```

### 双层约束结构（GPT 核心洞察，采纳）

很多高价值知识不是二选一，而是：
- **通用层**：一条领域通用约束（blueprint_ids=null）
- **特异层**：多条蓝图特异实现约束（各绑各的 blueprint_ids）
- **关系**：特异约束通过 `relations: [{type: specializes, target: 通用约束ID}]` 关联

这解决了 Gemini/Grok 提出的"跨蓝图排斥约束"问题——当通用约束在某蓝图中有不同实现时，不是"排斥"，而是通用层声明要求 + 特异层声明实现方式。

### 合并规则

| 字段 | 合并方式 |
|------|----------|
| core triple | 取最通用表述（去掉项目特有措辞） |
| evidence_refs | 全部保留 |
| confidence.score | 单项目 0.85 → 双项目 0.90 → 三项目 0.95 |
| confidence.consensus | mixed → strong → universal |
| confidence.source_type | cross_project |
| blueprint_ids | 2 个项目 → 列表；3 个项目 → null |
| notes | 记录各项目的具体实现差异 |

### 阈值/细节差异处理

- **同一数字不同表达**（72h vs 3天）：统一为 canonical 表述
- **不同阈值但同一要求**（72h vs 48h vs 1周）：取最保守值，或不写具体数字写"足够长的验证期"
- **领域分化**（Crypto 24h vs 股票 72h 跨周末）：利用 `scope.context_requires` 做特异化分离，不合并
- **本质不同**（vnpy 涨跌停检测，其他无）：不合并，蓝图特有

---

## 六、LLM 提取 Prompt 设计（综合方案）

### 策略：分 Kind 逐轮提取 + 遗漏检查

采纳 Claude 的"5 轮分 Kind 提取"（覆盖最系统），结合 GPT 的"两轮枚举→规范化"和 Grok/Gemini 的"exact_quote 防幻觉"。

### Prompt 结构

```
每个 Stage 的完整提取流程：

Round 1-5: 分 Kind 提取
  输入：
    - [系统角色] 金融量化约束提取专家
    - [Schema 定义] 当前 kind 的定义 + 2-3 个 few-shot 示例
    - [蓝图上下文] 当前 stage 完整定义
    - [源码内容] 对应文件（按 evidence 字段定位）
    - [补充材料] FAQ/CHANGELOG/Issues
    - [已提取约束] 前几轮已提取的约束（避免重复）
  输出要求：
    - JSON 数组，每条含完整 Constraint 字段
    - evidence_refs 必须带 file:line 或 doc URL
    - 新增 exact_quote_from_source 字段（防幻觉校验用，不入库）
    - 无证据 → source_type=expert_reasoning, score≤0.7

Round 6: 遗漏检查
  输入：前 5 轮全部结果
  提问：
    - 是否遗漏数据类型/格式约束？
    - 是否遗漏执行顺序约束？
    - 是否遗漏边界条件？
    - 是否遗漏性能限制？
    - 是否遗漏声明边界（claim_boundary）？
    - 蓝图 acceptance_hints 是否每条都有对应约束？

Round 7: 规范化
  输入：全部候选约束
  任务：
    - 拆分非原子项
    - 合并同义项
    - 统一 when/action 措辞
    - 补全 applies_to
    - 输出最终 JSONL-ready 结构
```

### claim_boundary 专项策略

```
专项输入（不限于源码）：
  - README 的 disclaimer / limitations 段
  - FAQ 的 "does not guarantee" 类措辞
  - License 中的免责声明
  - 领域监管常识（如 SEC/CSRC 的风险披露要求）
  - 蓝图 applicability.not_suitable_for 字段

专项 prompt 核心问题：
  "如果一个用户基于此蓝图构建了系统，他可能会对外宣称哪些能力？
   哪些宣称是危险的、不可支撑的、或违反行业惯例的？"
```

---

## 七、管线实现架构

### 新组件

| 组件 | 职责 | 复用情况 |
|------|------|----------|
| **BlueprintLoader** | 解析蓝图 YAML，提取 stages/edges/evidence refs | 新组件，简单 |
| **ExtractionContextBuilder** | 按 stage 组装上下文包（蓝图片段+源码+文档） | 新组件，核心 |
| **ConstraintExtractor** | LLM 调用层，分 Kind 提取 | 新组件，核心 |
| **ConstraintValidator** | Schema 校验 + 原子性检查 + 一致性检查 | 新组件，复用 JSON Schema |
| **CrossProjectMerger** | 跨项目去重 + 合并 + 冲突检测 | 新组件，**半自动** |
| **ConstraintStore** | JSONL 写入 + ID 分配 + hash 计算 | 改写 JudgmentStore |
| **LLMAdapter** | LLM 调用 | ✅ 已有，直接复用 |
| **RepoDocAdapter** | 文档获取 | ✅ 已有，可复用（获取 README/FAQ/docs） |

### 数据流

```
蓝图 YAML ─→ BlueprintLoader ─→ ExtractionContextBuilder ─→ ConstraintExtractor
                                        ↑                         │
                                   源码/文档                       ↓
                                                          ConstraintValidator
                                                                │
                                 ┌──────────────────────────────┘
                                 ↓
                          CrossProjectMerger ─→ ConstraintStore ─→ finance.jsonl
```

### 自动化程度

| 步骤 | 自动化 | 人工 |
|------|--------|------|
| 上下文组装 | 全自动 | — |
| LLM 提取 | 全自动 | — |
| 格式校验 | 全自动 | — |
| 去重候选 | 半自动（LLM 推荐） | 确认合并决策 |
| applies_to 判断 | LLM 初判 | 抽检 |
| 冲突检测 | LLM 标记 | 确认处理方式 |
| 最终审阅 | — | draft → active |

**校准策略**：第一个蓝图（freqtrade）人工深度参与，校准提取质量后，后两个蓝图提升自动化比例。

---

## 八、盲点与补充设计

### 采纳的盲点修补

| 盲点 | 来源 | 处理方式 |
|------|------|----------|
| **claim_boundary 系统性缺失风险** | Claude | 专项提取轮次 + 允许 expert_reasoning |
| **global_contracts 转化步骤缺失** | Claude | 增加 P1 前置步骤 |
| **旧约束迁移优先** | Claude | 增加 P0 前置步骤 |
| **约束腐烂/过期机制** | Grok/Gemini | 采集时填 review_after_days；volatile 约束绑定源 Issue 状态 |
| **双层约束结构** | GPT | 通用层 + 特异层，relations: specializes/generalizes |
| **跨蓝图排斥约束** | Gemini/Grok | 通过双层结构解决（不是排斥，是特化） |
| **约束间冲突检测** | Claude | 去重后对 blueprint_ids=null 的约束做成对冲突检查 |

### 暂不采纳的建议

| 建议 | 来源 | 不采纳理由 |
|------|------|-----------|
| target_scope 扩展到 interface/replaceable_point 级 | GPT | 当前 stage/edge/global 三级够用，过细会增加采集复杂度，后续按需扩展 |
| 向量数据库做去重（Qdrant） | Gemini | 约束量级（百条）不需要向量数据库，LLM 成对比较足够 |
| 用户反馈闭环（实盘偏差反馈） | Grok | 重要但超出当前 sprint 范围，记入 roadmap |
| canonical 规范化规则 | GPT | 好建议但现阶段约束数量少，规范化靠 LLM Round 7 处理，后续再考虑固化 |

---

## 九、预期产出

### 数量估算

每个蓝图 4-5 个 stage × 5 种 kind × 每种 2-4 条 ≈ 40-100 条/蓝图
加上 edge 约束（~10条）和 global 约束（~10条）
三个蓝图合计 ≈ 150-330 条原始约束
跨项目去重后 ≈ 100-200 条最终约束

### 质量指标

- 每条约束必须有 evidence_refs（source_type=expert_reasoning 除外）
- claim_boundary 类约束 ≥ 总量的 10%
- 每个 stage 至少覆盖 3 种 constraint_kind
- applies_to 一致性校验 100% 通过
- 原子性校验（一条一后果）100% 通过

---

## 十、下一步行动

1. 评审本方案
2. 确认后进入开发：
   - Phase 0：迁移旧约束 + global_contracts 转化
   - Phase 1：finance-bp-001 (freqtrade) 约束采集
   - Phase 2-3：zipline / vnpy
   - Phase 4：跨项目去重
   - Phase 5：人工审阅
