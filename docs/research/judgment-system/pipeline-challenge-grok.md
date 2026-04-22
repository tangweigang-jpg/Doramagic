# Grok 挑战结果

（完整内容已由用户提供，此文件为索引记录）

## 决策点 1：部分同意
- comments>=3 会误杀高质量独立 Bug Report
- 替代方案：mandatory 规则 + scoring_signals 加权打分（>=65分通过）
- 动态阈值：bug/incident >= 55, discussion >= 75
- 新增信号：linked_to_pr_or_commit (+25), author_reputation, reaction_total

## 决策点 2：反对
- 0.85 阈值同时造成漏重和误杀
- 替代方案：rule_based → hybrid_similarity (0.78) → LLM 裁决
- 合并策略：保留最早 id 为主条，证据追加，equivalent_to 记录

## 决策点 3：部分同意
- 图谱驱动优先，LLM 仅在 graph 扩展不足 10 条时触发
- 动态展开上限：min(12, 复杂度得分)
- 用户水平检测：专业术语密度
- 三层优先级：直接 1.0, graph 0.85, LLM 0.6
- 必须输出覆盖缺口警告
