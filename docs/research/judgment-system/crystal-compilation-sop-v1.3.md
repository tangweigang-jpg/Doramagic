# 晶体编译 SOP v1.3

> **定位**：蓝图提取 SOP v2.3 和约束采集 SOP v1.3 的下游消费者。
> 输入是已提取的蓝图+约束+资源，输出是可部署的晶体。
> **此 SOP 是领域无关的**。
>
> **版本历史**：
> - v1.0：首版，首测通过但发现严重认知错误（timeout/体积限制编撰）
> - v1.1：修正事实错误
> - v1.2：补知识压缩 + SKILL.md 渲染 + 领域通用化
> - **v1.3**：四方评审（Grok/Gemini/GPT/Sonnet）驱动的 7 项改进——时效性管理、References 强制加载、Stage 拓扑泛化、Delivery Gate 双层化、Spec Lock 领域无关元准则、知识压缩补 Actionability 维度、非金融 worked example

---

## 前置依赖

执行本 SOP 前需了解以下蓝图 schema 字段：

| 字段 | 含义（跨领域语义） |
|------|------------------|
| `business_decisions` | 蓝图中标注的设计决策列表 |
| `type=T` | 技术选择——纯工程实现方案（如用 SQLite 还是 PostgreSQL） |
| `type=B` | 业务决策——影响最终产出行为的主动选择（如先卖后买、SSR vs CSR） |
| `type=BA` | 业务假设——可能不成立的隐含前提（如固定滑点 0.1%、所有用户有 Node 18+） |
| `type=DK` | 领域知识——领域事实（如 A 股换手率是核心指标、REST API 幂等性） |
| `type=RC` | 外部强制规则——法规/平台/标准强制（如印花税率、GDPR、WCAG、App Store 审核规则） |
| `known_use_cases` | 蓝图中索引的典型使用场景 |
| `must_validate` | 每个 use case 中列出的验收要点 |
| `known_gap` | 蓝图中标注的已知缺失/风险 |
| `severity` | 约束的严重程度（fatal/critical/high/medium） |

---

## 核心原则

**晶体 = 好的蓝图 + 好的资源 + 好的约束 + 好的 Harness**

四层缺一不可。Harness 是让知识正确发挥作用的手段，**不能替代知识本身**。
晶体的核心价值是让 AI 获得它原本没有的领域知识。

---

## 适用范围

| 领域 | 蓝图来源示例 | 典型任务类型 | 典型交付物 |
|------|-------------|-------------|-----------|
| 金融量化 | zvt、zipline、freqtrade | 脚本执行 | 回测脚本 + 指标 |
| Web 开发 | Next.js、Django、FastAPI | 迭代构建 | 可运行应用 |
| 数据工程 | Airflow、dbt、Dagster | 声明式配置 | 数据管线 |
| AI/ML | LangChain、LlamaIndex、DSPy | 迭代构建 | RAG/Agent 系统 |
| 移动端 | React Native、Flutter | 迭代构建 | 可编译应用 |
| DevOps | Kubernetes、Terraform | 声明式配置 | 基础设施配置 |

---

## 输入

| 输入 | 来源 | 要求 |
|------|------|------|
| Blueprint YAML | 蓝图提取 SOP v2.3 | 含 business_decisions + known_use_cases |
| Constraints JSON/JSONL | 约束采集 SOP v1.3 | 含 severity、constraint_kind、stage_ids |
| Resources | 蓝图 replaceable_points | 含 options、fit_for |
| User Intent | 用户/产品经理 | 目标环境、任务类型、产出类型 |
| Target Host | 部署决策 | openclaw / claude_code / generic |
| Host Spec | `docs/research/host-specs/{host}-host-spec.md` | 宿主能力规范，不编撰 |

## 输出

| 输出 | 格式 | 用途 |
|------|------|------|
| Crystal IR | `crystal-{id}.ir.yaml` | 结构化中间表示 |
| seed.md | 每宿主一份 | 一次性执行指令 |
| SKILL bundle | `{skill-name}/` 目录 | 可复用 OpenClaw skill |

---

## Step 1: Execution Contract 编写

### 1a. Spec Lock 提取

**输入**：蓝图 `business_decisions` 中 type=B 或 type=BA 的条目。

**可漂移参数的判断元准则**（领域无关，v1.3 升级）：

一个参数是否需要锁定，取决于以下三个条件，**满足任一即锁**：

| 元准则 | 说明 | 金融例 | Web 例 | 数据例 |
|--------|------|--------|--------|--------|
| **(a) AI 无约束时会自主选择** | AI 有自己的"默认偏好"，会偏离用户意图 | TOP_N=5→AI 改 30 | App Router→AI 用 Pages Router | materialization=view→AI 改 table |
| **(b) 不同选择导致结果不可比较** | 参数变化后产出的性质发生质变 | 动量策略→布林带策略 | SSR→CSR（SEO 完全不同） | incremental→full refresh |
| **(c) 与用户意图直接绑定** | 用户明确要求了这个值 | "A 股回测" | "TypeScript 项目" | "每日增量更新" |

**格式**：
```yaml
- param: {参数名}
  value: {锁定值}
  violation: FATAL | WARN
  rationale: {为什么锁}
```

**规则**：
- type=RC（外部强制规则）→ 一律 `violation: FATAL`
- 路径参数使用 `{workspace}` 占位符

### 1b. Delivery Gate 提取

**输入**：`known_use_cases[target].must_validate` + severity=fatal 约束。

**三类通用 Gate**（领域无关，v1.3 升级）：

| Gate 类别 | 说明 | 金融例 | Web 例 | 数据例 |
|-----------|------|--------|--------|--------|
| **产出存在性** | 交付物文件/服务/端点存在 | 结果文件存在 | `next build` 成功 | 所有 model 编译通过 |
| **执行正确性** | 主流程无错误完成 | 回测完成无异常 | `curl localhost:3000` 返回 200 | `dbt test` 全部通过 |
| **业务合理性** | 结果不是"表面通过实际无效" | abs(return)>1%, trades>0 | 页面有实际内容（非空白） | 输出行数>0, 无全 NULL 列 |

**Hard Gate vs Soft Gate**（v1.3 新增）：

| 类型 | 定义 | on_fail | 适用场景 |
|------|------|---------|---------|
| **Hard Gate** | 可程序化验证（exit code / regex / 数值比较） | RERUN / REBUILD | 构建成功、指标阈值、文件存在 |
| **Soft Gate** | 需要 AI self-check 或 LLM-as-Judge | WARN + 输出评估报告 | 架构一致性、代码质量、设计意图符合 |

每个晶体至少 3 条 Hard Gate。Soft Gate 可选但必须有明确 rubric（评判标准）。

---

## Step 2: Failure Taxonomy 编写

### 2a. 通用失败类（6 条，领域无关）

| 失败类 | 触发条件 | 恢复动作 | 禁止动作 |
|--------|---------|---------|---------|
| `exec_rejected` | 宿主拒绝执行命令 | 重写命令为白名单格式 | 不重试相同命令 |
| `param_drift` | spec_lock 参数偏离锁定值 | 立即恢复锁定值 | 不辩解修改理由 |
| `timeout_risk` | 预估剩余工作 > 50% 时间预算 | 简化方案 | 不增加工具调用 |
| `framework_dead_end` | 框架/依赖错误重试 2 次仍失败 | 切换替代方案 | 不继续重试 |
| `mode_switch` | 产出文档/分析而非可执行交付物 | 删除文档，重新生成交付物 | 不产出参考文档 |
| `silent_drift` | 架构/方法偏离规格但未报错 | 对照 spec_lock 逐项检查 | 不假设"接近"可以 |

### 2b. 领域特定失败类派生

从蓝图 `known_gap=true` + 约束 severity=fatal/critical 派生。每条必须有**具体 recovery action**。

---

## Step 3: 任务类型判断 + Stage Spec（v1.3 重构）

### 3a. 任务类型判断

在设计阶段拓扑前，先判断任务类型：

| 类型 | 特征 | 典型场景 | 流控模式 |
|------|------|---------|---------|
| **A：一次性产出** | 输入确定→处理→输出确定 | 回测、报告生成、数据转换、脚手架生成 | **Pipeline** |
| **B：迭代构建** | 需要写→测→改循环 | Web 应用、移动端应用、重构、AI 系统 | **Iterative** |
| **C：声明式配置** | 产出是配置文件/DAG/规则 | dbt、Terraform、K8s、CI/CD | **Declarative** |

### 3b. 三种流控模式

**Pipeline 模式**（类型 A）：
```
setup → execute → validate → deliver
```
严格顺序，禁止回退。

**Iterative 模式**（类型 B）：
```
setup → scaffold → [loop: implement ↔ test, max_iterations=N] → deliver
```
implement↔test 允许内循环，必须声明 `max_iterations`（防止无限循环）。

**Declarative 模式**（类型 C）：
```
analyze → generate → verify → apply
```
generate 产出配置文件，verify 做 dry-run/lint，apply 提交。

### 3c. 通用规则

- 最多 4-5 个阶段
- 每阶段定义 goal / actions / exit_criterion / budget_ratio
- budget_ratio 之和 = 1.0，基于 Host Spec 的真实 timeout
- **禁止可选扩展阶段**（L3 教训）
- 时间预算从 Host Spec 读取，不编撰（L9 教训）

---

## Step 4: Host Adapter 编写

**原则**：白名单优先 + 引用 Host Spec + `{workspace}` 占位符。

```yaml
host_adapters:
  {host_name}:
    spec_ref: "docs/research/host-specs/{host}-host-spec.md"
    timeout_seconds: {从 Host Spec 读取}
    exec_rules:
      whitelist: [...]
    path_template: "{workspace}/{filename}"
```

**{workspace} 解析规则**：

| 渲染目标 | 谁解析 | 解析为 |
|---------|--------|--------|
| seed.md | 编译器（渲染时） | 宿主 workspace 绝对路径 |
| SKILL.md | 宿主 runtime（触发时） | skill 目录路径 |
| scaffold | AI（填充时） | 用户确认的工作目录 |

---

## Step 5: 知识压缩

### 5a. 四维筛选（v1.3：增加 Actionability）

每条知识按四个维度打分：

**维度 1：AI 新颖度**

| 等级 | 判断方法 | 处理 |
|------|---------|------|
| HIGH | AI 大概率不知道（领域特有、版本特定、框架内部行为） | 完整描述 |
| MEDIUM | AI 可能知道但容易出错 | 简要提醒 |
| LOW | AI 几乎肯定知道（通用编程知识） | 省略 |

判断辅助方法：用标准化测试提示词问目标模型该知识点，看回答是否正确。避免纯主观猜测。

**维度 2：失败预防度**

| 等级 | 判断标准 | 处理 |
|------|---------|------|
| CRITICAL | 直接防止已知失败案例 | 必须包含 |
| HIGH | 防止蓝图 known_gap 风险 | 应当包含 |
| LOW | 通用最佳实践，无对应失败 | 可省略 |

**维度 3：阶段相关度**

| 等级 | 处理 |
|------|------|
| 当前阶段直接相关 | 注入当前阶段 |
| 跨阶段通用 | 注入 Contract 或全局知识节 |
| 其他阶段专用 | 放 references/ 按需加载 |

**维度 4：操作化程度（Actionability）**（v1.3 新增）

| 等级 | 说明 | 处理 |
|------|------|------|
| HIGH | 包含具体指令、代码示例、精确数值 | 优先内联正文 |
| LOW | 抽象建议（"需谨慎"、"建议优化"） | 改写为具体指令后再内联，或降级到 references/ |

示例对比：
- LOW："dbt 增量模型需要谨慎设计唯一键策略"
- HIGH："dbt 增量模型必须在 `unique_key` 使用复合键 `['id', 'updated_at']`，单字段唯一键在重跑时产生重复数据"

### 5b. 压缩规则

1. **CRITICAL 失败预防 OR HIGH 新颖度**：完整包含，不压缩
2. **MEDIUM 新颖度 AND HIGH 失败预防**：简要包含（一句话 + 关键数值）
3. **三维均为 MEDIUM**：按需引用（放 references/）
4. **LOW 新颖度 AND LOW 失败预防**：省略
5. **LOW Actionability 的知识**：改写为 HIGH Actionability 后按上述规则处理，无法改写则降级到 references/

### 5c. 覆盖率标准

- type=RC（外部强制规则）：**100%** 覆盖
- type=B（业务决策）：**≥ 80%** 覆盖
- severity=fatal 约束：**100%** 覆盖
- severity=high + 本用例 stage 匹配：**≥ 60%** 覆盖
- HIGH 新颖度知识占总量 **≥ 40%**

### 5d. 非金融 worked example：Next.js App Router 晶体

| 知识项 | 新颖度 | 失败预防 | 阶段 | Actionability | 决策 |
|--------|--------|---------|------|--------------|------|
| Server Components 默认，只有 useState/useEffect/浏览器 API 才加 `'use client'` | MEDIUM | CRITICAL | implement | HIGH | **内联**（Rule 2） |
| App Router 的 `loading.tsx` 自动 Suspense boundary | HIGH | HIGH | implement | HIGH | **完整描述**（Rule 1） |
| Tailwind class 排序风格 | LOW | LOW | implement | LOW | **省略**（Rule 4） |
| `next.config.js` 中 `images.remotePatterns` 安全配置 | HIGH | CRITICAL | setup | HIGH | **完整描述**（Rule 1） |
| React 18 并发特性基础 | LOW | LOW | — | LOW | **省略**（Rule 4） |

---

## Step 6: Crystal IR 组装

```yaml
version: "1.3"
crystal_id: "{domain}-bp-{id}-{use_case}"
task_type: "A | B | C"  # Pipeline / Iterative / Declarative

references:
  blueprint: "path/to/blueprint.yaml"
  constraints: ["path/to/constraints.jsonl"]
  use_case: "use_case_name"
user_intent: { ... }

knowledge:
  business_decisions: [ 经四维筛选后的条目 ]
  constraints:
    fatal: [ 全量 ]
    high_relevant: [ stage 匹配的 ]
  resources:
    external_services: [ API / 数据源 / 第三方服务 ]
    dependencies: [ 包依赖 ]
    infrastructure: [ 存储 / 计算 / 部署环境 ]
  references:
    - path: "references/blueprint-full.md"
      load_trigger: "FORCED_READ_BEFORE_STAGE_2"
    - path: "references/constraints-by-stage.md"
      load_trigger: "ON_DEMAND"

harness:
  contract: { spec_lock: [...], delivery_gate: { hard: [...], soft: [...] } }
  failure_taxonomy: { universal: [...], domain_specific: [...] }
  stage_spec: { task_type: "...", stages: [...] }
  host_adapters: { ... }

# v1.3 新增：时效性管理
validity:
  compiled_at: "ISO date"
  source_commits:
    blueprint: "{commit_hash}"
    constraints: "{commit_hash}"
  version_pins:
    - dependency: "{framework_name}"
      version: "{semver_range}"
  review_triggers:
    - "{framework_name} major version release"
    - "RC type decision source changes"
  expires_at: null  # 或指定日期

compilation:
  sop_version: "crystal-compilation-v1.3"
  compiled_at: "ISO date"
```

---

## Step 7: 宿主渲染

### 渲染原则

1. **知识与 Harness 平衡**
2. **路径参数化**（`{workspace}`）
3. **从 Host Spec 派生**，不编撰
4. **References 强制加载**（v1.3：不是"请阅读"，是"必须先 read 工具调用"）

### 7a. seed.md 渲染

渲染模板中关于 references 的指令改为**强制 Tool Call**：

```markdown
## 执行前强制读取（FATAL：未读取不可继续）

在开始任何生成前，你必须执行以下读取并确认内容已加载：
1. 读取 `references/blueprint.md` → 确认已获取蓝图核心知识
2. 读取 `references/api-examples.md` → 确认已获取正确 API 调用格式

如果上述文件不存在或读取失败，立即报告错误，不要从自身知识编造内容。
```

### 7b. SKILL.md 渲染

目录结构：
```
{skill-name}/
  SKILL.md              # ≤ 80 行正文
  references/
    blueprint.md        # 完整蓝图知识
    constraints.md      # 按阶段分组的约束
    api-examples.md     # 正确 API 调用示例
  scaffolds/
    {output}.scaffold.md
```

SKILL.md 执行流程中强制读取步骤（v1.3）：
```markdown
## 执行流程
1. **[FATAL]** 执行 read 工具读取 `references/blueprint.md`，确认返回内容后继续
2. **[FATAL]** 执行 read 工具读取 `references/api-examples.md`
3. 读取 `scaffolds/{output}.scaffold.md` 获取输出骨架
4. 按 REPLACE_WITH 占位符逐项填充
5. 写入 `{workspace}/{output}`
6. 验证交付门禁（Hard Gate 全部通过，Soft Gate 输出评估）
```

### 7c. 渲染后检查

| 检查项 | 标准 |
|--------|------|
| 知识覆盖率 | RC 100%, B ≥ 80%, fatal 100%, high 相关 ≥ 60% |
| 知识 Actionability | 内联知识中 HIGH actionability ≥ 70% |
| References 强制读取 | 有 `[FATAL] 执行 read 工具` 指令 |
| 路径参数化 | 无硬编码用户路径 |
| Host Spec 对齐 | 所有平台数值有证据 |
| Hard Gate ≥ 3 条 | 至少 3 条可程序化验证的 gate |
| 时效性元数据 | version_pins 和 review_triggers 已填写 |
| SKILL.md 规范 | frontmatter 正确，正文 ≤ 80 行，metadata 单行 JSON |

---

## Step 8: 质量校验

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| Contract 完整性 | spec_lock 覆盖所有满足元准则(a)(b)(c)的参数 | 补充 |
| Delivery Gate | ≥ 3 Hard Gate + Soft Gate 有 rubric | 补充 |
| Failure Taxonomy | 6 通用 + ≥ 2 领域特定 | 补充 |
| Stage 任务类型 | 任务类型判断正确，流控模式匹配 | 重新判断 |
| 知识覆盖率 | 达到 5c 标准 | 补充知识 |
| 知识 Actionability | LOW actionability 知识已改写或降级 | 改写 |
| References 强制加载 | 渲染中有 FATAL read 指令 | 添加 |
| 路径参数化 | 无硬编码用户路径 | 替换 |
| Host Spec 对齐 | 所有数值有证据 | 查证修正 |
| **时效性** | version_pins 覆盖所有框架依赖，RC 类 decision 有 review_trigger | 补充 |
| **跨领域可执行** | 非本领域工程师阅读 SOP 后能理解每个判断点 | 补充示例 |

---

## Step 9: 晶体效能验证

**目的**：验证晶体是否真的让 AI 做得更好。覆盖率达标不等于有效——v1.0 首测知识覆盖率仅 6% 但 AI 仍通过全部 gate，说明可能靠自身能力完成而非靠晶体知识。

### 9a. 基线测试（无晶体）

给目标宿主**同样的 user_intent**，但**不给晶体**，只给一句话任务描述。

```
示例（金融）：
  有晶体时的 intent："A 股 MACD 日线金叉择时策略回测"
  基线 prompt："请帮我做一个 A 股 MACD 金叉策略的回测"

示例（Web）：
  有晶体时的 intent："基于 Next.js App Router 构建 SSR 博客应用"
  基线 prompt："请帮我用 Next.js 做一个博客网站"
```

记录基线产出：
- 是否完成任务
- 产出质量（Delivery Gate 通过数）
- 关键决策点 AI 做了什么选择（用什么框架/参数/架构）
- 出现了哪些错误

### 9b. 晶体测试（有晶体）

给目标宿主**同样的 user_intent** + **编译好的晶体**（seed.md 或 SKILL.md）。

记录同样的指标。

### 9c. 效能对比

| 对比维度 | 基线 | 晶体 | 判定 |
|---------|------|------|------|
| Hard Gate 通过数 | X/N | Y/N | Y > X 为有效 |
| 关键参数是否漂移 | 列出漂移项 | 列出漂移项 | 晶体版漂移更少为有效 |
| 错误类型 | 列出 | 列出 | 晶体版避免了基线的错误为有效 |
| 领域知识应用 | AI 是否犯了领域错误 | AI 是否正确应用了领域知识 | 最核心判据 |
| 交付时间 | T1 | T2 | 参考项，不作为主判据 |

**判定标准**：

| 结果 | 含义 | 动作 |
|------|------|------|
| 晶体版 Hard Gate 通过数 > 基线 | 晶体有效 | 可发布 |
| 晶体版避免了基线的领域错误 | 知识注入生效 | 可发布 |
| 晶体版与基线无显著差异 | **晶体无效** | 回到 Step 5 重新筛选知识——可能是 HIGH 新颖度的知识不够，或者 Actionability 不足 |
| 晶体版反而比基线差 | **晶体有害** | 回到 Step 1 检查 spec_lock 是否过度限制，或约束是否有错 |

### 9d. 知识归因分析

对比基线和晶体的 AI 行为差异，回答：

1. **哪些知识改变了 AI 的行为？**（在基线中犯的错误，在晶体版中被避免了）
   → 这些是晶体最有价值的知识，确认它们的四维评分正确
2. **哪些知识被忽略了？**（晶体中有但 AI 没使用）
   → 检查：是 Actionability 不够？位置不对（应该内联但放了 references/）？还是被其他指令淹没？
3. **AI 自主补充了哪些晶体没有的知识？**（晶体没覆盖但 AI 自己做对了）
   → 这些知识的 AI 新颖度应标为 LOW，下次编译可省略

### 9e. 验证通过标准

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| 效能提升 | 晶体版至少在 1 个维度显著优于基线 | 回到 Step 5 |
| 无负面效应 | 晶体版不比基线差 | 回到 Step 1 检查过度约束 |
| 知识生效 | 至少 1 条 HIGH 新颖度知识在 9d 中被确认"改变了 AI 行为" | 补充更多 HIGH 新颖度知识 |

**注意**：Step 9 不是每次编译都必须跑完整 A/B 测试。建议：

- **新蓝图首次编译**：必须完整跑 9a-9d
- **已验证蓝图的增量更新**：只跑 9b（晶体测试），与历史基线对比
- **跨宿主迁移**：在新宿主上重跑 9a-9c

---

## 教训日志

| # | 教训 | 来源 |
|---|------|------|
| L1 | spec_lock 必须覆盖所有可漂移参数 | v8 TOP_N 漂移 |
| L2 | delivery_gate 必须含业务合理性检查 | v5 pending_order bug |
| L3 | 禁止可选扩展阶段 | v8 股票池膨胀 |
| L4 | 代码模板给可执行示例不给伪代码 | v8 baostock 参数错误 |
| L5 | Host Adapter 白名单优先 | Gemini 评审 |
| L6 | 约束注入按阶段精选——v1 实测 104 条仅 35% 覆盖率，因果机制待验证（可能是结构问题而非数量问题） | v1 实测 |
| L7 | Crystal IR 与渲染分离 | 三方评审共识 |
| L8 | Failure Taxonomy 必须有具体 recovery action | v7 回退死路 |
| L9 | 宿主能力参数从 Host Spec 读取，禁止编撰 | v1.0 timeout/体积限制编撰 |
| L10 | 晶体知识是核心价值，Harness 不能替代知识 | v1.0 知识覆盖率 6% |
| L11 | "指令诅咒"0.95^N 未经实测验证，不作为第一性原理 | 事实核查 |
| L12 | 路径使用 `{workspace}` 占位符 | v1.0 硬编码路径 |
| L13 | 晶体必须能产出可复用 SKILL.md，不只是 seed.md | CEO 审查 |
| L14 | 知识压缩用四维筛选（新颖度×失败预防×阶段相关×操作化程度） | v1.2 四方评审 |
| **L15** | **时效性管理：每个晶体必须有 version_pins + review_triggers** | **四方评审一致：#1 优先级** |
| **L16** | **References 必须强制 read 而非"请阅读"——AI 会声称读了但实际编造** | **Gemini/Sonnet 评审** |
| **L17** | **Stage 拓扑不硬编码——Pipeline/Iterative/Declarative 三种模式** | **四方评审一致** |
| **L18** | **Delivery Gate 双层化——Hard Gate（程序化）+ Soft Gate（LLM-as-Judge）** | **四方评审一致** |
| **L19** | **Spec Lock 判断用领域无关元准则 (a)(b)(c)，不用金融参数列表** | **Sonnet 评审** |
| **L20** | **知识的 Actionability 决定它该内联还是放 references/——"需谨慎"≠"用复合键 ['id','updated_at']"** | **Sonnet 评审** |
| **L21** | **晶体必须经过效能验证（A/B 对照）——覆盖率达标不等于有效，必须证明"有晶体比没有晶体好"** | **CEO 审查：v1.0 首测 6% 覆盖率仍通过 = 晶体可能没起作用** |

---

*SOP v1.3 | 2026-04-06 | Doramagic CTO + CEO 联合制定*
*基于：v1.2 + 四方评审 7 项改进 + Step 9 效能验证*
*宿主规范：`docs/research/host-specs/openclaw-host-spec.md` + `docs/research/host-specs/claude-code-host-spec.md`*
