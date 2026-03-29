# Brick Coverage Validation
日期: 2026-03-29

## 背景与目标

`bricks/` 目录里已有多个 JSONL 文件（agent_evolution、api_integration、crewai 等），
但我们不知道这些 brick 对"真实场景"的覆盖率是多少。

问题：如果用户提交一个新的 skill 请求，Phase D（Synthesis）能从 brick 库匹配到多少有用知识？
覆盖率不足时，生成质量会降低。

目标：建立一套可重复运行的验证流程——取 100 条多样化的真实 ClawHub skill 描述，
模拟 brick 匹配，输出覆盖率指标，并给出行动阈值。

## 不在范围内

- 不评估 brick 内容质量（只评估覆盖率，即"能不能匹配到"）
- 不修改 brick 内容或 brick 注入逻辑
- 不评估 Phase B/C/E/F 的质量

## 方案设计

### 第一步：获取 100 条 skill 描述

**来源**：ClawHub API（`platform_openclaw` 包已有封装）

```python
# 调用方式（参考 packages/platform_openclaw）
skills = clawhub_client.list_skills(limit=200, sort="popular")
# 按领域分层采样，确保多样性：
#   健康/饮食 ≤ 15%，财务 ≤ 15%，旅行 ≤ 15%，其他领域补齐至 100 条
descriptions = [s.description for s in skills[:100]]
```

若 API 不可用，用 `bricks/BRICK_INVENTORY.md` 中已记录的 skill 类型作为 mock。

### 第二步：模拟 brick 匹配

复用 `packages/extraction/doramagic_extraction/brick_injection.py` 的匹配逻辑：

```python
for desc in descriptions:
    matched = brick_injector.match(desc, top_k=3)
    if matched and matched[0].score >= 0.5:
        result = "hit"
    elif matched:
        result = "partial"     # 有匹配但置信度低
    else:
        result = "miss"
```

### 第三步：覆盖率指标

```
total_hit     = count(result == "hit")
total_partial = count(result == "partial")
total_miss    = count(result == "miss")

coverage_rate = (total_hit + total_partial * 0.5) / 100
hit_rate      = total_hit / 100
```

附加指标：
- **领域分布**：哪些领域 miss 最多（找 brick 补充优先级）
- **Top miss 词**：miss 的 description 里出现频率最高的词（指导新 brick 主题）

### 第四步：行动阈值

| coverage_rate | 结论 | 行动 |
|--------------|------|------|
| >= 90% | brick 库充足 | 无需扩充，进入下一优先级 |
| 80%-89% | 基本够用，有缺口 | 补充 top 3 miss 领域的 brick（各 ≥ 5 条） |
| < 80% | 覆盖不足 | 启动 brick 扩充 sprint，目标补至 90% |

### 产出物

脚本 `scripts/validate_brick_coverage.py`，输出报告到 `reports/brick_coverage_<date>.json`：

```json
{
  "date": "2026-03-29",
  "total": 100,
  "hit": 72,
  "partial": 14,
  "miss": 14,
  "coverage_rate": 0.79,
  "action": "expand",
  "top_miss_domains": ["iot", "education", "legal"],
  "top_miss_terms": ["sensor", "quiz", "contract"]
}
```

## 验证标准

1. 脚本对 mock 的 100 条描述能正常跑完，输出 JSON 报告，不抛异常
2. 已知高覆盖领域（如"API 集成"）的 hit_rate >= 0.8（sanity check）
3. 行动阈值逻辑正确：mock coverage_rate=0.78 → action="expand"（单元测试）

## 风险与权衡

- **ClawHub API 可用性**：若 API 限流，样本不足 100 条。缓解：缓存一次结果到
  `data/clawhub_sample_100.json`，后续重复验证不重复调用 API。
- **匹配逻辑代表性**：`brick_injection.py` 的匹配算法可能与 Phase D 实际使用的路径不完全一致，
  导致覆盖率高估。需确认调用的是生产路径，非简化版。
- **采样偏差**：ClawHub 热门 skill 可能集中在少数领域。需要分层采样确保多样性，否则
  覆盖率数字仅反映热门领域，不代表长尾。
