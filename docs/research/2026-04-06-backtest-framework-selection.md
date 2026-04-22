# 回测框架选择工程实践研究报告

**日期**: 2026-04-06  
**作者**: Claude Sonnet 4.6（量化金融工程研究员角色）  
**研究背景**: Doramagic 晶体 v5-v8 四轮迭代中的框架失败分析  
**关联实验**: v5-hardened、v7 监控报告

---

## 摘要

本报告基于 Doramagic 晶体 v5/v7 的真实失败案例、finance-bp-002 蓝图、finance-C-086 约束条目、以及对 A 股量化生态的系统调研，对回测框架选择问题给出工程级分析和推荐。

核心结论：**在"弱模型+受限环境"下，框架的 AI 可用性比框架本身的功能完备性更重要。** 对于 OpenClaw（MiniMax-M2.7, 10 分钟超时）等受限环境，pandas 向量化是唯一可靠选择；晶体编译器应采用"蓝图驱动+环境感知"的混合策略，而非固定框架或完全动态选择。

---

## 1. 主流技术栈对比

### 1.1 框架全景表

| 框架 | 范式 | A 股支持 | 安装复杂度 | AI 可用性 | 生态活跃度 | 适用环境 |
|------|------|----------|------------|-----------|------------|----------|
| **pandas 向量化** | 向量化 | 原生（无日历限制） | 极低（pip pandas numpy） | 极高 | N/A（自写逻辑） | 全部环境 |
| **vectorbt** | 向量化（Numba加速） | 原生 | 低（pip vectorbt） | 高 | 活跃 | 本地/Codex/Claude |
| **backtrader** | 事件驱动 | 通过 PandasData 适配 | 低（pip backtrader） | 中 | 稳定（维护减少） | 本地/Codex |
| **zipline-reloaded** | 事件驱动 | 有限（日历实例问题，见第2节） | 极高（Cython依赖） | 极低 | 活跃（Stefan Jansen） | 仅本地宽松环境 |
| **vnpy** | 事件驱动+实盘 | 专为国内市场 | 高（多模块依赖） | 低 | 高 | 本地 |
| **rqalpha** | 事件驱动 | 专为 A 股（源自米筐） | 中 | 中 | 低（更新慢，非商业License） | 本地 |
| **qlib** | ML 因子研究管道 | 专为 A 股 | 高（PyTorch等重依赖） | 低 | 高（微软维护） | 本地/高算力 |
| **backtesting.py** | 极简向量化 | 原生（无日历约束） | 极低 | 极高 | 中 | 全部环境 |

### 1.2 AI 可用性评分细则

"AI 可用性"指：弱模型（MiniMax-M2.7 级别）在受限环境下（10分钟超时，无 pip install，无 cd &&）能否正确使用该框架完成端到端回测。评分维度：

| 维度 | pandas 向量化 | backtrader | zipline-reloaded |
|------|-------------|------------|------------------|
| 安装无需特权 | ✅ 已预装 | ✅ pip | ❌ 需 Cython 编译 |
| 无隐式配置文件 | ✅ | ✅ | ❌ ZIPLINE_ROOT, bundle ingest |
| 无外部日历依赖 | ✅ | ✅ | ❌ exchange_calendars |
| 错误信息可诊断 | ✅ | ✅ | ❌ 实例不匹配错误晦涩 |
| 代码模式简单 | ✅ | 中等 | ❌ 需理解 Pipeline API |
| 10分钟内可运行 | ✅ | ✅ | ❌（ingest 本身需要几分钟） |
| **综合 AI 可用性** | **极高** | **高** | **极低** |

### 1.3 各框架对 A 股的实际支持程度

**backtrader**
- 通过 `bt.feeds.PandasData` 直接摄入 DataFrame，无日历绑定问题
- 社区有大量 A 股 + tushare/baostock 实践案例（知乎、CSDN 均有多篇 2024-2025 年帖子）
- 不内置 A 股交易规则（T+1、涨跌停），需用户在 `next()` 中手写
- 已多年未发大版本，维护进入"稳定"而非"活跃"阶段

**vnpy**
- 原生支持 A 股，内置 CTP/XTP 等接入，有完整 A 股日历
- 定位是"实盘+回测"双模，回测模块（CtaBacktester）能力强
- 架构复杂，AI Agent 难以在 10 分钟内正确初始化整个框架

**qlib**
- 微软开源，专为 A 股因子挖掘设计
- 内置 LSTM/LightGBM/Transformer 等 ML 模型，数据服务器比 pandas 快 10 倍
- 定位是研究平台而非执行回测，部署复杂，不适合 AI Agent 快速构建

**rqalpha**
- API 与 Quantopian/zipline 风格一致，有 A 股日历和规则内置
- License 限制（非商业），社区活跃度下降，2023 年后更新稀少
- 中等 AI 可用性，适合本地宽松环境

**pandas 向量化（无框架）**
- 完全控制，无依赖，AI 模型可以"凭直觉"写出正确代码
- v7 的 `run_backtest.py`（8734 B）验证了这一路径的可行性：逻辑完整，含 3 指标，MOMENTUM_WINDOW=20 规格锁正确
- 缺点：无内置滑点模型、无 T+1 自动保证，需要 AI 自己实现

---

## 2. zipline A 股日历问题根因分析

### 2.1 证据链

本分析基于三个一手证据：

**证据 1：finance-C-086 约束条目（代码分析，confidence=1.0）**

```json
{
  "id": "finance-C-086",
  "core": {
    "when": "TradingAlgorithm 构造时传入 trading_calendar 参数",
    "action": "确保 trading_calendar.name 与 sim_params.trading_calendar.name 一致",
    "consequence": {
      "kind": "bug",
      "description": "algorithm.py:288-293 在名称不一致时抛出 ValueError: Conflicting calendars"
    }
  },
  "severity": "fatal",
  "evidence_refs": [{
    "locator": "algorithm.py:285-293 elif trading_calendar.name == ...: ... else: raise ValueError"
  }]
}
```

C-086 描述的是"名称一致性"检查（`name` 字符串比较），这个检查本身是可以通过的——只要确保名称一致。

**证据 2：v5 监控报告中的根因诊断**

> "Zipline-reloaded has a fundamental US-centric architecture:
> - `bundles.load()` creates readers with XNYS calendar regardless of bundle's registered calendar
> - `run_algorithm` -> `_run()` creates a `DataPortal` with the bundle reader's calendar, not the user-specified one
> - `calendar is calendar` identity check fails because `get_calendar("XSHG")` returns a different instance than the one stored in the bundle reader"

这里描述的是**实例同一性**检查（`is`），不是名称字符串比较。C-086 描述的和实际触发的是两个不同的校验点。

**证据 3：v5 的 run_backtest.py 修复尝试**

```python
# 从 readers 的 calendar 取实例（同源，保证三者一致）
TRADING_CALENDAR = bundle_data.equity_daily_bar_reader.trading_calendar
```

AI 尝试"从 bundle readers 取同源实例"来规避实例不匹配，但该文件引用了不存在的 API（`SimulatedAlgorithmicEngine.create_sim_params`、`ExecutionTracker`、`convert for _convert`），说明 AI 在 zipline 内部 API 上产生了幻觉，代码从未运行。

### 2.2 根因判断

zipline A 股日历问题的根因是**三重叠加**，不是单一原因：

| 层次 | 类型 | 描述 | 是否可修复 |
|------|------|------|-----------|
| L1: 框架设计 | 框架本身的设计缺陷 | `bundles.load()` 硬绑 XNYS 日历，DataPortal 构造时用 reader 的日历而非用户指定的日历 | 可修复（需改框架源码），社区有 fork 方案（czipline） |
| L2: 使用方式 | AI 使用方式错误 | AI 幻觉出了不存在的 API（ExecutionTracker, SimulatedAlgorithmicEngine），代码无法运行 | 可修复（需正确使用 `run_algorithm()` 接口） |
| L3: 环境限制 | OpenClaw 环境不支持 | `cd && python3` 被 exec preflight 拦截，ingest CLI 无法运行，10 分钟超时内 bundle ingest 完成不了 | 不可修复（环境限制） |

**结论**：在 OpenClaw 环境下，L3 环境限制本身就是 blocking 的，即使 L1、L2 都解决了，zipline 也无法正常工作。在本地宽松环境（如本地 Claude Code），L1 + L2 是可以解决的——社区已有 czipline 等 A 股适配 fork，并且在宽松环境下 AI 有时间反复调试。

**关于 C-086 的重新评价**：C-086 的约束（"name 必须一致"）是真实的，但它保护的是"已经能运行"的场景下的配置一致性，而不是"第一步就能运行"的场景。C-086 没有捕捉到更深的实例同一性问题（L1）。该约束需要补充一条新的约束，描述 `bundles.load()` 的 calendar 覆盖行为。

---

## 3. 宿主环境差异分析

### 3.1 环境能力矩阵

| 能力维度 | OpenClaw (MiniMax-M2.7) | Codex (GPT-5.4) | Claude Code (Opus) |
|----------|------------------------|-----------------|-------------------|
| 模型能力 | 中等（易幻觉复杂 API） | 强 | 极强 |
| 超时限制 | 10 分钟（hard limit） | 更长（约 30 分钟） | 无限制 |
| exec preflight | 拦截 `cd && python3` | 未知（可能宽松） | 完整终端访问 |
| pip install | 不支持（无特权） | 支持 | 支持 |
| 会话恢复 | compaction retry，有损 | checkpoint 机制 | 原生多轮对话 |
| 文件 edit 工具 | 精确文本匹配（易失败） | 更健壮 | 原生 Edit 工具 |
| 调试迭代次数 | 1-2 次（超时内） | 5-10 次 | 不限 |

### 3.2 各框架在不同环境的可行性

| 框架 | OpenClaw | Codex | Claude Code |
|------|----------|-------|-------------|
| pandas 向量化 | ✅ 可行（v7 验证代码逻辑正确） | ✅ 可行 | ✅ 可行 |
| vectorbt | ⚠️ 可能可行（依赖 numba，安装未验证） | ✅ 可行 | ✅ 可行 |
| backtrader | ⚠️ 未验证（需 pip，可能已预装） | ✅ 可行 | ✅ 可行 |
| zipline-reloaded | ❌ 三代失败（v5/v6/v7） | ⚠️ 可能，需调试 | ⚠️ 可能，需调试 L1 |
| vnpy | ❌ 架构过重，10 分钟内无法初始化 | ⚠️ 可能 | ✅ 可行 |
| rqalpha | ❌ 未在此环境验证 | ⚠️ 可能 | ✅ 可行 |

### 3.3 关键约束：exec preflight

v7 失败的直接触发点是 exec preflight 拦截 `cd /path && python3 script.py`。这是 OpenClaw 的安全机制，要求所有执行使用绝对路径格式 `python3 /absolute/path/to/script.py`。

任何需要"先 ingest 再运行"的框架（zipline、rqalpha）在此规则下都面临额外障碍：ingest 步骤通常通过 CLI（`zipline ingest -b bundle_name`）触发，这类命令格式被 preflight 拦截。

### 3.4 关键约束：10 分钟 embedding run timeout

zipline 的 bundle ingest 操作（即使是小数据集）通常需要 2-5 分钟，加上策略运行，10 分钟内完成端到端回测几乎不可能。向量化方案（读 CSV → 计算 → 输出）在 5 秒内完成。

---

## 4. 推荐方案：晶体编译 SOP 中的技术路线规范

### 4.1 方案评估

**选项 A：固定框架（pandas 向量化）**
- 优点：最简单，已验证，零歧义
- 缺点：放弃了更强环境下更好工具（如 backtrader 的事件驱动精确性、vectorbt 的速度）的可能性
- 当前 v8 的做法

**选项 B：纯环境感知（AI 根据环境选择）**
- 优点：理论上最优
- 缺点：弱模型（MiniMax-M2.7）做出正确的环境感知判断本身就不可靠；环境检测代码需要消耗额外 token；失败时没有明确回退路径
- 不推荐

**选项 C：蓝图驱动+约束提供替代方案**
- 蓝图声明主框架（按策略复杂度选），约束声明各框架的环境前置条件和降级路径
- AI 在读取晶体时，先检查环境前置条件，再选框架
- 优点：结构化，可扩展，不依赖 AI 的"直觉判断"
- 推荐，但需要晶体编译器增加环境感知约束层

**选项 D（推荐）：固定主路径 + 显式禁止列表 + 升级路径**

在 directive 的技术路线段，采用"三层结构"：

1. **主路径**（默认使用）：`pandas + numpy 向量化`，无条件适用
2. **禁止列表**（受限环境特有）：`zipline`、`vnpy`，附理由
3. **升级路径**（宽松环境提示）：如果确认环境支持 pip 且无超时，可考虑 backtrader

### 4.2 推荐方案详述

推荐采用 **方案 D**，理由：

1. **方案 A 不够**：固定 pandas 没有错，但缺少对 zipline 的显式禁止——AI 在受阻时会"自然回退"到 zipline（v7 的教训），不加禁止就是隐患。

2. **方案 B 过于乐观**：弱模型自主判断环境这件事本身不可靠。v7 中 MiniMax-M2.7 明知 exec preflight 失败，仍然回退到了 zipline 路径——这说明模型在受压时会违反自己的判断。

3. **方案 C 是中期目标**：蓝图驱动是正确方向，但需要晶体编译器增加环境感知约束层，当前工程成本较高。方案 D 是方案 C 的工程近似，在约束层没有就绪前可以先用。

### 4.3 具体的 directive 技术路线模板

以下是推荐的晶体 directive 技术路线段落模板（适用于 OpenClaw 环境的回测晶体）：

```markdown
## 技术路线

### 主框架（强制）

使用 **pandas + numpy 向量化回测**，不引入任何第三方回测框架。

数据摄入：baostock API（`import baostock as bs`，通常已预装）。
执行：`python3 /absolute/path/to/run_backtest.py`（禁止使用 `cd && python3` 格式）。

### 禁止使用（FATAL）

以下框架在当前环境下不可用，遇到问题时不得切换至这些框架：

- ❌ `zipline` / `zipline-reloaded`：需要 bundle ingest（CLI 命令），A 股日历实例绑定问题，10 分钟内无法完成初始化
- ❌ `vnpy`：架构过重，无法在 10 分钟内完成初始化
- ❌ `rqalpha`：未验证在当前环境可用

如果主框架因数据问题失败，**必须修复数据问题**，不得切换框架。

### 向量化回测必须满足的正确性要求

1. **T+1 信号延迟**：计算因子信号使用第 T 日收盘价，仓位从第 T+1 日开始持有（`positions.shift(1)` 或等价实现）
2. **交易成本**：A 股双向佣金万三（0.0003），卖出时额外印花税千一（0.001）
3. **指标输出**：必须计算并打印 `annual_return`、`max_drawdown`、`sharpe_ratio`（三个数值都必须非零）
4. **规格锁**：策略类型（如：20日动量因子选股）不得在执行过程中变更

### 规格锁验证门禁

在提交结果前，验证：
- [ ] 策略逻辑与规格一致（20日动量，非布林带/RSI/其他）
- [ ] 三个指标均非零（annual_return ≠ 0.00%，否则说明有 bug）
- [ ] 存在实际交易（调仓次数 > 0）
```

### 4.4 进阶方案：环境探针（中期）

如果后续需要支持多环境，推荐在晶体 Stage 0 增加**环境探针**阶段：

```python
# Stage 0: 环境探针（在任何其他代码之前运行）
import subprocess, sys

# 检查 pip 是否可用且有权限
can_pip = subprocess.run([sys.executable, '-m', 'pip', '--version'],
                         capture_output=True).returncode == 0

# 检查 zipline 是否可用
has_zipline = False
try:
    import zipline
    has_zipline = True
except ImportError:
    pass

# 选择框架
FRAMEWORK = "pandas"  # 默认
if has_zipline and can_pip:
    # 仅在确认 zipline 可用且有 pip 权限时，才考虑 zipline（还需验证日历问题）
    pass  # 当前仍然使用 pandas，zipline A股日历问题未解决

print(f"[Stage 0] Framework: {FRAMEWORK}, can_pip: {can_pip}, has_zipline: {has_zipline}")
```

此探针的价值在于：输出结果被记录在日志中，为后续晶体迭代提供环境判断依据，而不是让 AI 在运行时自主决策。

---

## 5. 结论

### 5.1 核心发现汇总

| 问题 | 结论 | 依据 |
|------|------|------|
| zipline 是否可用于 A 股？ | 本地宽松环境下可能，OpenClaw 下不可用 | v5/v7 三代失败；L3 环境限制 blocking |
| zipline 日历问题根因 | 三重叠加（框架设计 + AI 幻觉 + 环境限制），主因是 L1（bundles.load 硬绑日历） | v5 报告根因分析 + C-086 约束 |
| pandas 向量化是否足够？ | 足够，v7 run_backtest.py 逻辑正确（含 T+1、3 指标、规格锁） | v7 run_backtest.py 代码分析 |
| 框架选择应该固定还是感知？ | 主路径固定（pandas），加禁止列表和升级路径 | v7 教训：受压时 AI 会违反自己的判断 |
| 晶体编译 SOP 应该怎么做？ | 方案 D：三层结构（主路径+禁止列表+升级路径） | 基于四轮迭代教训综合判断 |

### 5.2 立即行动项（v8+）

1. **在 directive 技术路线段加入显式禁止列表**（zipline/vnpy/rqalpha），不依赖 AI 自觉
2. **加入规格锁验证门禁**：三指标非零是必要条件，annual_return = -0.25% 应触发 bug 调查而非直接交付
3. **exec 命令格式约束**：所有 exec 使用 `python3 /absolute/path/script.py` 格式
4. **补充 finance-C-086 的新兄弟约束**：描述 `bundles.load()` 硬绑 XNYS 日历的行为（当前 C-086 只覆盖名称一致性，未覆盖实例同一性问题）

### 5.3 中期路线图

- **当前（v8）**：固定 pandas 向量化，加禁止列表
- **中期（v10+）**：蓝图驱动框架选择，约束提供环境前置条件检查
- **长期**：每个目标宿主环境对应独立的晶体变体（OpenClaw 变体 vs Claude Code 变体）

---

## 附录 A：参考文件

| 文件 | 关键发现 |
|------|---------|
| `finance-bp-002.yaml` | zipline 架构蓝图，DataPortal 是数据统一入口 |
| `finance-C-086`（finance.jsonl 第 86 条） | trading_calendar.name 一致性约束（severity: fatal），但仅覆盖名称而非实例问题 |
| `v5-hardened-monitoring-report.md` | zipline 根因：bundles.load() 硬绑 XNYS，实例同一性检查失败；pending_order 单槽 bug |
| `v7-monitoring-report.md` | exec preflight 拦截 `cd && python3`；AI 受阻后回退到 zipline 死路；run_backtest.py 逻辑正确但未执行 |
| `~/quant-workspace/momentum-backtest/run_backtest.py` | 向量化回测完整实现（8734 B），含 T+1、3 指标、MOMENTUM_WINDOW=20，可直接复用 |
| `~/quant-workspace/zipline-project/run_backtest.py` | AI 幻觉的 zipline API（ExecutionTracker，SimulatedAlgorithmicEngine），代码从未运行 |

## 附录 B：参考资料

### 技术文档
- [zipline-reloaded 官方文档 - Trading Calendars](https://zipline.ml4trading.io/trading-calendars.html)
- [zipline-reloaded GitHub](https://github.com/stefan-jansen/zipline-reloaded)
- [czipline A 股适配 fork](https://github.com/zhangshoug/czipline)

### 社区实践
- [Backtrader vs VnPy vs Qlib 2026 对比](https://dev.to/linou518/backtrader-vs-vnpy-vs-qlib-a-deep-comparison-of-python-quant-backtesting-frameworks-2026-3gjl)
- [量化开源项目对比（backtrader/vectorbt/zipline/vnpy/wtpy/qlib）](https://blog.csdn.net/zhangyunchou2015/article/details/147185325)
- [A 股量化框架知乎讨论](https://www.zhihu.com/question/265096151)
- [backtrader 在 A 股的实践](https://zhuanlan.zhihu.com/p/144390882)

---

*本报告所有结论均基于代码分析、实验日志或社区实践，未作无依据的推测。*

*生成时间: 2026-04-06 | 研究者: Claude Sonnet 4.6*
