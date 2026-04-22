# Grok 的 AI 顾问知识结构框架

> 来源：Grok 网页版回复，2026-04-02

---

## 1. 知识类型（5类）

Grok 认为 Claude 的"约束/资源/模式"分类存在两处遗漏：

| 类型 | 英文 | 核心作用 | 为什么必须独立成类 |
|------|------|----------|------------------|
| Constraints | 约束（不变式） | 硬性"禁止+为什么+检测方法" | 防止LLM犯领域专家绝不会犯的低级错误 |
| Resources | 资源（带权衡表） | 推荐组件+替代方案+选择决策树 | 让LLM自动做出"生产级选型"而非默认免费API |
| Patterns | 模式（共识架构） | 跨项目验证过的代码结构/流程 | 提供可直接套用的"生产级骨架" |
| Protocols | 协议（运营流程） | 测试、部署、监控、风控完整闭环 | 确保代码"可运维、可审计、可演进" |
| Synthesis Rules | 合成规则 | 知识碰撞与自动生成机制 | 让同一个晶体在不同AI工具中都能"自我进化" |

## 2. 知识层级（5层洋葱模型）

- **Layer 0: Universal（通用计算原理）** — 所有软件共性（CS基础）
- **Layer 1: Domain（领域基础）** — 定量金融核心原理
- **Layer 2: Application（应用层）** — 算法交易/分析系统特性
- **Layer 3: Ecosystem（生态层）** — freqtrade、zipline、vnpy等跨项目共识
- **Layer 4: Instance（实例层）** — 用户本次具体需求

## 3. 类型×层级交叉示例

### Constraints
- L0：永远不要用float做货币/价格计算
- L1：财务计算必须使用decimal.Decimal或numpy.float128
- L2：回测时禁止任何look-ahead bias（必须用.shift(1)或event-driven pipeline）
- L3：freqtrade/zipline/vnpy共识——禁止用免费实时API做live决策
- L4：若支持加密货币，额外约束"永不使用中心化交易所的未验证K线"

### Resources
- L0：Python >= 3.11 + pandas + numpy
- L1：数据源必须支持corporate actions自动调整
- L2：回测引擎推荐zipline或freqtrade；禁止纯pandas rolling做生产回测
- L3：交易所接入统一使用ccxt + freqtrade的exchange wrapper
- L4：用户指定"支持A股"→自动推荐akshare + vnpy CTP接口

### Patterns
- L0：Strategy类模式（populate_indicators / populate_buy_trend / populate_sell_trend）
- L2：Research vs Execution分离
- L3：Protection层模式（MaxDrawdown、Cooldown、LowProfitPairs）
- L4：实时可视化仪表盘→streamlit + plotly + freqtrade RPC

### Protocols
- L2：回测必须包含slippage模型、commission、market impact；必须跑out-of-sample + walk-forward验证
- L3：必须先dry-run模式再live；日志必须包含trade_id + reason + fee全链路
- L4：多账户风控→全局仓位上限 + 单股最大暴露监控

### Synthesis Rules
- 规则1：Resource选择直接生成Constraint
- 规则2：Layer碰撞生成新知识
- 规则3：分歧信号处理（生成"混合资源决策树"）

## 4. 知识关系

- 资源选择→约束衍生（核心生成关系）
- 层级碰撞→新交叉知识
- Protocols锚定一切（任何Pattern/Constraint最终都要被Protocol验证）

## 5. LLM已有 vs 必须注入

- LLM已有（~30%）：L0全部、基础设计模式、通用金融公式
- 必须注入（~70%）：全部L3、全部L2生产约束、全部Synthesis Rules、全部Protocols、具体权衡表与决策树

## 6. 对前提假设的评价

"差距=约束知识缺失"85%准确，缺失两块：
1. 缺少"可执行的Operational Protocols"
2. 缺少动态合成能力

种子晶体的优化建议：
1. 内置版本控制与演进机制
2. 内置可审计性（每条约束附来源）
