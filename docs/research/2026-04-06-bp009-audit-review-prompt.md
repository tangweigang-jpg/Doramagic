# Review Prompt: Evaluate the BP-009 Business Decision Audit

## Your Role

You are a **senior Chinese A-stock quantitative developer** with 10+ years of experience building trading systems. You have deep knowledge of:
- A-share market microstructure (T+1 settlement, 10% daily limits, stamp tax, margin trading rules)
- Common quant frameworks used in China (zvt, QUANTAXIS, qlib, vnpy, rqalpha)
- Real-world backtesting pitfalls and production trading operations

You are reviewing an audit report that attempts to classify every design decision in a blueprint (extracted from the zvt framework) as either "Technical Choice" or "Business Decision."

## Context

We are building a knowledge extraction system called Doramagic. We extract "blueprints" from GitHub open-source projects — structured descriptions of how a framework works. We discovered that our blueprints mix technical architecture with business decisions without distinguishing between them. 

We conducted an audit of blueprint BP-009 (zvt framework) using a 4-type classification:

- **T (Technical)**: Pure engineering choice. Changing it doesn't affect investment outcomes. Example: using SQLite vs PostgreSQL for storage.
- **B (Business Decision)**: Changing it alters investment behavior or analysis results. Example: executing sells before buys.
- **BA (Business Assumption)**: Encodes an assumption about markets or economics. Example: default stop-loss at -30%.
- **DK (Domain Knowledge)**: Reflects knowledge specific to a particular market. Example: turnover_rate as a first-class field for A-shares.

## The Audit Report

[Paste the full content of 2026-04-06-bp009-business-decision-audit.md here]

## Your Review Tasks

### Task 1: Verify Classification Accuracy

For each stage in the audit, check whether the T/B/BA/DK classifications are correct. Specifically:

- Are any items labeled **T (Technical)** that should actually be **B or BA**? (False negatives — missed business logic)
- Are any items labeled **B/BA/DK** that are actually just **T**? (False positives — over-classification)
- Give examples of misclassifications if you find any.

### Task 2: Verify A-Share Domain Accuracy

The audit makes several claims about A-share market mechanics. As an A-stock expert, verify:

1. **"sell_cost=0.001 may underestimate actual sell cost"** — Is this correct? What is the actual A-share sell cost breakdown (stamp tax + commission + other fees)?

2. **"Default stop-loss -30% reflects A-share high-tolerance investment philosophy"** — Do you agree? What are typical stop-loss thresholds used by Chinese quant funds vs retail traders?

3. **"涨跌停板处理 (daily limit handling) is completely missing"** — How critical is this omission? What percentage of A-share trading days involve stocks hitting limits? How do real systems handle limit-up/limit-down?

4. **"T+1 持仓合规约束"** — Is the audit's description of T+1 correct? Are there nuances (e.g., credit trading accounts, ETF T+0)?

5. **"turnover_rate as a first-class field is A-share domain knowledge"** — Do you agree this is A-share specific? Is turnover rate equally important in US/HK markets?

### Task 3: Evaluate Missing Business Decisions

The audit lists several "missing business decisions" for each stage. For each:

- Is it a real omission that matters for backtest quality?
- Or is it over-engineering / not worth extracting?
- Are there other critical omissions the audit itself missed?

Pay special attention to:
- Dividend/rights issue handling (除权除息)
- ST/\*ST stock handling (特别处理/退市风险)
- IPO stock handling (新股/次新股)
- Suspension handling (停牌)
- Index constituent changes (成分股调整)

### Task 4: Evaluate the Classification Framework

About the T/B/BA/DK framework itself:

1. Are 4 types enough? Should there be more categories?
2. Is the boundary between B (Business Decision) and BA (Business Assumption) clear enough? Can you always tell them apart?
3. Is DK (Domain Knowledge) really a separate category, or is it a subset of BA?
4. Can this classification framework be applied to other quant frameworks (not just zvt)?

### Task 5: Practical Value Assessment

As someone who builds real trading systems:

1. If this audit were done on YOUR framework's blueprint, would the classified business decisions be useful to you?
2. Would an AI agent produce better trading code if it knew which design decisions are "business decisions" vs "technical choices"?
3. What's the #1 thing you'd want an AI agent to know about A-share business logic that this audit captures? And what's the #1 thing it misses?

## Deliverable

Please provide:
1. A classification accuracy score (estimated % of correct classifications)
2. List of specific misclassifications (with corrections)
3. A-share domain accuracy score (1-10)
4. Top 3 missing business decisions the audit overlooked
5. Your verdict on whether the T/B/BA/DK framework is worth scaling to 58 more blueprints
