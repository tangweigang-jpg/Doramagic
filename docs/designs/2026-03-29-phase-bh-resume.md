# Phase B-H Crash Resume
日期: 2026-03-29

## 背景与目标

Phase A 已有断点续跑能力：`FlowController.run()` 接受 `resume_run_id`，调用 `load_state()` 恢复
`ControllerState`，从 `PHASE_A_CLARIFY` 继续执行。

但 Phase B-H 无此能力。若 Phase C（fan-out，最耗时）或 Phase E（编译）中途崩溃，
整个 run 需从头重来，浪费 API 额度和时间。

目标：让 Phase B-H 支持从最后一个**已完成**的 Phase checkpoint 恢复，不重跑已完成的 Phase。

## 不在范围内

- 不支持 Phase 内部（executor 内部）的细粒度断点（如逐 repo 恢复）
- 不修改 `ControllerState` 的核心字段结构（保持向后兼容）
- 不引入外部数据库，只用文件系统

## 方案设计

### 现有状态管理

`ControllerState.phase_artifacts` 已经按 executor 名存储结果（`discovery_result`、
`extraction_aggregate` 等）。`save_state()` 在每次 run 结束时持久化到 `run_dir/state.json`。

缺口：Phase 执行**成功后**没有中间 checkpoint，崩溃时 state.json 可能停在上一次保存的旧状态。

### 方案：Phase 完成即 checkpoint

在 `_dispatch_executor()` 成功返回、调用 `self._transition(next_phase)` **之前**，
立即调用 `save_state()`。这样每个 Phase 完成就持久化一次，crash 后可恢复到最近完成的 Phase。

```python
# flow_controller.py _dispatch_executor() 末尾，transition 前插入：
save_state(self._state, self._run_dir)   # checkpoint after each phase
self._transition(next_phase)
```

### Resume 检测

`FlowController.run(resume_run_id=...)` 已有 resume 入口。扩展逻辑：

```python
if resume_run_id:
    state = load_state(run_dir)
    # Phase A clarify 原有逻辑不变
    # 新增：其他 Phase 直接从 state.phase 继续，无需额外分支
    # 因为 phase_artifacts 已含已完成 Phase 的结果，executor 不会重跑
```

关键点：`while` 循环从 `state.phase` 开始，已完成的 Phase 结果已在 `phase_artifacts` 里，
executor 被调用时可检查是否已有结果（通过 `_check_phase_cache` 辅助函数）跳过重复执行。

### 每 Phase checkpoint 存储内容

`state.json` 已包含所有必要字段（见 `ControllerState.to_dict()`）：
- `phase`: 下一个待执行的 Phase（transition 后的值）
- `phase_artifacts`: 所有已完成 Phase 的产出（executor 结果）
- `degraded_mode`, `delivery_tier`, `revise_count` 等控制字段

无需新增字段，只需确保 checkpoint 在正确时机写入。

### 清理

run 正常完成（`DONE` / `DEGRADED`）后，`state.json` 保留（用于审计）。
提供 `scripts/cleanup_runs.py` 定期清理超过 N 天的 run 目录。

## 验证标准

1. 模拟 Phase C 完成后 crash（state.json 停在 `PHASE_D`），resume 后直接从 Phase D 开始，
   Phase B/C 的 executor 不被调用（通过 mock executor 的调用次数验证）
2. `state.json` 在每个 Phase 完成后更新（内容中 `phase` 字段递进），通过文件时间戳验证
3. Resume 后最终产出与一次性完整 run 结果一致（integration test）

## 风险与权衡

- **executor 幂等性假设**：checkpoint 方案依赖"已有 artifact = 不重跑"。若 executor 的
  `_check_phase_cache` 逻辑有 bug，可能静默跳过本该重跑的 Phase。需要明确的 cache-hit 日志。
- **state.json 写入频率增加**：每 Phase 一次，共 7 次 I/O。文件小（< 1MB），影响可忽略。
- **向后兼容**：旧 state.json（无中间 checkpoint）的 run 无法 resume 到中间 Phase，
  只能从头执行，这是可接受的降级。
