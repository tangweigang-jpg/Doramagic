# 金融投资领域补充项目推荐（第三批）

> 生成日期：2026-04-05
> 目标：填补前 50 个项目未覆盖的薄弱领域

---

## 按"知识体系增量价值"排序

### 1. arch — 波动率建模核心库

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/bashtage/arch |
| Stars | ~1.5k |
| 主语言 | Python (Cython/Numba 加速) |
| 一句话定位 | 金融计量经济学标准库，提供 ARCH/GARCH/EGARCH/TARCH 等波动率模型 |
| 填补空白 | **波动率建模** — 前 50 项目无任何波动率计量模型实现 |
| 架构复杂度 | 中。模型族+分布族的正交组合设计，支持自定义均值/方差/分布 |

---

### 2. ArcticDB — 金融级时序数据库

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/man-group/ArcticDB |
| Stars | ~2.1k |
| 主语言 | C++ (Python 绑定) |
| 一句话定位 | Man Group 出品的无服务器 DataFrame 数据库，秒级处理十亿行+数千列 |
| 填补空白 | **金融时序数据存储** — 前 50 项目无专用时序数据库，ArcticDB 填补 tick/OHLCV 海量存储缺口 |
| 架构复杂度 | 高。C++ 压缩引擎 + S3/LMDB 后端 + 版本化存储 + 符号级快照 |

---

### 3. tsfresh — 时序特征工程

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/blue-yonder/tsfresh |
| Stars | ~9.1k |
| 主语言 | Python |
| 一句话定位 | 自动从时间序列提取 794 个特征，并通过假设检验进行特征筛选 |
| 填补空白 | **金融 ML 特征工程** — 可直接用于量价因子挖掘，与 Qlib 等框架互补 |
| 架构复杂度 | 中。特征计算器注册机制 + 分布式计算支持 + 统计检验过滤管线 |

---

### 4. gs-quant — 高盛量化工具包

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/goldmansachs/gs-quant |
| Stars | ~10k |
| 主语言 | Python |
| 一句话定位 | Goldman Sachs 开源的衍生品定价、交易、风险管理工具包，25 年实战经验沉淀 |
| 填补空白 | **衍生品定价与结构化产品** — 投行级衍生品分析能力，前 50 项目（除 QuantLib/FinancePy）无此深度 |
| 架构复杂度 | 高。多层 API 架构，本地计算+远程 API 混合模式，覆盖利率/信用/外汇/股权衍生品 |

---

### 5. hftbacktest — 高频交易回测引擎

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/nkaz001/hftbacktest |
| Stars | ~3.9k |
| 主语言 | Rust + Python |
| 一句话定位 | 基于全量订单簿数据的 HFT/做市回测引擎，模拟队列位置和延迟 |
| 填补空白 | **高频交易基础设施** — 唯一开源的 L2/L3 级高频回测框架，考虑队列优先级和延迟建模 |
| 架构复杂度 | 高。Rust 核心引擎 + Python SDK，tick-by-tick 事件驱动，支持多交易所实盘 |

---

### 6. rateslib — 固定收益定价库

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/attack68/rateslib |
| Stars | ~280 |
| 主语言 | Python |
| 一句话定位 | 专业固收库，覆盖债券/IRS/XCS/FX Swap 定价及全曲线构建，支持自动微分 |
| 填补空白 | **固定收益分析** — 投行级曲线构建+多币种交叉 gamma 风险，远超 QuantLib 的 Python 易用性 |
| 架构复杂度 | 高。多曲线联合优化 + AD 自动微分 + 工具级定价精度 |

注意：Source-available 双许可（非商用免费+商用订阅），非传统开源

---

### 7. TradingAgents — 多代理 LLM 交易框架

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/TauricResearch/TradingAgents |
| Stars | ~43k |
| 主语言 | Python |
| 一句话定位 | 模拟真实交易公司架构的多代理 LLM 交易框架，含基本面/情绪/技术分析师+交易员+风控团队 |
| 填补空白 | **AI Agent 金融研究** — 前 50 项目仅有 FinRobot/FinGPT，TradingAgents 提供完整的多角色协作范式 |
| 架构复杂度 | 高。基于 LangGraph 的多代理编排，支持 GPT-5/Claude 4/Gemini 3 等多提供商 |

---

### 8. Perspective — 高性能流式数据可视化

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/finos/perspective |
| Stars | ~9.3k |
| 主语言 | C++ / TypeScript / Rust (WebAssembly) |
| 一句话定位 | FINOS 旗下流式数据可视化引擎，WebAssembly 驱动的实时数据透视表+图表 |
| 填补空白 | **金融数据可视化基础设施** — 前 50 项目无实时流式可视化方案，适配 tick 数据/订单簿展示 |
| 架构复杂度 | 高。C++ 查询引擎编译为 WASM + Custom Element UI + WebSocket 远程模式 |

---

### 9. Ghostfolio — 开源财富管理软件

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/ghostfolio/ghostfolio |
| Stars | ~8k |
| 主语言 | TypeScript (Angular + NestJS) |
| 一句话定位 | 隐私优先的投资组合跟踪与财富管理平台，支持股票/ETF/加密货币 |
| 填补空白 | **投资组合管理终端** — 前 50 项目无完整的持仓跟踪+绩效分析 Web 应用 |
| 架构复杂度 | 高。Nx monorepo + Prisma ORM + PostgreSQL + Redis 缓存 + 多数据源集成 |

---

### 10. Wealthfolio — 桌面端投资追踪器

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/afadil/wealthfolio |
| Stars | ~6.3k |
| 主语言 | Rust + TypeScript (Tauri) |
| 一句话定位 | 离线优先的跨平台桌面/移动投资追踪应用，数据本地存储 |
| 填补空白 | **本地化财富管理** — 与 Ghostfolio 互补，专注离线隐私场景，Tauri 架构值得学习 |
| 架构复杂度 | 中。Tauri (Rust 后端 + Web 前端) + 本地 SQLite + 可选 Docker 自托管 |

---

### 11. VisualHFT — 市场微结构实时可视化

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/visualHFT/VisualHFT |
| Stars | ~1k |
| 主语言 | C# (WPF) |
| 一句话定位 | 实时展示订单簿动态、执行质量和微结构指标（VPIN/LOB 不平衡等）的桌面 GUI |
| 填补空白 | **高频交易可视化** — 前 50 项目无微结构可视化工具，内置 VPIN/弹性/OTT 等专业指标 |
| 架构复杂度 | 中。插件化架构 + 多交易所 WebSocket 连接器 + 模块化分析组件 |

---

### 12. optlib — 期权定价与 Greeks 计算

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/dbrojas/optlib |
| Stars | ~1.3k |
| 主语言 | Python |
| 一句话定位 | 轻量级期权定价库，实现 Black-Scholes/Merton/Black76/Garman-Kohlhagen 四大模型 |
| 填补空白 | **衍生品基础定价** — 比 py_vollib 更全的模型覆盖，同时返回价格和全部 Greeks |
| 架构复杂度 | 低。纯函数式 API，每个模型独立实现，依赖极少 |

---

### 13. rotki — 隐私优先的投资组合会计系统

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/rotki/rotki |
| Stars | ~1.7k |
| 主语言 | Python + TypeScript |
| 一句话定位 | 本地加密存储的投资组合追踪、分析、会计和税务报告工具 |
| 填补空白 | **税务优化+合规** — 前 50 项目无税务报告功能，rotki 覆盖多国税法的 PnL 报告生成 |
| 架构复杂度 | 高。桌面 Electron 应用 + Python 后端 + SQLCipher 加密数据库 + 多链/多交易所集成 |

---

### 14. skorecard — 信用评分卡建模

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/ing-bank/skorecard |
| Stars | ~106 |
| 主语言 | Python |
| 一句话定位 | ING 银行出品的 scikit-learn 兼容信用评分卡工具，自动分箱+交互式调整 |
| 填补空白 | **合规与监管** — 银行级信用风险建模，传统评分卡方法论的工程化实现 |
| 架构复杂度 | 中。sklearn Pipeline 兼容 + Dash 交互界面 + optbinning 自动分箱 |

---

### 15. xalpha — 中国基金投资管理引擎

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/refraction-ray/xalpha |
| Stars | ~2.3k |
| 主语言 | Python |
| 一句话定位 | 中国场外基金投资管理与回测引擎，支持基金组合分析和净值跟踪 |
| 填补空白 | **中国散户刚需** — 前 50 项目缺乏场外基金管理工具，xalpha 覆盖定投/组合/净值分析 |
| 架构复杂度 | 中。多数据源爬虫 + 基金/组合/指标三层对象模型 |

---

### 16. LOBFrame — 订单簿深度学习基准框架

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/FinancialComputingUCL/LOBFrame |
| Stars | ~200 |
| 主语言 | Python |
| 一句话定位 | UCL 出品的 LOB 数据处理与深度学习预测基准框架，标准化预处理/建模/评估流程 |
| 填补空白 | **市场微结构 ML** — 学术级 LOB 预测基准，可复现 DeepLOB/HLOB 等 SOTA 模型 |
| 架构复杂度 | 中。模块化 ML 管线 + PyTorch Lightning 训练 + 标准化评估指标 |

---

### 17. Equinox — 可持续金融项目风险平台

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/open-risk/equinox |
| Stars | ~38 |
| 主语言 | Python (Django) |
| 一句话定位 | 支持项目融资可持续性风险管理的开源平台，整合 EBA/PCAF/赤道原则标准 |
| 填补空白 | **ESG 与可持续金融** — 前 50 项目无 ESG 风险管理工具，Equinox 是目前最完整的开源实现 |
| 架构复杂度 | 中。Django Web 应用 + 地理空间数据集成 + 多监管标准数据 schema |

---

### 18. bondTrader — 可转债 T+0 自动交易

| 维度 | 详情 |
|------|------|
| GitHub | https://github.com/freevolunteer/bondTrader |
| Stars | ~200（估计） |
| 主语言 | Python |
| 一句话定位 | A 股可转债日内 T+0 自动交易系统，集成实时行情+策略触发+交易托管 |
| 填补空白 | **中国散户刚需（可转债）** — 可转债 T+0 策略的完整工程实现，含 WebSocket 行情接口 |
| 架构复杂度 | 中。行情订阅 + 策略引擎 + 券商交易接口三层架构 |

---

## 覆盖分析

| 薄弱领域 | 补充项目 | 覆盖程度 |
|----------|---------|---------|
| 波动率建模 | arch | ★★★★★ 完全覆盖 |
| 时序数据库 | ArcticDB | ★★★★★ 完全覆盖 |
| 金融 ML 特征工程 | tsfresh | ★★★★☆ 通用时序，需金融适配 |
| 衍生品与期权 | gs-quant, optlib, rateslib | ★★★★★ 多层次覆盖 |
| ESG/可持续金融 | Equinox | ★★★☆☆ 专注项目融资，ESG 评分仍弱 |
| 投资组合终端 | Ghostfolio, Wealthfolio | ★★★★★ Web+桌面双覆盖 |
| 高频交易基础设施 | hftbacktest, VisualHFT, LOBFrame | ★★★★★ 回测+可视化+ML 三维覆盖 |
| 绩效归因 | （无高质量独立项目） | ★☆☆☆☆ 仍需关注 |
| 合规/监管报告 | skorecard, rotki | ★★★☆☆ 信用评分+税务，监管报告仍弱 |
| 中国散户刚需 | xalpha, bondTrader | ★★★★☆ 基金+可转债，打新/港股通仍缺 |
| AI Agent 金融研究 | TradingAgents | ★★★★★ 多代理协作范式 |
| 固定收益 | rateslib | ★★★★☆ 专业级但非纯开源 |
| 金融数据可视化 | Perspective | ★★★★★ 流式可视化标杆 |

## 结论

经过三轮 68 个项目的系统梳理，**绩效归因**（Brinson/多期/因子归因）和**监管报告**（XBRL、合规自动化）是仅存的两个显著空白领域。这两个方向的开源项目普遍 Star 数极低（<100）、维护不活跃，反映了其高度专业化和商业壁垒高的特点。建议在蓝图体系中将这两个领域标记为"商业软件主导，开源可参考但不构成独立蓝图"。
