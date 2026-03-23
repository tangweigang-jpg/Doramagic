# DECISIONS_S1.md — cross-project.discovery 设计决策（Sonnet S1）

日期：2026-03-19
版本：v0.1（赛马 Round 2，赛道 A）

---

## D1: candidate_id 生成策略

**决策**：`candidate_id = "cand-" + SHA256(url)[:8]`

**理由**：
- URL 是项目的唯一稳定标识符（即使名称变化，URL 不变）
- SHA256 截断 8 位提供足够的碰撞抵抗力（约 4 billion 空间，项目库远小于此）
- 完全确定性：同一 URL 永远产生相同 ID，无需外部状态

**替代方案**：UUID v4（被否决，因为每次运行不同，破坏幂等性）

---

## D2: 粗筛策略（github_repo vs community_skill 分离处理）

**决策**：粗筛对 github_repo 和 community_skill 采用不同规则：
- `github_repo`：stars ≥ threshold，stale_months 内有更新，有 README，不在暗雷黑名单
- `community_skill`：仅检查 README 和暗雷黑名单（无 stars/日期字段）

**理由**：
- community_skill（clawhub:// URL）没有 stars/更新日期等量化指标
- 强制用相同标准会错误地过滤掉所有 OpenClaw 社区资源
- 规格明确要求区分两种类型，不能混淆

---

## D3: 相关度评分策略（三层关键词匹配）

**决策**：综合得分公式：
```
quick_score = relevance × 0.5 + quality × 0.3 + complementarity × 0.2
```

- **relevance**（0-1）：directions 字段精确/部分匹配 + tags 关键词匹配
- **quality**（0-1）：stars（log scale）+ forks 比率 + issue 活跃度 + 更新时间
- **complementarity**（0-1）：预置互补性分数（未来可从提取阶段动态计算）

**理由**：
- 相关度权重最高（0.5），防止高星但不相关的项目主导排名（规格禁止"直接把 stars 作为唯一排序信号"）
- 质量分采用 log scale 防止超高 stars 项目碾压低 stars 但高相关项目
- 互补性（0.2）预留未来增强空间，当前为静态预置值

---

## D4: 最小相关度阈值（`_MIN_RELEVANCE = 0.05`）

**决策**：`_search_direction` 中，相关度低于 0.05 的项目不进入候选池。

**理由**：
- 防止 quality + complementarity 分数把不相关项目"救活"
- 保证搜索结果语义相关，避免噪音
- 0.05 是宽松阈值（约等于 1 个 tag 关键词命中），防止过度过滤

---

## D5: 类型配额策略（保证 github_repo + community_skill 共存）

**决策**：在 `_deduplicate_and_rank` 中强制保留至少 1 个 community_skill 槽位：
```python
result.extend(github_repos[: max(top_k - 1, 1)])  # 最多 top_k-1 个 github_repo
remaining = top_k - len(result)
result.extend(community_skills[:remaining])         # 剩余槽位给 community_skill
```

**理由**：
- 规格验收标准明确要求至少 1 个 community_skill
- 纯分数排序可能导致 github_repo 完全占据 top_k，社区资源被挤出
- 配额策略保证了类型多样性，同时仍优先展示高分候选

**候选扩展**：未来可支持多类型配额（tutorial、use_case 各保留 N 个槽位）

---

## D6: search_coverage 完整性保证

**决策**：主流程先为每个 direction 构建 coverage 条目，再汇总候选。status 语义：
- `covered`：该方向有 score ≥ 4.0 的候选
- `partial`：有候选但最高分 < 4.0
- `missing`：完全无候选（相关度 < 0.05 或均被粗筛过滤）

**理由**：
- 规格明确禁止"静默丢掉某个 search_direction"
- 即使 degraded 状态，search_coverage 仍必须完整
- covered/partial/missing 区分帮助下游决定是否需要人工补充

---

## D7: API hint 的可选加权处理

**决策**：
- api_hint = None：发出 `W_NO_API_HINT` 警告，继续纯库搜索
- api_hint 存在：用 `domain_bricks` 对命中 brick 的候选加 +0.5 分（上限 10.0）

**理由**：
- 规格要求"API hint 缺失时仍能独立产出"
- 加权（非过滤）保持结果完整性，让相关候选适当提升排名
- +0.5 分轻量加权，不影响极不相关项目的命运

---

## D8: 降级（degraded）策略

**决策**：
- 0 候选 → `degraded + E_NO_CANDIDATES + no_candidate_reason`
- 1-2 候选 → `degraded + W_FEW_CANDIDATES`
- 有 missing direction → `degraded + W_MISSING_DIRECTIONS`
- 3-5 候选且所有 direction 至少 partial → `ok`

**理由**：
- 遵循 envelope 规格的 status 语义
- 降级（degraded）优于阻塞（blocked），下游仍可使用部分结果
- 警告驱动可观测性

---

## 候选扩展（未正式纳入当前 schema）

以下声明为"候选扩展"，当前版本不写入正式输出：

1. **real_github_search**：接入真实 GitHub API（`GET /search/repositories`）
2. **dynamic_complementarity**：从 Phase C 提取包反馈动态更新互补性分数
3. **embedding_similarity**：用 embedding 计算 `need_profile.intent` 与项目描述的语义相似度
4. **clawhub_api**：接入真实 OpenClaw Hub API 搜索社区 skill
5. **dark_trap_rules**：从 `doramagic-dark-traps.md` 动态加载暗雷规则，而非硬编码黑名单
