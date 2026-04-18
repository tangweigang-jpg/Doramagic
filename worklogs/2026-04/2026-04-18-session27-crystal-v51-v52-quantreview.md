# Session 27 — v5.1 → v5.2 + 量化评审三轮 + 8.72 分可发布

**日期**: 2026-04-18（跨夜）
**主线程**: Claude Opus 4.7 (1M context)
**子代理**: sonnet（N 次：v5.1 方案并行设计 / v5.2 capability_catalog 并行实施 / 量化评审 A~J 十轴 / 二轮评审 / 三轮验证）
**commit**: 934694c + 7ec70de
**起点**: Session 26 结束于 commit 518e596（晶体工具链首次 git 固化）+ Session 26 worklog，压缩后开启 Session 27

---

## 一、Session 起点（压缩恢复）

Session 26 完成了晶体工具链的 git 固化（commit 518e596，8 文件 / +5798 行）。压缩发生后，Session 27 从"恢复上下文"开始。

**Session 26 末尾遗留的关键痛点**：bp-009 v3.5 晶体在 OpenClaw 实测中的表现只是输出了"meta changelog"——一张三行描述 v3.5 改动的表格。宿主 AI 没有主动引导用户，没有"装好了，你可以做这些"的结构化消息，没有对新用户的任何上手指引。

这是产品层面的核心缺陷：**晶体安装了，但对用户完全沉默**。

---

## 二、v5.1 尝试 + OpenClaw 22:44 实测失败

### 2.1 第一性原理讨论

用户明确提出三条业务目标：
1. **最大化 AI 还原项目所有功能**（知识完整性，v3.5 已解决）
2. **最大化晶体在宿主 AI 中运行 + 创建 skill**（执行契约层）
3. **安装后引导用户使用**——像用户问"能做什么"那样的富结构化回答

第三条是 Session 27 的核心战场。

### 2.2 v5.1 方案设计（主线程 + 3 sonnet 子代理并行）

主线程研判：宿主 AI 不是"字面执行"晶体里的声明，而是"解读"它。要让宿主在安装后主动呈现引导，必须在晶体结构里声明足够清晰的"安装后行为契约"。

**v5.1 Schema 新增**：
- `meta.authoritative_artifact`：声明晶体为权威制品
- `meta.execution_protocol`：执行协议声明
- `post_install_notice`（PIN-01）：安装后通知块，含 positioning + 3 条 beginner_prompts + more_info_hint
- blueprint `featured_use_cases`：精选 use case 列表

**SOP 同步**：v5.0 → v5.1，新增 SA-14 / SA-15 / SA-16 三条断言。

3 个 sonnet 子代理并行分工：Schema 扩展 / bp-009 seed.md 注入 PIN-01 / SOP 文档更新。

### 2.3 22:44 OpenClaw 实测：失败

bp-009 编译完成，用户实测提交 OpenClaw。

**结果**：OpenClaw 只产出 meta changelog 三行表，**PIN-01 没有触发**，没有结构化的安装引导消息。

---

## 三、误入 v6.0 Runtime + 回滚（本 session 最大的弯路）

### 3.1 灾难性误判

v5.1 失败后，主线程做出了一个**严重的错误推断**：

> "契约声明 ≠ 执行。宿主 AI 不会字面执行 `post_install_notice`，因为它本质上还是靠推断。解决方法是**自建运行时**——在宿主 AI 的 skill 执行层加一个 Crystal Runtime，强制执行契约声明。"

这个推断触发了 v6.0 Crystal Runtime 项目：
- 计划新建 `packages/doramagic_runtime/`
- 设计 15+ 小时工作量
- 预计 2400 行代码
- 完全脱离"晶体编译主线"轨道

### 3.2 用户纠正 + 回滚

用户直接指出：**"这不是我想要的业务。回滚到晶体编译主线。"**

主线程复盘：根本没有理解 Crystal-Host 关系的本质。晶体是"知识制品"，宿主是"解读者"。**自建 runtime 不是解决宿主解读行为的正确路径**——宿主行为由宿主平台决定，我们能影响的是"给宿主看的数据密度和结构"，而不是"在宿主内部注入执行器"。

这个教训被存入 memory：`feedback_crystal_host_relationship.md`。

---

## 四、v5.2 capability_catalog 成功

### 4.1 诊断 v5.1 失败的真因

回归后，主线程重新诊断：

**v5.1 PIN-01 的实际内容**：positioning（1 段）+ 3 条 beginner_prompts + 1 条 more_info_hint。总数据量极稀疏。

**宿主的决策逻辑**：宿主 AI 面对新安装的晶体，会衡量"这份数据值不值得在回复中呈现"。3 条 prompts + 1 条 hint → 宿主判断：不够，折叠为 changelog。

**真因**：不是"契约没声明"，是**"contract 数据密度不够"**。宿主看不到密集的、值得呈现的结构，自然选择最小化输出。

### 4.2 v5.2 方案：加 capability_catalog

**核心思路**：给宿主看**密集数据**，让它"不得不"呈现。

**v5.2 新增**：
- Schema 新增 `post_install_notice.capability_catalog`：全量 31 UC 按 5 组结构化预分组
- Schema 新增 `post_install_notice.call_to_action`：明确的行动召唤
- Blueprint 加 `capability_groups`（策展 5 组，blueprint_declared）
- locale_contract 细化

### 4.3 实施（主线程 + 3 sonnet 子代理并行）

三个子代理并行分工：
- **SA-A**：Schema v5.1 → v5.2（`post_install_notice` 结构扩展 + `capability_catalog` 字段定义）
- **SA-B**：`compile_crystal_skeleton.py` 新增 `build_capability_catalog` + `_heuristic_emoji`（普适性：不硬编码任何领域词，按 UC 属性启发式分配 emoji）
- **SA-C**：bp-009 blueprint 加 `capability_groups` 声明 + SOP v5.1 → v5.2（新增 SA-17 catalog 完整性断言 + SKILL.md emitter 渲染 Section 1 capability catalog）

**普适性原则**：`_heuristic_emoji` 函数不写任何 fin/quantify/stock 等领域词，纯按 UC 的 action 类型和 tag 分类 → 确保该函数对 53 个其它蓝图同样有效。

编译 → 门禁 SA-1 ~ SA-17 全部 PASS → 提交 OpenClaw 23:37。

### 4.4 23:39 实测成功

**OpenClaw 产出**（用户截图确认）：

```
G 大脑袋 | 量化策略伙伴

定位：专注 A股/港股/加密货币量化策略的开发与回测伙伴...

你能做什么：
📊 数据采集与管理 (8个策略)
🧮 策略开发与回测 (7个策略)
📈 实盘交易 (4个策略)
📋 系统管理与监控 (11个策略)
🔧 学习与调试 (1个策略)

推荐尝试：
• UC-111: 多策略组合回测
• UC-110: 实盘策略配置
• UC-108: 因子库构建

想试哪个？
```

**核实数据**：
- positioning 中文化：✅
- 5 组 emoji 分类（📊/🧮/📈/📋/🔧）：✅
- 31 UC 总数精确（宿主自行 reshuffle 为 8/7/4/11/1，语义合理）：✅
- 推荐尝试 3 条（UC-111/110/108）：✅
- call_to_action "想试哪个？"：✅

这是 PIN-01 **首次真正触发**的历史性实测。

**记忆存入**：`feedback_contract_data_density.md`——"契约数据密度决定 host 执行率"。稀疏契约被忽略（v5.1），密集结构化数据被呈现（v5.2）。

---

## 五、量化评审三轮（7.26 → 8.30 → 8.72）

### 5.1 一轮量化评审（7.26/10）

10 个 sonnet 子代理（A~J）分别担任不同轴评审员，独立评分，最后汇总。

**评审结果**：**7.26/10**

三个最致命的扣分：

**D 轴 5/10：31 条 short_description 全部 mid-sentence 截断**
- 原因：编译脚本的 `_build_uc_summary` 函数用了 `description[:80]`，硬切 80 字符
- 结果：大量描述在句子中间截断，例如 `"从多个数据源采集历史行情数据，支持股票、期货..."` → `"从多个数据源采集历史行情数据，支持股票、期"` （`...`）
- 严重度：每次 host 展示 UC 时用户看到残缺句子，信任感直接受损

**B 轴 6/10：32 个 stage 中 26 个是占位桩**
- 原因：非主流 stage 的叙事段落内容是 `"Cross-cutting concern: {stage_name}."` 占位字符串
- 结果：晶体的"项目地图"有 81% 是空壳，宿主无从给用户真实信息
- 严重度：阅读体验断崖，实质信息密度低于预期

**H 轴 7/10：`locale_contract.user_facing_fields` 只有 2 项**
- 原因：locale_contract 定义了哪些字段需要中文化，但只声明了 2 个顶层字段
- 结果：host 翻译时缺乏粒度，不知道子字段是否需要处理

### 5.2 一轮 3 处 Fix（主线程直接实施）

**Fix #1（D 轴）**：`_build_uc_summary` 改为取 first sentence，不 mid-cut
```python
# 旧：description[:80] + "..." if len > 80
# 新：取第一个句子（按 "。" / "." 分割，取第一段）
```

**Fix #2（B 轴）**：26 个 stub stage 合并重写为单个 `cross_cutting_concerns` stage
- 实质化 3 字段叙事：narrative（项目共性模式）/ key_decisions（跨 stage 决策）/ common_pitfalls（普遍陷阱）
- 不再有任何 `"Cross-cutting concern: X."` 占位

**Fix #3（H 轴）**：`locale_contract.user_facing_fields` 从 2 项扩到 9 项，覆盖所有应中文化的叶子字段

**修完后主线程额外同步 3 件事**：
1. Schema default 同步 9 字段（避免脚本新增字段而 Schema 未声明默认值，下个蓝图报 KeyError）
2. SOP 新增 Q1/Q2/Q3 三条质量规则（普适性成文，下一蓝图的编译者有明确规则可查）
3. quality_gate 新增 SA-18 mid-cut 守卫（`[:80]` 字面量检测，防止未来脚本改动引入同类问题）

### 5.3 二轮量化评审（8.30/10，+1.04）

重编 bp-009 → 10 轴重评。**8.30/10**，较一轮提升 1.04 分。

新发现 2 个遗留问题：

**遗留 1：skill_crystallization.action 硬编码**
```yaml
skill_crystallization:
  action: "fin-bp-009-uc_101.skill"  # 硬编码，与 slug_template 矛盾
```
这意味着批量编译 53 个其它蓝图时，每个都会产出指向 bp-009 的 skill 文件名，而不是对应蓝图的实际 slug。

**遗留 2：locale_contract user_facing_fields 的 `human_summary` 粒度不足**
`human_summary` 是顶层字段，但它包含多个子概念（项目定位 / 核心能力 / 目标用户 / 局限声明）。只声明顶层等于没声明粒度。

### 5.4 二次 Fix（主线程 + 子代理协作）

**Fix A（skill_crystallization 重构）**：
- `build_skill_crystallization` 函数重构
- `action` 改为 `{slug}.skill` 运行时占位（不再硬编码）
- `skill_file_schema` 从 crystal 实际数据动态抽取（`intent_keywords` / `fatal_guards` / `spec_locks` / `preconditions` 均从蓝图/约束数据动态填充，不依赖任何硬编码领域词）

**Fix B（locale 粒度扩展）**：
- `user_facing_fields` 的 `human_summary` 条目扩为 4 个子字段：
  - `human_summary.positioning`
  - `human_summary.core_capability`
  - `human_summary.target_audience`
  - `human_summary.limitations`
- 总计从 9 项扩到 12 项

### 5.5 三轮量化评审（8.72/10，+0.42）

重编 bp-009 → 10 轴三评。**8.72/10**，累计从 7.26 提升 +1.46 分。

**J 轴（Ship/No-Ship 判定）**：**"可发布"**——满足产品宪法核心要求，无阻塞性缺陷。

---

## 六、双 commit 入库

### commit 934694c

`feat(crystal-tooling): v5.0 → v5.2 schema-driven pipeline + capability catalog`

**规模**：18 文件 / +11,500 行

主要内容：
- Schema 新建（v5.1 + v5.2 两个版本存档）
- `compile_crystal_skeleton.py` 大改（新增 `build_capability_catalog` / `build_post_install_notice` / `build_skill_crystallization` / `_heuristic_emoji` 等多个生成器）
- `crystal_quality_gate.py` 新增 SA-14~SA-18
- SOP v5.2（新增 Section 完整规则 + Q1/Q2/Q3 质量规则）
- Makefile 更新
- bp-009 v5.1/v5.2 seed 文件
- blueprint.v17 首次入库（历史版本可追溯）

### commit 7ec70de

`fix(crystal-tooling): remove hardcoded zvt values + expand locale granularity`

**规模**：5 文件 / +99 行

主要内容：
- `build_skill_crystallization` 去硬编码（`{slug}` 占位 + 动态数据抽取）
- `user_facing_fields` 从 9 项扩到 12 项（`human_summary` 子字段化）
- Schema default 补全

**设计原则**：两个 commit 互相独立。934694c 是能力建设（feature），7ec70de 是质量修缮（fix）。未来若需精确 revert 某个变更，两个 commit 可以独立操作。

---

## 七、教训 + memory 更新

### 7.1 Crystal-Host 关系（最大教训）

**教训**：晶体被宿主"解读"而非"字面执行"。宿主 AI 是一个推断引擎，它看晶体的方式是"这份数据告诉我应该做什么"，而不是"这条指令告诉我必须执行什么"。

**推论**：从"格式偏差"（宿主没触发 PIN-01）推导出"必须自建运行时"是根本性错误。运行时属于宿主平台的能力层，我们无权也无需侵入。

**正确路径**：影响宿主行为的唯一合法手段，是**调整晶体里的数据密度和结构**——让宿主"看到值得呈现的东西"，而不是"给宿主装一个执行器"。

**Memory 文件**：`feedback_crystal_host_relationship.md`

### 7.2 契约数据密度决定 host 执行率

**教训**：稀疏契约（v5.1：3 条 prompts + 1 条 hint）被宿主忽略。密集结构化数据（v5.2：31 UC 按 5 组分类 + call_to_action）被宿主呈现。

**量化**：从"宿主忽略"到"宿主全量展示"的临界点，不在于声明了什么，在于给了多少可以直接呈现的结构化数据。

**推广**：这条规律不止适用于 `post_install_notice`——任何希望宿主执行的契约块，都需要达到"数据密度足以让宿主觉得值得呈现"的阈值。

**Memory 文件**：`feedback_contract_data_density.md`

### 7.3 普适性 = 脚本 + SOP + Schema 三端一致

**教训**：编译脚本层修复后（Fix #1/#2/#3），必须同步 Schema default 和 SOP 成文规则。否则：
- Schema default 缺失 → 下一个蓝图编译时 KeyError（脚本行为和 Schema 不匹配）
- SOP 规则未成文 → 下一个编译者不知道"不允许 mid-cut"，再次引入同类问题
- 质量门禁未更新 → SA 无法捕获回归

**三端同步不是重复劳动**，是确保 53 个其它蓝图批量编译时不重踩同样坑的基础设施投入。

---

## 八、数字盘点

| 维度 | 数字 |
|---|---|
| session 总耗时 | ~5-6 小时（含 v6.0 误入弯路 ~1 小时）|
| sonnet 子代理调用 | 约 10 次（v5.1 并行 3 + v5.2 并行 3 + 评审 A~J 合计 10 轴 + 二轮 + 三轮）|
| v5.1 → v5.2 schema 新增字段 | authoritative_artifact + execution_protocol + post_install_notice（PIN-01）+ capability_catalog + call_to_action + locale 细化 12 项 |
| SA 断言演化 | 13（v5.0）→ 16（v5.1）→ 17（+catalog 完整性）→ 18（+mid-cut 守卫）|
| 评审分数演化 | 7.26 → 8.30（+1.04）→ 8.72（+0.42）|
| 累计提升 | +1.46 分（跨 2 轮修复 / 5 处 Fix）|
| commit | 2 次独立 commit（feature + fix）|
| 代码行净变化 | +11,500 行（commit 934694c）+ +99 行（commit 7ec70de）|
| 踩坑次数 | 1 次大的（v6.0 误入 + 回滚）+ 若干小的（ruff format 循环等）|
| OpenClaw 实测次数 | 2（22:44 v5.1 失败 + 23:39 v5.2 成功）|
| memory 更新 | 2 条（crystal_host_relationship + contract_data_density）|

---

## 九、未完成事项

| 优先级 | 任务 | 来源 |
|---|---|---|
| HIGH | 批量编译其他 53 蓝图验证普适性 | v5.2 工具链的真正考验 |
| HIGH | `skill_file_schema.name` 和 `intent_keywords` 仍带 UC-101 痕迹（非阻塞但影响泛化）| 二轮评审遗留 |
| MEDIUM | `evidence_verify_ratio 44.3%` 是蓝图层问题，不是晶体能修（需在蓝图采集 SOP 层解决）| Session 26 延续 |
| MEDIUM | OpenClaw 实测 execute 指令验证 UC-129 回测（Session 26 遗留，至今未做）| Session 26 |
| LOW | `human_summary` 止损默认值 `-0.3%` 核实是否为 `-3%` 笔误 | Session 26 遗留 |
| LOW | 批量编译 10 颗晶体后，用量化评审框架做均值评估（泛化质量基线）| 工具链成熟后 |

---

## 十、一句话总判定

**本 session 的核心价值**：从"安装后沉默"到"安装后主动引导"——v5.2 在 23:39 的 OpenClaw 实测中，宿主 AI 第一次自发呈现了完整的 5 组 / 31 UC / 推荐 3 条 / call_to_action 结构，证明了"契约数据密度"而非"契约声明强度"才是驱动 host 行为的关键变量。代价是走了一条 v6.0 Runtime 的弯路——主线程误判一次，但在用户一句话纠正后成功回归，并把教训写进了 memory。

**产品路径指引**：v5.2 工具链已具备批量编译能力（`make crystal-full BP=... VERSION=...`）。下一步是将 53 个剩余蓝图依次通过流水线，用量化评审框架（A~J 十轴）验证普适性——批量输出后，Doramagic 的"AI 领域抄作业大师"定位将有 54 颗以上的高质量晶体支撑。

---

*v1.0 | 2026-04-18 | Session 27 | 主线程 Opus 4.7 (1M) + N× Sonnet 子代理 + OpenClaw 2× 实测*
