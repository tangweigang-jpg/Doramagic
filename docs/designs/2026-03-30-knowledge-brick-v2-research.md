# 知识积木 v2 体系调研综合报告
日期: 2026-03-30
执行者: Claude Code opus + 10 个 sonnet 子代理并行调研

## 调研范围

10 个方向，围绕三个原则：技术先进性、普适性、AI 智能性和适配性。

---

## 一、核心结论（从 10 份报告中提炼）

### 1. 积木的四层架构（来自 AI 原生知识表示调研）

```
Layer 1: 存储层 — JSON-LD + 自定义扩展（积木身份证）
Layer 2: 检索层 — Embedding + Qdrant Hybrid Search（语义+关键词+Reranker）
Layer 3: 调用层 — MCP inputSchema 格式（LLM 原生理解）
Layer 4: 生成层 — 模板骨架 + LLM 填充（混合生成）
```

### 2. 积木格式的跨领域启发（来自配方数据库调研）

从烹饪菜谱、硬件配置、药物配方、代码脚手架、基础设施即代码 5 个领域提炼出 7 个共性维度：

| 维度 | 在积木中的体现 |
|------|--------------|
| 标识 | id + name + version |
| 输入（参数） | Terraform 式 Input 类型声明（type + required + default + validation） |
| 工具/依赖 | requires 前置积木、conflicts_with 互斥积木 |
| 步骤/过程 | how_it_works 步骤描述 |
| 约束/兼容性 | PCPartPicker 式显式约束层 |
| 输出/产出 | Output 类型标签（用于自动组合兼容检查） |
| 元数据 | category, tags, version, common_failures |

### 3. 组合机制（来自能力组合调研）

**三层分离架构**：
- **执行层**：函数组合模式（每个积木 = async function(ctx) → ctx）
- **定义层**：YAML 声明式（Trigger-Condition-Action 结构）
- **编排层**：自实现轻量 StateGraph（50-100 行，不引入 LangGraph/Airflow）

### 4. 代码生成策略（来自代码生成调研）

**推荐：模板骨架 + LLM 填充 + 沙箱验证循环**
- 固定结构（imports、签名、错误处理）用 Jinja 模板
- 业务逻辑由 LLM 基于积木约束生成
- 生成后 subprocess 沙箱执行，traceback 反馈重试（最多 3 次）
- **不建议**设计新 DSL，推荐"受约束 Python API 库"（积木 SDK 化）

### 5. 个性化机制（来自个性化引擎调研）

**三阶段推进**：
- Phase 1（立即可做）：对话后 LLM 自动提炼用户画像 JSON，下次注入 system prompt
- Phase 2：三段式澄清决策 + PAMU 双轨记忆（短期+长期）
- Phase 3：PAHF 完整闭环（行动前澄清 + 行动后反馈 → 记忆更新）

### 6. 自进化机制（来自自进化知识系统调研）

**三飞轮**：
- 飞轮 1：使用反馈 → 质量优化（LLM-as-Judge 自动评分）
- 飞轮 2：外部信号 → 新知识采集（HN/GitHub/ProductHunt 每日扫描）
- 飞轮 3：时间衰减 → 知识淘汰（健康分 = 调用率 × 成功率 × 社区活跃度）

**P0 立即可做**：使用行为埋点（零命中/低点击率）+ LLM-as-Judge 积木质量自动评分

### 7. LLM 工具标准对齐（来自 LLM 工具定义调研）

**部分对齐，不完全复制**：
- 对齐 name + description（所有平台最小公约数）
- 参数用 MCP inputSchema（最广兼容，支持 anyOf/$ref）
- 保留 Doramagic 特有字段（knowledge_type, signal, evidence_refs）
- 不强制 strict 模式（积木要向前兼容）

### 8. 市场现状（来自 skill/agent 市场调研）

- 市场已有 35 万+ skills，**80% 是 AI 垃圾**
- 用户要的是"少一点能力，多一点可靠性"
- GPT Store 95% 消亡率
- **机会空白：缺少可信的、有深度的、垂直领域知识单元**
- **不要做工作流平台**（Dify/n8n 已饱和），做"可信知识的源头供应商"

### 9. 现有积木可复用性（来自积木评估）

- **21 个 HIGH**（直接可用）：skill_architecture, langchain, fastapi_flask, financial_trading 等
- **22 个 MEDIUM**（部分可用）
- **7 个 LOW**（需重建）
- 核心问题：`rationale` 类占比过高（60%+），编译器需要的是约束性、模板性、否定性知识

### 10. 现有方案对比（来自 skill/workflow 结构调研）

**最佳参考：Anthropic SKILL.md 语义触发 + Apify input_schema 参数化**

---

## 二、新积木格式设计草案

综合 10 份调研，推荐以下格式：

```yaml
# === 标识层 ===
id: "stock-price-alert-v1"
name: "股票价格提醒"
version: "1.0.0"
category: ["金融", "监控"]
tags: ["股票", "A股", "价格提醒", "定时任务"]

# === 核心能力（FHIR isActive 启发）===
core_capability: "监控 A 股股票实时价格，当涨跌幅超过设定阈值时通过 Telegram 发送提醒"
supporting_infrastructure: ["akshare（A股数据）", "Telegram Bot API"]

# === 输入声明（Terraform variable 启发）===
inputs:
  ticker:
    type: string
    required: true
    description: "股票代码，如 600519"
    validation: "len(value) == 6 and value.isdigit()"
  stock_name:
    type: string
    required: true
    description: "股票名称，如 贵州茅台"
  threshold_pct:
    type: float
    required: false
    default: 5.0
    description: "触发提醒的涨跌幅百分比"
  direction:
    type: enum
    values: ["up", "down", "both"]
    default: "both"
  interval_min:
    type: integer
    default: 5
    validation: "value >= 1"

# === 输出声明 ===
outputs:
  alert_message:
    type: text
    description: "发送给用户的提醒消息"
  current_price:
    type: float

# === 兼容性约束（PCPartPicker 启发）===
constraints:
  requires: []
  conflicts_with: []
  compatible_with: ["telegram-notifier", "daily-summary-formatter"]

# === 能力类型（Trigger-Condition-Action 结构）===
capability_type: "poll"      # poll | filter | notify | transform
data_source: "stock_api"     # stock_api | gmail | rss | github | webhook

# === 钩子（Cookiecutter 启发）===
pre_conditions:
  - "akshare 库已安装（pip install akshare）"
  - "网络可访问 eastmoney push API"
post_conditions:
  - "返回的 current_price > 0"

# === 已知失败模式（核心竞争力）===
common_failures:
  - severity: HIGH
    pattern: "交易所 API 限流（5 req/min）"
    mitigation: "内置指数退避，最少间隔 60s"
  - severity: MEDIUM
    pattern: "非交易时间段无数据"
    mitigation: "检测交易时段（9:30-11:30, 13:00-15:00），非交易时段降低轮询频率"
  - severity: LOW
    pattern: "股票停牌时价格不更新"
    mitigation: "检测涨跌幅为 0 且成交量为 0 的情况，跳过提醒"

# === 代码模板引用 ===
template_ref: "templates/poll-stock.py.tmpl"

# === 调用接口（MCP inputSchema 格式，LLM 原生理解）===
mcp_tool_definition:
  name: "stock_price_alert"
  description: "监控 A 股股票价格，涨跌幅超过阈值时发送 Telegram 提醒。适用于需要实时盯盘的场景。"
  inputSchema:
    type: object
    properties:
      ticker: { type: string, description: "6位股票代码" }
      threshold_pct: { type: number, default: 5.0 }
      direction: { type: string, enum: ["up", "down", "both"] }
    required: ["ticker"]

# === 元数据 ===
source: "manual"             # manual | auto-extracted | community
freshness_date: "2026-03-30"
evidence_refs:
  - "https://github.com/akfamily/akshare"
  - "15 个 financial_trading 积木的失败模式分析"
```

---

## 三、与现有积木格式的对比

| 维度 | 现有格式（v1） | 新格式（v2） |
|------|--------------|-------------|
| 本质 | 知识陈述（"React 应该这样设计"） | 能力配方（"如何构建股票提醒工具"） |
| 输入定义 | 无 | Terraform 式类型声明 |
| 输出定义 | 无 | 类型标签（用于自动组合检查） |
| 失败模式 | knowledge_type: failure（文本描述） | 结构化 severity + pattern + mitigation |
| 组合支持 | 无 | requires/conflicts_with/compatible_with |
| LLM 可调用 | 需要 brick_injection.py 转换 | mcp_tool_definition 直接注入 |
| 代码生成 | 无 | template_ref 指向代码模板 |
| 个性化 | 无 | inputs 的 default 可按用户画像调整 |

---

## 四、实施路线图

### 阶段 0：格式验证（1-2 天）
- 用新格式手写 3 个积木（stock_alert, rss_monitor, telegram_notifier）
- 验证 LLM 能否基于新格式生成可运行代码
- 验证积木间的自动组合兼容检查

### 阶段 1：核心引擎（3-5 天）
- 实现 YAML 积木解析器
- 实现轻量 StateGraph 执行器（50-100 行）
- 实现模板骨架 + LLM 填充的代码生成管道
- 实现 subprocess 沙箱验证

### 阶段 2：积木库迁移（3-5 天）
- 从 21 个 HIGH 评级文件中迁移有价值的失败模式到新格式
- 新增用户场景积木（金融、办公、学习、生活）
- 实现 Qdrant Hybrid Search 检索层

### 阶段 3：个性化 + 自进化（持续）
- 用户画像自动提炼
- 使用行为埋点
- LLM-as-Judge 积木质量自动评分
- HN/GitHub 每日扫描自动采集

---

## 五、调研来源索引

10 份调研报告的完整内容保存在各子代理的输出文件中。关键来源包括：

- Microsoft GraphRAG、HybridRAG（NVIDIA/BlackRock）
- Anthropic MCP 规范 v2025-11-25
- Schema.org Recipe、Cooklang DSL、FHIR MedicationKnowledge
- Terraform modules、Pulumi ComponentResource
- PCPartPicker 兼容性系统
- iEcoreGen（模板+LLM 混合，pass@1 提升 29%）
- PAHF（Meta AI，2026.2）、PAMU（2025.10）个性化框架
- SkillsMP（66,500+ skills）、Skills.sh（83,627 skills）市场数据
- RLAIF-V（CVPR 2025）、LLM-as-Judge 评估框架
