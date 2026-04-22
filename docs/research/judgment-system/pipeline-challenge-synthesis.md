# 流水线挑战合成：三方一致推翻了什么，我们怎么改

---

## 总判断

三方的挑战出奇地一致。这意味着我的原方案在三个点上都有明确的设计缺陷，不是偏好差异而是客观问题。

---

## 决策点 1：社区知识过滤

### 原方案
`body_length >= 80 + comments >= 3 + 技术关键词 + 排除 feature request`

### 三方一致意见
**`comments >= 3` 是错误的硬门槛。** 三方都指出同一个致命问题：高质量的独立 Bug Report（0 评论但描述精确、有复现步骤、被 PR 直接修复）会被系统性误杀，而这恰恰是经验层最有价值的原料。

### 各方独特贡献

| 来源 | 独特洞察 |
|------|---------|
| Gemini | **双轨制**：代码共证轨（Closed + Merged PR = 零门槛最高质量）+ 边界妥协轨（wontfix/works-as-intended = 框架作者的使用禁忌，价值连城） |
| GPT | **按 Issue 类型分流**：bug_report / incident / discussion / feature_request_with_constraint_signal 各有不同阈值 |
| Grok | **加权打分模型**：多信号打分取代硬阈值，linked_to_pr 权重最高 |

### 最终裁决：采纳 Gemini 的双轨制 + GPT 的类型分流 + Grok 的打分补充

```
过滤器 v2:

轨道一：代码共证轨（最高优先，零门槛）
  规则: Issue 状态 = Closed AND 关联了 Merged PR/Commit
  门槛: 无。不看字数、不看评论数、不看 reaction。
  理由: 这是被代码证实的经验，是最纯的判断原料。

轨道二：边界妥协轨（高优先）
  规则: Issue 状态 = Closed AND label IN [wontfix, works-as-intended, known-issue, by-design]
  门槛: body_length >= 50（作者通常会解释为什么不修）
  理由: 框架作者说"这个修不了/就是这样设计的" = 最高规格的使用禁忌。

轨道三：社区信号轨（常规通道）
  规则: 不满足轨道一/二的 Issue，按打分模型评估
  打分:
    + 3.0  linked_to_pr_or_commit (但未被轨道一捕获的，如 closed without merge)
    + 2.5  has_repro_steps OR has_expected_vs_actual
    + 2.0  maintainer_reply_with_root_cause
    + 1.5  has_logs_or_stacktrace
    + 1.5  label IN [bug, regression, incident, data-issue]
    + 1.0  reactions >= 3
    + 0.5  comments >= 3 (降为弱信号)
    + 0.5  body_length >= 120
    - 2.0  pure feature request (无失败证据)
    - 1.5  generic question (无具体场景)
  阈值:
    bug/incident 类: >= 3.0 送 LLM
    discussion 类:  >= 4.5 送 LLM
    其余:          >= 5.0 送 LLM

不进入任何轨道的 Issue → 丢弃
```

### 采纳的额外风险警告
- **GPT：幸存者偏差** — 只抓热门 Issue 会学到"社区吵得凶的问题"而非"最致命的问题"。缓解：轨道一专门捕获沉默但被代码修复的 Bug。
- **GPT：maintainer 风格偏差** — 有些项目在 PR 里讨论不在 Issue 里。缓解：轨道一同时检查 PR 中的讨论。

---

## 决策点 2：语义去重

### 原方案
`when + action` 向量相似度 > 0.85 → 标记重复 → LLM 裁决

### 三方一致意见
1. **0.85 单一阈值同时造成漏重和误杀**
2. **只比 `when + action` 严重不足** — 应该比较 consequence 的根因
3. **不要做文本硬合并** — 用关系连接（subsumes/strengthens），保留所有证据

### 各方独特贡献

| 来源 | 独特洞察 |
|------|---------|
| Gemini | **去重锚点应该是 Consequence（根本原因）**，不是 when+action。专家判断两个问题是否一致，看的是后果是否触发同一物理系统限制 |
| GPT | **规范化签名**：把 action/target/condition 归一化后做精确匹配（float → binary_float, cash ledger → monetary_ledger），然后再做语义补漏 |
| Grok | **分桶后再做向量比较**：同资源同任务 0.78, 跨资源同模式 0.84, 跨领域 0.88 — 不同上下文用不同阈值 |

### 最终裁决：四步去重，以结构匹配为主，语义为辅

```
去重流水线 v2:

Step 1: 规范化（确定性，零成本）
  将每颗判断编译为 canonical signature:
    scope_sig  = normalized(domains + resources + task_types)
    rule_sig   = normalized(modality + action + target)
    cause_sig  = normalized(consequence.kind + consequence 关键实体)
  词汇归一: float → binary_float, PnL ledger/cash ledger → monetary_ledger
  完全相同的 signature → 直接标记为重复候选

Step 2: 分桶（确定性）
  按 scope_sig 分桶，只在同桶内做比较
  大幅减少计算量，避免跨领域误伤

Step 3: 桶内多信号判重
  强重复条件（任一命中 → 直接候选）:
    - rule_sig 一致 + scope 重叠 > 70%
    - 同一 resource + 同一 consequence.kind
    - cause_sig 一致（Gemini 洞察：同一根因 = 同一判断）
  弱重复条件（送 LLM 裁决）:
    - 向量相似度 > 0.78（Grok 阈值）
    - action family 一致 + consequence 语义相近
    - 共享同一上位判断（subsumes 关系）

Step 4: LLM 裁决（受约束）
  LLM 只能输出四种结果（GPT 方案）:
    - duplicate_merge: 同一判断不同表述 → 保留 when 更精确的，证据合并
    - subsumes_link: A 包含 B → 建立 subsumes 关系
    - strengthens_link: A 和 B 互为证据 → 建立 strengthens 关系
    - distinct_keep: 不同判断 → 各自保留
  不允许 LLM 自由发挥合并文本
```

### 合并策略
- **永不删除判断** — "合并"的含义是：保留一个 canonical 主条，被合并项通过 relations 挂载
- 主条选择规则：when 定义最精确 + evidence 最多 + severity 最高
- 被合并项的所有 evidence_refs 追加到主条
- 如果 consequence 冲突 → 不合并，标记 `conflicts` 关系，进入人工队列

---

## 决策点 3：检索意图展开

### 原方案
LLM 展开 5 个问题域 + 只能展开到库中已有判断

### 三方一致意见
1. **图谱扩展优先于 LLM 猜测** — 既然 Schema 设计了 relations，就应该沿着 generates/depends_on 做确定性扩展
2. **固定 5 个上限不合理** — 应该动态调整
3. **必须报告覆盖缺口** — "只展开到已有"会制造虚假的完整感
4. **直接匹配权重显著高于推测匹配**

### 各方独特贡献

| 来源 | 独特洞察 |
|------|---------|
| Gemini | **完全用图谱替代 LLM 展开** — "用 LLM 猜展开是用幻觉对抗无知"；用 prompt 实体密度判断用户水平 |
| GPT | **四阶段设计最完整**：显式匹配 → 图谱扩展 → LLM 补盲 → 缺口检查；最详细的用户水平启发式 |
| Grok | **动态预算公式**：2 + task_complexity + resource_risk + domain_risk + novice_bonus |

### 最终裁决：图谱优先 + LLM 补盲 + 缺口报告

Gemini 说"完全不用 LLM 展开"，但我不完全同意。图谱只能扩展到已有连接——如果判断库的关系图还不完善（初期必然如此），纯图谱扩展会遗漏重要判断。LLM 补盲作为最后兜底是必要的，但优先级最低。

```
检索流水线 v2:

Step 1: 意图解析（轻量 LLM 或规则）
  从用户输入提取:
    - domains, task_types, resources, markets, tech_stack
    - 实体密度得分（用于判断用户水平）

Step 2: 直接匹配（确定性）
  domain_index 召回 + universal 判断
  scope 过滤（context_requires 检查）
  version.status = active
  → 产出: P1 判断集（权重 1.0）

Step 3: 图谱扩展（确定性，优先于 LLM）
  从 P1 判断出发，沿 generates / depends_on 走最多 2 跳
  自动拉入因果链上的判断
  → 产出: P2 判断集（权重 0.8）

Step 4: LLM 补盲（仅在 P1 + P2 不足时触发）
  触发条件: P1 + P2 < 10 颗判断，或用户实体密度 < 0.4（新手）
  LLM 任务: 列出"图谱未覆盖但任务必须考虑的问题域"
  输出: query_tags 列表（不是判断本身）
  用 query_tags 在库中二次召回
  → 产出: P3 判断集（权重 0.6）
  展开预算: 动态，基于任务复杂度
    简单脚本: 2-3
    研究工具: 4-6
    回测系统: 6-10
    实盘系统: 10+

Step 5: 缺口报告（一等公民）
  如果 LLM 在 Step 4 识别的问题域在库中无对应判断:
    → 输出覆盖缺口警告:
      "当前知识库在 [A股涨跌停规则] 领域尚未覆盖。
       此场景的晶体可信度降低。
       建议补充来源: [相关 GitHub 项目/文档]"
  缺口信息同时反馈给 Scout（定向阶段），
  驱动下一轮采集优先补这个缺口。
  → 形成闭环: 检索发现缺口 → Scout 定向补采 → 入库 → 检索不再缺

Step 6: 排序与裁剪
  综合排序:
    P1 权重 1.0 × severity × confidence
    P2 权重 0.8 × severity × confidence
    P3 权重 0.6 × severity × confidence
  用户水平调整:
    新手（实体密度 < 0.4）: P2/P3 权重 +0.1（多给他看"不知道自己不知道"的）
    专家（实体密度 > 0.7）: P3 权重 -0.15（减少 LLM 猜测噪音）
```

---

## 三项额外风险（三方共同指出，原方案完全未考虑）

### 风险 1：社区偏见 ≠ 生产真相
GPT 最深刻的一句话："GitHub Issue 反映的是哪些问题被愿意发声的人提出来，不等于真实问题分布。" 经验层判断可能被"话多的人"主导。

**缓解**: 轨道一（代码共证轨）不依赖社区讨论热度，直接从代码修复中提取，天然绕过这个偏见。

### 风险 2：项目偏好 ≠ 领域约束
GPT："某项目不用 Decimal，不代表 float 就合理。" 跨项目合成时必须区分：领域约束（不可违反）vs 项目局部实现（仅此项目的选择）vs 资源妥协（因为工具限制而做的折衷）。

**缓解**: 知识层判断要求至少 2 个项目交叉验证（source = S2_cross_project）。单项目独有做法标记为 `source = S1_single_project, confidence < 0.7`。

### 风险 3：虚假完整感
三方都强调：如果系统不报告缺口，用户会以为晶体已经覆盖了所有风险，实际上可能缺了关键领域。这比"给出错误建议"更危险——因为用户不会去质疑一个看起来完整的系统。

**缓解**: 缺口报告作为检索的一等公民输出，且反馈给 Scout 驱动定向补采。

---

## 对流水线设计方案的更新指令

以上三个裁决需要回写到 `judgment-pipeline-design.md`。具体变更:

1. **第二章（提取）通道 C** — 前置过滤器替换为三轨制
2. **第三章（清洗）** — 去重逻辑替换为四步流水线，锚定 consequence 根因
3. **第五章（检索）** — 替换为图谱优先 + LLM 补盲 + 缺口报告的六步流程
4. **新增第六.5章** — 缺口报告 → Scout 的反馈闭环
