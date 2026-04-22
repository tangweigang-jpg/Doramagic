# Judgment System 调优指南

> 本文档面向使用 Claude Code CLI 对 judgment-system 各模块进行迭代改进的操作者。
> 每个参数标注了所在文件、当前值、调优方向和观测指标。

---

## 调优原则

1. **单变量原则**：每次只改一个参数，对比改动前后的效果
2. **先粗后细**：先调对结果影响最大的参数（prompt > 权重 > 阈值），再调细粒度参数
3. **数据驱动**：每次调优跑同一批 Issue（建议 50~100 条），记录通过率和判断质量
4. **不可只调不测**：改完参数后必须跑 `make check` + 至少一次真实数据验收

---

## 一、LLM 参数（影响最大）

### 1.1 模型选择

| 参数位置 | 当前值 | 可选值 | 影响 |
|----------|--------|--------|------|
| `classifier.py` → `classify_record(model=)` | `"sonnet"` | `"sonnet"` / `"opus"` | Sonnet 作为分类基线，准确度足够。Opus 在边界案例（workaround vs anti_pattern 区分）上更好，但成本 5x |
| `extractor.py` → `extract_judgments(model=)` | `"sonnet"` | `"sonnet"` / `"opus"` | 核心提取环节，Sonnet 是性价比最优。Opus 提取质量更高但成本 5x，建议只在金融等高价值领域用 Opus |
| `linker.py` → `auto_link(model=)` | `"sonnet"` | `"sonnet"` / `"opus"` | Sonnet 足以识别判断间关系。Opus 在 subsumes/supersedes 这类微妙关系上判断更准 |

**调优方法**：

```bash
# 切换模型只需改调用参数，不改代码逻辑
# 在 scripts/harvest.py 或 pipeline.py 中修改 model 参数
```

**观测指标**：
- 分类准确率：人工抽查 20 条，统计分类正确率
- 提取通过率：`extracted / filtered_in` 的比例（目标 > 40%）
- 关系有效率：人工抽查关系，统计合理比例（目标 > 70%）

### 1.2 Temperature

| 参数位置 | 当前值 | 调优范围 |
|----------|--------|----------|
| `classifier.py` → `adapter.chat(temperature=)` | `0.0` | `0.0`（不要动） |
| `extractor.py` → `adapter.chat(temperature=)` | `0.0` | `0.0 ~ 0.3` |
| `linker.py` → `adapter.chat(temperature=)` | `0.0` | `0.0`（不要动） |

**调优逻辑**：
- 分类和关系建立必须 `0.0`，确保确定性输出
- 提取器可以尝试 `0.1 ~ 0.3`：更高的 temperature 会让 LLM 从同一条 Issue 中发现更多非显性判断，但也会增加幻觉风险
- **不要超过 0.3**，否则输出格式稳定性急剧下降

### 1.3 Max Tokens

| 参数位置 | 当前值 | 调优逻辑 |
|----------|--------|----------|
| `classifier.py` → `max_tokens=` | `200` | 分类只输出一个 JSON 对象，200 足够。不需要调 |
| `extractor.py` → `max_tokens=` | `3000` | 如果发现 JSON 数组被截断（解析失败率高），增加到 `4000`。但注意成本线性增长 |
| `linker.py` → `max_tokens=` | `500` | 如果关系数量超过 5 个开始被截断，增加到 `800` |

---

## 二、Prompt 模板（影响第二大）

### 2.1 EXTRACTION_SYSTEM_PROMPT

**文件**：`packages/judgment_pipeline/doramagic_judgment_pipeline/extract/extractor.py`

**可调部分及效果**：

| 可调区域 | 当前内容 | 调优方向 |
|----------|----------|----------|
| 约束第 1 条 "条件必须具体" | 禁止"开发时" | 如果提取率过低（大量判断被 validator 拒绝），可以适当放宽，改为"不能是单个词" |
| 约束第 6 条 模糊词黑名单 | 注意、考虑、适当、合理、尽量、可能需要 | 如果中文判断通过率太低，减少黑名单词（先移除"建议"和"参考"） |
| `consequence_kind` 枚举 | 9 个值 | 扩充新领域时增加。例如做 DevOps 领域可以加 `deployment_failure` |
| `crystal_section` 选择指南 | 6 行说明 | 如果发现 LLM 总是选 `constraints`，说明指南不够清晰，需要加每个 section 的正反例 |
| "最多提取 5 颗判断" | 5 | 调高到 8-10 可以提高单条 Issue 的产出，但低质量判断也会增多 |

### 2.2 EXTRACTION_FEW_SHOT

**调优方法**：这是最高杠杆的调优点——增加真实的正反样例。

```
当前：1 个正例 + 1 个反例
推荐：3 个正例 + 2 个反例（覆盖不同 layer、不同 severity）
```

**操作**：从实际提取结果中挑选最好的 3 个判断作为正例，最常见的 2 种失败模式作为反例，追加到 `EXTRACTION_FEW_SHOT` 字符串中。

**注意**：few-shot 不要超过 5 对，否则 prompt 过长会挤占 Issue 内容的 token 空间。

### 2.3 CLASSIFICATION_SYSTEM_PROMPT

**文件**：`packages/judgment_pipeline/doramagic_judgment_pipeline/extract/classifier.py`

| 可调区域 | 调优方向 |
|----------|----------|
| 6 个分类类别 | 扩充新领域时可能需要加新类别。注意：改了这里必须同步改 `VALID_CATEGORIES` 集合 |
| 各类别的定义文本 | 如果 `workaround` 和 `anti_pattern` 经常混淆，需要加更精确的区分标准 |
| "你只需要返回一个 JSON 对象" | 如果 LLM 仍然输出多余文字，加强为"你的全部回复必须是且仅是一个 JSON 对象，不要任何前缀、解释或 markdown 格式" |

### 2.4 LINKER_SYSTEM_PROMPT

**文件**：`packages/judgment_pipeline/doramagic_judgment_pipeline/store/linker.py`

| 可调区域 | 调优方向 |
|----------|----------|
| 6 种关系类型 | `supersedes` 和 `subsumes` 容易被滥用。如果关系图噪声太多，先删掉这两个，只保留前四种 |
| `max_candidates` | 当前 20。候选太多会让 prompt 超长且 LLM 出错率上升。对小知识库（<100 判断）可降到 10 |
| "不要强行建立关系" | 如果关系数量仍然过多，加上"平均每颗新判断应该只有 0~2 个关系，超过 3 个大概率是你在过度连边" |

---

## 三、过滤器参数（影响第三大）

### 3.1 信号权重

**文件**：`packages/judgment_pipeline/doramagic_judgment_pipeline/extract/filter.py` → `_compute_signal_score()`

| 信号 | 当前权重 | 调高场景 | 调低场景 |
|------|----------|----------|----------|
| `has_repro_steps` | +2.5 | — | 如果低质量重现步骤也大量通过 |
| `expert_reply` | +2.0 | 如果专家回复的 Issue 被大量漏掉 | — |
| `has_logs_or_evidence` | +1.5 | — | 如果仅仅贴了一段无意义的 stack trace 也通过了 |
| `bug/regression/incident` 标签 | +1.5 | — | — |
| `is_design_boundary` | +2.0 | — | 如果大量低价值 wontfix 通过 |
| `closed_by_maintainer` | +1.0 | 如果维护者闭环讨论被漏掉 | — |
| `approval_score >= 3` | +1.0 | — | 如果投票水分大的社区 |
| `reply_count >= 3` | +0.5 | — | — |
| `body_length >= 120` | +0.5 | — | — |
| `feature/enhancement` 无日志 | -1.5 | 如果 feature request 噪声太多 → -2.0 | 如果误杀有价值的 feature 讨论 → -1.0 |
| `question` 无重现步骤 | -1.5 | — | 如果 Q&A 类 Issue 中维护者给了好的回答 → -0.5 |

**调优方法**：

```bash
# 1. 导出某个仓库的全部 Issue（比如 100 条）
# 2. 跑一次 filter，记录每条的得分和通过/拒绝
# 3. 人工标注哪些被拒绝的 Issue 其实有价值（false negative）
# 4. 分析这些 false negative 的信号分布，针对性调权重
```

### 3.2 阈值

**文件**：`filter.py` → `_get_threshold()`

| 场景 | 当前阈值 | 调优方向 |
|------|----------|----------|
| bug/regression/incident 标签 | 3.0 | 基本不动。这类 Issue 质量天然高 |
| `pre_category == "bug"` | 3.0 | 同上 |
| workaround/anti_pattern | 3.0 | 可以适当提高到 3.5，如果这类判断噪声太多 |
| discussion 标签 | 3.5 | 如果讨论类 Issue 通过率太高且质量差 → 提到 4.0 |
| 默认 | 4.5 | 这是最敏感的旋钮。调到 4.0 会大幅增加通过量（+30%~50%），但低质量也会增多 |

**观测指标**：
- 通过率 = `filtered_in / fetched`（目标 20-40%，太低说明阈值太严，太高说明太松）
- 后续提取成功率 = `extracted / filtered_in`（如果通过率高但提取成功率低，说明过滤器放了太多垃圾）

### 3.3 Track 1 门槛

**文件**：`filter.py` → Track 1 代码块

当前 Track 1 要求 `has_code_fix` + 至少一个技术失败信号。如果发现过多 typo/doc 类修复被收录：

```python
# 加更严格的条件
has_failure_signal = (
    labels & {"bug", "regression", "incident", "data-issue"}
    or (signals.get("has_repro_steps") and signals.get("has_logs_or_evidence"))  # 两个同时满足
    or signals.get("body_length", 0) >= 200  # 提高 body 长度要求
)
```

---

## 四、Validator 参数

### 4.1 模糊词黑名单

**文件**：`packages/judgment_schema/doramagic_judgment_schema/validators.py`

```python
VAGUE_WORDS_ZH = ["注意", "考虑", "适当", "合理", "尽量", "可能需要", "建议", "参考"]
VAGUE_WORDS_EN = ["consider", "be careful", "try to", "might need", "possibly", "appropriate", "reasonable", "should consider"]
```

**调优逻辑**：
- 如果提取通过率太低（大量判断被 validator 拒绝），人工检查被拒判断，看哪些模糊词其实是合理用法。例如"参考"在"参考 API 文档的 rate limit 部分"中是合理的
- 可以改为更精确的匹配：不检查整个 action 字符串，只检查 action 的开头动词
- **新领域扩充时**：比如做医疗领域，"适当"可能是精确用法（"适当剂量"），需要从黑名单移除

### 4.2 原子性检测词

```python
NON_ATOMIC_MARKERS_ZH = ["以及", "同时", "并且", "此外", "另外"]
```

- 这些当前只产生 warning，不阻断。如果发现非原子判断太多，可以升级为 error
- 新增中英文标记词：`"另一方面"`, `"on the other hand"`, `"moreover"`

### 4.3 长度阈值

| 检查项 | 当前值 | 调优 |
|--------|--------|------|
| `core.when` 过长警告 | > 100 字符 | 如果中文 when 普遍较长，放宽到 150 |
| `core.action` 过短警告 | < 10 字符 | 合理，一般不调 |
| `Consequence.description` 最小长度 | 10（Pydantic Field） | 如果产生过多"后果未明确"的兜底，提高到 15 |

---

## 五、去重参数

### 5.1 Normalizer 词汇表

**文件**：`packages/judgment_schema/doramagic_judgment_schema/normalizer.py` → `VOCABULARY_MAP`

```python
VOCABULARY_MAP = {
    "float": "binary_float",
    "decimal": "exact_decimal",
    "yfinance": "yfinance_api",
    ...
}
```

**调优逻辑**：
- 新增领域时必须扩充词汇表。例如做 DevOps 领域：`"k8s": "kubernetes"`, `"docker": "container_runtime"`, `"CI": "continuous_integration"`
- 如果发现两个语义相同的判断没被去重，检查它们的关键词是否在词汇表中归一化到了同一个词
- **过度归一化风险**：`"收益"` 和 `"盈亏"` 被归到同一个词，但它们在交易和投资中语义不同。发现误合并时需要拆分词汇映射

### 5.2 去重灵敏度

**文件**：`packages/judgment_pipeline/doramagic_judgment_pipeline/refine/dedup.py`

当前去重只做"强重复"（精确 signature 匹配）。如果发现大量近似重复的判断通过了去重：

**升级路径**：
1. 先检查词汇表是否覆盖了造成"近似但未被匹配"的同义词
2. 如果词汇表已覆盖还是漏了，考虑加 "弱重复" 检测：同桶内 `rule_sig` 或 `cause_sig` 的编辑距离 < 3 也标记为疑似重复
3. 终极方案：加 LLM 辅助去重（给 LLM 两个判断让它判断是否语义重复），但成本高，建议只在候选数量 > 200 时启用

---

## 六、检索与编译参数

### 6.1 检索权重

**文件**：`packages/crystal_compiler/doramagic_crystal_compiler/retrieve.py`

| 来源 | 当前权重 | 调优 |
|------|----------|------|
| 直接匹配（domain 一致） | 1.0 | 不动 |
| Universal 判断 | 0.9 | 如果 universal 判断太多冲淡了领域特有判断 → 降到 0.7 |
| 图谱 1 跳扩展 | 0.8 | 如果扩展出来的判断不相关 → 降到 0.6。如果需要更深的关联 → 加 2 跳（权重 0.6） |

### 6.2 排序公式

当前排序：`weight × severity_order × confidence.score`

可调维度：
- 加入 freshness 惩罚：`volatile` 类判断降权 0.8，`stable` 保持 1.0
- 加入 evidence_refs 数量加权：证据越多越可信
- 加入 consensus 加权：`universal` 共识 > `strong` > `mixed` > `contested`

### 6.3 缺口检测

当前只检查三个 layer 是否有覆盖 + 判断总数 < 10。可以扩展：

- 检查 severity 分布：如果没有 fatal 级判断，可能遗漏了关键风险
- 检查 crystal_section 分布：如果全部是 constraints 没有 world_model，说明提取 prompt 或分类映射需要调优
- 检查 freshness 分布：如果全是 semi_stable 没有 volatile，可能缺少对最新版本变化的追踪

### 6.4 晶体模板

**文件**：`packages/crystal_compiler/doramagic_crystal_compiler/compiler.py` → `CRYSTAL_TEMPLATE`

模板的结构（硬约束 / 软约束 / 资源边界 / 缺口报告）是产品决策，一般不频繁调。但可以调的是：

- 硬约束的筛选条件：当前是 `severity in (fatal, high)` 且 `modality in (must, must_not)`。如果硬约束太多（>20 条），可以只保留 `fatal`
- 个性化提示的问题列表：根据领域不同定制（金融问资金规模、A股/美股；DevOps 问云平台、集群规模）
- 格式化风格：当前每条判断带 severity 标签和证据引用。如果用户反馈太冗长，可以改为纯规则列表

---

## 七、系统级参数

### 7.1 GitHub API 采集参数

**文件**：`packages/judgment_pipeline/doramagic_judgment_pipeline/source_adapters/github.py`

| 参数 | 影响 | 调优 |
|------|------|------|
| Issue 拉取数量（per_page） | 单次采集的 Issue 数 | 开始用 30-50 做验证，稳定后提高到 100 |
| 评论拉取深度 | 传给 LLM 的上下文量 | 当前取前 10 条。高活跃 Issue 可能有 50+ 条评论，取太少会丢信息。但取太多会超 token |
| Issue 状态过滤 | closed/open/all | 建议只采 closed（已有结论的讨论价值更高） |
| Issue 时间范围 | 采哪个时间段的 Issue | 建议从最近 2 年开始，太老的 Issue 可能已不适用 |

### 7.2 成本控制

每条 Issue 的 LLM 调用成本估算（以 Anthropic 2025 定价）：

| 环节 | 模型 | 输入 tokens | 输出 tokens | 单价（约） |
|------|------|------------|------------|-----------|
| 分类 | Sonnet | ~800 | ~50 | $0.003 |
| 提取 | Sonnet | ~3000 | ~500 | $0.012 |
| 关系 | Sonnet | ~1500 | ~200 | $0.006 |
| **合计/条** | | | | **~$0.021** |

**50 条 Issue ≈ $1.05，500 条 ≈ $10.5**

如果需要降成本：
1. 关系建立可以关闭（`auto_link` 不调用），省掉 ~$0.006/条，后续手动补
2. 减少采集数量或缩小仓库范围
3. 提高过滤器阈值，减少进入 LLM 环节的 Issue 数量

### 7.3 并发与速率

当前 pipeline 是串行的（逐条 Issue 处理）。如果需要加速：

- Anthropic API 默认 rate limit：Sonnet 60 RPM
- 串行处理 100 条 Issue 约需 15-20 分钟
- 可以改为异步并发（`asyncio.gather` + semaphore），但需注意 rate limit
- **建议 Sprint 1-3 完成后再考虑并发优化**，先确保串行流程正确

---

## 八、调优顺序建议

系统跑通后，按以下优先级调优：

```
第一轮：跑 30 条真实 Issue，人工审查结果
  ├── 如果通过率太低 → 调过滤器阈值（§三）
  ├── 如果提取质量差 → 调 EXTRACTION prompt + few-shot（§二）
  └── 如果大量重复 → 扩充 VOCABULARY_MAP（§五）

第二轮：跑 100 条，量化指标
  ├── 如果分类错误多 → 升级 classifier 到 Sonnet 或加 few-shot
  ├── 如果关系图太稀疏 → 调 linker prompt，放宽关系标准
  └── 如果关系图太密 → 减少关系类型到 4 种

第三轮：编译晶体，做用户测试
  ├── 如果晶体太长 → 收紧硬约束筛选条件
  ├── 如果晶体不聚焦 → 调检索权重和缺口检测
  └── 如果晶体缺少某类知识 → 回头调过滤器，放宽对应类别的阈值
```

---

## 九、参数变更记录模板

每次调优后在本文档末尾追加一条记录：

```markdown
### YYYY-MM-DD — 调优描述
- **改了什么**：filter.py 默认阈值从 4.5 → 4.0
- **为什么改**：人工审查发现 35% 的高价值 workaround Issue 被误杀
- **数据**：通过率从 18% → 27%，提取成功率从 45% → 42%（可接受的下降）
- **结论**：保留此改动
```

---

*最后更新：2026-04-03*
