# Harness 技术四方评审汇总（实际三方 + 一方偏题）

**日期：2026-04-06**
**评审方：Sonnet (Claude) / Gemini / GPT**
**偏题方：Grok（回复的是 bp-009 蓝图升级评审，已单独归档）**

---

## 一、总体判断对比

| 评审方 | 一句话判断 |
|--------|-----------|
| **Sonnet** | NLAH 的价值是局部的、条件性的——精选 2-3 个组件做外科手术式引入，不要搬运整个范式 |
| **Gemini** | 有条件赞成深度融合，但必须实施"程序化校验、自然语言驱动"的混合控制模式，不能单纯增加文本指令 |
| **GPT** | 有条件赞成引入轻量化、宿主感知的 Execution Harness 层，但不能照搬 NLAH 全套，也不能把 harness 做成"更多文本约束" |

**三方共识：有条件赞成引入，但绝对不能全盘照搬，也不能做成"更多自然语言规则"。**

---

## 二、Q1-Q7 三方立场对比表

### Q1：Crystal 是否应该新增 Execution Harness 层？

| 维度 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| 立场 | 有条件赞成 | 有条件赞成 | 有条件赞成 |
| 核心论点 | v9 的 directive hardening 已经是隐性 harness，问题是要不要从隐性变显性 | v9 成功不是三层公式赢了，而是手工编码了执行逻辑——执行协议与领域知识本质正交 | v5-v9 真实失败大多在"执行控制"层，不是知识缺失层 |
| 关键限制 | 必须是轻量声明，不能是重量执行（IHR 的 16.3M tokens 不可接受） | 不能堆砌大段自然语言，会触发 Context Eviction 和指令诅咒 | 必须是"薄层"，不能吞掉 Blueprint/Constraint 的职责 |

**Q1 共识：三方一致赞成，但均强调"轻量/薄层"原则。**

---

### Q2：NLAH 六个组件取舍

| 组件 | Sonnet | Gemini | GPT | 共识 |
|------|--------|--------|-----|------|
| **Contracts** | ★★★★★ 强烈推荐 | ✅ 引入 | ✅ 引入 | **3/3 一致引入** |
| **Stage Structure** | ★★★★ 推荐但简化 | ✅ 引入（与 State 合并） | ✅ 引入 | **3/3 一致引入** |
| **State Semantics** | ★★★★ 有条件引入 | ✅ 引入（与 Stage 合并） | ✅ 引入 | **3/3 一致引入** |
| **Failure Taxonomy** | ★★★★★ 强烈推荐 | ✅ 引入 | ✅ 引入 | **3/3 一致引入** |
| **Adapters & Scripts** | ★★★★ 有条件引入 | ❌ 不引入（由宿主决定） | ½ 只作为命名钩子 | **分歧：Sonnet/GPT 有条件引入，Gemini 反对** |
| **Roles** | ❌ 不推荐 | ❌ 不引入 | ❌ 谨慎 | **3/3 一致不引入** |

**Q2 共识（4 进 2 退）**：
- **必须引入**：Contracts、Stage Structure、State Semantics、Failure Taxonomy
- **不引入**：Roles
- **有争议**：Adapters（Gemini 认为应完全由宿主处理；Sonnet/GPT 认为声明式引入有价值）

---

### Q3：Execution Contract 声明式 vs 程序化？

| 维度 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| 立场 | 混合：结构化自然语言 + 宿主侧轻量校验 | 混合：晶体内声明式 Schema + 宿主侧 Interceptor 程序化阻断 | 混合：声明式定义 + 程序化执行双层方案 |
| 晶体侧 | 结构化自然语言（表格/YAML-like，可 parse） | Declarative Schema（如 `required_args: {"TOP_N": 5}`） | 结构化 contract（不是 prose） |
| 宿主侧 | 交付验收点轻量校验（文件存在、指标非 NaN、参数范围） | Interceptor 程序化阻断（不符合则直接报错给模型） | Host adapter 把 contract 程序化执行 |

**Q3 共识：三方完全一致——混合方案（晶体内声明式定义 + 宿主侧程序化校验）。**

---

### Q4：如何解决"指令诅咒"与"更多 Harness 规则"的矛盾？

| 维度 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| 核心策略 | 分层次加载规则（执行 harness/参数锁/业务约束三层，按需加载） | 动态长臂上下文（Stage 切分 + 分阶段可见约束） | 不是减少知识，是把知识拆成不同执行面（spec lock/stage gate/state file/failure recovery/delivery gate） |
| 约束处理 | 动态选取相关 20-30 条，不全量注入 | 重构 104 条零碎约束为 15 条系统级 Harness State Semantics | 规则拆到不同执行面，每面只承载该面的规则 |
| 关键洞察 | 内容约束和执行约束对 AI 认知负荷不同 | 打破一次性灌输范式 | 把 harness 仍渲染成更长 markdown section 矛盾不会消失 |

**Q4 共识：三方一致——通过分层/分阶段加载约束来解决矛盾，而非减少规则总量或堆砌更多文本。**

---

### Q5：内嵌 vs 外挂？

| 维度 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| 立场 | 晶体声明 + 宿主适配分离 | 外挂 Runtime + 内嵌 Configuration | 晶体内嵌抽象协议 + 宿主外挂执行器 |
| 晶体内嵌什么 | host_requirements + host_adapters 声明 | Configuration（如 `allow_shell: false`） | 协议语义、contract、failure classes、state slots |
| 宿主侧什么 | shared runtime charter | Harness Runtime Agent 翻译为本地 System Prompt | Host Profile + Host Renderer |

**Q5 共识：三方完全一致——中间路线（晶体内嵌语义/声明，宿主外挂执行/适配）。**

---

### Q6："代码→自然语言迁移性能反升"意味什么？

| 维度 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| 核心解读 | 性能提升来自状态持久化策略改变，不是语言形式改变 | 性能提升来自 LLM 不需要做"代码→逻辑的反编译推理"，直接在逻辑态修正 | 性能提升来自控制逻辑被重组后更贴近最终验收对象，不是"自然语言天生更强" |
| 对 Doramagic 的含义 | 引入 file-backed state 就能获得大部分收益，不需要昂贵的 in-loop LLM | 自然语言 harness 绝对比纯代码挂载更契合生成模型，但必须结合编译态验证 | 真正重要的是 contract-first + artifact-backed closure + compaction-stable state |
| 风险提醒 | GUI 场景收益不能直接泛化到代码执行场景 | 不要迷信论文数据，OSWorld 与量化交易差异极大 | 最危险的误读是以为只要写更多 harness prose 就能提升性能 |

**Q6 共识：三方一致——不是"自然语言更好"，而是"状态外化+制品闭合+验收对齐"才是真正的性能来源。不能简单模仿论文在晶体中堆更多文字。**

---

### Q7：行动建议对比

#### 短期（立即/0-1 月）

| 建议 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| 结构化 Contract（规格锁形式化） | ✅ P0 | ✅ 短期 | ✅ 短期 1 |
| File-backed State（制品路径声明） | ✅ P0 | ✅ 短期（Stage 内含） | ✅ 中期 1 |
| Stage Structure（阶段切分） | ✅ P1 | ✅ 短期 | ✅ 短期 1 内含 |
| Host Profile / Adapter | ✅ P1 | ✅ 短期（内嵌 Config） | ✅ 短期 2 |

#### 中期（1-3 月）

| 建议 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| Failure Taxonomy + Recovery | ✅ P1 | ✅ 中期 | ✅ 中期 2 |
| 约束动态加载/分阶段注入 | ✅ P2 | ✅ 中期（分步注入） | — |
| 验收 Gate 分层（correctness + sanity） | — | — | ✅ 中期 3 |
| 晶体健康度自动评估（CES） | ✅ P2 | — | — |

#### 长期

| 建议 | Sonnet | Gemini | GPT |
|------|--------|--------|-----|
| Crystal IR（从 markdown 升级为中间表示） | — | — | ✅ 长期 1 |
| 独立 Harness Runtime | — | ✅ 中长期 | ✅ 长期 2 |
| Self-Evolution（经验回流） | ✅ P3 | — | ✅ 长期 3 |

---

## 三、三方独立发现的问题（你没问的）

### Sonnet 独立发现

1. **晶体的渲染目标选错了**：不是一次性渲染 seed.md，而是按阶段渲染不同部分（setup 加载资源、execute 加载蓝图+约束、validate 加载 Contract）
2. **"Verifier 有害"被严重低估**：v5 的 -0.25% 通过门禁恰好是 Verifier 与真实验收不对齐的典型案例
3. **NLAH 论文引用了 OpenClaw**：论文 Related Work 第 5 节明确引用 OpenClaw 2026，认为其与 IHR 互补
4. **晶体公式缺一个隐含第四项：Execution Context**：v9 五项修复中至少三项是宿主相关而非业务相关

### Gemini 独立发现

5. **"不要告诉模型不要用 &&"**：提及 `&&` 的 Token 反而会激活其概念权重——正确做法是用 Harness 的 Adapters 收敛可用工具子集（"模型手中没有锤子就不会乱砸"）
6. **v9 的"删除可选扩展阶段"和"白名单穷举"是绝对不可忽视的核心洞察**

### GPT 独立发现

7. **缺的不是"更多规则"而是"规则的执行面"（knowledge-to-runtime projection）**：Blueprint/Constraint/Resource 都是知识对象，但失败最多的是参数锁没被 enforce、状态没被 reopen、输出没被 gate
8. **缺少 Host Capability Model**：没有统一 runtime，只有不同宿主，如果没有 HostProfile 同一晶体的 harness 设计天然失真
9. **需要把"成功关闭条件"从 acceptance checklist 升级为 delivery gate**：NLAH 反复强调 close on artifact, not plausibility

---

## 四、三方核心分歧

| 分歧点 | Sonnet | Gemini | GPT |
|--------|--------|--------|-----|
| **Adapters 是否引入晶体** | 声明式引入（host_adapters 字段） | 不引入，由宿主决定 | 只作为命名钩子引入 |
| **约束动态加载的时机** | 中期 P2，用分类标签 | 短期就要做，结合 Stage 分步注入 | 未明确提出 |
| **Crystal IR 必要性** | 未提 | 未提 | 长期必要，从 markdown 升级为 IR 再渲染 |
| **独立 Harness Runtime** | 不需要 | 中长期需要 | 长期需要但按任务族复用 |

---

## 五、Grok bp-009 评审要点（偏题但有价值）

Grok 回复的是 bp-009 蓝图升级评审，与 Harness 无关，但其发现对蓝图升级有价值：

### 评分

| 维度 | 得分 |
|------|------|
| 分类质量 | 8.5/10 |
| A 股准确性 | 8/10 |
| 用例索引 | 7.5/10 |
| 实用价值 | 8.5/10 |
| 仍缺什么 | 6.5/10 |

### 三个误分类

1. `sell_cost=0.001` 标为 BA → 应为 RC+BA（印花税是国家强制，且当前默认已过时）
2. `涨跌停板处理` severity=high → 应为 critical（系统性高估动量策略收益率）
3. `rich_mode=True/False` 双层默认值矛盾未突出 → 应单独列为 high-severity BA

### Top 3 待解

1. 隐性业务逻辑提取仍不足（Schema 字段背后的领域假设）
2. A 股特有监管/合规约束覆盖不全（ST、除权除息、新股过滤）
3. 缺少"冲突检测"（业务决策与用户意图冲突时如何处理）

### Grok 最终判决

Conditional Yes——先在 5 个核心蓝图验证质量提升效果，再决定全量扩展。

---

## 六、CTO 综合建议（待 CEO 决策）

### 三方完全一致的结论（可直接执行）

1. **引入 Execution Harness 层**——但必须是轻量声明层，不是重量执行层
2. **引入 4 个 NLAH 组件**：Contracts、Stage Structure、State Semantics、Failure Taxonomy
3. **不引入 Roles**
4. **混合方案**：晶体内声明式定义 + 宿主侧程序化校验
5. **中间路线**：晶体内嵌协议语义，宿主外挂执行器
6. **论文核心启示**：不是"自然语言更好"，而是 contract-first + artifact-backed closure + compaction-stable state

### 建议的最小闭环（P0）

**Crystal Harness Schema v0.1**，只包含：

```yaml
execution_harness:
  # 1. Contracts（参数规格锁 + 交付门禁）
  spec_lock:
    - param: TOP_N
      value: 5
      violation: FATAL
    - param: STOCK_POOL_SIZE
      max: 20
      violation: FATAL
  delivery_gate:
    - condition: "abs(annual_return) > 0.01"
      on_fail: "BUG_INVESTIGATION"
    - condition: "sharpe_ratio is not NaN"
      on_fail: "RERUN"

  # 2. Stage Structure（阶段拓扑）
  stages:
    - name: setup
      exit_criterion: "all dependencies installed, data downloaded"
    - name: execute
      exit_criterion: "backtest completed, results file exists"
    - name: validate
      exit_criterion: "all delivery_gate conditions pass"
    - name: deliver
      exit_criterion: "structured output sent"

  # 3. State Semantics（持久化制品）
  state_slots:
    - path: "{workspace}/backtest_result.json"
      purpose: "回测结果，session 恢复时优先读取"
    - path: "{workspace}/run_log.txt"
      purpose: "执行日志，断点续跑参考"

  # 4. Failure Taxonomy（失败分类 + 恢复策略）
  failure_classes:
    - name: exec_rejected
      trigger: "tool call rejected by host preflight"
      recovery: "rewrite command to match exec whitelist format"
      forbidden: "do NOT retry same command, do NOT use shell operators"
    - name: param_drift
      trigger: "any spec_lock parameter deviates from locked value"
      recovery: "immediately revert to spec_lock value, do NOT justify the change"
    - name: timeout_risk
      trigger: "estimated remaining work > 50% of time budget"
      recovery: "simplify approach, reduce file count, merge steps"
    - name: framework_dead_end
      trigger: "framework API error after 2 attempts"
      recovery: "switch to alternative approach, do NOT retry same framework"

  # 5. Host Adapter（宿主适配声明）
  host_adapters:
    openclaw:
      exec_format: "python3 /absolute/path/file.py"
      exec_blacklist: ["&&", ";", "|", "||", ">>", "sudo", "rm"]
      timeout_seconds: 600
      single_file_mode: true
      edit_mode: "write_file_only"
    claude_code:
      exec_format: "unrestricted"
      timeout_seconds: null
      single_file_mode: false
      edit_mode: "edit_or_write"
```

### 待 CEO 决策的分歧项

| 分歧 | 选项 A | 选项 B |
|------|--------|--------|
| Adapters 归属 | 内嵌晶体（Sonnet/GPT） | 纯宿主侧（Gemini） |
| 约束动态加载时机 | 短期就做（Gemini） | 中期再做（Sonnet） |
| Crystal IR 升级 | 长期考虑（GPT） | 不需要（Sonnet/Gemini） |
| 独立 Harness Runtime | 中长期（Gemini/GPT） | 不需要（Sonnet） |

---

*四方评审汇总 v1.0 | 2026-04-06 | CTO 编制*
