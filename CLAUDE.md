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
- **架构**: Blueprint + Constraint + Crystal（知识锻造师，v2）
- **版本**: 见 pyproject.toml `version` 字段

## 目录结构（v2 重构后）

```
Doramagic/
├── v1/                    # v1 全栈缝合者 归档（只读）
│   ├── packages/          # 12 个 v1 Python 包 + _deprecated_variants/
│   ├── knowledge/bricks/  # 278 JSONL 知识积木（34 领域）
│   ├── skills/            # 历史 skill 版本
│   ├── experiments/       # exp01–exp08 流水线演进实验
│   ├── runs/              # 历史运行输出
│   ├── races/             # 多模型竞速记录
│   ├── openclaw-test/     # OpenClaw 实地测试记录
│   └── docs/              # v1 工程日志、研究、设计文档
├── knowledge/             # v2 知识资产（活跃）
│   ├── sources/           # 真源：{domain}/{bp-slug}/{LATEST.yaml, LATEST.jsonl, *-vN.seed.yaml}，含 _shared/ 领域资源池
│   ├── catalogs/          # 外部参考（public_apis.yaml，供 enrich_pool_from_catalog.py 消费）
│   └── _archive/          # 历史归档（v2 架构收敛前的 api_catalog/blueprints/bricks/constraints/crystals/judgments/meta/scenes）
├── packages/              # v2 活跃 Python 包（contracts, shared_utils 等）
├── sops/                  # 顶层 SOP 文件（蓝图提取、约束采集、晶体编译）
├── worklogs/              # 工作日志（2026-03/, 2026-04/）
├── docs/                  # v2 文档（research/, designs/, archive/）
└── PRODUCT_CONSTITUTION.md  # v2 产品宪法（v1 见 v1/PRODUCT_CONSTITUTION_v1.md）
```

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

### 知识资产（v2）

v2 架构收敛后，**蓝图、约束、晶体统一归口到 `knowledge/sources/`**：

- **路径规范**：`knowledge/sources/{domain}/{bp-slug}/`
  - `LATEST.yaml` — 蓝图（版本化 `blueprint.vN.yaml`，LATEST 为 symlink）
  - `LATEST.jsonl` — 项目级约束（版本化 `constraints.vN.jsonl`）
  - `{bp-id}-vN.seed.yaml` — 晶体（SOP v5.3 契约，由 `make crystal-full` 产出）
  - `crystal_inputs/` — 编译中间产物
- **领域资源池**：`knowledge/sources/{domain}/_shared/`
  - `resources.yaml` / `replaceable_slots.yaml` — 跨项目共享（≥2 BP 引用）
  - `resources_full.yaml` / `replaceable_slots_full.yaml` — 全量（含单 BP 独占）
- **外部参考**：`knowledge/catalogs/public_apis.yaml`（scan 富化依赖）
- **SOP**：`sops/` — 蓝图提取、约束采集、晶体编译三大 SOP
- **历史归档**：`knowledge/_archive/{DATE}/` 为只读，不进编译流水线

### 知识积木（v1 归档）

`v1/knowledge/bricks/` 是归档的 v1 积木文件，v2 不使用。

### 发布

完整 8 步流程见 `scripts/release/README.md`，不可跳步。ClawHub slug: `dora`。
发布规范详见项目记忆 `reference_doramagic_release_spec.md`。

### 已知技术债

- `v1/packages/orchestration/` 是旧版 PhaseRunner，已归档（v1）
- ~~`skills/doramagic/packages/` 副本~~ 已解决：v13.1.0 起通过 pip 包分发
- 6 组测试在 `make test` 中被 `--ignore`，需逐步恢复

### 踩雷检查（CRITICAL）

涉及已知问题域（LLM 调用、积木体系、发布流程、contracts 变更）时，先查阅 `docs/pitfalls.md` 确认是否有相关踩坑经验。不重复踩已知的坑。

### 代码审查

由 `.claude/settings.json` 的 PreToolUse hook 自动拦截 `git commit`，达到阈值时阻断提交并要求先跑 `/codex:review`。

### 工程纪律

- 任何代码改动前先做**变更影响评估**（影响哪些包、哪些下游）
- 复杂任务主动拆解，用 Sub-agents 并行处理
- 优先使用 Plan Mode：先输出计划，确认后再动代码
- 每次重大任务结束后做 post-mortem，提取教训更新 `docs/pitfalls.md`

---

*最后更新: 2026-04-07*
