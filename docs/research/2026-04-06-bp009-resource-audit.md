# BP-009 资源专项审视报告

**蓝图**: finance-bp-009 — 模块化量化框架（zvt Schema 驱动 + 向量化因子计算）  
**审视日期**: 2026-04-06  
**审视人**: Claude Sonnet 4.6（资源专项审视）  
**蓝图版本**: 1.0.0（confidence: 0.92）

---

## 1. 资源盘点（完整清单）

### 1.1 从 replaceable_points 提取的资源

| 资源类别 | 具体资源 | 所在 Stage | 来源字段 |
|---------|---------|-----------|---------|
| 数据源 | em（东方财富）| recorder_layer | replaceable_points.data_source |
| 数据源 | joinquant（聚宽）| recorder_layer | replaceable_points.data_source |
| 数据源 | sina（新浪）| recorder_layer | replaceable_points.data_source |
| 数据源 | qmt（迅投 QMT）| recorder_layer | replaceable_points.data_source |
| 数据源 | exchange（交易所直连）| recorder_layer | replaceable_points.data_source |
| 存储后端 | SqliteStorageBackend（SQLite 文件）| infrastructure_layer | replaceable_points.storage_backend |
| 因子转换器 | MaTransformer（均线）| factor_engine | replaceable_points.transformer |
| 因子转换器 | MacdTransformer（MACD）| factor_engine | replaceable_points.transformer |
| 状态累积器 | 自定义 Accumulator 子类 | factor_engine | replaceable_points.accumulator |

### 1.2 从 known_use_cases 提取的资源

| 资源类别 | 具体资源 | 来源用例 |
|---------|---------|---------|
| 执行引擎 | StockTrader | MACD 日线金叉策略 |
| 执行引擎 | TargetSelector（condition_and 模式）| 均线多因子选股 |
| 数据格式 | 日线 OHLCV + 复权价（hfq）| MACD 日线金叉策略 |
| 数据格式 | 日线 OHLCV + 成交量 + 换手率 | 均线多因子选股 |
| 数据源 API | 东方财富 API（无账号、免费）| 东方财富数据源接入 |
| 数据格式 | 财务报表数据（FinanceFactor Schema）| 基本面因子选股 |
| 数据格式 | 日线/分钟 OHLCV（高低点序列）| 缠论因子策略 |
| 数据格式 | 历史 OHLCV 训练集 + 特征因子数据 | ML 预测因子 |
| ML 框架 | sklearn 兼容模型 | ML 预测因子 |
| 实盘接口 | QMT 量化交易软件（迅投系统，需券商开通）| QMT 实盘接口对接 |
| 存储 | 本地 SQLite（AccountStats/Position/Order 表）| Dash Web 监控界面 |
| 可视化 | Dash（端口 8050，独立进程）| Dash Web 监控界面 |

### 1.3 从 optional_extensions 提取的资源

| 资源类别 | 具体资源 | 扩展 ID |
|---------|---------|---------|
| Web UI | Dash（zvt.main:main）| web_ui |
| REST API | FastAPI（zvt_server.py）| rest_api |
| 定时任务 | APScheduler + SQLite Job Store + 线程池/进程池 | scheduler |
| 通知系统 | EmailInformer（SMTP）+ WechatInformer（微信）| informer |
| ML 模块 | MlFactor（shift(-predict_range) 标签构造）| ml_module |
| 标签系统 | 行业/主题/AI 建议标签（tag/目录）| tag_system |
| 缠论因子 | ZenFactor（笔/段/中枢）| zen_factor |
| 实盘接口 | QmtBroker（仅 Windows）| qmt_broker |

### 1.4 从 applicability.prerequisites 提取的硬依赖

| 类别 | 资源 | 字段 |
|-----|------|------|
| Python 版本 | Python 3.8+ | prerequisites |
| ORM 框架 | SQLAlchemy | prerequisites |
| 数据处理 | Pandas | prerequisites |
| 外部账号 | 至少一个数据源账号（东方财富免费）| prerequisites |

---

## 2. 资源覆盖完整性

### 2.1 "是什么 + 能力 + 限制"描述完整性

| 资源 | 是什么 | 能力 | 限制 | 总体 |
|-----|--------|------|------|------|
| em（东方财富）| 有（free, china_stock, main_source）| A 股日线/分钟线、基本面 | 不适合美股、期货 | **完整** |
| joinquant（聚宽）| 有（paid, china_stock, historical）| A 股历史数据、财务数据 | 不适合实时行情 | **完整** |
| sina（新浪）| 有（free, real_time_quote）| 实时行情 | 不适合历史 K 线 | **完整** |
| qmt | 有（windows_only, broker_api, live_trading）| 实盘交易 | Linux/Mac 不支持 | **完整** |
| exchange（交易所）| 有（official, institutional）| 交易所直连 | 不适合个人投资者 | **完整** |
| SqliteStorageBackend | 有（file_based, zero_config）| 单机开发、回测研究 | 不适合分布式、高并发 | **完整** |
| MaTransformer | 有（moving_average, vectorized）| 均线计算 | 无明确 not_fit_for | **基本完整**（缺限制描述）|
| MacdTransformer | 有（macd, ewm）| MACD 指标 | 无明确 not_fit_for | **基本完整**（缺限制描述）|
| Dash Web UI | 有（optional_extension）| 可视化监控 | 仅描述端口/进程 | **弱**（缺能力边界描述）|
| APScheduler | 有（optional_extension）| 定时任务 | 无限制描述 | **弱** |
| EmailInformer/WeChat | 有（optional_extension）| 通知 | 无限制描述 | **弱** |
| sklearn ML 模型 | 仅在 known_use_cases 提及 | 预测因子 | 无独立描述 | **缺失**（无 replaceable_point）|
| FastAPI REST API | 仅在 optional_extensions | REST 接口 | 无能力/限制描述 | **弱** |

### 2.2 resource_boundary 约束覆盖情况

当前 4 条 resource_boundary 约束（来自 finance.jsonl）：

| 约束 ID | 覆盖资源 | 覆盖质量 |
|--------|---------|---------|
| finance-C-453 (high) | QMT：非 Windows 不可用 | 精准，覆盖 OS 依赖限制 |
| finance-C-454 (medium) | SQLite：Windows 下 sub_size 自动降为 900 | 精准，覆盖平台行为差异 |
| finance-C-456 (medium) | Factor keep_window：避免全量数据加载 | 精准，覆盖内存使用限制 |
| finance-C-461 (high) | SQLite：不支持多进程并发写入 | 精准，覆盖并发限制 |

**缺口**：派生约束（v1.3）中有 23 条，均为 domain_rule / operational_lesson / claim_boundary 类型，**无一条 resource_boundary**。说明资源约束提炼工作尚未启动。

---

## 3. 资源缺口

### 3.1 A 股量化 Skill 必须资源对照表

| 资源需求 | bp-009 覆盖情况 | 缺口等级 |
|---------|---------------|---------|
| A 股日线/分钟线数据源 | 已覆盖（em/joinquant 均支持）| 无缺口 |
| 实时行情数据 | 已覆盖（sina 实时行情）| 无缺口 |
| A 股交易日历 | **缺口**：蓝图有 in_trading_date() 调用但数据来源未说明，trader.py:439 逻辑未在资源层描述 | 中 |
| 实盘交易接口 | 已覆盖（QMT，明确 Windows 限制）| 基本覆盖，但仅 1 个券商接口 |
| 非 QMT 实盘接口 | **缺口**：其他券商接口（如 XTP、miniQMT、华鑫奇点）完全未提及 | 高 |
| 回测执行引擎 | 已覆盖（Trader.run() + SimAccount）| 无缺口 |
| 数据存储 | 已覆盖（SQLite，明确单机限制）| 无缺口 |
| 高性能存储替代品 | **缺口**：PostgreSQL/MySQL/TDengine 替代路径完全未描述，replaceable_point 仅有 SQLite 一个选项 | 高 |
| 可视化/报告工具 | 弱覆盖（Dash 在 optional_extensions 中，but 无能力描述）| 中 |
| 财务数据源 | 弱覆盖（joinquant 含财务，但 FinanceFactor Schema 对应哪个 provider 不清晰）| 中 |
| Python 依赖包 | **缺口**：只在 prerequisites 简单提了 SQLAlchemy+Pandas，完整依赖（ta-lib/pandas-ta/plotly/dash/fastapi/apscheduler）均未描述 | 高 |
| AkShare/tushare 等数据源 | **缺口**：AkShare 是当前最流行的免费 A 股数据源之一，被 zvt 用于部分数据，但蓝图完全未提及 | 高 |
| 基准指数数据（沪深 300 等）| **缺口**：基准比较是量化策略评估的必需品，蓝图中无基准数据资源描述 | 中 |
| 风险指标计算库 | **缺口**：夏普/最大回撤等需要 quantstats/pyfolio 或自实现，蓝图无描述 | 中 |
| 数据验证/监控 | **缺口**：数据质量检查（缺数/异常值）资源层完全空白 | 低 |

### 3.2 最关键缺口汇总

1. **AkShare**：现实中 zvt 2023 年后已集成 AkShare 作为主要免费数据源之一，蓝图只有 em/joinquant/sina/qmt/exchange，遗漏了一个高度活跃的数据源。
2. **非 QMT 实盘接口**：仅 QMT 一个实盘选项，且限制于 Windows。对 Mac/Linux 用户，实盘路径完全缺失。
3. **存储后端只有 SQLite**：replaceable_point 标注"目前仅有 SQLite 实现"，但没有提供其他存储方案的实现成本评估，对需要扩展的用户是盲点。
4. **完整 Python 依赖清单缺失**：一个完整的 Skill 在编译时需要知道 `pip install` 什么，当前仅有 SQLAlchemy+Pandas。

---

## 4. 现有资源质量评估

### 4.1 replaceable_points 四字段完整性检查

**已有 replaceable_points 的 stage**：
- `infrastructure_layer`：storage_backend（1 个 option）
- `recorder_layer`：data_source（5 个 options）
- `factor_engine`：transformer（2 个 options）、accumulator（1 个 option）

**四字段检查**（name / traits / fit_for / not_fit_for）：

| replaceable_point | name | traits | fit_for | not_fit_for | 完整度 |
|------------------|------|--------|---------|-------------|--------|
| SqliteStorageBackend | ✅ | ✅ | ✅ | ✅ | 100% |
| em（东方财富）| ✅ | ✅ | ✅ | ✅ | 100% |
| joinquant | ✅ | ✅ | ✅ | ✅ | 100% |
| sina | ✅ | ✅ | ✅ | ✅ | 100% |
| qmt | ✅ | ✅ | ✅ | ✅ | 100% |
| exchange | ✅ | ✅ | ✅ | ✅ | 100% |
| MaTransformer | ✅ | ✅ | ✅ | **❌** | 75% |
| MacdTransformer | ✅ | ✅ | ✅ | **❌** | 75% |
| 自定义 Accumulator | ✅ | ✅ | ✅ | **❌** | 75% |

### 4.2 default 选择合理性

| replaceable_point | default | 合理性 |
|------------------|---------|--------|
| storage_backend | SqliteStorageBackend | ✅ 合理：单机研究首选，零配置 |
| data_source | em（东方财富）| ✅ 合理：免费、无账号、覆盖 A 股日线/分钟线 |
| transformer | null | ⚠️ 可接受：无默认符合框架"不内置策略"的设计哲学，但对新手不友好 |
| accumulator | null | ✅ 合理：状态累积是可选的，大多数因子无需 |

### 4.3 selection_criteria 清晰度

| replaceable_point | selection_criteria 描述 | 清晰度 |
|------------------|------------------------|--------|
| storage_backend | "目前仅有 SQLite 实现，路径格式 {data_path}/{provider}/{provider}_{db_name}.db" | ⚠️ 描述了现状，但缺乏"何时考虑替换"的判断标准 |
| data_source | "根据数据需求和环境选择。新增数据源只需继承 Recorder 并设置 provider" | ✅ 清晰，且说明了扩展方式 |
| transformer | "根据技术指标需求选择，可自定义 Transformer 子类" | ⚠️ 过于简短，缺乏不同指标类型的选择建议 |
| accumulator | "仅当因子需要跨周期状态时使用" | ✅ 清晰，判断标准明确 |

### 4.4 遗漏的重要选项

**data_source 缺少的选项**：
- **AkShare**：免费、活跃维护、覆盖 A 股+港股+期货，是当前 Python 量化社区最主流的免费数据源
- **Tushare Pro**：付费但数据质量高，是专业量化研究的常用选择
- **Wind（万得）**：机构标准数据源，需本地客户端，enterprise 场景必需

**storage_backend 缺少的选项**：
- 无任何替代方案描述（PostgreSQL、MySQL、ClickHouse、TDengine 等），而 StorageBackend 是框架中唯一的真正 ABC——理论上可以完整替换，但蓝图完全没有提供替换路径

**broker/实盘接口缺少的选项**：
- miniQMT（更轻量的 QMT）
- XTP（中泰证券，支持 Linux）
- 华鑫奇点 ORCA（Linux 友好）

---

## 5. 改进建议

### 5.1 需要在蓝图 replaceable_points 中补充的资源

#### 优先级 P0（影响晶体可用性）

**补充 AkShare 为 data_source 选项**：
```yaml
- name: akshare
  traits: [free, china_stock, active_maintenance, multi_market]
  fit_for: [A 股/港股/期货日线历史, 指数成分股, 财务数据, 宏观数据]
  not_fit_for: [分钟级实时行情（延迟较高）, 高频数据]
```

**在 prerequisites 中补充完整依赖**：
```yaml
prerequisites:
  - Python 3.8+
  - SQLAlchemy + Pandas（核心 ORM 和数据处理）
  - 至少一个数据源账号（东方财富免费）
  core_packages:
    - sqlalchemy>=1.4
    - pandas>=1.3
    - requests（HTTP 数据源调用）
  optional_packages:
    - dash + plotly（Web UI）
    - fastapi + uvicorn（REST API）
    - apscheduler（定时任务）
    - scikit-learn（ML 因子）
    - akshare / joinquant-sdk / xtquant（数据源）
```

#### 优先级 P1（影响资源描述完整性）

**补充 transformer 和 accumulator 的 not_fit_for 字段**：
```yaml
- name: MaTransformer
  not_fit_for: [需要跨周期状态的指标（如布林带动态调整）, tick 级计算（groupby 开销大）]

- name: MacdTransformer
  not_fit_for: [分钟级以下频率（ewm 计算量大）, 非 OHLCV 数据]
```

**新增 storage_backend 的替代路径描述**：
```yaml
options:
  - name: SqliteStorageBackend
    traits: [file_based, zero_config, default]
    fit_for: [单机开发、回测研究（<100 万条数据）]
    not_fit_for: [分布式、高并发写入、数据量超过 10GB]
  - name: 自定义 StorageBackend（PostgreSQL/MySQL）
    traits: [server_based, concurrent_write, scalable]
    fit_for: [多进程写入、团队协作、生产环境]
    not_fit_for: [快速原型（需要额外配置数据库服务）]
    implementation_note: "继承 StorageBackend ABC，实现 get_engine 和 get_session_factory 即可"
```

#### 优先级 P2（完善性补充）

**新增 broker 作为独立 replaceable_point**（在 trader_engine 或 infrastructure_layer）：
```yaml
- name: broker
  description: 实盘交易接口
  options:
    - name: QmtBroker（QMT）
      traits: [windows_only, xtquant_required]
      fit_for: [QMT 开户用户、A 股实盘]
      not_fit_for: [Linux/Mac、非 QMT 券商]
    - name: 自定义 Broker
      traits: [extensible]
      fit_for: [XTP/ORCA 等其他实盘接口]
      not_fit_for: [无对应 SDK 的环境]
  default: null（回测时不需要）
```

**新增基准数据源描述**（用于绩效评估）：
```yaml
- name: benchmark_data
  description: 策略绩效基准指数数据
  options:
    - name: 沪深 300 日线（em provider 可获取）
    - name: 中证 500 日线（em provider 可获取）
  note: "账户净值与基准的相对收益是策略评估的核心指标，建议明确配置"
```

### 5.2 需要新增的 resource_boundary 约束

以下资源限制已在现有 4 条 resource_boundary 之外，建议补充：

| 建议约束 | when | 触发条件 | severity |
|---------|------|---------|---------|
| RB-NEW-1 | 使用 em 数据源时 | 东方财富分钟数据仅保留近期（约 20 个交易日），历史分钟数据不可用 | high |
| RB-NEW-2 | 使用 joinquant 数据源时 | 聚宽需要付费账号，且每日调用次数有限制（免费版 50 次/日）| medium |
| RB-NEW-3 | 使用 SQLite 在 macOS 上时 | macOS APFS 文件系统在 SQLite WAL 模式下有并发限制，76 个 SQLite 文件同时写入时可能触发文件描述符上限（ulimit） | medium |
| RB-NEW-4 | 使用 Dash Web UI 时 | Dash 必须在独立进程运行（不可与 Trader.run() 同进程），否则 GIL 导致实时数据更新阻塞 | high |
| RB-NEW-5 | 在 Python 3.11+ 环境使用时 | xtquant（QMT Python SDK）对 Python 版本有严格限制，通常仅支持 3.6~3.9 | high |
| RB-NEW-6 | 使用 APScheduler 调度 Recorder 时 | APScheduler SQLite Job Store 与 zvt 的 76 个 SQLite 文件共用文件系统，高频调度时可能触发文件锁竞争 | medium |

---

## 6. 总体评分（1-10）

| 维度 | 得分 | 说明 |
|-----|------|------|
| 资源盘点完整性 | 5/10 | 核心资源（em/SQLite/QMT）有，但 AkShare、完整依赖包、非 QMT 实盘接口缺失 |
| 资源描述质量 | 7/10 | 核心资源的 name/traits/fit_for/not_fit_for 大多完整，仅 transformer 类缺 not_fit_for |
| resource_boundary 约束密度 | 4/10 | 4 条覆盖了重要的平台/并发限制，但大量资源边界（数据源限制、Python 版本、文件描述符）未转化为约束 |
| default 选择合理性 | 8/10 | em 作为数据源默认值、SQLite 作为存储默认值均合理 |
| 可替换性描述 | 5/10 | storage_backend 只有 1 个选项，broker 完全没有 replaceable_point，可替换路径描述不足 |
| 依赖透明度 | 3/10 | 完整 pip 依赖缺失，对晶体编译（自动生成 skill）不友好 |

**综合评分：5.3/10**

---

## 7. 结论：资源是否足以支撑好的晶体编译？

**结论：勉强够用，但存在多个影响晶体质量的关键缺口。**

### 已经做好的部分
- 核心数据源（em/joinquant/sina/qmt）的四字段描述是蓝图中质量最高的资源段，清晰描述了能力和限制
- SQLite 存储的并发限制（finance-C-461）和 Windows 平台差异（finance-C-454）有对应 resource_boundary 约束
- QMT 的 Windows 限制（finance-C-453）有明确约束保障

### 必须解决的缺口（否则晶体会产生误导）

1. **AkShare 缺失**：当用户询问"怎么用 zvt 免费获取 A 股数据"时，晶体只会推荐 em，而 2024 年后 AkShare 在 zvt 中的使用已非常普遍。这会导致晶体给出过时的推荐。

2. **完整依赖包缺失**：晶体生成的 skill 如果需要运行代码示例，无法生成正确的 `requirements.txt` 或 `pip install` 指令。这是从蓝图到可执行 skill 的关键断点。

3. **em 分钟数据限制未转化为约束**：东方财富分钟数据只有近期数据，但这一关键限制只在 known_use_cases 的 must_validate 中提到，没有 resource_boundary 约束，晶体编译时可能丢失这个信息。

4. **非 QMT 实盘路径完全空白**：Mac/Linux 用户想做实盘的需求完全没有资源支撑，晶体遇到这类问题会无从回答。

### 改进优先级建议

- **立即修复**（影响晶体基本可用性）：补充 AkShare 为 data_source 选项 + 补充 em 分钟数据限制的 resource_boundary 约束
- **短期修复**（影响晶体专业度）：补充完整依赖包清单 + transformer/accumulator 的 not_fit_for + storage_backend 的替代路径
- **长期完善**（影响晶体覆盖广度）：补充非 QMT 实盘接口选项 + 基准数据源描述 + Python 版本兼容性约束
