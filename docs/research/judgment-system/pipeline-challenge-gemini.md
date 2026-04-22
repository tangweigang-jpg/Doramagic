# Gemini 挑战结果

（完整内容已由用户提供，此文件为索引记录）

## 决策点 1：完全反对
- 双轨过滤制：
  - 轨道一（代码共证轨）：Closed + 关联 Merged PR → 最高质量，零门槛
  - 轨道二（边界妥协轨）：Closed + wontfix/works-as-intended/known-issue → 框架作者的使用禁忌
- Reactions 比 comments 更好的质量代理

## 决策点 2：部分反对
- 去重锚点应该是 Consequence（根本原因），不是 when+action
- 图谱聚合：只在同一 resource_deps 的判断中做撞库
- 合并 = 建立 Subsumes 关系，不是删除
- 保留 When 最精确的为主节点，被合并项的 evidence 累加

## 决策点 3：完全反对 LLM 展开
- "用 LLM 猜展开，是用幻觉对抗无知"
- 替代：基于 Schema 中的 Edges 做确定性图谱拓扑展开（最多 2 跳）
- 用户画像：基于 prompt 的实体密度判断水平
- 直接命中具有一票否决权，放 System Prompt 核心位
- 覆盖盲区警报是"极其性感的特性"
