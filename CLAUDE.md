# CLAUDE.md - Doramagic 项目规范

> 继承 `~/.claude/CLAUDE.md` 全局规范。本文件仅包含 Doramagic 特有规则。

---

## 产品灵魂（CRITICAL）

- **Doramagic 原则**：永远不教用户做事，给他工具
- **Doramagic 定位**：AI 领域的抄作业大师，善于从 GitHub 开源项目、skill、用户在 AI 领域的各种实践经验中提取知识
- 详细产品宪法见 `PRODUCT_CONSTITUTION.md`（新增功能或架构变更时必读）

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

`knowledge/bricks/` 是唯一物理知识源（JSONL 积木文件）。
根目录 `bricks/` 是指向 `knowledge/bricks/` 的符号链接（向后兼容）。

- 每文件至少 15% 为 `knowledge_type: "failure"`（反模式）
- 每条 brick 需要真实文档 URL 的 `evidence_refs`
- 新增 brick 后更新 `packages/extraction/doramagic_extraction/brick_injection.py` 的框架映射
- 直接编辑 `knowledge/bricks/*.jsonl`（或通过 bricks_v2/ 编译写入）

### 发布

完整 8 步流程见 `scripts/release/README.md`，不可跳步。ClawHub slug: `dora`。

### 已知技术债

- `packages/orchestration/` 是旧版 PhaseRunner，已被 `packages/controller/` 取代，待废弃
- ~~`skills/doramagic/packages/` 副本~~ 已解决：v13.1.0 起通过 pip 包分发
- 6 组测试在 `make test` 中被 `--ignore`，需逐步恢复

### 踩雷检查（CRITICAL）

涉及已知问题域（LLM 调用、积木体系、发布流程、contracts 变更）时，先查阅 `docs/pitfalls.md` 确认是否有相关踩坑经验。不重复踩已知的坑。

### 代码审查（CRITICAL）

当单轮改动满足以下**任一条件**时，必须在部署/测试前启动双引擎代码审查：

| 触发条件 | 阈值 |
|---------|------|
| 新增/修改代码行数 | ≥ 50 行 |
| 涉及文件数 | ≥ 3 个 |
| 修改了 contracts 层 | 任何改动 |
| 新增 async/LLM 调用路径 | 任何新增 |
| 修改了质量门禁/评分权重 | 任何改动 |

**审查流程**：
1. **Codex CLI 审查**：`codex exec review` — 侧重逻辑正确性、边界条件、性能/成本影响
2. **Claude Code 自审**：对 Codex 审查结果进行评估，合并有效建议，标注误报
3. 修复所有 P0/P1 问题后，`make check` 通过方可部署

**审查豁免**：纯文档改动（*.md）、知识砖块追加（*.jsonl）、测试文件改动不触发审查。

### 工程纪律

- 任何代码改动前先做**变更影响评估**（影响哪些包、哪些下游）
- 复杂任务主动拆解，用 Sub-agents 并行处理
- 优先使用 Plan Mode：先输出计划，确认后再动代码
- 每次重大任务结束后做 post-mortem，提取教训更新 `docs/pitfalls.md`

---

*最后更新: 2026-04-01*
