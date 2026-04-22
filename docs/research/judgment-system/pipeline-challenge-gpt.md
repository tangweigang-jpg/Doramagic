# GPT 挑战结果

（完整内容已由用户提供，此文件为索引记录）

## 决策点 1：部分同意
- comments>=3 应从硬过滤改为弱特征（排序信号）
- 加入强信号：linked PR/commit, maintainer root cause reply
- 按 issue 类型分流：bug_report / incident_report / discussion_with_lesson / feature_request_with_constraint_signal
- 打分模型：linked_pr +3.0, has_repro +2.5, maintainer_reply +2.0...
- 阈值：>=3.0 直接送 LLM, 1.5-3.0 低优先, <1.5 丢弃
- 额外风险：幸存者偏差（只学到社区吵得凶的问题）、maintainer 风格偏差

## 决策点 2：部分同意
- 只比 when+action 不够，需要比 target, otherwise, applicability, resource_tags, layer, severity
- 四步：规范化签名 → 分桶 → 多信号判重 → LLM 裁决（只允许四类结果）
- 不做硬合并，用 canonical judgment + relations 挂载
- 分桶阈值：同资源同任务 0.78, 跨资源同模式 0.84, 跨领域 0.88

## 决策点 3：部分同意
- 先图谱扩展 1-2 跳，再 LLM 补盲
- 动态预算：脚本 2-4, EOD工具 5-8, 回测系统 8-12, 实盘 12+
- 用户水平启发式：新手信号（用词泛、不提具体约束）vs 专家信号（区分 backtest/paper/live）
- 缺口报告必须是一等公民
- 三层优先级：直接 1.0, 图谱 0.8, LLM 0.55-0.7
- 额外风险：可能学到"项目实现偏好"而非"领域约束"
