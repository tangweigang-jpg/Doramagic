# Finance Blueprint Gap Analysis
# 59 现有蓝图 vs 18 类用户需求覆盖度分析

> 分析日期：2026-04-14
> 分析范围：59 个 finance 领域蓝图（finance-bp-001 ~ finance-bp-059）
> 方法：对照 18 类用户需求类别逐一评估覆盖广度与深度

---

## 分析框架说明

**覆盖评级定义：**
- **EXCELLENT**：≥3 个高质量蓝图直接覆盖，核心子需求全部触达
- **GOOD**：2~3 个蓝图覆盖，主要子需求基本满足，有次要空白
- **ADEQUATE**：1~2 个蓝图覆盖，主干需求被满足，但深度或广度不足
- **THIN**：仅有间接或部分覆盖，用户需求只能被边缘触及
- **ABSENT**：零覆盖，无任何可用蓝图

**Doramagic 定位提醒：** 蓝图覆盖即"有种子晶体可编译交付"；ABSENT/THIN 类别无法向用户交付对应领域的高质量 skill。

---

## Category 1: Opportunity Discovery — 机会发现

**覆盖评级：GOOD**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-007 | A 股综合选股系统 | 股票筛选、指标过滤、批量扫描 |
| finance-bp-009 | 模块化量化框架（zvt） | Schema 驱动因子计算、选股逻辑 |
| finance-bp-010 | LLM 驱动股票智能分析系统 | NL 查询驱动分析、AI 评股 |
| finance-bp-027 | OpenBB 金融研究平台 | 多数据源统一接口、主题/板块查询 |
| finance-bp-033 | 散户实时行情获取系统 | 实时行情多数据源适配 |
| finance-bp-040 | ESG 新闻情感评分系统 | 事件驱动 ESG 主题跟踪 |
| finance-bp-054 | 多 Agent 协作股票分析（A 股） | 事件预测、AI 驱动机会识别 |

### 冗余与重叠
- bp-007 与 bp-009 在 A 股选股维度高度重叠（都做批量筛选+技术指标），但 bp-009 更偏模块化框架，bp-007 更偏任务流水线
- bp-010 与 bp-054 的 LLM 驱动分析有重叠，bp-054 是 A 股增强版

### 关键缺口
1. **自然语言查询股票**（iWencai 风格）：现有蓝图偏规则筛选，真正的 NL-to-filter 转换缺少专用蓝图
2. **板块/主题追踪**：缺乏专门的行业轮动、板块资金流向分析蓝图
3. **事件驱动机会**：财报、分红、解禁、股东增减持等事件驱动的机会发现缺覆盖
4. **量化选股因子库**：bp-009 有因子框架但缺乏系统化的因子库（类似 Alphalens + WorldQuant 风格的因子发现系统）

**优先级：P1** — 机会发现是 iWencai 用户的核心需求，NL 查询能力缺口需补充一个专门的 NL-to-filter 蓝图

---

## Category 2: Analysis & Decision — 分析与决策

**覆盖评级：GOOD**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-010 | LLM 驱动股票分析系统 | AI 股票诊断、多维度评分 |
| finance-bp-017 | 综合基本面研究工具包 | 基本面指标计算（PE/PB/ROE/DCF 等） |
| finance-bp-027 | OpenBB 金融研究平台 | 多数据源研究数据聚合 |
| finance-bp-031 | Alpha 因子归因分析系统 | 因子 IC、分位数分析 |
| finance-bp-044 | FinGPT 金融 LLM 微调 | 情感分析、市场预测 LLM |
| finance-bp-045 | 多 Agent LLM 交易框架 | 多角色辩论式决策 |
| finance-bp-054 | 多 Agent A 股分析 | 综合 AI 诊断报告 |

### 冗余与重叠
- bp-010、bp-045、bp-054 三个 AI 分析蓝图有明显功能重叠，都做"LLM 驱动分析+决策建议"
- bp-044（FinGPT 微调）与上述三个蓝图的定位不同（训练侧 vs 应用侧），实际不构成冗余

### 关键缺口
1. **股票诊断工具**（类 F10）：专门的上市公司基本面深度解析缺少独立蓝图（bp-017 偏工具包，不是诊断流程）
2. **研报生成**：机构研究报告结构化生成（背景+业务+财务+估值+评级）无专用蓝图
3. **技术分析**：缠论（bp-008）是专项技术，但经典技术分析体系（道氏理论、形态识别、支撑阻力）无独立蓝图
4. **卖方研究整合**：聚合卖方研报、一致性预期、评级变化的流程缺失

**优先级：P1** — 研报生成是高价值但无覆盖的需求，可直接提升 Doramagic 对投研用户的价值

---

## Category 3: Quantitative Strategy — 量化策略

**覆盖评级：EXCELLENT**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-001 | freqtrade 加密自动交易 | 策略回测、实盘执行 |
| finance-bp-002 | zipline 事件驱动回测 | Pipeline 模式因子策略 |
| finance-bp-004 | qlib AI 量化平台 | 因子研究、Alpha 生成 |
| finance-bp-005 | rqalpha A 股回测 | A 股事件驱动 |
| finance-bp-006 | QUANTAXIS 分布式量化 | 全栈量化框架 |
| finance-bp-008 | 缠论信号系统 | 专项技术信号 |
| finance-bp-009 | zvt 模块化量化 | 向量化因子计算 |
| finance-bp-028 | vectorbt 向量化回测 | 高性能向量化策略 |
| finance-bp-031 | alphalens 因子归因 | Alpha 因子分析 |
| finance-bp-035 | FinRL RL 交易信号 | 强化学习信号生成 |
| finance-bp-038 | hikyuu A 股回测 | 组件化 A 股策略 |
| finance-bp-042 | backtrader 事件驱动 | 经典事件驱动框架 |
| finance-bp-043 | LEAN 多资产回测 | 机构级多资产引擎 |
| finance-bp-053 | LOBFrame LOB 预测 | 订单簿深度学习信号 |
| finance-bp-056 | backtesting.py 轻量回测 | 轻量 OHLCV 回测 |
| finance-bp-057 | Darts 时序预测 | 通用时序预测框架 |

### 冗余与重叠
- **事件驱动回测高度冗余**：bp-002（zipline）、bp-005（rqalpha）、bp-038（hikyuu）、bp-042（backtrader）、bp-043（LEAN）五个都是事件驱动回测，差异主要在市场（A 股/美股/多资产）和性能定位
- **向量化回测**：bp-028（vectorbt）和 bp-056（backtesting.py）都是轻量化向量化回测，前者 Numba 加速，后者更简洁
- bp-001 和 bp-021（nautilus_trader）在高频/实盘方向有一定重叠

### 关键缺口
1. **统计套利/配对交易**：协整检验、均值回复策略缺少专用蓝图
2. **高频因子/微观结构因子**：bp-053 做 LOB 预测，但系统化 LOB 因子工程（订单流不平衡、价格冲击等）无蓝图
3. **期权策略框架**：期权定价蓝图充足，但专门的期权策略（delta 对冲、波动率套利、calendar spread）无蓝图

**优先级：P2** — 此类别已 EXCELLENT，冗余大于缺口，优先精简或关联已有蓝图，而非新增

---

## Category 4: Portfolio Construction — 组合构建

**覆盖评级：EXCELLENT**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-011 | PyPortfolioOpt 均值-方差 | 经典 MVO 优化、风险预算 |
| finance-bp-012 | Riskfolio-Lib 多风险度量 | CVaR/MAD/CDaR 等多目标 |
| finance-bp-016 | skfolio sklearn 兼容框架 | ML Pipeline 组合优化 |
| finance-bp-023 | cvxportfolio 多期优化 | 含交易成本的多期优化 |
| finance-bp-034 | Ghostfolio 投资组合追踪 | 持仓追踪、X-Ray 风险分析 |
| finance-bp-058 | Copulas 多元依赖建模 | 相关性结构建模 |

### 冗余与重叠
- bp-011、bp-012、bp-016 三个都做均值-方差类优化，差异在求解器和约束体系
- bp-023 独特性强（多期 + 交易成本），无直接重叠

### 关键缺口
1. **智能再平衡**：触发条件 + 税务效率 + 最小交易量的再平衡算法无专用蓝图
2. **因子风险模型**：Barra 风格的多因子风险模型（系统风险 vs 特异风险分解）缺少蓝图
3. **动态资产配置**：TAA（战术资产配置）框架、Black-Litterman 模型有部分覆盖（bp-011 提供 BL 支持），但全流程动态配置系统缺少专用蓝图

**优先级：P2** — 覆盖 EXCELLENT，已有高质量蓝图

---

## Category 5: Trade Execution — 交易执行

**覆盖评级：GOOD**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-018 | easytrader A 股执行 | A 股 GUI 自动化跟单 |
| finance-bp-021 | nautilus_trader 算法执行 | 高性能算法执行引擎 |
| finance-bp-024 | hftbacktest HFT 基础设施 | HFT 回放与测试 |
| finance-bp-041 | Hummingbot 做市商框架 | 做市策略 Controller+Executor |
| finance-bp-047 | ib_async IB 券商桥接 | IB TWS 异步接入 |
| finance-bp-059 | VisualHFT HFT 可视化 | 实时市场微结构可视化 |

### 冗余与重叠
- bp-021 与 bp-024 都做 HFT 基础设施，但 bp-021 偏执行架构，bp-024 偏回放测试
- bp-059 作为可视化工具与执行类蓝图定位不完全重叠

### 关键缺口
1. **国内券商 API 接入**：A 股通用券商接入框架（中信/华泰/同花顺 API）无专用蓝图；bp-018 是 GUI 自动化而非 API 接入
2. **订单管理系统（OMS）**：完整 OMS 流程（订单生命周期、状态机、风控前置）无独立蓝图，各回测框架内置的 OMS 分散在各处
3. **滑点与执行成本建模**：独立的交易成本分析（TCA）蓝图缺失
4. **FIX 协议接入**：机构级 FIX 协议适配无蓝图

**优先级：P1** — 国内券商 API 接入是 A 股用户核心痛点，无覆盖

---

## Category 6: Monitoring & Management — 监控与管理

**覆盖评级：ADEQUATE**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-014 | QuantStats 绩效归因 | 夏普比、最大回撤等绩效报告 |
| finance-bp-015 | pyfolio Tear Sheet | 全套策略绩效分析报告 |
| finance-bp-030 | empyrical 风险统计库 | 底层风险/回报统计函数 |
| finance-bp-034 | Ghostfolio 组合追踪 | 持仓追踪、资产配置快照 |
| finance-bp-039 | perspective 流式可视化 | 实时数据流可视化 |

### 冗余与重叠
- bp-014、bp-015、bp-030 高度冗余：都做策略绩效分析，差异在呈现形式（报告/统计函数/交互式）
- bp-034 的组合追踪与纯风险监控定位不同

### 关键缺口
1. **实时风险预警系统**：仓位预警（超仓、回撤触发）、资金使用率预警无专用蓝图
2. **归因分析**：Brinson 多层级绩效归因（资产配置效果 + 证券选择效果）缺少独立蓝图
3. **组合健康看板**：多账户聚合、跨策略风险合并监控缺失
4. **实时 PnL 监控**：日内交易的实时盈亏追踪（非事后分析）无专用蓝图

**优先级：P1** — 实时风险预警是生产级交易系统的必需组件，当前覆盖偏"事后分析"

---

## Category 7: Credit Risk — 信用风险

**覆盖评级：ADEQUATE**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-049 | portfolioAnalytics 信用组合 | Vasicek/CreditMetrics 组合风险 |
| finance-bp-050 | skorecard 信用评分卡 | 分箱+WoE+逻辑回归评分卡 |
| finance-bp-052 | openNPL 不良贷款数据管理 | EBA 模板、NPL 数据结构 |

### 冗余与重叠
- 三个蓝图定位差异清晰：个贷评分（bp-050）、组合风险（bp-049）、NPL 数据（bp-052），重叠极小

### 关键缺口
1. **PD/LGD/EAD 建模**：三参数估计系统（违约概率、违约损失率、违约敞口）无完整蓝图；bp-049 偏组合模型而非单笔估计
2. **IFRS 9 / CECL 拨备计算**：贷款损失准备金计算（Stage 1/2/3 分类、ECL 计算）无蓝图
3. **应力测试**：信用组合压力测试（宏观情景映射到 PD 迁移矩阵）缺失
4. **CVA/DVA 计算**：衍生品信用估值调整无蓝图
5. **机器学习信贷**：基于 XGBoost/LGBM 的信贷违约预测（超越传统评分卡）缺少独立蓝图

**优先级：P1** — IFRS 9 是银行信贷部门的强监管需求，PD/LGD/EAD 建模是信用风险的核心，当前覆盖仅 ADEQUATE 不足以满足银行用户

---

## Category 8: Market Risk — 市场风险

**覆盖评级：GOOD**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-012 | Riskfolio-Lib | CVaR、风险度量组合 |
| finance-bp-013 | QuantLib | 完整衍生品定价与风险管理 |
| finance-bp-019 | FinancePy | 多资产定价与风险 |
| finance-bp-020 | gs-quant 结构化产品 | Goldman Sachs 风险框架 |
| finance-bp-022 | arch GARCH 建模 | 波动率建模、VaR 计算 |
| finance-bp-048 | equinox ESG 风险平台 | ESG 风险评估 |
| finance-bp-058 | Copulas 依赖建模 | 尾部风险、相关性结构 |

### 冗余与重叠
- bp-013（QuantLib）与 bp-019（FinancePy）在衍生品定价上有显著重叠，但 QuantLib 是 C++ 绑定（机构级），FinancePy 是纯 Python（易用性优先）
- bp-020 偏结构化产品和 Goldman Sachs 框架，专业性强

### 关键缺口
1. **历史模拟 VaR / Monte Carlo VaR**：系统化 VaR 计算框架（非组合优化的副产品）缺少独立蓝图
2. **FRTB（基本市场风险审查框架）**：Basel III/IV 下的 SA 和 IMA 计算无蓝图
3. **情景分析系统**：用户自定义情景冲击（宏观变量 → 资产价格）的系统化框架缺失
4. **Greeks 聚合**：机构级 Greeks 聚合与对冲缺口计算无专用蓝图（bp-046/055 做单期权定价）

**优先级：P1** — FRTB 是未来 3 年银行市场风险管理的强监管驱动需求

---

## Category 9: Regulatory & Compliance — 监管合规

**覆盖评级：THIN**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-037 | rotki 加密货币税务申报 | 加密 PnL 计算、税务报告（偏 crypto） |
| finance-bp-048 | equinox ESG 风险平台 | ESG/绿色金融合规数据 |
| finance-bp-052 | openNPL 不良贷款平台 | EBA NPL 数据模板合规 |

### 冗余与重叠
- 三个蓝图覆盖三个不同合规细分，无直接冗余

### 关键缺口
1. **AML/KYC**：反洗钱规则引擎、交易监控、可疑交易报告（STR）完全缺失
2. **监管报告生成**：CCAR/DFAST（美国压力测试）、COREP/FINREP（欧洲监管报告）无蓝图
3. **资本计算**：巴塞尔协议资本充足率（RWA 计算、信用/市场/操作风险资本）无蓝图
4. **审计追踪**：交易日志、变更记录、监管审计追踪系统无蓝图
5. **MiFID II/EMIR**：交易后报告、最佳执行证明无蓝图
6. **A 股监管**：CSRC 相关合规（内幕交易识别、信息披露监控）完全缺失

**优先级：P0** — 合规是金融机构不可绕过的需求，且当前几乎为零覆盖

---

## Category 10: Wealth Management — 财富管理

**覆盖评级：THIN**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-025 | xalpha 中国基金管理 | 基金净值计算、配置管理 |
| finance-bp-034 | Ghostfolio 组合追踪 | 个人资产组合追踪 |
| finance-bp-037 | rotki 加密组合管理 | 加密资产+税务 |

### 冗余与重叠
- 三个蓝图定位各异，无明显冗余

### 关键缺口
1. **智能投顾（Robo-Advisor）**：风险测评→资产配置→定期再平衡的全流程 Robo-Advisor 无蓝图
2. **适合性评估**：KYC + 风险承受能力评估 + 产品适合性匹配系统缺失
3. **税务优化**：美国 TLH（税收损失收割）、境内个税优化策略无蓝图
4. **退休规划**：蒙特卡洛退休收入模拟、取款率策略（4% 法则等）无蓝图
5. **家族办公室功能**：多账户聚合、主从账户结构、受托人报告无蓝图

**优先级：P1** — 智能投顾是高频用户需求且可直接对应 Doramagic 的"工具交付"哲学

---

## Category 11: Insurance/Actuarial — 保险/精算

**覆盖评级：ABSENT**

### 现有蓝图
无任何直接相关蓝图。

bp-058（Copulas）可以极为间接地用于精算建模中的多元损失分布拟合，但这不构成实质覆盖。

### 关键缺口
1. **准备金计算**：Chain Ladder、Bornhuetter-Ferguson 等传统准备金方法无蓝图
2. **死亡率建模**：Lee-Carter、CBD 等死亡率预测模型无蓝图
3. **Solvency II**：欧盟保险监管框架（SCR/MCR 计算）无蓝图
4. **巨灾风险建模**：自然灾害损失分布、再保险定价无蓝图
5. **保险产品定价**：寿险、财险、健康险定价模型无蓝图

**优先级：P2** — 保险精算是专业细分市场，用户基数有限；建议作为长期扩展目标

---

## Category 12: Treasury/ALM — 资金管理/资产负债管理

**覆盖评级：THIN**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-013 | QuantLib | 利率曲线、债券定价（为 ALM 提供工具） |
| finance-bp-029 | rateslib 固收定价 | 利率衍生品定价、曲线拟合 |

### 冗余与重叠
- bp-013 与 bp-029 都做利率工具定价，但 bp-029 更专注利率曲线（rateslib 特色），bp-013 更全面

### 关键缺口
1. **流动性管理**：LCR/NSFR 计算（巴塞尔流动性监管）、现金流预测无蓝图
2. **FX 对冲**：外汇敞口识别 + 对冲策略优化（自然对冲 + 衍生品对冲）无蓝图
3. **IRRBB（利率风险）**：利率敏感性分析、EVE/NII 情景测试无蓝图
4. **现金池管理**：多账户现金归集、跨境资金调配无蓝图
5. **债券投资组合 ALM**：久期匹配、缺口分析、再投资风险无专用蓝图

**优先级：P1** — IRRBB 是银行监管强要求，FX 对冲是企业财务高频需求

---

## Category 13: Fixed Income Deep — 固收深度

**覆盖评级：ADEQUATE**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-013 | QuantLib | 完整固收定价（债券、MBS、利率衍生品） |
| finance-bp-019 | FinancePy | 债券、浮动利率、CDS |
| finance-bp-020 | gs-quant | 结构化产品、利率掉期 |
| finance-bp-029 | rateslib | 利率曲线、Repo 定价 |
| finance-bp-032 | bondTrader 可转债 | 可转债 T+0 散户策略 |

### 冗余与重叠
- bp-013、bp-019、bp-029 在固收定价工具上高度重叠，但侧重点不同（机构级/易用性/利率曲线专项）

### 关键缺口
1. **MBS/ABS 现金流建模**：住房抵押贷款支持证券的提前还款模型（PSA/CPR）、ABS 分层结构缺少专用蓝图
2. **信用违约互换（CDS）**：CDS 定价和对冲策略（bp-019 有基础覆盖但不完整）
3. **债券指数追踪**：被动固收策略、久期匹配指数追踪无蓝图
4. **中国债券市场特色**：国债逆回购、银行间市场特有工具缺失

**优先级：P2** — 已有 ADEQUATE 基础，MBS/ABS 是进阶需求

---

## Category 14: Lending/Payments — 贷款/支付

**覆盖评级：THIN**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-050 | skorecard 信用评分卡 | 贷款前端准入评分 |
| finance-bp-052 | openNPL 不良贷款管理 | 贷后 NPL 数据管理 |

### 冗余与重叠
- bp-050（前端准入）和 bp-052（贷后处理）无重叠，互补关系

### 关键缺口
1. **贷款发放系统（LOS）**：申请受理→信息核验→决策→放款的全流程无蓝图
2. **贷后催收**：逾期分层、催收策略优化（呼叫中心/短信/法律手段）无蓝图
3. **BNPL 先买后付**：分期决策、欺诈识别、资产证券化无蓝图
4. **支付处理**：支付路由、清算结算、对账系统无蓝图
5. **反欺诈**：实时交易欺诈识别（图神经网络、规则引擎）缺失

**优先级：P1** — 贷款发放和反欺诈是金融科技用户的高频需求，当前几乎零覆盖

---

## Category 15: Alternative Data — 另类数据

**覆盖评级：ADEQUATE**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-027 | OpenBB 金融研究平台 | 多源数据聚合（含另类数据接口） |
| finance-bp-033 | 散户实时行情系统 | A 股多数据源适配 |
| finance-bp-036 | tsfresh 时序特征工程 | NLP + 时序特征提取 |
| finance-bp-040 | ESG_AI 情感评分 | 新闻 NLP + 情感分析 |
| finance-bp-044 | FinGPT LLM 微调 | 财经文本情感分析 |

### 冗余与重叠
- bp-040 与 bp-044 的情感分析功能有重叠（前者基于 GDELT + Node2Vec，后者基于 LLM 微调）

### 关键缺口
1. **卫星图像分析**：停车场/工厂热图→经济活动估计无蓝图
2. **社交媒体情感**：Twitter/Reddit/雪球实时情绪追踪系统（bp-040 偏 ESG 新闻，不够通用）
3. **财报 NLP**：10-K/年报结构化解析、MD&A 情感提取无专用蓝图
4. **网络爬虫框架**：金融数据定向爬取+清洗+存储的标准化流程无蓝图
5. **供应链数据**：企业关系图谱、供应链风险信号无蓝图

**优先级：P2** — 另类数据是量化基金的差异化武器，但需求门槛较高，优先服务机构用户

---

## Category 16: Macro & Multi-Asset — 宏观与多资产

**覆盖评级：ADEQUATE**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-001 | freqtrade | 加密货币 |
| finance-bp-004 | qlib | 多资产量化 |
| finance-bp-013 | QuantLib | 利率/FX 衍生品 |
| finance-bp-019 | FinancePy | 跨资产定价 |
| finance-bp-020 | gs-quant | 宏观结构化产品 |
| finance-bp-043 | LEAN 多资产回测 | 股票/期货/期权/外汇多资产 |
| finance-bp-025 | xalpha | 中国基金/ETF |

### 关键缺口
1. **经济指标仪表板**：GDP/CPI/PMI 等宏观指标采集+可视化+与资产相关性分析缺少独立蓝图
2. **大宗商品**：商品期货定价（季节性、库存模型）无专用蓝图
3. **碳市场**：碳配额交易、绿色债券定价无蓝图
4. **FX 量化策略**：汇率预测、套息交易、FX 动量策略缺少专用蓝图（bp-013 有 FX 定价工具，但无策略框架）

**优先级：P2** — 宏观指标仪表板对研究型用户价值高，可通过 bp-027 (OpenBB) 部分满足

---

## Category 17: AI/LLM Finance — AI/LLM 金融应用

**覆盖评级：GOOD**

### 现有蓝图
| Blueprint ID | 名称 | 覆盖子需求 |
|---|---|---|
| finance-bp-010 | LLM 驱动股票分析 | AI 股票诊断、报告生成 |
| finance-bp-035 | FinRL RL 交易信号 | 强化学习信号生成 |
| finance-bp-044 | FinGPT LLM 微调 | 金融 LLM 微调流程 |
| finance-bp-045 | 多 Agent LLM 交易框架 | 多角色辩论、多 Agent 协作 |
| finance-bp-051 | FinRobot AI Agent 平台 | LLM Multi-Agent 金融分析 |
| finance-bp-053 | LOBFrame 深度学习 | 深度学习 LOB 预测 |
| finance-bp-054 | 多 Agent A 股分析 | A 股增强 AI 分析 |
| finance-bp-057 | Darts 时序预测 | LLM/ML 时序预测 |

### 冗余与重叠
- **Multi-Agent 框架高度冗余**：bp-045（TradingAgents）、bp-051（FinRobot）、bp-054（TradingAgents-CN）定位几乎相同，都是多 Agent 协作股票分析，差异仅在市场侧重（全球/全球+机构/A 股）
- bp-010 与 bp-054 的 AI 分析功能高度重叠

### 关键缺口
1. **NL-to-SQL/NL-to-Filter**：自然语言查询金融数据库（类 iWencai）的专用蓝图缺失
2. **金融报告自动生成**：结构化研报（背景+财务分析+估值+风险）的 LLM 生成管线缺少专用蓝图
3. **RAG 金融知识库**：金融文档检索增强生成（财报+研报+政策文件）无蓝图
4. **量价 + NLP 融合信号**：将传统量价因子与 NLP 情感融合的统一信号框架缺失

**优先级：P1** — NL-to-filter 和 RAG 金融知识库是 Doramagic 自身定位高度相关的领域，应优先补充

---

## Category 18: Knowledge & Education — 知识与教育

**覆盖评级：THIN**

### 现有蓝图
无直接针对"教育/百科"的蓝图。

以下蓝图有教育属性的侧面：
- bp-017（FinanceToolkit）：透明公式 + 带文档的指标计算，具教学属性
- bp-013（QuantLib）：完整的金融术语和定价概念覆盖
- bp-027（OpenBB）：内置文档和 API 参考，具参考百科属性

### 关键缺口
1. **金融百科蓝图**：类 Investopedia 的结构化金融概念图谱（概念→公式→例子→适用场景）无蓝图
2. **量化教程框架**：从零开始的量化入门教程系统（类 Quantopian 学院）缺失
3. **概念解释生成**：将蓝图中的技术概念转化为用户易懂语言的系统化机制（这更接近 Doramagic skill 的 context_acquisition 设计，而非独立蓝图）

**战略性备注：** 此类别在 Doramagic 的产品宪法下有特殊性——"不教用户做事，给他工具"。教育类蓝图本质上是"教用户"的，与产品灵魂有潜在冲突。建议将教育需求通过"知识晶体中的人话摘要"和"context_acquisition 的解释模块"来满足，而非单独建立教育类蓝图。

**优先级：P2** — 因产品哲学约束，此类别不建议作为独立蓝图扩展方向

---

## 汇总表

| # | 类别 | 覆盖评级 | 现有相关蓝图数 | 主要缺口 | 优先级 |
|---|------|---------|-------------|---------|--------|
| 1 | Opportunity Discovery | GOOD | 7 | NL 查询、板块追踪、事件驱动机会 | P1 |
| 2 | Analysis & Decision | GOOD | 7 | 研报生成、技术分析体系 | P1 |
| 3 | Quantitative Strategy | **EXCELLENT** | 16 | 统计套利、期权策略 | P2 |
| 4 | Portfolio Construction | **EXCELLENT** | 6 | 智能再平衡、因子风险模型 | P2 |
| 5 | Trade Execution | GOOD | 6 | 国内券商 API、OMS | P1 |
| 6 | Monitoring & Management | ADEQUATE | 5 | 实时风险预警、Brinson 归因 | P1 |
| 7 | Credit Risk | ADEQUATE | 3 | IFRS 9/CECL、PD/LGD/EAD | P1 |
| 8 | Market Risk | GOOD | 7 | FRTB、历史模拟 VaR | P1 |
| 9 | Regulatory & Compliance | **THIN** | 3 | AML/KYC、监管报告、A 股合规 | **P0** |
| 10 | Wealth Management | **THIN** | 3 | Robo-Advisor、退休规划 | P1 |
| 11 | Insurance/Actuarial | **ABSENT** | 0 | 全领域缺失 | P2 |
| 12 | Treasury/ALM | **THIN** | 2 | 流动性、IRRBB、FX 对冲 | P1 |
| 13 | Fixed Income Deep | ADEQUATE | 5 | MBS/ABS、CDS、中国债市 | P2 |
| 14 | Lending/Payments | **THIN** | 2 | LOS、反欺诈、BNPL | P1 |
| 15 | Alternative Data | ADEQUATE | 5 | 财报 NLP、社交媒体情感 | P2 |
| 16 | Macro & Multi-Asset | ADEQUATE | 7 | 经济指标仪表板、大宗商品 | P2 |
| 17 | AI/LLM Finance | GOOD | 8 | NL-to-filter、RAG 知识库 | P1 |
| 18 | Knowledge & Education | **THIN** | 0 | 与产品哲学冲突，不建议独立扩展 | P2 |

---

## 关键结论

### 1. 显著优势区（EXCELLENT/GOOD）：5 个类别
- **量化策略**（EXCELLENT）和**组合构建**（EXCELLENT）是最强覆盖区，分别有 16 和 6 个高质量蓝图。这反映了 Doramagic 当前知识库的核心竞争力在量化投资领域。
- **市场风险**（GOOD）和 **AI/LLM 金融**（GOOD）覆盖较充分，但都有针对性缺口需要补充。

### 2. 结构性空白（ABSENT/THIN）：6 个类别
- **监管合规**（THIN，P0）：金融机构的刚需，当前几乎零覆盖，是最紧迫的填补目标。
- **保险/精算**（ABSENT）：完全空白，但为细分专业市场，优先级可暂设 P2。
- **财富管理**（THIN）、**资金管理/ALM**（THIN）、**贷款/支付**（THIN）、**知识教育**（THIN）：4 类都是重要的金融服务细分市场，当前仅有边缘覆盖。

### 3. 内部冗余热点
- **事件驱动回测**：bp-002/005/038/042 四个高度同质蓝图，可考虑合并"关联" relations，避免用户选择困难
- **AI Multi-Agent 分析**：bp-045/051/054 三个几乎相同定位的蓝图，建议重新审视差异化定位，确保 known_use_cases 清晰区分

### 4. 优先级排序建议（按业务影响 × 当前空白度）

**立即行动（P0）：**
- `finance-bp-060`: 监管合规引擎（AML 规则+合规报告，可参考 great_expectations + AML 开源框架）

**短期扩展（P1，3 个月内）：**
- `finance-bp-061`: IFRS 9 / CECL 贷款损失准备计算（可参考 ifrs9models 或 open-risk/openNPL 扩展）
- `finance-bp-062`: 智能投顾全流程（Robo-Advisor，风险测评→资产配置→再平衡）
- `finance-bp-063`: 国内券商 API 接入框架（通用适配器，参考 easytrader 但走 API 而非 GUI）
- `finance-bp-064`: NL-to-filter 金融查询（自然语言→选股条件，LLM + 结构化查询）
- `finance-bp-065`: 贷款发起系统（LOS 流程框架）
- `finance-bp-066`: IRRBB 利率风险管理（银行账簿利率风险）

**中期扩展（P2）：**
- 保险/精算基础框架（1 个蓝图：准备金计算 + 精算生命表）
- MBS/ABS 现金流建模
- 经济指标宏观仪表板
- 财报 NLP 解析框架

### 5. 致 Doramagic 产品决策层的战略建议

当前 59 个蓝图呈现**量化/交易侧过饱和 + 银行/合规侧严重缺失**的不平衡状态。随着 Doramagic 进入企业金融机构市场（银行、保险、资管），合规（P0）、信贷（P1）、ALM（P1）三个方向的投入回报比最高，因为：
1. 这些需求有强监管驱动（不可跳过），用户愿意为高质量知识付费
2. 开源生态在这些领域比量化交易侧稀疏，Doramagic 的知识提炼价值更高
3. 与现有量化蓝图的互补性强，可形成"前台交易+中台风控+后台合规"的完整链条

---

*分析者：Claude Sonnet 4.6 | 2026-04-14*
*方法：基于 59 个 finance 蓝图 YAML 元数据 + 产品宪法 v2 + 用户需求类别定义*
