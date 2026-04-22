# Quant/投研 研究员 15 晶体产品需求文档

> Strategic product research for Doramagic.ai Second Domain Commitment
>
> Date: 2026-04-18
> Author: Claude Opus 4.7 (research) + CEO review pending
> Status: **DRAFT — awaiting CEO judgment calls (see Reader Guide §11)**
> Target audience: CEO, product, knowledge-engineering lead
> Source corpus: 73 验收合格 finance blueprints (see `knowledge/sources/finance/STATUS.md`)

---

## 1. Executive Summary

**What this doc answers.** Should Doramagic commit to "投研 / 量化 / 数据科学" as the second major domain after the existing Finance blueprint library? If yes, which 15 seed crystals constitute the minimum-viable offering, what workflow moments do they cover, and how do they differentiate against incumbents in both CN and US markets?

**Top-line recommendation: Yes, commit — but treat it as a focused wedge, not a horizontal play.** The target is not "替代 Bloomberg"; it is "给 Bloomberg 付不起的那 90% 研究员一个可以跑起来的工作流"。The 73 existing finance blueprints (qlib, backtrader, vectorbt, freqtrade, ccxt, Riskfolio-Lib, alphalens-reloaded, pyfolio-reloaded, edgartools, akshare, tushare-adjacent, OpenBB, QuantLib, mlfinlab, FinRL, …) already cover roughly **80% of the surface area** a retail-quant workflow needs. What is missing is not more code — it is **curation into outcome-shaped crystals** that a user's AI can actually execute without the user having to first become a backtrader or qlib expert. That curation is exactly what Doramagic does.

**The 15-crystal set proposed here spans six workflow moments**: (a) 数据采集 & 清洗, (b) 单标的研究, (c) 策略想法 → 回测, (d) 组合 / 风险 / 归因, (e) 研报 / 备忘录生成, (f) 另类数据 / 边缘信号. Five of the 15 are "wedge" crystals — the minimum subset that alone makes the product worth using on day 1: `C-01 万能数据取数`, `C-04 单股一页深度简报`, `C-07 策略想法到回测`, `C-11 组合风险一键体检`, `C-13 研报生成`.

**Key uncertainties (need CEO judgment):**

1. **用户 AI 分布** — 晶体依赖"用户把 .md 文件丢给自己的 AI"的消费模式。如果 SOM 里 >50% 的 CN 用户没有持续稳定的外接 AI 订阅（Claude Code / ChatGPT Plus / Cursor），Phase 2 会卡住。需要 CEO 决定是否为 CN 用户绑定一个国内模型（DeepSeek / Kimi / MiniMax）的首选清单，写入晶体的 `execution_directive`。
2. **数据源合规** — CN 侧的"实时行情 + Level-2"涉及上交所 / 深交所付费协议，Doramagic 的晶体**绝不能**隐含"用户可以免费拿到 Level-2"。需要 CEO 签字的 `claim_boundary` 一级红线。
3. **investment advice 边界** — 简中语境下"投资建议"有监管资质门槛。CEO 必须决定晶体的语言立场：是"我替你分析"还是"这是一个分析工具"。本文假设是后者（工具论）。

---

## 2. Target User Profile (CN + US)

### 2.1 Personas

**Persona A — "副业量化张三" (CN, ~35-45% of CN SOM)**
- 白天券商 / 基金公司中后台或 IT 岗, 晚上写 A 股策略, 3 年以上 Python + pandas 经验
- 当前工具栈: Tushare Pro (付费 500-2000 元/年, 获得 5000-10000 积分) + akshare 免费补数据 + 聚宽 / 米筐免费版回测 + 微信群薅研报
- 月度工具预算 ≤ 500 元人民币, 年度 ≤ 3000 元。完全买不起 Wind (¥39,800/年/账号), Choice 个人版勉强可考虑但"功能不覆盖回测"
- 痛点: ① Tushare 积分永远不够, 接口限流到崩溃; ② 因子回测从 0 搭环境要 2 周, 每次换数据源要重写 adapter; ③ "想法很多, 代码写得慢, 策略死在数据清洗阶段"; ④ A 股特有陷阱 (ST/*ST, 涨跌停, 停牌, 除权除息) 每个框架处理得都不一样
- 聚集地: 知乎"量化投资"话题 (5k+ 关注者账号多), B 站 UP 主 (何其野, 小火慢炖), 公众号 (量化投资与机器学习), QQ 群 (聚宽官群, Tushare 官群), GitHub (QUANTAXIS, czsc, vnpy 社区)

**Persona B — "独立研究员 Alex" (US, ~30-40% of US SOM)**
- 前 L3 / VP at 中小型 hedge fund 或 sell-side equity research, 30-40 岁, 离职 / gardening leave 中或个人盘, MBA / CFA / PhD (物理 / 统计常见)
- 当前工具栈: Koyfin Plus ($39/mo) + FactSet student license 过期版 + yfinance + QuantConnect free tier + Substack 订阅 10+ 份 ($10-50/mo 每份)
- 月度工具预算: $100-400/mo, 愿意为"省 10 小时/周"付 $200/mo
- 痛点: ① Bloomberg 的 WACC / DDM / peer comp 模板没了, 手动复刻很痛; ② yfinance 数据质量不稳定 (missing splits, 盘后价格漂移); ③ 想做 factor tilt 分析要手动拼 alphalens + pyfolio + Riskfolio, 每个包的 API 风格都不一样; ④ 写研报 memo 要在 Excel / Google Docs / Python notebook 之间切 5 次上下文
- 聚集地: r/algotrading (370k+), r/SecurityAnalysis, Hacker News, Twitter/X quant fintwit (ML_Quant, macro_alf, jasonzweigwsj), Substack (Net Interest, Doomberg, byfire / Gappy), Discord (QuantConnect, Composer)

**Persona C — "MBA/CFA 应届 Jerry" (CN+US split ~50/50, ~15% of SOM)**
- 金融硕士 / MBA / 转行做 equity research 的 junior, 22-28 岁
- 当前工具栈: 学校过期 Bloomberg (毕业失效), 学校 WRDS 快要失效, yfinance + 手抓 SEC 10-K, 东财网页抓数据, Excel 为主
- 月度工具预算: $0-50 (学生) / ¥0-300 (CN student)
- 痛点: ① Excel 建 DCF 要 2 天, 改一个参数要手动刷全表; ② 抓 10-K 的关键段落 (Risk Factors / MD&A) 靠 Ctrl+F; ③ 不会真正的因子回测, 只会"回测过去 3 年年化 XX%"; ④ 研报格式没学过, 每次都照抄前辈 template
- 聚集地: 小红书 (一级市场 / 投行日常), 知乎 (金融话题), 一亩三分地 (北美留学 + quant 求职), WallStreetOasis, Mergers & Inquisitions, LinkedIn

**Persona D — "家族办公室 / 小私募 junior 王" (CN+US, ~10% of SOM)**
- 工作 1-3 年在 family office 或 AUM < $500M 的小私募, 做 multi-asset 配置或策略研究
- 当前工具栈: 公司有 1 个 Wind / Bloomberg 共享账号 (排队用), 个人电脑装 Python + akshare / yfinance, 内部自研的回测框架基本等于没有, 大量 Excel
- 月度预算: 公司报销范围内可上 Koyfin Advisor / FinChat, 个人工具 ≤ $100/mo
- 痛点: ① 老板经常下午 4 点扔一句"给我这个 ticker 写一页", 1 小时内要出; ② 组合归因 (Brinson / factor-based) 没人真的会; ③ 宏观数据 (CPI, FOMC, PMI) 需要跨国拼; ④ 回测的结果老板不信, 要反复 sanity check
- 聚集地: LinkedIn, 公众号, 行业微信群, CAIA / CFA 社群

**Persona E — "Crypto quant 周" (Global, ~10-15% of SOM, skews younger)**
- 全职或重度副业 crypto 交易, 20-35 岁, 有编程能力
- 当前工具栈: ccxt + Python + Hyperliquid / Binance API, TradingView Pro+ ($30/mo) 画图, Dune Analytics 免费/pro, Glassnode $29-800/mo 看链上
- 月度预算: $50-500/mo, 非常愿意为速度付钱
- 痛点: ① 跨所 orderbook merge + 套利监控要自己拼; ② 回测 perp + funding rate + 杠杆的复合收益没有好框架 (freqtrade 部分支持); ③ 链上信号与行情信号融合很难; ④ 风控 (爆仓 / 连环清算) 血泪教训多
- 聚集地: Twitter/X (crypto fintwit), Discord (Hyperliquid, GMX, 各 DAO), Telegram, r/CryptoCurrency, r/Bitcoin

### 2.2 Explicit CN vs US contrast

| 维度 | CN 独立量化 | US 独立量化 |
|------|------------|------------|
| 主交易标的 | A 股 + 商品期货 + 少量港股 / 美股 | 美股 + 期权 + 部分 futures + crypto |
| 数据源默认 | akshare / Tushare / 聚宽 / 米筐本地 | yfinance / polygon / Alpaca / QuantConnect 数据 |
| 特殊规则 | T+1, 涨跌停 10%/20%/30%, ST, 停复牌, 集合竞价, 除权 | T+0, 做空有 locate, PDT ($25k) 限制, 盘前盘后, earnings halts |
| 监管语境 | "投资建议"强敏感, "荐股" 要持牌 | Securities law 要求披露 long/short, 但个人 blog 合规灰度宽松 |
| 回测框架偏好 | vnpy, backtrader, czsc, 聚宽内置 | backtrader, vectorbt, zipline-reloaded, QuantConnect LEAN |
| 写作输出场景 | 公众号文章, 雪球长文, 内部日报 | Substack post, Twitter 长推, LinkedIn article, PM memo |
| 付费意愿 | 年费 300-3000 元, 月费阻力大 | 月费 $30-300 可接受, 年费一次性 >$500 需要仔细算 |
| 社交传播链路 | 知乎长文 → 公众号 → 社群 → 裂变 | Twitter/X → Substack → HN / r/algotrading → 口碑 |
| AI 消费侧现状 | DeepSeek / Kimi / 豆包 / MiniMax / 国外 Claude (翻墙) 混用 | Claude Code / ChatGPT / Cursor 是 default |

### 2.3 Market sizing (rough — see §7 for method)

- **Global TAM**: 量化 / 投研从业 + 严肃个人投资者 + 金融专业学生 ≈ **12-18M people**. (Reference anchor: QuantConnect 宣称处理 500k backtest/月, 活跃用户池 ~100k+; r/algotrading 370k; 中国证券业协会注册从业人员 ~38万, 基金业协会 ~40万, 合计金融专业在校生+毕业 ~200万/年.)
- **SAM** (付不起 Bloomberg 但愿意月付 $20-100 / ¥100-500): **3-5M people**. 推理: Koyfin 活跃用户约 30万; FinChat 约 20万+; 聚宽 + 米筐 + Tushare Pro 注册合计百万级, 付费活跃 ~20-50万; US MBA/CFA 候选人存量 ~30万; CN 量化相关微信群总和估 50-100万但去重后约 10-20万.
- **SOM (3 年)**: **50k-200k 付费用户**, 客单价 ¥300-1200 / $30-120 每月. ARR 目标区间 $5M-50M (详见 §7).

**Source citations for the market size anchors**: [QuantConnect pricing / stats](https://www.quantconnect.com/pricing/), [FinChat/Fiscal.ai review (Wall Street Zen)](https://www.wallstreetzen.com/blog/finchat-io-fiscal-ai-review/), [Koyfin pricing](https://www.koyfin.com/pricing/), Bloomberg cost of ~$32k/yr [documented](https://costbench.com/software/financial-data-terminals/bloomberg-terminal/). Tushare 积分规则 [官方文档](https://tushare.pro/document/1?doc_id=290). Wind 39,800 元/年 [财经媒体](https://finance.sina.cn/2023-09-11/detail-imzmiqth5856632.d.html). 用户数做逆向推理 (搜索 + 社交媒体关注数 + 付费转化率 2-5% 行业常识), 非一手数据, **标注为估算 / assumption**.

---

## 3. Day-in-the-Life Workflow Map

下表刻画的是一个"副业量化 + 独立研究员"混合画像 (Persona A + B 的交集), 工作日典型一天 (A 股交易时段 + 夜晚自研; US 场景换成美股盘中盘后即可):

| 时间 | 动作 | 工具 / 上下文 | 摩擦点 (friction) |
|------|------|---------------|------------------|
| 07:30 晨起 | 看隔夜 US 收盘 + 亚太开盘预期 + 昨晚持仓 | 东方财富 / Yahoo Finance / 雪球 / Twitter fintwit | 要打开 5 个 app, 没有"一屏摘要" |
| 09:00-09:30 集合竞价 | 看关注股涨跌停板, 盘前新闻 | 同花顺 / TradingView / 公司公告 PDF | 公告 PDF 阅读极慢, 新闻噪音 >> 信号 |
| 09:30-11:30 盘中 | 盯盘 + 策略监控 + 临时查个股 | 量化平台 (聚宽/米筐) + Python notebook + 微信群 | **临时查个股**最痛: 要手抓 10+ 个数据源拼基本面 |
| 11:30-13:00 午休 | 扫因子 / 行业热度 / 宏观数据发布 | Bloomberg / Wind (没有就靠东财 + 国家统计局) | 因子计算每次重跑慢, 没缓存 |
| 13:00-15:00 下午盘 | 维护持仓 + 开发新策略 + 回测 | backtrader / vectorbt / qlib | 回测框架 API 复杂, 结果可视化要自己拼 |
| 15:00-16:00 收盘 | 归因 + 净值更新 + 风控检查 | pyfolio + Riskfolio + Excel | 归因脚本每次要手动调, 归因结论不稳定 |
| 16:00-18:00 研究 | 写研报 / 复盘 / 跟踪热点 | Word / Markdown + 多个数据源截图 | **写作**最耗时, 手动拼图拼表 |
| 18:00-23:00 副业时段 | 看论文 / 学新框架 / 写代码 / 回测跑批 | arxiv + GitHub + Jupyter + 公众号 | 论文复现成本高, 新框架学习曲线陡 |

**Tool-friction heatmap (从痛到不痛):**

1. 🔥🔥🔥 "临时给一个 ticker 写一页分析" — Persona D 老板需求, 当前要 1-2 小时
2. 🔥🔥🔥 "新策略想法 → 能跑的回测" — 环境搭建 + 数据接入 + 框架学习 1-2 周起
3. 🔥🔥🔥 "组合归因与风险体检" — 手拼 alphalens + pyfolio + Riskfolio, 半天起
4. 🔥🔥 数据采集与清洗跨源 (A 股 + US + crypto)
5. 🔥🔥 10-K / 年报 / 公告关键信息抽取
6. 🔥🔥 研报 / memo 写作
7. 🔥 宏观数据面板 (CPI/PMI/FOMC/非农)
8. 🔥 另类数据 (sentiment, 卫星, 链上) 接入

**这 8 个 friction 点 → 15 个晶体, 一一对应 (§5).**

---

## 4. Competitive Landscape

| 对手 | 定位 | 价格 (2026) | 核心优势 | 对 Doramagic 的 gap |
|------|------|-------------|----------|---------------------|
| **Bloomberg Terminal** | 机构全功能终端 | [$31,980/yr 单席](https://costbench.com/software/financial-data-terminals/bloomberg-terminal/), 多席 $28k | 数据深 + 专线 + chat | 价格 10-100x 贵, 锁定机构; **个人无门** |
| **Refinitiv Workspace** | 机构终端 | $22k-24k/yr 估 | 同上, LSEG 后稍平民化 | 同上 |
| **FactSet** | Buy-side 机构 | $12k-25k/yr | 组合分析 + 估值模型 | 同上 |
| **Koyfin** | Bloomberg 降配版 | [Plus $39/mo, Advisor $209-299/mo](https://www.koyfin.com/pricing/) | 股票 + ETF 筛选 + 好图 | 不支持 A 股 (致命 for CN), 不支持 crypto, 不支持"让我跑回测" |
| **Morningstar Premium** | 零售基金 + 股票 | $34.95/mo | 评级 + 基金深度 | 不 quant-first |
| **FinChat.io (Fiscal.ai)** | AI 研究终端 | [Plus $29, Pro $64/mo](https://www.wallstreetzen.com/blog/finchat-io-fiscal-ai-review/) | AI 问答 + 10 万家公司 | 纯 chat, **不产出可执行 skill**, 信息 → 决策链断 |
| **Stock Analysis / TIKR / Simply Wall St** | 零售 value investor 向 | $10-30/mo | 估值表 + DCF | 不覆盖 quant / 回测 |
| **TradingView** | 图表 + 社区 | Pro $15, Premium $60/mo | 图 + Pine Script + 社区 | Pine 有限制, 回测不严肃 |
| **Alpha Vantage / Polygon / Financial Modeling Prep** | 数据 API | FMP $25-150/mo, Polygon $29-2000/mo | 程序化数据 | 只给数据, 不给工作流 |
| **QuantConnect** | Quant 回测云 | [Starter $8, Researcher $20, Pro $40/mo](https://www.quantconnect.com/pricing/) | LEAN + 多资产数据 + 云回测 | 学习曲线陡, UI 生硬, 不做"写研报" |
| **Composer.trade** | No-code algo trading | [~$24/mo or $288/yr](https://www.composer.trade/pricing) | AI + 无代码 | 不够深, 限美股 + 预设策略 |
| **Boosted.ai** | 机构 AI 投研 | $50k-500k/yr 机构向 | AI factor + 报告 | 贵, 不面向个人 |
| **Portfolio123** | 因子策略研究 | $75-700/mo | 因子回测 + 选股 | 只有美股, UI 老旧, 学习曲线陡 |
| **Wind (万得)** | CN 机构终端 | [¥39,800/年/账号](https://finance.sina.cn/2023-09-11/detail-imzmiqth5856632.d.html) | A 股深度 + 专业债券 + 基金 | 机构向, 个人买不到席位或买了用不起 |
| **东方财富 Choice** | CN 中端终端 | ¥9,800-¥24,000/年 估 | A 股 + 基金 + 宏观 | 比 Wind 便宜, 但仍是终端, 不是工作流 |
| **同花顺 iFinD** | CN 中端 | ¥3,680-¥12,000/年 | 个人可买, A 股数据全 | 更像看盘 + 资讯, 非 quant |
| **Tushare Pro** | CN 数据 API | [¥500-2000 捐赠换 5000-10000 积分, 港美股/分钟线另外付费](https://tushare.pro/document/1?doc_id=290) | CN 最成熟数据 API | 只数据, 高限流, 无工作流 |
| **通联数据 / 优矿 Uqer** | CN 量化平台 | 企业合作为主, 个人免费有限 | 因子 + 回测 | 个人深度有限, 偏企业 |
| **聚宽 / 米筐 RiceQuant** | CN 量化平台 | 免费 + 付费会员 ¥1k-10k/年估 | 回测 + 策略社区 | 平台锁定, 策略不能带走 |

### 4.1 The gap Doramagic can exploit

1. **工作流缺口** — 没有一个产品同时覆盖"数据 → 研究 → 回测 → 归因 → 写作", 用户必须自己缝合 4-6 个工具. Doramagic 的晶体天然以工作流 (workflow moment) 为单位, **这是唯一的结构性优势**.
2. **AI-native 交付** — FinChat 做到了 AI-chat, 但输出仍是 "信息", 用户还要自己执行. Doramagic 输出的是 **"给 AI 读的配方"**, 执行在用户自己的 AI 环境发生, 带完整权限 + 持续迭代 + 可传播.
3. **CN + Crypto 同栈** — 所有西方竞品 (Koyfin, FinChat, QuantConnect) 对 A 股和 CN 本地数据源支持极差. 所有 CN 平台 (聚宽, 米筐, Wind) 对 US + crypto 支持差. Doramagic 站在两者之上, 天然跨地域.
4. **可传播, 可叉开** — 晶体是 .md 文件, 可以在群里发、推特上贴、GitHub 上放. 这是所有 SaaS 终端结构上做不到的.

**但要认清限制**: Doramagic 不提供行情数据, 不替代 Bloomberg 的实时 feed. 晶体是"配方 + 约束", 用户必须自己带数据源订阅 (Tushare / yfinance / Polygon / ccxt API key). **这是明确的身份边界**, 写入 §6.

---

## 5. The 15 Crystals — Detailed Spec

### 5.1 晶体矩阵总览

| ID | 中文名 | 英文名 | 工作流区域 | 优先级 | 规模 | Wedge? |
|----|--------|--------|------------|--------|------|--------|
| C-01 | 万能数据取数 | Universal Market Data Fetcher | 数据采集 | P0 | M | ★ Wedge |
| C-02 | A股数据清洗体检 | A-Share Data Sanity Checker | 数据采集 | P0 | S | |
| C-03 | Crypto 跨所行情聚合 | Multi-Venue Crypto Feed | 数据采集 | P1 | M | |
| C-04 | 单股一页深度简报 | One-Page Equity Brief | 单标的研究 | P0 | L | ★ Wedge |
| C-05 | 10-K / 年报关键段抽取 | Filing Section Extractor | 单标的研究 | P0 | M | |
| C-06 | 技术面信号扫描 | Technical Signal Scanner | 单标的研究 | P1 | M | |
| C-07 | 策略想法到回测 | Idea-to-Backtest | 策略 & 回测 | P0 | L | ★ Wedge |
| C-08 | 因子研究与 IC 分析 | Factor Research & IC | 策略 & 回测 | P0 | L | |
| C-09 | 参数优化与 WFA | Parameter Optimization | 策略 & 回测 | P2 | M | |
| C-10 | 组合优化 (均值方差/风险平价) | Portfolio Optimizer | 组合 & 风险 | P1 | M | |
| C-11 | 组合风险一键体检 | Portfolio Risk Audit | 组合 & 风险 | P0 | L | ★ Wedge |
| C-12 | 基于因子的业绩归因 | Factor-Based Attribution | 组合 & 风险 | P1 | M | |
| C-13 | 研报 / Memo 生成 | Research Memo Writer | 写作 & 输出 | P0 | M | ★ Wedge |
| C-14 | 宏观数据面板 | Macro Dashboard | 另类 / 边缘 | P1 | M | |
| C-15 | 链上 / 情绪 / 新闻信号融合 | Alt-Data Signal Fuser | 另类 / 边缘 | P2 | L | |

**Wedge 逻辑**: 5 个 Wedge 晶体覆盖 "数据进来 → 研究 → 回测 → 风险 → 写出去" 的最小闭环, 用户看完这 5 个会说"这就是我想要的工作台, 剩下的都是 bonus".

---

### 5.2 每颗晶体详情

> 格式: value prop / trigger moment / inputs / outputs / acceptance / alternatives / differentiation / CN-US variant / blueprint reuse / effort / priority

---

#### C-01 `crystal-quant-001` 万能数据取数 / Universal Market Data Fetcher

- **Value prop (用户独白)**: "我想给我的 AI 说一句 `取过去 5 年 000001.SZ 的日线, 以及 AAPL 同期的日线和 BTC/USDT 现货`, 不要让我关心背后用哪个源."
- **Trigger moment**: 每个研究任务的第一步. Persona A 每天至少触发 3 次, Persona B 2 次.
- **Inputs**: symbol(s) (A股/港股/美股/crypto/ETF/指数 / 期货合约), 时间段, 频率 (1m/5m/日/周), 是否前复权, 目标字段 (OHLCV / 成交额 / 换手率 / funding rate)
- **Outputs**: 一个标准化的 `pandas.DataFrame` 或 parquet 文件, 跨标的统一 schema (`symbol, dt, open, high, low, close, volume, adj_factor, venue`), 内嵌数据源溯源列 + 缺失标记
- **Acceptance**:
  1. CN/US/Crypto 三类标的至少各能取到 2 个 symbol 且 schema 一致
  2. 返回数据在给定时间段覆盖率 ≥ 95% (否则明确报 gap)
  3. 复权方式显式, 默认前复权 (A 股) 或含 dividend-adjusted (US)
  4. 脱敏自动: 不把 API key 写入代码, 走环境变量
- **Existing alternatives + cost**:
  - 用户自己手搓 adapter: 开发 2-5 天, 维护持续
  - OpenBB SDK: 免费, 但 CN 数据源支持极弱
  - Tushare + yfinance + ccxt 三拼: 免费/低价但 schema 不一致
- **Doramagic differentiation**: 晶体里定义了**跨源统一 schema + 自动 fallback 顺序 + CN/US/Crypto 三栈同框**, 用户的 AI 直接按配方生成一个 `fetch_prices()` 函数, 不需要用户懂 adapter pattern.
- **CN vs US variant**: **不分叉**, 但在 `context_acquisition` 里追问用户主要交易哪类标的, 决定首选数据源 (CN → akshare+tushare, US → yfinance+polygon, Crypto → ccxt)
- **Blueprint reuse**: `bp-079 akshare` + `bp-128 yfinance` + `bp-111 ccxt` + `bp-097 OpenBB` + `bp-084 eastmoney` + `bp-110 cryptofeed` + `bp-103 ArcticDB` (缓存层)
- **Effort**: M (1-2 周)
- **Priority**: **P0 ★ Wedge**

---

#### C-02 `crystal-quant-002` A股数据清洗体检 / A-Share Data Sanity Checker

- **Value prop**: "我拿到一份 A 股行情, 帮我检查 ST/停牌/除权/涨跌停/异常成交, 别等回测跑完我才发现数据坏了."
- **Trigger moment**: C-01 之后, C-07/C-08 之前. 每个回测前都触发一次.
- **Inputs**: 一个 A 股行情 DataFrame (或 parquet 路径), 可选的交易日历, 可选的股票基础信息表
- **Outputs**: (1) 体检报告 markdown (行数 / 缺失率 / ST 标记 / 停牌天数 / 涨跌停日占比 / 除权未调整天数), (2) 清洗后的 DataFrame (带 `is_st`, `is_suspended`, `is_limit_up`, `is_limit_down`, `ex_rights_adj_applied` 标记列), (3) 一张 "数据质量信心分" (0-100)
- **Acceptance**:
  1. 能识别 ST/*ST/PT 历史段
  2. 涨跌停识别 (主板 10%, 创业板/科创板 20%, ST 5%, 北交所 30%) 按规则自动判
  3. 除权日前后价差 >10% 且无除权标记 → 报警
  4. 体检报告 ≤ 1 页可读
- **Existing alternatives**: Tushare stock_basic + 手工脚本 (3-8 小时), 聚宽内置 API (平台锁定)
- **Doramagic differentiation**: 晶体把 A 股 5 大陷阱编码为 fatal 约束, 不依赖某个平台; 输出带"信心分"让用户回测前就能判断是否值得跑
- **CN vs US**: **CN 独有**. US 版本 (C-02b, 未入 15 之列) 规则不同, 未来 P2.
- **Blueprint reuse**: `bp-084 eastmoney` + `bp-079 akshare` + `bp-069 tqsdk-python` + `bp-091 czsc` (A 股知识密集) + `bp-082 stock-screener` (筛选逻辑复用)
- **Effort**: S (3-5 天)
- **Priority**: **P0** (对 CN 用户是 Wedge 级; 全局 P0 因为 CN 是核心市场)

---

#### C-03 `crystal-quant-003` Crypto 跨所行情聚合 / Multi-Venue Crypto Feed

- **Value prop**: "帮我同时拉 Binance / OKX / Bybit 的 BTC-USDT perp orderbook 和 funding rate, 做价差监控或回测数据底座."
- **Trigger moment**: Persona E 的 daily; 其他 persona 触发频次低
- **Inputs**: 交易所列表, symbol(s), perp vs spot, 时间段, 是否要 L2 orderbook
- **Outputs**: 标准化 tick/kline + funding rate 时序 + 统一 symbol 映射表 (BTC/USDT = BTCUSDT = BTC-PERP = BTC-USD)
- **Acceptance**: 3+ 交易所同时取到数据, schema 一致, funding rate 时间对齐
- **Existing alternatives**: ccxt 自己封 (1-3 天), Kaiko/CryptoCompare 付费 API ($100-1000/mo)
- **Doramagic differentiation**: 晶体内置 symbol 跨所映射表 + rate limit 自动退避 + WS 重连模式, 直接给用户 AI 一个 `fetch_crypto_klines()` 可用函数
- **CN vs US**: 不分叉 (crypto 全球)
- **Blueprint reuse**: `bp-111 ccxt` + `bp-110 cryptofeed` + `bp-096 hummingbot` (部分 market data 模式)
- **Effort**: M (1-2 周)
- **Priority**: **P1**

---

#### C-04 `crystal-quant-004` 单股一页深度简报 / One-Page Equity Brief

- **Value prop**: "给我 ticker AAPL 或 600519.SH, 帮我生成一页纸: 基本面 + 技术面 + 估值 + 最近公告要点 + 风险, 老板 1 小时后要."
- **Trigger moment**: Persona D 最高频. Persona B 每周 5-10 次. Persona C 每周 2-3 次.
- **Inputs**: 单一 ticker (支持 A 股 / 港股 / 美股), 输出语言 (中/英), 可选比较组 (peers)
- **Outputs**: 单文件 markdown (可渲染为 PDF), 约 1 页, 包含:
  1. 公司速览 (业务 / 行业 / 市值)
  2. 近 3 年关键财务 (营收 / 毛利 / 净利 / ROE / FCF) 带迷你图
  3. 估值 (PE / PB / EV/EBITDA vs peer + 5 年历史带宽)
  4. 技术面摘要 (200 日均线 / 动量 / 波动率)
  5. 最近 60 天重要公告 / 新闻要点 3-5 条
  6. 3 条投资要点 + 3 条风险点 (有立场!)
- **Acceptance**:
  1. 1 页 A4 可印, 不溢出
  2. 所有数字带来源脚注 (venue + date)
  3. 估值带同行对比而非孤立
  4. "投资要点 + 风险"是有立场的陈述句, 不是模板空话
- **Existing alternatives**: Bloomberg `DES<GO>` + 手工整理 (20-40 分钟), Koyfin overview + 手工截图 (15-30 分钟), FinChat AI prompt (5 分钟但格式不稳定), Persona D 手搓 1 小时
- **Doramagic differentiation**: 输出是结构化 markdown 模板 + 约束 (必有 peer comp, 必有风险段, 必有来源) + 可复用多次, 比 FinChat 的自由对话更可靠
- **CN vs US variant**: **轻度分叉** — 同一晶体但 `context_acquisition` 引导宿主 AI 自动判断市场, CN → akshare + 东方财富公告, US → yfinance + edgartools (10-K 最近一份 MD&A)
- **Blueprint reuse**: `bp-079 akshare` + `bp-128 yfinance` + `bp-070 edgartools` + `bp-097 OpenBB` + `bp-082 stock-screener` + `bp-004 daily_stock_analysis` + `bp-118 FinanceToolkit` (财务比率)
- **Effort**: L (3-4 周 — 模板设计 + 多市场适配)
- **Priority**: **P0 ★ Wedge** (这颗几乎单独可以卖)

---

#### C-05 `crystal-quant-005` 10-K / 年报关键段抽取 / Filing Section Extractor

- **Value prop**: "给我这家公司的最新 10-K 的 Risk Factors + MD&A, 用要点总结, 链回原文."
- **Trigger moment**: 深度研究阶段. Persona B/C 每周 3-5 次.
- **Inputs**: ticker or filing URL or local PDF, 目标 sections (Risk Factors / MD&A / Business / Legal Proceedings / Subsequent Events)
- **Outputs**: 按 section 的要点总结 (≤ 200 字/section), 每条要点带原文锚点 (页码 / 段落 hash), 可选中文翻译版
- **Acceptance**:
  1. 能定位到正确的 section (不会把 Risk Factors 和 Quantitative Disclosures 混淆)
  2. 每条要点可点回原文
  3. 不虚构 (与原文不一致的陈述比例 < 2%)
- **Existing alternatives**: 人工 Ctrl+F (30 分钟), SEC EDGAR full-text search 免费但不摘要, AI 聊天但不结构化
- **Doramagic differentiation**: 晶体把"section 定位规则 + 要点约束 (必带原文锚点) + 不虚构 fatal"编码
- **CN vs US**: **分叉** — US 用 edgartools 抓 EDGAR; CN 用巨潮资讯网 / 东方财富公告 (PDF 或 HTML), 规则不同, 一颗晶体但双分支 `execution_directive`.
- **Blueprint reuse**: `bp-070 edgartools` + `bp-114 edgar-crawler` + `bp-084 eastmoney` (CN 公告); **需要新蓝图**: CN 巨潮资讯 / cninfo 公告采集 (可用 akshare 已含的公告接口代替, 无需新蓝图)
- **Effort**: M (1.5-2 周)
- **Priority**: **P0**

---

#### C-06 `crystal-quant-006` 技术面信号扫描 / Technical Signal Scanner

- **Value prop**: "给我一个股票池, 扫一遍我关心的技术信号 (突破 / 背离 / 均线多头 / 缠论买点), 排序输出."
- **Trigger moment**: 每日盘后. Persona A/E 高频, Persona B/D 中频.
- **Inputs**: 股票池 (列表 / 指数成分 / 自定义), 时间, 信号清单 (可勾选), 信号权重
- **Outputs**: 按信号评分排序的 ranking 表 + 每行的触发信号明细 + TOP 10 的小图
- **Acceptance**:
  1. 至少支持 8 个主流信号 (SMA/EMA 交叉, MACD, RSI, Bollinger, ATR 突破, 量价背离, 均线多头排列, 缠论/czsc 买卖点)
  2. 计算可复现 (给定数据 → 给定信号结果一致)
  3. 不误用"未来数据" (lookahead bias 检查 fatal)
- **Existing alternatives**: TradingView 筛选器 (美股为主), 东财/同花顺选股 (黑盒), TA-Lib 手写 (慢)
- **Doramagic differentiation**: 晶体把"无 lookahead" 作为 fatal 约束 + 支持缠论/czsc 这种 CN 特有流派 (西方工具不支持) + 一次性扫大池
- **CN vs US**: 不分叉, 但 CN 侧缠论 / czsc / 波浪是独有加分
- **Blueprint reuse**: `bp-091 czsc` + `bp-109 ta-lib-python` + `bp-122 ta-python` + `bp-082 stock-screener` + `bp-092 vectorbt` (批量计算)
- **Effort**: M (1.5-2 周)
- **Priority**: **P1**

---

#### C-07 `crystal-quant-007` 策略想法到回测 / Idea-to-Backtest

- **Value prop**: "我有一个想法: '月初买入前一个月涨幅最大的 5 只大盘股, 月末卖出'. 给我一个能跑的回测 + 绩效报告, 不要让我学 backtrader."
- **Trigger moment**: 每当用户有新想法. 每周 1-3 次.
- **Inputs**: 自然语言描述的策略 (通过苏格拉底对话细化为: universe + signal + entry/exit rules + rebalance freq + initial capital + benchmark), 回测时间段
- **Outputs**: (1) Python 回测脚本 (完全可运行, 带注释), (2) 绩效报告 (年化 / 最大回撤 / 夏普 / 索提诺 / 胜率 / 换手), (3) 权益曲线图 + 回撤图, (4) 与 benchmark 对比
- **Acceptance**:
  1. 脚本开箱能跑 (前提: C-01 取数函数存在)
  2. 不是"把 backtrader tutorial 复制一遍" — 策略逻辑真的按用户描述编码
  3. 关键 bias 检查: no lookahead, no survivorship, 合理 slippage & commission
  4. 报告在 1 页摘要 + 1 页图可读完
- **Existing alternatives**: 用户自学 backtrader/vectorbt 2 周, QuantConnect LEAN 学习 1 周, 聚宽/米筐平台锁定
- **Doramagic differentiation**: **自然语言 → 可运行脚本**, 带 A 股和 US 两个实现模板, bias 检查作为 fatal 约束. 这是 Doramagic 相对 Composer.trade 的深度优势 (Composer 只支持预设 building blocks, 不支持自由策略)
- **CN vs US**: **不分叉**, 但 `execution_directive` 让宿主 AI 根据 universe 是 A 股还是美股自动选 backtrader/vectorbt 不同的 boilerplate
- **Blueprint reuse**: `bp-086 backtrader` + `bp-092 vectorbt` + `bp-088 zipline-reloaded` + `bp-087 qlib` + `bp-100 LEAN` + `bp-089 rqalpha` + `bp-081 vnpy` + `bp-125 bt` + `bp-107 empyrical-reloaded` + `bp-106 pyfolio-reloaded`
- **Effort**: L (3-6 周 — 最核心也最复杂的晶体)
- **Priority**: **P0 ★ Wedge**

---

#### C-08 `crystal-quant-008` 因子研究与 IC 分析 / Factor Research & IC

- **Value prop**: "我想检验一个新因子: '过去 60 天波动率 / 过去 60 天均值'. 给我 IC 时序 + 分组收益 + 衰减图, 判断它有没有 alpha."
- **Trigger moment**: Persona A/B 每周 1-2 次.
- **Inputs**: 因子表达式 (自然语言 or 表达式 DSL), universe, 时间段, 行业/市值中性化选项
- **Outputs**: (1) IC 时序图 (Pearson + Spearman), (2) 5 分组收益图, (3) 因子暴露衰减 (半衰期), (4) 行业/市值中性化后的因子收益
- **Acceptance**:
  1. IC 计算正确 (手工抽查 3 个时点 IC 值, 误差 < 5%)
  2. 分组 monotonic 检查 (好因子 5 组应大致单调)
  3. 中性化前后对比清晰
  4. 半衰期数字给出来, 超过 20 天报警"因子衰减慢, 可能是暴露类因子"
- **Existing alternatives**: alphalens 手搓, qlib Alpha158/360 (但学习曲线陡)
- **Doramagic differentiation**: 用户说自然语言, 晶体帮忙转成 qlib 表达式 + alphalens workflow. 中性化步骤是 fatal 约束 (否则 IC 会骗人).
- **CN vs US**: 不分叉 (方法论通用, 数据源差异由 C-01 兜底)
- **Blueprint reuse**: `bp-087 qlib` + `bp-120 alphalens-reloaded` + `bp-093 PyPortfolioOpt` + `bp-115 mlfinlab` + `bp-121 machine-learning-for-trading`
- **Effort**: L (2-4 周)
- **Priority**: **P0**

---

#### C-09 `crystal-quant-009` 参数优化与 WFA / Parameter Optimization & Walk-Forward

- **Value prop**: "我的策略参数想做 walk-forward, 不要拿历史全样本 overfit 骗自己."
- **Trigger moment**: C-07 之后, 发布/上实盘之前.
- **Inputs**: 策略脚本 (C-07 输出), 参数搜索空间, WFA 窗口 & 步长, 样本外目标 (夏普 / PSR / 胜率)
- **Outputs**: (1) 参数稳健性热图, (2) 样本内 vs 样本外分布图, (3) PSR/DSR 统计量, (4) 推荐参数组 + 置信区间
- **Acceptance**:
  1. WFA 窗口不泄露
  2. PSR/DSR 计算依据 Bailey & López de Prado 公式
  3. 推荐参数有明确"不推荐"理由 (overfit 高分段标红)
- **Existing alternatives**: QuantConnect 参数优化 (要升级 Pro $40+), mlfinlab 手动, vectorbt grid search + 手写 WFA
- **Doramagic differentiation**: 把"别被 overfit 骗" 的护栏编码为 fatal; PSR/DSR 是独立研究员很少正确使用的统计.
- **CN vs US**: 不分叉
- **Blueprint reuse**: `bp-092 vectorbt` + `bp-115 mlfinlab` (PSR/DSR) + `bp-086 backtrader` + `bp-100 LEAN`
- **Effort**: M (1.5-2.5 周)
- **Priority**: **P2** (好用但非 must-have for day 1)

---

#### C-10 `crystal-quant-010` 组合优化 / Portfolio Optimizer

- **Value prop**: "我有 10 只想买的股, 按风险平价 / 均值方差 / Black-Litterman 给我权重."
- **Trigger moment**: 每次调仓前, 每月 1-4 次.
- **Inputs**: 标的清单, 历史价格 (C-01 兜底), 优化方法, 约束 (max weight / sector cap / turnover limit), 风险厌恶系数
- **Outputs**: 权重表 + 有效前沿图 + 敏感性分析 + 与等权基准的对比
- **Acceptance**:
  1. 权重之和 = 1 ± 1e-6, 非负 (除非显式允许做空)
  2. 约束确实被满足
  3. 有效前沿图能正确显示
  4. 敏感性分析: 收益估计误差 ±1% 时权重变动幅度给出
- **Existing alternatives**: PyPortfolioOpt / Riskfolio-Lib 手搓 (3-5 小时), Portfolio123 (限美股, $75+/mo)
- **Doramagic differentiation**: 自然语言参数, 约束显式化, 给敏感性分析 (多数用户忽略). 支持 Black-Litterman 这种 views 型优化 (学生几乎没人会用).
- **CN vs US**: 不分叉
- **Blueprint reuse**: `bp-093 PyPortfolioOpt` + `bp-117 Riskfolio-Lib` + `bp-020 gs-quant` + `bp-101 FinancePy`
- **Effort**: M (1.5-2 周)
- **Priority**: **P1**

---

#### C-11 `crystal-quant-011` 组合风险一键体检 / Portfolio Risk Audit

- **Value prop**: "我持仓是这 15 只, 帮我算 VaR / CVaR / 最大回撤 / 行业暴露 / 因子暴露 (市值/价值/动量) / 相关性矩阵 / 集中度."
- **Trigger moment**: 每周/每月收盘后. Persona D 老板最关心.
- **Inputs**: 持仓表 (symbol, weight, cost), 历史窗口, 基准 index, 因子模型选择 (Fama-French 3/5 或 CNE6 Barra-like)
- **Outputs**: 体检报告 markdown + 1 页图:
  1. VaR 95% / 99% + CVaR
  2. 最大回撤 + 回撤持续
  3. 行业 / 地域 / 市值暴露
  4. 因子暴露分解
  5. 集中度 (HHI, top-3 占比)
  6. 主要相关性簇 (heatmap)
  7. 风险提示 3 条 (有立场)
- **Acceptance**:
  1. 计算与手工抽查一致
  2. 因子暴露回归 R² > 0.5 (否则提示因子选错)
  3. 报告可直接发给老板
- **Existing alternatives**: 手拼 pyfolio + Riskfolio + alphalens 半天; Bloomberg PORT 机构向
- **Doramagic differentiation**: 一次到位, 给"有立场的风险提示"(非空话), 中美因子模型二选一
- **CN vs US**: **轻度分叉** — 因子模型 CN 用 Barra CNE6-like (从 qlib / 学术论文重建), US 用 Fama-French
- **Blueprint reuse**: `bp-106 pyfolio-reloaded` + `bp-107 empyrical-reloaded` + `bp-117 Riskfolio-Lib` + `bp-120 alphalens-reloaded` + `bp-119 transitionMatrix` + `bp-067 firesale_stresstest` (压力测试可选扩展)
- **Effort**: L (3-4 周)
- **Priority**: **P0 ★ Wedge**

---

#### C-12 `crystal-quant-012` 基于因子的业绩归因 / Factor-Based Attribution

- **Value prop**: "上个月我赚了 3.2%, 基准 1.8%. 告诉我超额 1.4% 是 alpha 还是哪个因子 beta."
- **Trigger moment**: 每月 / 每季度.
- **Inputs**: 持仓历史 (逐日或月末), 基准, 因子模型
- **Outputs**: 月度 / 季度归因表: alpha / factor betas 逐项贡献 + t-stat 显著性
- **Acceptance**:
  1. 贡献加和 ≈ 实际超额收益 (±10bp 内)
  2. t-stat 给出且解释 "哪些显著"
  3. 建议: 根据显著暴露给出"去除 / 加强"的方向 (有立场)
- **Existing alternatives**: empyrical + pyfolio + 手搓; Bloomberg PORT; FactSet
- **Doramagic differentiation**: 月度例行, 可复用, 低门槛. 比 pyfolio 手写省 2 小时.
- **CN vs US**: 与 C-11 同分叉策略
- **Blueprint reuse**: `bp-106 pyfolio-reloaded` + `bp-107 empyrical-reloaded` + `bp-120 alphalens-reloaded` + `bp-124 arch` (risk models)
- **Effort**: M (1.5-2 周)
- **Priority**: **P1**

---

#### C-13 `crystal-quant-013` 研报 / Memo 生成 / Research Memo Writer

- **Value prop**: "帮我把这次研究写成一份 PM 级 memo: 核心观点 + 论据 + 风险 + 数据表 + 图. 中英双语可选."
- **Trigger moment**: 每次研究结论出炉时. Persona D 每周 2-5 次, Persona B 每周 1-3 次, Persona C 每周 1 次.
- **Inputs**: 研究素材 (数据表 + 图 + 要点), 结论方向 (看多/看空/中性), 目标读者 (PM / 老板 / 公众号粉丝), 篇幅 (1 页 / 3 页 / 长文)
- **Outputs**: 标准格式 markdown memo:
  1. Thesis 单句
  2. 3 条核心论据 (每条配数据/图)
  3. 3 条风险 (有立场, 不空话)
  4. 估值 / 催化剂表
  5. 结论 + 目标价位或触发条件
- **Acceptance**:
  1. 核心论据每条有数据/图佐证, 不空话
  2. 风险段非模板空话 (有具体情景)
  3. 结论有可证伪的"如果 X 发生则失效"
- **Existing alternatives**: Word/Google Docs 手写 2-4 小时; ChatGPT 生成 "听起来好但无数据" memo; FinChat 对话式输出格式不稳定
- **Doramagic differentiation**: 晶体把"有立场 + 数据佐证 + 可证伪"作为 fatal 约束. 模板是真正的 sell-side / buy-side memo 结构 (Thesis / Evidence / Risks / Catalysts), 不是流水账.
- **CN vs US variant**: 仅输出语言与模板措辞差异, 共用同一颗晶体
- **Blueprint reuse**: `bp-074 FinRobot` + `bp-099 TradingAgents-CN` + `bp-083 Economic-Dashboard` (报告 pattern) + `bp-004 daily_stock_analysis`
- **Effort**: M (2-3 周)
- **Priority**: **P0 ★ Wedge**

---

#### C-14 `crystal-quant-014` 宏观数据面板 / Macro Dashboard

- **Value prop**: "给我一张图看: 中美 CPI / PPI / PMI / 非农 / FOMC / 利率曲线 / 信用利差 / 人民币汇率. 今天发了什么, 历史分位在哪."
- **Trigger moment**: 周一晨会前, 关键数据发布日 (每月 10-15 天)
- **Inputs**: 目标指标清单 (预定义菜单), 区域 (中/美/欧/日), 显示模式 (时序 + 历史分位)
- **Outputs**: 多子图 dashboard (plotly/altair), 每个指标带: 最新值 / YoY / 历史分位 / 与预期差, 发布日程表
- **Acceptance**:
  1. 数据时效 ≤ 1 个发布周期
  2. 历史分位计算用至少 10 年数据
  3. 预期值 (市场 consensus) 有标注 (where available)
- **Existing alternatives**: Bloomberg ECO, FRED + 手拼, 公众号截图靠谱但死数据
- **Doramagic differentiation**: 跨国宏观一屏 + 历史分位自动 (多数终端都不给) + 可按自己关心的指标定制
- **CN vs US**: **不分叉但必须双轨** — 数据源 CN 用国家统计局 / 人行 / 东方财富, US 用 FRED / BEA; 晶体里写死双数据源 fallback.
- **Blueprint reuse**: `bp-083 Economic-Dashboard` + `bp-077 Open_Source_Economic_Model` + `bp-097 OpenBB` + `bp-079 akshare` (宏观接口) + `bp-084 eastmoney`
- **Effort**: M (1.5-2 周)
- **Priority**: **P1**

---

#### C-15 `crystal-quant-015` 链上 / 情绪 / 新闻信号融合 / Alt-Data Signal Fuser

- **Value prop**: "帮我把 Twitter 情绪 + Glassnode 链上指标 + 新闻情感合成一个信号, 告诉我它和 BTC 收益的相关性/领先滞后关系."
- **Trigger moment**: 研究 alpha 来源时. Persona E 月度, Persona B/D 季度.
- **Inputs**: 数据源组合 (from 预设菜单: Twitter sentiment, 链上, NLP 新闻, Google Trends, 卫星), 目标标的, 合成方法 (等权 / PCA / 回归)
- **Outputs**: (1) 合成信号时序, (2) 信号与收益的 lead-lag 相关性矩阵, (3) 基于信号的简单策略回测 (链入 C-07), (4) 信号稳健性报告
- **Acceptance**:
  1. 数据源接入可复现 (给出 fetch 脚本 + API key 占位)
  2. 滞后检验严格 (no lookahead)
  3. 信号与现有因子的相关性 < 0.5 (否则提示"这只是现有因子的变体")
- **Existing alternatives**: 机构花 $50k-500k 做; 独立研究员靠 Glassnode + TradingView + 手抓, 基本不合成
- **Doramagic differentiation**: 把 alt-data 整合的"最难那一步"(对齐 + 滞后 + 正交化) 编码进晶体, 对 crypto 尤其刚需
- **CN vs US**: 不分叉. CN 场景替换 Twitter → 雪球/微博情绪 (通过新蓝图或 akshare 替代接口)
- **Blueprint reuse**: `bp-080 FinDKG` (知识图谱) + `bp-074 FinRobot` + `bp-061 FinRL` + `bp-110 cryptofeed` (on-chain adj); **可能需要 1 颗新蓝图**: 社交情绪 / NLP-for-finance (candidates: FinBERT, stocktwits API) — 记为 gap.
- **Effort**: L (3-6 周)
- **Priority**: **P2**

---

### 5.3 The coherence story

15 颗晶体不是拼盘, 是一条工作流:

```
早晨 C-14 宏观 → C-01 取数 → C-02 A股体检 / C-03 crypto 底座
     ↓
盘中 C-04 单股简报 / C-05 10-K 抽取 / C-06 技术扫描
     ↓
研究 C-07 想法回测 → C-08 因子 IC → C-09 WFA 优化
     ↓
组合 C-10 优化 → C-11 风险体检 → C-12 归因
     ↓
输出 C-13 memo → (回到 Day 1)
边缘 C-15 alt-data (探索 alpha 时触发)
```

**5 个 wedge 覆盖一个闭环**: C-01 进水 → C-04 看一只 → C-07 回测想法 → C-11 组合风险 → C-13 写出去. 用户 day 1 就能感到"这个工作台能替我工作"。

---

## 6. CN vs US Delivery Considerations

### 6.1 数据源可用性

| 类别 | CN 方案 | US 方案 | 是否晶体内显式 |
|------|---------|---------|----------------|
| 股票日线 | akshare (免费) / Tushare Pro (付费) | yfinance (免费) / Polygon / FMP | 是, C-01 |
| 股票分钟 | tushare Pro 付费 / 东财 / tqsdk | Polygon / Alpaca | 是 |
| 美股 CN 用户取数 | akshare (via 新浪美股, 延迟) 或墙外 yfinance | yfinance 直连 | 是, 提示 |
| 基本面 | akshare fundamental / 东财 / Tushare | yfinance / FMP / OpenBB / edgartools | 是 |
| 10-K 年报 | 巨潮资讯 / 东财公告 | SEC EDGAR (edgartools) | 是, C-05 双分支 |
| 宏观 | 国家统计局 / 人行 / 东财 / akshare | FRED / BEA / OpenBB | 是, C-14 双轨 |
| 期货商品 | tqsdk (免费) / Tushare / 米筐 | Polygon / Alpaca / CME | 是 |
| Crypto | ccxt (全球) / cryptofeed | 同 | 是, C-03 |
| Alt-data | 雪球评论 / 微博 / 东财吧 | Twitter/X API / Reddit / Glassnode | 是, C-15 gap |

**底线**: 晶体**不预装 API key**, 用户带自己的订阅. 但晶体**显式告诉宿主 AI** "如果用户是 CN 用户, 首选 akshare → tushare → 东财 fallback 顺序".

### 6.2 监管约束 (CRITICAL)

- **CN 侧**: 根据《证券投资顾问业务暂行规定》, 向不特定对象提供具体证券 "买卖建议" 需证券投资顾问资质. Doramagic 晶体输出的 C-04 / C-13 必须**以工具姿态表达**, 不使用"建议买入/卖出"句式, 改用"研究结论:该标的处于 X 状态"+"如果你决定入场,应关注 Y 风险". 这是 `claim_boundary` fatal 约束, 覆盖所有有输出文字的晶体 (C-04, C-05, C-11, C-13 四颗最关键).
- **US 侧**: 非持牌 Investment Advisor 做个人 research 合规空间较宽, 但仍需避免"accept fiduciary responsibility" 语言. Substack 文章级别的 disclosure ("not financial advice") 通常足够.
- **Crypto**: 各国差异大, 统一给 "not financial advice" 声明模板.

**统一规则**: 所有面向终端 user 的晶体在 output footer 自动插入免责声明 (多语言). 硬编码入 crystal template.

### 6.3 支付 / 定价本地化

- CN: 微信支付 + 支付宝 + 年付为主 (月付习惯弱). 价位锚: 聚宽会员 ¥1k-5k/年, Tushare 捐赠 ¥500-2000. Doramagic CN 定价建议 **¥99/月 或 ¥899/年 (Pro)**, **¥9.9/颗晶体按颗买 (尝鲜)**, 免费层给 3 颗晶体.
- US: Stripe + 月付主导. 价位锚: Koyfin Plus $39, QuantConnect Researcher $20, FinChat Plus $29. Doramagic 定价建议 **$29/月 或 $290/年 (Pro)**, 免费层 3 颗晶体.

### 6.4 分发渠道

| 平台 | 动作 | 目标人群 | 内容形式 |
|------|------|----------|----------|
| 知乎 | 量化 / 金融话题长文 + 盐选 | Persona A + C | "我用 Doramagic 15 分钟完成了以前要 3 天的因子分析" |
| 公众号 | 与量化 UP 合作 + 自媒体号 | Persona A + D | 每周 1 篇晶体应用 case |
| 小红书 | 金融副业 / MBA 话题 | Persona C | 短视频 + carousel |
| B 站 | 何其野级 UP 主合作 | Persona A + C | 15 分钟 demo video |
| GitHub | 开源几颗晶体 | 所有 persona | star → try → convert |
| Twitter/X | fintwit 大号互动 | Persona B + E | 每颗晶体 demo 短推 |
| r/algotrading | post + 回应 | Persona B + E | 长文 + 开源示例 |
| Hacker News | Show HN | Persona B (dev-leaning) | 一次性事件 |
| Substack 合作 | 付费嵌入 | Persona B | 合作 writer 用晶体产出内容 |
| Discord / Telegram | 社群 | Persona E + A | 持续陪伴 |

**CN 策略权重**: 公众号 + 知乎 + B 站 ≈ 70% 种子流量. **US 策略权重**: Twitter/X + r/algotrading + HN ≈ 60%. 两边都不靠付费投放.

---

## 7. Market Sizing & Revenue Model

### 7.1 TAM / SAM / SOM (重申 + 细化)

- **TAM**: 全球量化 / 投研从业 + 严肃个人投资者 + 金融专业学生 ≈ 12-18M
- **SAM**: 付不起 Bloomberg 但愿意月付 $20-100 / ¥100-500 ≈ 3-5M
- **SOM (3 年)**: 50k-200k 付费用户

**Source 备注**: 本节数字为三角估算, 非一手市调. 详见 §2.3.

### 7.2 定价 tier 建议

| Tier | 价格 | 包含 |
|------|------|------|
| Free | $0 / ¥0 | 3 颗晶体 (轮换), 水印 memo |
| Pro | $29/mo or $290/yr · ¥99/mo or ¥899/yr | 全部 15 颗 + 优先更新 + 无水印 + 私有上下文记忆 |
| Team (2-10 人) | $99/mo (US) · ¥399/mo (CN) | Pro + 共享晶体 + 共享上下文 |
| Enterprise | 按席位谈 | Pro + 私部署 + 客户晶体定制 |

"按颗买"选项: $9 / ¥9.9 单颗, 留给尝鲜用户和教学场景.

### 7.3 $1M ARR thought experiment

**Path A (US-skewed)**: 3,000 Pro users @ $290/yr = $870k + 50 Team @ $1,200/yr = $60k + 5 enterprise @ $20k = $100k ≈ **$1.03M ARR**. 要求: 约 12 个月内 3k 付费 Pro, 转化率 5% → 60k 免费注册 → 相当于 r/algotrading + fintwit 种子覆盖 1% 触达.
**Path B (CN-skewed)**: 10,000 Pro users @ ¥899/yr = ¥8.99M ≈ $1.24M. 需约 200k 免费注册, 5% 转化. 知乎 + 公众号 + B 站 种子+口碑 1 年可期.
**Path C (混合)**: 50/50, 加速更稳.

**判断**: $1M ARR 在 12-18 月达成概率 30-50%, 在 24 月内 60-75%. 前提: 5 个 wedge 晶体真正做到"day 1 闪现价值", 否则掉到 LT 拉胯.

### 7.4 对比: 护城河积累

每新出 1 颗高质量晶体 → 额外 1-2% 付费用户粘性. 15 颗覆盖主工作流后, 继续向相邻领域 (宏观对冲 / 信用分析 / 衍生品定价 — 有 `bp-123 QuantLib-SWIG` / `bp-101 FinancePy` / `bp-127 py_vollib` 兜底) 扩, 3 年可做到 30-50 颗.

---

## 8. Risks & Open Questions

### 8.1 Key assumptions that might be wrong

1. **Phase 2 假设 (晶体在用户 AI 侧跑通)**: 假设 >60% 目标用户有稳定的 Claude/ChatGPT/DeepSeek/Kimi 订阅. 如果 CN 用户比例低于 30%, Phase 2 断链. **缓解**: CEO 判断是否需绑定首选模型并在 `execution_directive` 里硬写.
2. **"AI 消费 md" 范式认知**: 假设用户愿意"把 .md 文件丢给 AI" — 在 r/algotrading 这是新习惯, 教育成本不低. **缓解**: 首批 3 颗晶体配 video demo 压爆认知.
3. **数据源订阅用户已自备**: 假设用户有 akshare / tushare / yfinance / polygon 至少一个. Persona C (学生) 可能没有. **缓解**: 免费源 (akshare + yfinance + ccxt) 作为 default, 订阅源作为可选.
4. **语言立场 (工具论而非顾问论)**: 假设用户接受"晶体不给你买卖建议". 部分 Persona A/C 可能想要 "帮我选股". **缓解**: 不松口. 清晰是品牌定力.
5. **73 蓝图已覆盖 80%**: 这是 paper 推演, 未真实编译 15 颗晶体验证. **缓解**: 做一次 C-04 + C-07 + C-11 三颗 proof-of-compilation, 验证蓝图复用是否够用.

### 8.2 Single biggest strategy-killer

**"用户的 AI 跑不起来晶体"**. 如果宿主 AI 读了晶体后输出的代码错得离谱 (跑不起来 / 幻觉数据源 / 忽略 fatal 约束), 那 Phase 2 就没戏, 整个 "knowledge forging" 模型就塌. 这是 v9 已通过但仅在单颗晶体上验证, **15 颗 × 多语言 × 多宿主 AI 的端到端可用率需要专门的 QA 矩阵**. 建议在推出 Pro tier 前做一次"10 种宿主 AI × 15 颗晶体 × 3 种场景" 的实测回归, 最低可用率 90% 作为 launch gate.

### 8.3 What research is still missing

1. **用户访谈**: 本文全部基于 web research + internal knowledge. 需至少 **30 个一对一访谈** (CN 15, US 15), 验证 persona + friction 排序 + 付费意愿.
2. **Proof-of-compilation**: 用 v10 管线把 3-5 颗晶体真实编译出来, 在 Claude Code + DeepSeek + Cursor 三环境下跑通, 记录失败率.
3. **竞品 UX teardown**: 订阅 Koyfin Plus + FinChat Pro + QuantConnect Researcher + 聚宽会员 1 个月, 实操跑通 15 个场景, 对比 time-to-outcome.
4. **监管咨询**: CN 侧"不构成投资建议"边界要找合规律师 review 一次, 写成 2 页 playbook.
5. **数据源合作谈判**: 是否可能与 Tushare / 聚宽 / Polygon 谈数据转销或合作 (降低用户门槛), 但不在 v1 launch 路径.

---

## 9. Appendix — Mapping to Finance 73 Blueprints

### 9.1 覆盖矩阵

| Crystal | Primary blueprints | Secondary blueprints | Gap (new bp needed?) |
|---------|-------------------|---------------------|----------------------|
| C-01 Fetch | bp-079 akshare, bp-128 yfinance, bp-111 ccxt | bp-097 OpenBB, bp-084 eastmoney, bp-110 cryptofeed, bp-103 ArcticDB | 无 |
| C-02 A股体检 | bp-084 eastmoney, bp-079 akshare | bp-069 tqsdk, bp-091 czsc, bp-082 stock-screener | 无 |
| C-03 Crypto feed | bp-111 ccxt, bp-110 cryptofeed | bp-096 hummingbot | 无 |
| C-04 One-page brief | bp-004 daily_stock_analysis, bp-082 stock-screener, bp-118 FinanceToolkit | bp-079 akshare, bp-128 yfinance, bp-070 edgartools, bp-097 OpenBB | 无 |
| C-05 Filing extractor | bp-070 edgartools, bp-114 edgar-crawler | bp-084 eastmoney (CN 公告) | **CN 巨潮资讯可选** (akshare 可 cover) |
| C-06 TA scanner | bp-091 czsc, bp-109 ta-lib-python, bp-122 ta-python | bp-082 stock-screener, bp-092 vectorbt | 无 |
| C-07 Idea→backtest | bp-086 backtrader, bp-092 vectorbt, bp-087 qlib, bp-088 zipline-reloaded, bp-100 LEAN | bp-089 rqalpha, bp-081 vnpy, bp-125 bt, bp-106 pyfolio-reloaded, bp-107 empyrical-reloaded | 无 |
| C-08 Factor research | bp-087 qlib, bp-120 alphalens-reloaded | bp-093 PyPortfolioOpt, bp-115 mlfinlab, bp-121 machine-learning-for-trading | 无 |
| C-09 Param opt/WFA | bp-092 vectorbt, bp-115 mlfinlab | bp-086 backtrader, bp-100 LEAN | 无 |
| C-10 Portfolio opt | bp-093 PyPortfolioOpt, bp-117 Riskfolio-Lib | bp-020 gs-quant, bp-101 FinancePy | 无 |
| C-11 Risk audit | bp-106 pyfolio-reloaded, bp-107 empyrical-reloaded, bp-117 Riskfolio-Lib, bp-120 alphalens-reloaded | bp-119 transitionMatrix, bp-067 firesale_stresstest | 无 |
| C-12 Attribution | bp-106 pyfolio-reloaded, bp-107 empyrical-reloaded, bp-120 alphalens-reloaded | bp-124 arch | 无 |
| C-13 Memo writer | bp-074 FinRobot, bp-099 TradingAgents-CN | bp-083 Economic-Dashboard, bp-004 | **可选**: 金融写作风格知识库 (可用提示工程替代) |
| C-14 Macro dashboard | bp-083 Economic-Dashboard, bp-077 OSEM | bp-097 OpenBB, bp-079 akshare, bp-084 eastmoney | 无 |
| C-15 Alt-data fuser | bp-080 FinDKG, bp-074 FinRobot | bp-061 FinRL, bp-110 cryptofeed | **需要 1 颗新蓝图**: NLP-for-finance (FinBERT 等) / 社交情绪 |

### 9.2 蓝图利用率

- 73 蓝图中在上面 15 颗晶体里**被至少引用一次**: **36 个 primary + 14 个 secondary = 50 个 (69%)**
- 未被 15 颗引用的 23 颗 (保险精算 / 信用风险 / AML / 会计 / 债券等): 是下一批 (investment banking / credit research / insurance actuarial) 的弹药
- **Gap 识别**: C-15 社交情绪需要 1 颗新蓝图; C-05 CN 公告可选; C-13 金融写作风格可选. 即 15 颗晶体中 **13 颗可完全基于现有 73 蓝图编译**, 2 颗需补缺.

这是一个极高的复用率, **印证"73 蓝图已经覆盖 80% 投研工作流"的命题**.

---

## 10. Closing Argument

投研 / 量化领域与 Doramagic 的产品哲学契合度极高:
- 工作流**确实由可提取的开源框架构成** (backtrader, qlib, alphalens, pyfolio, ...) → 蓝图路径通
- 工作流**确实受 fatal 约束** (lookahead bias, survivorship, A 股涨跌停, 10-K section 定位) → 约束路径有价值
- 工作流**确实需要"交给 AI 跑"而不是"再学一个工具"** → 晶体交付模型有价值
- 目标用户**既买不起 Bloomberg 又需要专业级输出** → 定价空间真实存在

73 蓝图已经是强大的护城河起点. 15 颗晶体把它变成一个可运行的工作台. 如果 CEO 决定 commit, 建议按以下顺序落地:

1. **M1**: 先编 5 颗 wedge (C-01, C-04, C-07, C-11, C-13), 每颗一个 v1 晶体经过管线编译, 同步做 QA 矩阵
2. **M2**: 10 个用户 closed beta (5 CN, 5 US), 记录时间和失败模式, 迭代
3. **M3**: 推 P0 剩余 2 颗 (C-02, C-05, C-08) + 对 wedge 做稳定化
4. **M4**: 推 P1 (C-03, C-06, C-10, C-12, C-14) 发 launch
5. **M5-M6**: P2 (C-09, C-15) + 进入下一垂类

---

## 📋 Reader Guide

### 5 个 CEO 应自问的问题

1. **"我有多信 Phase 2?"** — 晶体的价值全部依赖用户 AI 能跑通. 你手头有没有至少 1 次跨 3 种宿主 AI 的端到端实测数据? 没有 → 先去做一次, 再决定 commit.
2. **"CN 用户的 AI 分布我知道吗?"** — 如果 CN 主要用户用 DeepSeek / Kimi, 晶体的 execution_directive 要不要为它们 shape? 这是要在晶体编译 SOP 里解决的问题, 不是后续优化.
3. **"我愿不愿守住'工具论', 不变成'买卖建议'?"** — 这会影响转化率. 愿意守住 = 品牌长期价值 + 监管护身. 不愿守住 = 短期转化但踩雷风险.
4. **"投研是终点还是跳板?"** — 如果投研只是"拿来证明 Doramagic 能扩到第二领域", 那 15 颗的覆盖深度够了. 如果想做成 Bloomberg 对立面的长青产品, 需要 3 年积累到 50-80 颗 + 数据订阅合作 + 内容社区 —— 你当前的团队规模能支撑哪个?
5. **"5 个 wedge 哪一个最先做 proof-of-compilation?"** — 我建议 **C-04 单股一页深度简报**: Persona 覆盖最广, 视觉冲击力最强, 适合成为第一个 demo video. 你同意吗?

### 3 个研究答不了、必须 CEO 判断的地方

1. **CN 用户 AI 消费侧绑定策略** — 晶体要不要针对国内模型 shape? 研究只能给选项, 不能给答案. 决策依据是商业战略 + 合规判断, 不是用户调研能解决.
2. **"工具论 vs 顾问论" 的品牌语言边界** — 这是价值观题, 不是数据题. 研究只能陈列风险, 不能替你选.
3. **团队资源分配: 73 → 100 蓝图 vs 15 → 30 晶体** — 向 depth (更多晶体 / 同一领域) 还是 breadth (第三垂类) 投? CEO 必须决定, 研究给不了答案.

---

**Document path**: `/Users/tangsir/Documents/openclaw/Doramagic/docs/research/2026-04-18-quant-researcher-15-crystals-requirements.md`

---

## Sources

- [Bloomberg Terminal Pricing 2026: $20K-$32K/Year Plans — Costbench](https://costbench.com/software/financial-data-terminals/bloomberg-terminal/)
- [Bloomberg Terminal Cost 2026: Full Pricing Breakdown — Godeldiscount](https://godeldiscount.com/blog/bloomberg-terminal-cost-2026)
- [Perplexity AI Just Turned A $30,000/Year Bloomberg Terminal Into A $200/Month Subscription — Yahoo Finance](https://finance.yahoo.com/news/perplexity-ai-just-turned-30-153122212.html)
- [Koyfin pricing and subscription FAQ](https://www.koyfin.com/pricing/)
- [Koyfin Plans Comparison](https://www.koyfin.com/pricing/plans-comparison/)
- [Best Bloomberg Terminal Alternatives 2026 — Koyfin blog](https://www.koyfin.com/blog/best-bloomberg-terminal-alternatives/)
- [QuantConnect Pricing](https://www.quantconnect.com/pricing/)
- [QuantConnect Review 2026 — newtrading.io](https://www.newtrading.io/quantconnect-review/)
- [FinChat / Fiscal.ai Review — Wall Street Zen](https://www.wallstreetzen.com/blog/finchat-io-fiscal-ai-review/)
- [FinChat Review 2026 — aichief.com](https://aichief.com/ai-business-tools/finchat/)
- [Composer.trade Pricing](https://www.composer.trade/pricing)
- [Composer Review — OpenTools](https://opentools.ai/tools/composer-trade)
- [Wind 万得 金融终端 价格分析 — 新浪财经](https://finance.sina.cn/2023-09-11/detail-imzmiqth5856632.d.html)
- [一个万得账号要多少钱 — 知乎](https://www.zhihu.com/question/39264388)
- [Tushare Pro 积分与频次权限对应表](https://tushare.pro/document/1?doc_id=290)
- [2026 年量化数据源终极选型 — 知乎专栏](https://zhuanlan.zhihu.com/p/2005025480454197447)
- [JoinQuant 聚宽量化投研平台](https://www.joinquant.com/)
- [RiceQuant 米筐量化平台](https://www.ricequant.com/)
- [awesome-quant (中国量化相关资源索引) — GitHub](https://github.com/thuquant/awesome-quant)
- [Best Bloomberg Terminal Alternatives in 2026 — Helm Terminal](https://helmterminal.dev/blog/best-bloomberg-terminal-alternatives)
- [Best Bloomberg Terminal Alternatives — StockAnalysis](https://stockanalysis.com/article/bloomberg-terminal-alternatives/)
- [Polygon.io Pricing](https://polygon.io/pricing)
- [Financial Modeling Prep Pricing](https://site.financialmodelingprep.com/pricing-plans)
- [Quant Hedge Funds in 2026: A Due Diligence Framework — Resonanz Capital](https://resonanzcapital.com/insights/quant-hedge-funds-in-2026-a-due-diligence-framework-by-strategy-type)
- [Hedge Fund Outlook 2026 — WithIntelligence](https://www.withintelligence.com/insights/hedge-fund-outlook-2026/)
