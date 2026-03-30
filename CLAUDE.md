# CLAUDE.md - Doramagic 项目规范

> 继承 `~/.claude/CLAUDE.md` 全局规范。本文件仅包含 Doramagic 特有规则。

---

## 项目信息

- **语言**: Python 3.12
- **包管理**: uv
- **架构**: Conditional DAG（FlowController + Phase Executors）
- **版本**: 见 pyproject.toml `version` 字段

## 构建与测试命令

```bash
make check      # lint + typecheck + test（提交前必须通过）
make lint       # ruff check packages/ tests/
make format     # ruff format packages/ tests/
make typecheck  # mypy（contracts 包 + 逐步扩展）
make test       # pytest tests/ packages/
```

## 项目特有规则

### LLM 调用

生产代码**禁止**直接 `import anthropic` 或 `import google.generativeai`，必须通过 `packages/shared_utils/doramagic_shared_utils/llm_adapter.py` 的 `LLMAdapter` 统一调用。

### Contracts 层

`packages/contracts/doramagic_contracts/` 是所有包的唯一依赖锚点。修改 contracts 必须确认不破坏下游包。

### Bricks 知识积木

`bricks/` 目录存放 JSONL 知识积木文件：
- 每文件至少 15% 为 `knowledge_type: "failure"`（反模式）
- 每条 brick 需要真实文档 URL 的 `evidence_refs`
- 新增 brick 后更新 `packages/extraction/doramagic_extraction/brick_injection.py` 的框架映射

### 发布（完整流程，不可跳步）

```bash
# 1. 版本号同步（pyproject.toml + SKILL.md + README.md + marketplace.json）
# 2. skills/doramagic/packages/ 副本同步（rsync）
# 3. make check 全通过
bash scripts/publish_preflight.sh                     # 4. 预检
bash scripts/release/publish_to_github.sh vX.Y.Z --dry-run  # 5. 试运行
bash scripts/release/publish_to_github.sh vX.Y.Z            # 6. 正式发布（含 GitHub + ClawHub）
# 7. 在 GitHub 创建 Release（英文 release notes）
# 8. 写开发日志 + 更新踩坑记录
```

发布脚本自动执行：GitHub push + tag + ClawHub publish。
ClawHub slug: `dora`（不是 doramagic）
GitHub 远程: `https://github.com/tangweigang-jpg/Doramagic.git`

### 已知技术债

- `packages/orchestration/` 是旧版 PhaseRunner，已被 `packages/controller/` 取代，待废弃
- `skills/doramagic/packages/` 是手动维护的副本，发布前须同步
- 6 组测试在 `make test` 中被 `--ignore`，需逐步恢复

### 开发前必读

- `docs/pitfalls.md` — 踩坑记录
- `TODOS.md` — 待办与安全发现
- `docs/rules/01-global-engineering-rules-v1.md` — 全局工程规则（Google × Claude）
- `docs/rules/02-doramagic-product-rules-v1.md` — Doramagic 产品规则（基于踩坑）
- `docs/rules/03-discussion-checklist-v1.md` — 需要与 CEO 讨论的决策清单

---

*最后更新: 2026-03-29*
