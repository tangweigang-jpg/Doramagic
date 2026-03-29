# Contributing to Doramagic

## Getting Started

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git
cd Doramagic
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Running Tests

```bash
make test
```

Or manually:

```bash
PYTHONPATH=packages/contracts:packages/extraction:packages/shared_utils:packages/community:packages/cross_project:packages/skill_compiler:packages/orchestration:packages/platform_openclaw:packages/domain_graph:packages/controller:packages/executors:packages/racekit:packages/evals \
  .venv/bin/python -m pytest tests/ packages/ -v \
  --ignore=packages/preextract_api \
  --ignore=packages/doramagic_product
```

## Project Structure

- `packages/` -- Core Python engine (contracts, controller, executors, extraction, orchestration, etc.)
- `bricks/` -- 278 knowledge bricks across 34 frameworks/domains (JSONL format)
- `skills/doramagic/` -- Self-contained OpenClaw / Claude Code skill bundle
- `tests/` -- Unit and E2E smoke tests (26 tests)
- `scripts/` -- Utility and release scripts

## Architecture Overview

Doramagic v12.1.1 uses a **conditional DAG** (not a linear pipeline):

- `packages/controller/` -- FlowController with conditional edge FSM
- `packages/executors/` -- Phase executors (NeedProfileBuilder, WorkerSupervisor, DiscoveryRunner, etc.)
- `packages/extraction/` -- Stage 0-5 soul extraction pipeline (runs inside each RepoWorker)
- `packages/contracts/` -- Pydantic schemas shared across all packages

## Adding Knowledge Bricks

Bricks are JSONL files in `bricks/`. Each line is a JSON object:

```json
{
  "brick_id": "framework-l1-name",
  "domain_id": "framework",
  "knowledge_type": "rationale|capability|constraint|interface|failure|assembly_pattern",
  "statement": "The knowledge claim (max 200 words, focus on WHY/UNSAID)",
  "confidence": "high",
  "signal": "ALIGNED",
  "source_project_ids": ["hardcoded-expert-knowledge"],
  "support_count": 5,
  "evidence_refs": [{"kind": "community_ref", "path": "https://docs.example.com/...", "start_line": null, "end_line": null, "snippet": null, "artifact_name": null, "source_url": "https://docs.example.com/..."}],
  "tags": ["framework", "topic", "l1"]
}
```

Requirements:
- At least 15% of bricks per file should be `knowledge_type: "failure"` (anti-patterns)
- Every brick needs a real documentation URL in `evidence_refs`
- L1 bricks (framework philosophy) tagged with `"l1"` in tags

After adding bricks, update the framework mapping in `packages/extraction/doramagic_extraction/brick_injection.py`.

## Code Quality

```bash
make lint       # ruff check
make format     # ruff format
make typecheck  # mypy on contracts
make check      # all of the above + tests
```

## 开发流程（赛马制）

所有功能开发采用赛马模式，Claude Code 和 Codex 并行实现，择优合并：

1. **调研** — 开发前先做外部调研
2. **设计** — 写清楚"做什么、为什么做、怎么验证成功"
3. **赛马** — 创建 `claude/<功能名>` 和 `codex/<功能名>` 两条分支
4. **评审** — 对比两个实现（正确性、代码质量、测试覆盖）
5. **合并** — 择优合并到 `main`，删除赛马分支
6. **日志** — 写开发日志 + 踩坑记录

分支命名规则：
- `claude/<功能名>` — Claude Code 赛马分支
- `codex/<功能名>` — Codex 赛马分支
- `fix/<问题>` — 热修复

## Pull Requests

1. 创建功能分支（遵循上述命名规则）
2. 完成开发
3. 运行 `make check`（lint + typecheck + tests 必须全部通过）
4. 提交 PR，描述必须包含 **为什么** 这样改（不是改了什么）
5. PR 合并前必须通过 AI 代码审查

### Commit Message 格式（中文）

```
<类型>: <描述>

类型: 功能 | 修复 | 重构 | 测试 | 文档 | 构建 | 发布
```

## 日志与踩坑记录

### 开发日志

每个任务完成后必须写日志，存放在 `docs/logs/YYYY-MM-DD-<描述>.md`。

### 踩坑记录

遇到问题后追加到 `docs/pitfalls.md`，格式：
```
不要<做法>（因为<原因>，发现于<日期>）
```

开发前**必须先读取** `docs/pitfalls.md`。

## 发布检查清单

### 发布到 GitHub 前

```bash
# 预检
bash scripts/publish_preflight.sh

# 正式发布
bash scripts/release/publish_to_github.sh vX.Y.Z
```

预检内容：社区标准文件完整、无硬编码密钥/路径、无内部文件泄露、版本号一致、lockfile 同步。

### GitHub 版本必须

- [ ] 版本号符合 semver（vX.Y.Z）
- [ ] 在 main 分支，工作树干净
- [ ] `make check` 全部通过
- [ ] 社区文件完整（README、LICENSE、CHANGELOG、CONTRIBUTING、SECURITY、INSTALL）
- [ ] 内部目录已清理（research/、experiments/、races/ 等）
- [ ] 内部文件已移除（TODOS.md、INDEX.md 等）

## License

MIT
