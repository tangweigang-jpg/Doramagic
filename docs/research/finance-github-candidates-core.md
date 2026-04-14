# Finance Blueprint Gap — GitHub Candidate Projects

> Research date: 2026-04-14
> Purpose: Fill critical gaps in Doramagic's finance blueprint library (59 existing blueprints, heavily quant-trading biased)
> Methodology: WebSearch on GitHub, star counts collected from search result snippets

---

## P0 — Critical Gaps

---

### Gap 1: Regulatory Compliance / AML-KYC

Priority: P0

**Context**: Existing blueprints have zero coverage of AML/KYC. The three best candidates cover complementary layers: synthetic data generation for model testing, real-time rule-engine decision-making, and the sanctions/PEP data layer.

#### Candidate 1: IBM/AMLSim

- URL: https://github.com/IBM/AMLSim
- Stars: ~304
- Language: Python + Java (Python for data generation and ML training scripts)
- Description: Multi-agent based simulator that generates synthetic banking transaction data with known money laundering patterns. Produces account lists, transaction records, and AML alerts. Used primarily for training/testing ML models and graph algorithms.
- Why it fits: Only serious open-source project that models transaction networks and money laundering typologies (layering, structuring, fan-out) with realistic graph structure. Blueprint-worthy because the data pipeline architecture (account simulation → transaction generation → pattern injection → alert labeling) is a clean, extractable 4-stage design.
- Last active: 2024-12 (last release)

#### Candidate 2: checkmarble/marble

- URL: https://github.com/checkmarble/marble
- Stars: ~500+
- Language: Go (backend) + TypeScript (frontend), with REST API accessible from any language
- Description: Real-time transaction monitoring and AML decision engine. Provides rule builder, case manager, batch and real-time processing. Used by 100+ fintechs and banks in 15+ countries.
- Why it fits: Production-grade rule engine for transaction monitoring. The architecture (rule definition → event ingestion → real-time scoring → case creation → investigator workflow) is a complete AML operational pipeline. Best candidate for the monitoring/alert workflow blueprint.
- Last active: 2025-Q1 (actively maintained)

#### Candidate 3: opensanctions/opensanctions

- URL: https://github.com/opensanctions/opensanctions
- Stars: ~703
- Language: Python
- Description: Open database of international sanctions data, politically exposed persons (PEPs), and persons of interest. Aggregates OFAC, UN, EU, UK, and many other sanctions lists. Companion project `yente` provides an entity matching and search API.
- Why it fits: The data ingestion and entity-matching architecture is highly extractable. Blueprint covers: source crawling → normalization → deduplication → entity linking → API serving. Essential for the sanctions screening layer that every AML/KYC system needs. Python-native.
- Last active: 2025 (actively maintained)

**Honorable mention**: moov-io/watchman (~429 stars, Go) — Go-based sanctions screening HTTP server, well-structured but non-Python.

---

### Gap 2: IFRS 9 / CECL Expected Credit Loss

Priority: P0

**Context**: IFRS 9 requires banks to compute Expected Credit Loss = PD × LGD × EAD × discount factor, with 3-stage classification. CECL (US equivalent) requires lifetime loss allowances. No existing blueprint covers this.

#### Candidate 1: naenumtou/ifrs9

- URL: https://github.com/naenumtou/ifrs9
- Stars: ~70
- Language: Python (Jupyter Notebooks)
- Description: Full scope IFRS 9 impairment model covering PD (probability of default), LGD (loss given default), EAD (exposure at default), staging criteria, and ECL computation. Includes survival analysis, transition matrices, macro-economic scenario overlays.
- Why it fits: Most complete pure-Python IFRS 9 implementation. The staging logic (Stage 1: 12-month ECL, Stage 2: lifetime ECL triggered by SICR, Stage 3: credit-impaired) is explicitly modeled. Each component (PD model, LGD model, EAD model, staging, ECL aggregation) is a separate, extractable module.
- Last active: 2023-2024 (established, stable)

#### Candidate 2: Daniel11OSSE/ifrs9-ecl-modeling

- URL: https://github.com/Daniel11OSSE/ifrs9-ecl-modeling
- Stars: ~30 (emerging, niche)
- Language: Python
- Description: Complete IFRS 9 ECL Modeling Framework with PD, LGD, EAD, staging, and scenario analysis. Applies IFRS 9 staging logic and computes ECL under different economic scenarios (base, adverse, upside).
- Why it fits: Newer project with explicit scenario analysis support (multiple economic scenarios weighted by probability — the IFRS 9 "forward-looking information" requirement). Complements naenumtou/ifrs9 by showing the macro-scenario overlay pattern.
- Last active: 2024

#### Candidate 3: open-risk/openLGD

- URL: https://github.com/open-risk/openLGD
- Stars: ~85 (open-risk org)
- Language: Python
- Description: Python library for statistical estimation of Credit Risk Loss Given Default (LGD) models. Can be used standalone or in federated learning context. Part of Open Risk's comprehensive credit risk modeling suite (also includes transitionMatrix, portfolioAnalytics, openNPL).
- Why it fits: LGD is the hardest component to get right in IFRS 9 (PD is more commoditized). Open Risk provides production-quality statistical machinery. The open-risk organization is a reference for regulatory-grade credit risk modeling in Python.
- Last active: 2024 (open-risk org consistently maintained)

---

### Gap 3: Stress Testing (DFAST/CCAR/EBA)

Priority: P0

**Context**: Bank stress testing (Federal Reserve DFAST, CCAR; EBA EU-wide) requires projecting capital ratios under macroeconomic stress scenarios. Dedicated open-source frameworks are scarce — this is a domain where proprietary tools dominate.

#### Candidate 1: ox-inet-resilience/firesale_stresstest

- URL: https://github.com/ox-inet-resilience/firesale_stresstest
- Stars: ~50 (niche academic)
- Language: Python
- Description: Agent-based model for systemically-important banks in the EU. Reproduces Cont-Schaanning (2017) firesale contagion model. Uses actual 2018 EBA stress test data. Models 5 building blocks: institutions, contracts, constraints, markets, behaviours.
- Why it fits: Only serious Python open-source project that uses real EBA stress test data and models bank-level capital evolution under stress. The architecture pattern (initial balance sheets → shock propagation → liquidity spirals → capital depletion) is extractable as a blueprint. Academic pedigree (Oxford INET).
- Last active: 2022 (established/stable, academic)

#### Candidate 2: open-source-modelling/Open_Source_Economic_Model

- URL: https://github.com/open-source-modelling/Open_Source_Economic_Model
- Stars: ~40 (niche)
- Language: Python
- Description: Open-source asset-liability model using agent-based modelling concepts. Part of the Open Source Modelling initiative that also publishes insurance_python. Models economic scenarios and their impact on balance sheets.
- Why it fits: Covers the macroeconomic scenario generation layer that feeds into stress tests. The Economic Scenario Generator (ESG) pattern — generating correlated paths for interest rates, credit spreads, equity returns, GDP — is a critical stress testing building block with no other open-source Python implementation.
- Last active: 2023-2024

#### Candidate 3: apbecker/Systemic_Risk (ECB stress test data)

- URL: https://github.com/apbecker/Systemic_Risk
- Stars: ~30 (niche)
- Language: Python + R
- Description: Systemic risk analysis using ECB stress test data. Focuses on network effects and contagion in the banking system.
- Why it fits: Provides the systemic risk angle of stress testing — not just individual bank capital projection but interbank contagion. Complements firesale_stresstest. Good for extracting the network-topology → shock-propagation → systemic-failure-cascade blueprint pattern.
- Last active: 2022 (stable)

**Note**: Dedicated DFAST/CCAR Python frameworks do not exist in open source at production quality. The above candidates cover complementary aspects (balance sheet modeling, ESG, systemic contagion). A composite blueprint pulling from all three is the realistic path.

---

### Gap 4: Robo-Advisor / Wealth Management

Priority: P0

**Context**: Goal-based planning, automated rebalancing, and tax-loss harvesting are core robo-advisor functions. The existing quant-trading blueprints do not cover the retail wealth management workflow.

#### Candidate 1: wealthbot-io/wealthbot

- URL: https://github.com/wealthbot-io/wealthbot
- Stars: ~675
- Language: PHP (Symfony) — not Python, but has clear REST API and well-documented architecture
- Description: Full open-source wealth management platform for Investment Advisors. Includes client onboarding, risk profiling, portfolio model management, automatic rebalancing (household and account level), tax-loss harvesting, custodian integration, performance reporting.
- Why it fits: Most comprehensive open-source robo-advisor with all core features implemented (not just portfolio optimization). The multi-component architecture (RIA portal → client onboarding → risk profiling → model assignment → rebalancer → reporting) is the reference blueprint for the wealth management workflow. Despite PHP backend, the architecture is fully extractable.
- Last active: 2023 (established, stable — some maintenance)

#### Candidate 2: VanAurum/robo-advisor

- URL: https://github.com/VanAurum/robo-advisor
- Stars: ~200
- Language: Python
- Description: Open-source initiative for Markowitz portfolio optimization and rebalancing strategy with transaction cost awareness. Configurable rebalancing thresholds (percentage deviation triggers), trade cost modeling, fractional share support.
- Why it fits: Pure Python. Focuses specifically on the optimization + rebalancing engine — the quantitative core of any robo-advisor. The blueprint pattern (asset allocation target → drift detection → cost-aware rebalancing → order generation) is clean and extractable.
- Last active: 2022 (established)

#### Candidate 3: redstreet/fava_tax_loss_harvester

- URL: https://github.com/redstreet/fava_tax_loss_harvester
- Stars: ~300+
- Language: Python
- Description: Tax loss harvesting plugin for Fava/Beancount personal finance system. Identifies positions eligible for tax-loss harvesting, checks wash-sale rules, and generates harvest recommendations.
- Why it fits: Tax-loss harvesting (TLH) is one of the hardest robo-advisor features to implement correctly because of wash-sale rules and substitution security logic. This is the only serious Python open-source TLH implementation. Blueprint-worthy for the TLH-specific sub-pipeline.
- Last active: 2024 (actively maintained)

---

### Gap 5: Insurance / Actuarial

Priority: P0

**Context**: Insurance reserving, mortality modeling, Solvency II compliance, and catastrophe risk modeling are entirely absent from the current blueprint library.

#### Candidate 1: casact/chainladder-python

- URL: https://github.com/casact/chainladder-python
- Stars: ~200
- Language: Python
- Description: Actuarial reserving package by the Casualty Actuarial Society. Implements triangle data manipulation, development factor methods, Bornhuetter-Ferguson, Cape Cod, and stochastic reserving (Mack, ODP). API mimics pandas/scikit-learn.
- Why it fits: The CAS (Casualty Actuarial Society) is the authoritative body for P&C actuarial standards. This is the canonical Python reserving library. The pipeline pattern (loss development triangle → tail selection → IBNR estimation → uncertainty quantification) is the core non-life reserving blueprint.
- Last active: 2024 (actively maintained by CAS)

#### Candidate 2: open-source-modelling/insurance_python

- URL: https://github.com/open-source-modelling/insurance_python
- Stars: ~100 (niche but growing)
- Language: Python
- Description: Collection of Python algorithms from Open Source Modelling for actuarial use. Covers Solvency II components: Smith-Wilson interest rate extrapolation (EIOPA prescribed), Nelson-Siegel-Svensson, liability valuation, SCR (Solvency Capital Requirement) calculations, EIOPA risk-free rate curves.
- Why it fits: Only Python implementation of Solvency II-specific calculations (Smith-Wilson is the EIOPA-mandated curve extrapolation method). The Solvency II blueprint (risk-free curve → liability discounting → SCR computation → own funds → solvency ratio) is a regulatory compliance architecture that no other open-source project covers.
- Last active: 2024 (active)

#### Candidate 3: franciscogarate/pyliferisk

- URL: https://github.com/franciscogarate/pyliferisk
- Stars: ~119
- Language: Python
- Description: Python library for life actuarial calculations. Implements International Actuarial Notation. Includes mortality tables (multiple standard tables built-in), life contingency calculations (annuities, insurance, net premiums), commutation functions.
- Why it fits: Life insurance mortality modeling is a distinct blueprint from P&C reserving. This library provides the core mortality table + life contingency machinery needed for life insurance pricing and reserving blueprints. No dependencies beyond Python standard library — easy to extract patterns from.
- Last active: 2022 (established, stable)

---

## P1 — High Priority Gaps

---

### Gap 6: Loan Origination / Lending

Priority: P1

#### Candidate 1: frappe/lending

- URL: https://github.com/frappe/lending
- Stars: ~264
- Language: Python (Frappe/ERPNext framework)
- Description: Open Source Lending software built on ERPNext. Covers full loan lifecycle: origination, disbursement, repayment schedules, interest calculation, collections, co-lending models. Production-used by NBFCs and financial institutions.
- Why it fits: End-to-end loan management with real production code. The lifecycle blueprint (application → underwriting → disbursement → repayment schedule → collections → closure) is the most complete Python-native implementation. Frappe framework means the business logic is separated from the web framework, making it extractable.
- Last active: 2025 (actively maintained, v1.5.0 Dec 2024)

#### Candidate 2: digifi-io/loan-origination-system

- URL: https://github.com/digifi-io/loan-origination-system
- Stars: ~6 (main repo — but 45,000+ dev hours, used by major lenders)
- Language: JavaScript/Node.js
- Description: First open-source loan origination system (LOS). Modular platform covering consumer, residential, SME, and commercial lending. Includes underwriting workflow, document management, e-sign, CRM, task automation, data security.
- Why it fits: Most feature-complete LOS architecture in open source, despite low stars (commercial product open-sourced). The modular architecture (application intake → credit decision engine → document collection → approval workflow → funding) is the reference for how a real bank LOS is structured. Language-agnostic blueprint extraction.
- Last active: 2022-2023 (established)

#### Candidate 3: KhalilBelghouat/StressTestingLoanPortfolio

- URL: https://github.com/KhalilBelghouat/StressTestingLoanPortfolio
- Stars: ~30
- Language: Python
- Description: Stress testing for loan portfolios using economic scenarios. Models loan-level PD migration under macro stress, portfolio loss distributions, capital requirements. Adapted from MATLAB-based regulatory implementations.
- Why it fits: Covers the credit risk → loan portfolio stress testing connection. Useful as a specialized sub-blueprint for the underwriting risk assessment stage within loan origination.
- Last active: 2023

---

### Gap 7: Treasury / ALM / IRRBB

Priority: P1

**Context**: Interest Rate Risk in the Banking Book (IRRBB) is a Basel III pillar. Asset-Liability Management (ALM) for banks requires modeling NII (Net Interest Income) sensitivity and EVE (Economic Value of Equity) under rate shocks.

#### Candidate 1: open-source-modelling/Open_Source_Economic_Model

- URL: https://github.com/open-source-modelling/Open_Source_Economic_Model
- Stars: ~40
- Language: Python
- Description: Open-source asset-liability model using agent-based modelling. Generates economic scenarios and models their impact on institution balance sheets. Covers liability valuation under changing rates, liquidity gaps, duration analysis.
- Why it fits: The ALM blueprint pattern (balance sheet mapping → gap analysis → rate scenario generation → NII/EVE sensitivity → capital impact) is partially covered here. Works in conjunction with the Solvency II-focused insurance_python from the same organization.
- Last active: 2023-2024

#### Candidate 2: montrixdev/mxdevtool-python

- URL: https://github.com/montrixdev/mxdevtool-python
- Stars: ~15 (niche)
- Language: Python
- Description: Financial library covering Economic Scenario Generator (ESG), Asset Liability Management, and pricing. Includes stochastic rate models (Vasicek, Hull-White), duration/convexity calculations, and cash flow mapping for ALM.
- Why it fits: The ESG component is the key missing piece in open-source ALM. Rate scenario generation (parallel shifts, twists, butterfly moves — the standard IRRBB shock scenarios) is here in Python. Most relevant for the IRRBB regulatory shock scenario pipeline.
- Last active: 2023

#### Candidate 3: attack68/rateslib

- URL: https://github.com/attack68/rateslib
- Stars: ~223
- Language: Python
- Description: State-of-the-art fixed income library for pricing bonds, bond futures, IRS, XCS, FX swaps. Full yield curve construction with automatic differentiation for delta/gamma risk sensitivities.
- Why it fits: The yield curve construction + rate sensitivity pipeline is the foundational analytics layer for any Treasury/ALM system. While rateslib is more derivatives-focused than pure ALM, its curve-building and DV01/duration mechanics are exactly what ALM systems need. Note: dual-licensed (source-available for non-commercial, commercial subscription for production). Blueprint extraction from source is permissible for knowledge purposes.
- Last active: 2025 (actively maintained)

---

### Gap 8: NL-to-Filter Stock Query

Priority: P1

**Context**: iwencai-style natural language stock screening ("show me A-share companies with ROE > 15% and debt ratio < 40% that beat earnings estimates last quarter") requires NLP → structured query translation. No existing blueprint covers this.

#### Candidate 1: xang1234/stock-screener

- URL: https://github.com/xang1234/stock-screener
- Stars: ~50 (emerging)
- Language: Python
- Description: Stock scanner with 80+ fundamental and technical filters, AI chatbot (Groq/DeepSeek/Gemini), theme discovery from RSS/Twitter/news, StockBee-style market breadth indicators. LLM translates natural language queries into structured screening criteria.
- Why it fits: The NL-to-filter pipeline (user query → LLM intent extraction → filter parameter mapping → screener execution → result ranking) is fully implemented. 6 LLM providers supported with web search augmentation. Most complete open-source implementation of the iwencai-style paradigm.
- Last active: 2025 (actively maintained)

#### Candidate 2: jbpayton/langchain-stock-screener

- URL: https://github.com/jbpayton/langchain-stock-screener
- Stars: ~50
- Language: Python (LangChain)
- Description: LangChain agent tool for stock screening. Takes natural language query as input, maps to technical indicator thresholds, returns matching stocks. Designed as a pluggable tool within LangChain agent frameworks.
- Why it fits: Simpler and more focused than xang1234. Shows the tool-use pattern specifically — how an LLM agent calls a stock screener as a structured tool. Blueprint for the "NL query → agent tool call → structured filter → results" sub-pipeline. Good for agents that need stock screening as one capability among many.
- Last active: 2023

#### Candidate 3: OpenBB-finance/OpenBB

- URL: https://github.com/OpenBB-finance/OpenBB
- Stars: ~31,000+
- Language: Python
- Description: Financial data platform for analysts, quants, and AI agents. Provides standardized access to equity, options, crypto, forex, macro, fixed income data. MCP server support for AI agents. The experimental agent sub-project adds LLM-driven research workflows.
- Why it fits: OpenBB is the most starred open-source financial data platform. The blueprint pattern (data source abstraction → standardized financial data models → agent-callable tools → research workflow) is the infrastructure layer that NL-to-filter and report generation both depend on. Widely adopted, actively developed.
- Last active: 2025 (very active)

---

### Gap 9: Research Report Generation

Priority: P1

**Context**: Automated financial analyst report generation — SEC filings → key metrics extraction → narrative synthesis → report formatting. No existing blueprint covers LLM-driven financial research automation.

#### Candidate 1: AI4Finance-Foundation/FinRobot

- URL: https://github.com/AI4Finance-Foundation/FinRobot
- Stars: ~4,800
- Language: Python
- Description: Open-source AI agent platform for financial analysis using LLMs. Generates professional equity research reports: fetches financial data, runs multi-agent LLM analysis (chain-of-thought Financial CoT), outputs structured reports. Covers market forecasting, portfolio management, algorithmic trading, and risk assessment.
- Why it fits: Highest-starred project in the financial LLM agent space. The multi-agent report generation pipeline (data agent → analysis agent → writing agent → fact-check agent → formatting agent) is the core blueprint. Brain module (LLM reasoning) + Perception module (data ingestion) + Action module (report generation) is a clean 3-layer architecture.
- Last active: 2025 (very active)

#### Candidate 2: OpenBB-finance/experimental-openbb-platform-agent

- URL: https://github.com/OpenBB-finance/experimental-openbb-platform-agent
- Stars: ~200
- Language: Python
- Description: R&D playground for OpenBB agents. Implements LLM agents that autonomously perform financial research using OpenBB data, generate analyst-style reports, and answer questions with up-to-date market data.
- Why it fits: Shows the agent-driven research workflow built on real financial data infrastructure. The pattern (research question → data retrieval plan → multi-step data fetching → LLM synthesis → structured output) is extractable. Complements FinRobot by showing data-layer-first architecture.
- Last active: 2024-2025

#### Candidate 3: hgnx/automated-market-report

- URL: https://github.com/hgnx/automated-market-report
- Stars: ~30
- Language: Python
- Description: Automated daily stock market report generator. Fetches data from multiple sources, performs analysis, produces PDF report. Focused on daily market summary reports (indices, sector performance, top movers, sentiment).
- Why it fits: Simpler, complete end-to-end pipeline for market report generation. The 5-stage blueprint (data fetching → multi-source aggregation → analysis → narrative generation → PDF/HTML rendering) is cleanly separable. Good reference for the "daily briefing" variant of research report generation.
- Last active: 2024

---

### Gap 10: Payment Processing / Ledger

Priority: P1

**Context**: Payment gateway, double-entry ledger, and reconciliation are foundational fintech infrastructure. No existing blueprint covers this.

#### Candidate 1: formancehq/ledger

- URL: https://github.com/formancehq/ledger
- Stars: ~1,100
- Language: Go (backend) with REST API and Python client
- Description: Programmable open-source core ledger for fintech. Atomic multi-posting transactions, account-based modeling, programmable via Numscript DSL, PostgreSQL storage. Used for user balance apps, digital asset platforms, payment systems, loan management.
- Why it fits: Most production-ready open-source financial ledger. The architecture (Numscript transaction language → atomic posting engine → immutable ledger log → OLAP replica) is a proper double-entry ledger design. The transaction modeling layer (defining financial transactions as first-class programs) is a highly extractable blueprint pattern.
- Last active: 2025 (actively maintained)

#### Candidate 2: blnkfinance/blnk

- URL: https://github.com/blnkfinance/blnk
- Stars: ~300+
- Language: Go with Python-accessible REST API
- Description: Open-source ledger and financial core for fintech products. Includes double-entry ledger, balance management, and automated reconciliation (matches external bank statements to internal ledger with custom matching rules).
- Why it fits: Adds the reconciliation layer that formancehq/ledger lacks. The reconciliation blueprint pattern (external statement ingestion → matching rule engine → exception identification → manual review workflow → ledger adjustment) is a distinct but critical payment processing component.
- Last active: 2025 (actively maintained)

#### Candidate 3: moov-io (ACH, wire, payment infrastructure)

- URL: https://github.com/moov-io
- Stars: Org-level (watchman ~429, ach ~1,400+)
- Language: Go with REST APIs
- Description: Moov.io is an organization building open-source payment infrastructure: ACH file parsing/generation, wire transfers, ISO 8583 (card payments), bank routing number lookups, and Watchman (AML screening). Used in production by financial institutions.
- Why it fits: Provides the payment scheme integration layer (ACH, wire, ISO 8583) that sits above the ledger. The ACH pipeline (payment file generation → NACHA format compliance → batch processing → settlement → reconciliation) is a separate, highly structured blueprint. moov-io/ach has 1,400+ stars.
- Last active: 2025 (very active)

---

### Gap 11: CVA/DVA/FVA — XVA Computation

Priority: P1

**Context**: Counterparty credit risk valuation adjustments (CVA, DVA, FVA, KVA, MVA — collectively XVA) require Monte Carlo simulation of exposure profiles across derivatives portfolios. Highly technical, limited open-source coverage.

#### Candidate 1: OpenSourceRisk/Engine (ORE)

- URL: https://github.com/OpenSourceRisk/Engine
- Stars: ~658
- Language: C++ (core) with Python bindings via ORE-SWIG
- Description: Open Source Risk Engine based on QuantLib. Provides XVA analytics, credit risk, market risk, interest rate simulation. Sponsored by Acadia Inc. Implements CVA, DVA, FVA, SIMM (initial margin), SA-CCR. Python accessible via SWIG wrappers.
- Why it fits: The most comprehensive open-source XVA engine. The architecture (trade representation → market scenario generation → exposure simulation → netting/collateral → XVA aggregation) is the canonical counterparty risk blueprint. Industry-standard methodology documented clearly.
- Last active: 2025-01 (regularly updated)

#### Candidate 2: konstantineder/montecarlo-risk-engine

- URL: https://github.com/konstantineder/montecarlo-risk-engine
- Stars: ~50
- Language: Python (PyTorch-powered)
- Description: PyTorch-based Monte Carlo engine for derivative pricing, exposure simulation, and XVA analytics. Combines stochastic rate models (Vasicek, CIR) with intensity models for CVA. Supports automatic differentiation (AAD) for sensitivities.
- Why it fits: Pure Python/PyTorch alternative to C++-heavy ORE. The blueprint pattern (rate model calibration → joint simulation with correlation → exposure profile calculation → CVA/DVA aggregation) is clearly implemented. Newer project but shows modern PyTorch-based approach for the GPU-accelerated XVA computation paradigm.
- Last active: 2024

#### Candidate 3: sa-ccr/sa-ccr-python

- URL: https://github.com/sa-ccr/sa-ccr-python
- Stars: ~30
- Language: Python
- Description: Python implementation of SA-CCR (Standardized Approach for Counterparty Credit Risk) based on CRR2 Regulation. Calculates replacement cost and potential future exposure for various asset classes.
- Why it fits: SA-CCR is the Basel III/CRR2 regulatory framework for computing counterparty credit risk capital. Every bank must implement it. This is the cleanest Python implementation. Blueprint covers: trade classification → netting set aggregation → supervisory factor application → EAD computation. Simpler than full XVA but directly regulatory-compliant.
- Last active: 2023

---

### Gap 12: MBS/ABS Modeling

Priority: P1

**Context**: Mortgage-backed securities and asset-backed securities require prepayment modeling, waterfall cash flow simulation, and tranche pricing. No existing blueprint covers structured finance.

#### Candidate 1: yellowbean/AbsBox + Hastructure

- URL: https://github.com/yellowbean/AbsBox (Python wrapper)
- Hastructure engine: https://github.com/yellowbean/Hastructure
- Stars: ~56 (AbsBox) / ~80 (Hastructure)
- Language: Python wrapper over Haskell engine
- Description: Cashflow engine for ABS/MBS structured finance. Models waterfalls (senior/mezzanine/equity tranches), prepayments, defaults, recoveries, triggers. Human-readable waterfall definition using Python dicts/lists. Supports pool-level and loan-level modeling.
- Why it fits: Only serious open-source ABS/MBS cash flow engine with Python interface. The waterfall modeling pattern (pool cash flow → sequential/pro-rata distribution → coverage tests → triggers → tranche paydown) is the core structured finance blueprint. Active maintainer (yellowbean/Shawn Zhang) with good documentation.
- Last active: 2024-2025 (actively maintained)

#### Candidate 2: AyushiVinayB/MBSModel

- URL: https://github.com/AyushiVinayB/MBSModel
- Stars: ~15
- Language: Python
- Description: Pricing and Risk Application for Mortgage Backed Securities. Models pass-through MBS with PSA prepayment model (Public Securities Association benchmark), cash flow projections, duration and convexity calculations, OAS (Option-Adjusted Spread) analytics.
- Why it fits: Shows the prepayment modeling layer specifically — the PSA model and CPR (Constant Prepayment Rate) are the standard inputs for agency MBS pricing. Blueprint for the prepayment → cash flow projection → price/duration sub-pipeline. Simpler and more extractable than AbsBox for the MBS-specific patterns.
- Last active: 2023

#### Candidate 3: cfrm17/cmbs

- URL: https://github.com/cfrm17/cmbs
- Stars: ~10 (niche)
- Language: Python
- Description: Commercial Mortgage Backed Securities (CMBS) modeling. Covers CMBS tranche structure, credit enhancement, IO strips, DSCR (Debt Service Coverage Ratio) triggers, default/loss allocation to tranches.
- Why it fits: CMBS is distinct from residential MBS (agency). The DSCR → credit enhancement → loss allocation pipeline is a separate blueprint. Domain-best for CMBS-specific structured finance patterns.
- Last active: 2023

---

## P2 — Medium Priority Gaps

---

### Gap 13: Factor Discovery System

Priority: P2

**Context**: Systematic alpha factor mining (WorldQuant/Citadel style) — generating, testing, and selecting quantitative signals from price/volume/fundamental data.

#### Candidate 1: microsoft/qlib

- URL: https://github.com/microsoft/qlib
- Stars: ~20,000+ (recently surged with RD-Agent integration)
- Language: Python
- Description: AI-oriented quant investment platform by Microsoft Research Asia. Full ML pipeline: data processing, model training, backtesting, portfolio optimization, order execution. Factor research via Alpha360/Alpha158 benchmark datasets. Now integrates RD-Agent for automated factor discovery.
- Why it fits: The most authoritative open-source quantitative research platform. The factor discovery pipeline (data preparation → feature engineering → ML model training → alpha signal evaluation → portfolio construction) is the definitive reference. RD-Agent adds LLM-driven automated factor generation. Stars surge (6,000 in one month) confirms current relevance.
- Last active: 2025 (very active)

#### Candidate 2: QuantaAlpha/QuantaAlpha

- URL: https://github.com/QuantaAlpha/QuantaAlpha
- Stars: ~50 (very new, April 2025 founded)
- Language: Python
- Description: LLM + evolutionary strategy driven factor mining. User describes research direction, factors are automatically generated, evolved, and validated. Uses Qlib as backtesting backend. Web UI with factor library and independent backtesting.
- Why it fits: Represents the cutting-edge paradigm (LLM-guided evolutionary factor mining). The architecture (research hypothesis → LLM factor expression generation → backtesting → evolutionary selection → factor library) is a new blueprint pattern emerging in 2025. Founded by academics from Tsinghua/PKU/CMU.
- Last active: 2025 (actively developing)

#### Candidate 3: marketneutral/alphatools

- URL: https://github.com/marketneutral/alphatools
- Stars: ~300
- Language: Python
- Description: Quantitative finance research tools. Parses and compiles "expression" style alphas (WorldQuant Alpha101 style) into Zipline/Pipeline factors. Integration with Quantopian Pipeline framework.
- Why it fits: The formula-to-factor compilation pattern (mathematical expression → executable factor → cross-sectional evaluation → IC/IR metrics) is a clean blueprint for the systematic alpha generation layer. Shows the "expression alpha" paradigm (as opposed to ML-based alpha).
- Last active: 2022 (established, stable)

---

### Gap 14: Bond Index / Fixed Income Analytics Deep

Priority: P2

**Context**: Bond index construction, duration management, yield curve fitting, spread analytics. Partially covered by existing quant blueprints but not as a dedicated fixed income focus.

#### Candidate 1: domokane/FinancePy

- URL: https://github.com/domokane/FinancePy
- Stars: ~2,000
- Language: Python
- Description: Comprehensive Python finance library for pricing and risk-management of financial derivatives: fixed income, equity, FX, credit. Covers bond pricing, yield curve fitting, duration/convexity, interest rate swaps, options, CDS. Well-documented with Jupyter notebooks.
- Why it fits: The most complete Python fixed income library with broad coverage. Bond analytics blueprint (yield curve bootstrapping → bond pricing → DV01/duration/convexity → spread analytics → portfolio risk aggregation) is fully implemented. 2,000 stars validates community adoption.
- Last active: 2024-2025 (actively maintained)

#### Candidate 2: attack68/rateslib

- URL: https://github.com/attack68/rateslib
- Stars: ~223
- Language: Python
- Description: State-of-the-art fixed income library. Multi-curve construction, automatic differentiation for risk sensitivities, bond futures, IRS, XCS pricing. Designed by practitioners from global investment banks.
- Why it fits: Institutional-grade curve construction methodology. The multi-curve framework (OIS discounting, IBOR forwards, spread adjustments) is the modern fixed income analytics architecture. Better than FinancePy for rate derivatives; both are complementary.
- Last active: 2025 (actively maintained)
- Note: Source-available dual license (non-commercial free, commercial subscription). Blueprint extraction permissible.

#### Candidate 3: reese3928/fincomepy

- URL: https://github.com/reese3928/fincomepy
- Stars: ~30
- Language: Python
- Description: Fixed income calculations: bond pricing, yield-to-maturity, Macaulay duration, modified duration, DV01, convexity, key rate duration, yield curve bootstrapping.
- Why it fits: Simpler, focused fixed income calculation library. Good reference for the bond analytics sub-pipeline blueprint. Clean Python with no heavy dependencies — easy to read and extract patterns from.
- Last active: 2023

---

### Gap 15: Carbon Credit / Climate Finance

Priority: P2

**Context**: Carbon accounting, emission trading, ESG portfolio analytics. Nascent but rapidly growing domain with regulatory momentum (EU Taxonomy, SEC climate disclosure rules).

#### Candidate 1: opentaps/open-climate-investing

- URL: https://github.com/opentaps/open-climate-investing
- Stars: ~48
- Language: Python
- Description: Multi-factor equity returns model adding Brown Minus Green (BMG) climate factor to Fama-French/Carhart. Calculates market-implied carbon risk of stocks, portfolios, mutual funds. Portfolio optimization to minimize carbon risk. Free book included.
- Why it fits: The climate factor model pattern (factor construction from emissions data → regression on historical returns → BMG factor loading → portfolio optimization with climate constraint) is novel and extractable. Only Python implementation of the BMG factor for climate-aligned investing.
- Last active: 2023 (established)

#### Candidate 2: hyperledger-labs/blockchain-carbon-accounting

- URL: https://github.com/hyperledger-labs/blockchain-carbon-accounting
- Stars: ~200
- Language: TypeScript/JavaScript (Hyperledger Fabric + Hardhat)
- Description: Blockchain application for climate action accounting: emissions calculations, carbon trading, validation of climate claims. Part of Linux Foundation Hyperledger Climate Action SIG. Includes Voluntary Carbon Offsets Directory.
- Why it fits: The carbon credit issuance and trading workflow (emissions measurement → verification → credit issuance → registry → trading → retirement) is the core climate finance architecture. Despite non-Python primary language, the architecture is clearly documented and extractable as a blueprint.
- Last active: 2023

#### Candidate 3: os-climate (OS-Climate organization)

- URL: https://github.com/os-climate
- Stars: Org-level (multiple repos)
- Language: Python
- Description: Linux Foundation OS-Climate initiative. Multiple Python tools for climate finance: physical risk analytics, transition risk modeling, PCAF (Partnership for Carbon Accounting Financials) methodologies, data commons for climate-financial data.
- Why it fits: The OS-Climate organization represents the institutional approach to climate finance analytics. The physical risk blueprint (asset location → climate hazard data → exposure scoring → portfolio climate VaR) and transition risk blueprint (carbon intensity → policy scenario → stranded asset modeling) are both here.
- Last active: 2024-2025 (actively maintained by LF Energy community)

---

### Gap 16: Real Estate / REIT Analytics

Priority: P2

**Context**: Property valuation models, REIT financial analysis, cap rate modeling, rent roll analysis. No existing blueprint covers real estate finance.

#### Candidate 1: jayshah5696/AutomaticValuationModel

- URL: https://github.com/jayshah5696/AutomaticValuationModel
- Stars: ~30
- Language: Python
- Description: Automated Valuation Model (AVM) for real estate. Uses comparable sales data to estimate property value via ML. Analyzes historical price movements, property characteristics. Standard AVM architecture used by Zillow, Redfin, and appraisal firms.
- Why it fits: The AVM blueprint (property feature engineering → comparable selection → hedonic regression/ML → confidence interval → automated valuation) is the core real estate analytics pattern. Every prop-tech and REIT analytics system uses some form of AVM.
- Last active: 2022

#### Candidate 2: rajarshimaity3235/REIT

- URL: https://github.com/rajarshimaity3235/REIT
- Stars: ~10 (niche, domain-best)
- Language: Python (Streamlit)
- Description: REIT Analytics Streamlit dashboard. Historical price/volume analysis, financial metrics (FFO, AFFO, NAV, cap rate, dividend yield, payout ratio), geographical diversification visualization for REIT portfolios.
- Why it fits: Domain-best for REIT-specific financial metrics. The REIT analysis blueprint (FFO/AFFO computation → NAV estimation → cap rate analysis → geographic exposure → peer comparison) uses REIT-specific accounting adjustments that differ from standard equity analysis. Blueprint for the "REIT-specific metric" layer.
- Last active: 2023

#### Candidate 3: crankstorn/real-estate-analysis

- URL: https://github.com/crankstorn/real-estate-analysis
- Stars: ~30
- Language: Python (Streamlit)
- Description: Residential real estate return analysis web application. Compares properties on rental yield, cash-on-cash return, IRR, NOI. Input rent roll and expense assumptions, outputs investment metrics.
- Why it fits: The real estate investment analysis pipeline (property data → income/expense modeling → cash flow projection → return metrics: cap rate/IRR/cash-on-cash → sensitivity analysis) is extractable. Shows the "rental property underwriting" blueprint, which is distinct from AVM and REIT analytics.
- Last active: 2023

---

## Summary Table

| Gap | Priority | Best Candidate | Stars | Language | Blueprint Confidence |
|-----|----------|---------------|-------|----------|---------------------|
| AML/KYC | P0 | IBM/AMLSim + checkmarble/marble | 304 / 500+ | Python / Go | High |
| IFRS 9 ECL | P0 | naenumtou/ifrs9 | ~70 | Python | High |
| Stress Testing | P0 | ox-inet-resilience/firesale_stresstest | ~50 | Python | Medium (composite needed) |
| Robo-Advisor | P0 | wealthbot-io/wealthbot | ~675 | PHP (arch extractable) | High |
| Insurance/Actuarial | P0 | casact/chainladder-python | ~200 | Python | High |
| Loan Origination | P1 | frappe/lending | ~264 | Python | High |
| Treasury/ALM/IRRBB | P1 | Open_Source_Economic_Model | ~40 | Python | Medium |
| NL Stock Query | P1 | xang1234/stock-screener + OpenBB | 50 / 31,000 | Python | High |
| Research Reports | P1 | AI4Finance/FinRobot | ~4,800 | Python | High |
| Payment/Ledger | P1 | formancehq/ledger | ~1,100 | Go+API | High |
| CVA/XVA | P1 | OpenSourceRisk/Engine | ~658 | C++/Python | High |
| MBS/ABS | P1 | yellowbean/AbsBox | ~56 | Python | High |
| Factor Discovery | P2 | microsoft/qlib | ~20,000 | Python | High |
| Fixed Income Deep | P2 | domokane/FinancePy | ~2,000 | Python | High |
| Carbon Finance | P2 | opentaps/open-climate-investing | ~48 | Python | Medium |
| Real Estate/REIT | P2 | jayshah5696/AutomaticValuationModel | ~30 | Python | Medium |

---

## Extraction Priority Recommendation

For immediate blueprint extraction (highest ROI):

1. **casact/chainladder-python** — Clean Python, CAS-backed, well-documented, P&C reserving blueprint is self-contained
2. **naenumtou/ifrs9** — Python notebooks, IFRS 9 staging logic explicitly coded, easy to trace
3. **AI4Finance/FinRobot** — High stars, multi-agent report generation architecture clearly documented
4. **microsoft/qlib** — Essential factor discovery reference, extremely well-documented
5. **opensanctions/opensanctions** — Python, active, entity matching architecture extractable
6. **yellowbean/AbsBox** — Only Python ABS/MBS engine, maintainer responsive
7. **formancehq/ledger** — Best ledger architecture documentation, Go but REST-first design

For composite blueprints (require combining 2-3 projects):
- **IFRS 9 complete**: naenumtou/ifrs9 + Daniel11OSSE/ifrs9-ecl-modeling + open-risk/openLGD
- **AML full stack**: IBM/AMLSim (data) + checkmarble/marble (engine) + opensanctions (data layer)
- **Stress testing**: firesale_stresstest + Open_Source_Economic_Model + open-risk/portfolioAnalytics
