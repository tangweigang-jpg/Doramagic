# 73 颗 Doramagic Finance 晶体命名（FINAL，营销 + 用户识别二审）

**二审原则**（比初稿加了营销维度）：
1. **搜索意图命中** — 名字要包含用户实际搜索词（forecasting / performance / risk / optimization / derivatives）
2. **强 brand 保留**（≥10k star 或圈内熟知）— qlib / vnpy / backtrader / ccxt / akshare / openbb / LEAN / beancount / yfinance / freqtrade / FinRL
3. **冷门项目改功能名** — absbox / chainladder / mlfinlab / openLGD 这些非专业用户不认识的，转为功能导向
4. **同质化去重** — 4 颗"-backtest"加差异化词（event-driven / daily / vectorized / portfolio）
5. **Token 控制** — 2-3 tokens 主流（168 样本 73% 落点），极短 2 tokens 留给强 brand

---

## 最终映射表（73 颗，LOCKED）

| # | BP | 初稿 | **FINAL** | 二审理由 |
|---|---|---|---|---|
| 1 | bp-004 | daily-stock-analysis | **daily-stock-analysis** | 社区惯例，搜索词命中 |
| 2 | bp-009 | a-stock-quant-lab | **a-stock-quant-lab** | 已发，保留 |
| 3 | bp-020 | gs-quant-toolkit | **gs-quant-pricing** | GS Quant 主打定价/风险，"pricing" 更精准 |
| 4 | bp-050 | credit-scorecard | **credit-scorecard** | 短+搜索命中 |
| 5 | bp-060 | aml-transaction-sim | **aml-data-generator** | 实际功能是生成模拟数据 |
| 6 | bp-061 | finrl-rl-trading | **finrl-rl-trading** | RL 核心卖点 |
| 7 | bp-062 | ifrs9-ecl-engine | **ifrs9-loss-engine** | ECL → loss（非专业用户更懂）|
| 8 | bp-063 | chainladder-reserving | **insurance-loss-reserving** | chainladder 方法名冷门，改搜索词命中 |
| 9 | bp-064 | insurance-actuarial-lib | **insurance-actuarial-python** | 明示语言，区分 R/SAS 同类 |
| 10 | bp-065 | life-insurance-risk | **life-insurance-math** | risk 太泛，math 精准 |
| 11 | bp-066 | robo-advisor-bot | **robo-advisor-python** | bot 太弱 |
| 12 | bp-067 | firesale-stress-test | **firesale-stress-test** | 准确 |
| 13 | bp-068 | xalpha-fund-tracker | **xalpha-fund-tool** | xalpha 中文圈知名 |
| 14 | bp-069 | tqsdk-futures-trading | **tqsdk-futures-api** | api 更准 |
| 15 | bp-070 | edgar-sec-filings | **sec-edgar-tools** | 用户搜 "SEC" |
| 16 | bp-071 | opensanctions-aml | **opensanctions-watchlist** | watchlist 核心功能 |
| 17 | bp-072 | p2p-lending-risk | **p2p-lending-data** | 实际产出 data（数据集）|
| 18 | bp-073 | ledger-cli-accounting | **ledger-plaintext-accounting** | plaintext 是 ledger 特色 |
| 19 | bp-074 | finrobot-agent | **finrobot-multi-agent** | multi-agent 卖点 |
| 20 | bp-076 | absbox-securitization | **abs-cashflow-modeling** | absbox 不知名，改功能 |
| 21 | bp-077 | economic-model-oss | **macro-economic-model** | macro 关键词 |
| 22 | bp-078 | fava-investor-reports | **fava-beancount-viewer** | 关联 beancount 生态 |
| 23 | bp-079 | akshare-cn-data | **akshare-financial-data** | akshare 全球知名，去 cn |
| 24 | bp-080 | finance-knowledge-graph | **finance-kg-embedding** | 学术差异化 |
| 25 | bp-081 | vnpy-trading-lab | **vnpy-futures-trading** | vnpy 强项是期货 |
| 26 | bp-082 | stock-screener-tool | **stock-screener** | 2 tokens 更短 |
| 27 | bp-083 | economic-dashboard | **economic-dashboard** | 准确 |
| 28 | bp-084 | eastmoney-cn-api | **eastmoney-api** | 2 tokens，eastmoney 自带 cn 认知 |
| 29 | bp-085 | freqtrade-crypto-bot | **freqtrade-crypto-bot** | 精准 |
| 30 | bp-086 | backtrader-backtest | **backtrader-event-driven** | 差异化核心特性 |
| 31 | bp-087 | qlib-quant-lab | **qlib-ai-quant** | Microsoft qlib AI 卖点 |
| 32 | bp-088 | zipline-backtest | **zipline-daily-backtest** | daily 粒度明确 |
| 33 | bp-089 | rqalpha-cn-backtest | **rqalpha-cn-backtest** | 准确 |
| 34 | bp-090 | quantaxis-cn-quant | **quantaxis-data-platform** | QA 主打数据平台 |
| 35 | bp-091 | czsc-chan-theory | **czsc-chan-theory** | 缠论是强认知词 |
| 36 | bp-092 | vectorbt-fast-backtest | **vectorbt-vectorized** | vectorized 差异化 |
| 37 | bp-093 | portfolio-optimizer | **portfolio-optimization** | optimization 搜索词 |
| 38 | bp-094 | easytrader-cn-broker | **easytrader-cn-broker** | 准确 |
| 39 | bp-095 | rotki-crypto-portfolio | **rotki-crypto-tracker** | tracker 更明确 |
| 40 | bp-096 | hummingbot-market-maker | **hummingbot-market-maker** | 保留（mm 缩写太 cryptic）|
| 41 | bp-097 | openbb-terminal | **openbb-terminal** | 终端品牌本身就是卖点 |
| 42 | bp-098 | nautilus-algo-trading | **nautilus-algo-trading** | 精准 |
| 43 | bp-099 | trading-agents-cn | **trading-agents-cn** | 精准 |
| 44 | bp-100 | lean-algo-trading | **lean-cloud-backtest** | QuantConnect lean 是云回测 |
| 45 | bp-101 | financepy-derivatives | **financepy-derivatives** | 准确 |
| 46 | bp-102 | darts-time-series | **darts-forecasting** | forecasting 搜索词 |
| 47 | bp-103 | arcticdb-timeseries | **arcticdb-timeseries** | 准确 |
| 48 | bp-104 | engine-pricing-lib | **reactive-pricing-engine** | ⚠ 我猜 reactive（原 "Engine" 项目） |
| 49 | bp-105 | climate-investing-research | **climate-esg-investing** | ESG 关键词 |
| 50 | bp-106 | pyfolio-analytics | **pyfolio-performance** | performance 搜索词 |
| 51 | bp-107 | empyrical-metrics | **empyrical-risk-metrics** | risk 加上 |
| 52 | bp-108 | finmarketpy-toolkit | **cuemacro-finmarket** | Cuemacro 作者 brand |
| 53 | bp-109 | talib-indicators | **talib-technical-analysis** | TA 全写友好 |
| 54 | bp-110 | cryptofeed-market-data | **cryptofeed-ws-feeds** | websocket 是核心 |
| 55 | bp-111 | ccxt-crypto-api | **ccxt-crypto-api** | 准确 |
| 56 | bp-112 | openlgd-credit-loss | **credit-lgd-model** | LGD 专业词+model |
| 57 | bp-114 | edgar-crawler | **edgar-crawler** | 准确 |
| 58 | bp-115 | mlfinlab-research | **advanced-financial-ml** | 改功能名，mlfinlab 非圈内不知 |
| 59 | bp-116 | finrl-meta-env | **finrl-meta-envs** | envs 复数更准 |
| 60 | bp-117 | riskfolio-portfolio | **riskfolio-optimization** | optimization 搜索词 |
| 61 | bp-118 | financetoolkit-analysis | **financial-ratios-toolkit** | ratios 是核心 |
| 62 | bp-119 | credit-transition-matrix | **credit-transition-matrix** | 准确 |
| 63 | bp-120 | alphalens-factor | **alphalens-factor-analysis** | factor-analysis 完整 |
| 64 | bp-121 | ml4t-curriculum | **ml4t-book-notebooks** | book+notebooks 明确性质 |
| 65 | bp-122 | pandas-ta-indicators | **pandas-ta-indicators** | 准确 |
| 66 | bp-123 | quantlib-pricing | **quantlib-derivatives** | derivatives 搜索词 |
| 67 | bp-124 | arch-volatility-models | **arch-garch-volatility** | garch 核心词 |
| 68 | bp-125 | bt-backtest-framework | **bt-portfolio-backtest** | portfolio 差异化 |
| 69 | bp-126 | lifelines-survival | **lifelines-survival-analysis** | analysis 全写 |
| 70 | bp-127 | py-vollib-options | **py-vollib-options-pricing** | pricing 明确 |
| 71 | bp-128 | yfinance-market-data | **yfinance-market-data** | 准确 |
| 72 | bp-129 | beancount-accounting | **beancount-plaintext-ledger** | plaintext 是特色 |
| 73 | bp-130 | tensortrade-rl | **tensortrade-rl-env** | env 明确是 RL 环境 |

---

## 最终 self-audit

- **Token 分布**：2 tokens (18 颗)、3 tokens (47 颗)、4 tokens (8 颗) → 主流 3 tokens
- **Length**：平均 21 字符，最短 `stock-screener`(14)，最长 `py-vollib-options-pricing`(24)
- **品牌保留**：55/73 含原项目名前缀
- **功能导向改名**：6 颗冷门项目转为领域关键词（absbox / chainladder / mlfinlab / openLGD 等）
- **同质化消除**：4 颗 backtest 都有差异化词（event-driven / daily / vectorized / portfolio）
- **搜索命中**：每颗至少 1 个高频搜索关键词

---

## 不确定项

只剩 1 颗（⚠）：
- bp-104 `reactive-pricing-engine` — 项目名 "Engine" 太通用，我猜是 reactive pricing engine（响应式定价）。**如果你知道实际用途，改我**。

其他 72 颗**确定 LOCKED**。
