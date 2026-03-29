# Cross-Project GCD (Greatest Common Denominator)
日期: 2026-03-29

## 背景与目标

`cross_project` 包已有 `compare.py`（跨项目信号分类：ALIGNED / MISSING / DRIFTED / ORIGINAL）和
`synthesis.py`（综合信号产出知识选择结果）。但这两个模块都是针对**单次运行、特定领域**的一次性操作。

问题：当 Doramagic 处理了同一领域（如"健康追踪"）的多个 skill 请求后，同一套实践模式会在不同 run 的
`synthesis_bundle` 里重复出现，但没有机制将它们"提升"为共享的 brick。

目标：实现一个 `gcd.py` 模块，扫描多次历史 run 产出，找到**跨 run 反复出现**的知识点，
自动写入 `bricks/` 作为新的 knowledge brick，供后续 run 直接复用。

## 不在范围内

- 不修改现有 `compare.py` / `synthesis.py` 逻辑
- 不自动删除旧 brick（只新增或标记 confidence 更新）
- 不跨领域 GCD（只在同一 `domain_id` 内做）
- 不实时触发（批处理，手动或定时运行）

## 方案设计

### 输入

```
GCDInput:
  domain_id: str               # 如 "health_tracking"
  run_dirs: list[Path]         # 该领域历史 run 目录，每个含 synthesis_report.json
  min_occurrence: int = 3      # 至少出现在几次 run 中才视为共识
  similarity_threshold: float = 0.75  # 使用 compare.py 的 Jaccard 相似度
```

### 处理流程

```
1. Extract   — 从每个 run_dir 读 synthesis_report.json，取出 decisions[].normalized_statement
2. Compare   — 复用 compare.py 的 _pairwise_matches + _components 逻辑（不重新实现）
3. Filter    — 保留跨 run 出现次数 >= min_occurrence 的 cluster
4. Dedupe    — 与现有 bricks/*.jsonl 做匹配，跳过已有 brick（避免重复写入）
5. Promote   — 将符合条件的 cluster 写为新 brick 行（JSONL 格式）
```

### 输出

新增到 `bricks/<domain_id>.jsonl`，每条 brick 格式复用 contracts 的 `KnowledgeAtom` 结构：

```json
{
  "atom_id": "gcd-<sha1>",
  "knowledge_type": "consensus",
  "subject": "...",
  "predicate": "...",
  "object": "...",
  "scope": "cross_project",
  "normative_force": "should",
  "confidence": 0.85,
  "gcd_meta": {
    "source_runs": ["run-001", "run-002", "run-003"],
    "occurrence_count": 3,
    "domain_id": "health_tracking",
    "promoted_at": "2026-03-29"
  }
}
```

### 集成点

- `FlowController` 中暂不自动调用；提供 CLI 脚本 `scripts/run_gcd.py`
- 未来可在 Phase A 的 `load_accumulated_knowledge()` 里加载 GCD brick，让后续 run 受益

## 验证标准

1. 对 3 个包含共同知识点的 mock `synthesis_report.json`，GCD 能产出至少 1 条新 brick
2. 对同领域已有 brick 的知识点，GCD 跳过（不重复写入），通过 brick `atom_id` 去重验证
3. `min_occurrence=3` 时，只出现 2 次的 cluster 不被提升（单元测试覆盖边界）

## 风险与权衡

- **误提升风险**：相似度 0.75 可能将不同含义的语句归为一类。缓解：`min_occurrence >= 3` + 人工抽检。
- **brick 膨胀**：批量运行后 JSONL 文件可能快速增长。后续需要 brick 剪枝机制（超出范围）。
- **复用 compare.py 内部函数**：`_pairwise_matches` 等函数是模块私有的，需将其提取为共享工具。
