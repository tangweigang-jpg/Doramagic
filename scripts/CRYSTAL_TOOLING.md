# Crystal Tooling — 晶体编译工具链

**目的**：把"晶体编译"从黑盒 agent 任务升级为**可复现、可审计、100 pct 覆盖机械保证**的工程流水线。

**起因**：v3.2 时期的 agent 子代理声称 164/164 BD + 147/147 约束 + 33/33 D-check PASS，但 `crystal_quality_gate.py` 实测覆盖率仅 BD 78.7 pct / 约束 19.7 pct——触发了 SOP v3.1 新定义的 `false_completion_claim` 失败类。工具链的设计目标就是让虚报**结构性不可能**。

---

## 工具链架构

```
┌─────────────────────────┐
│ knowledge/sources/{BP}/ │
│   ├── LATEST.yaml       │  (蓝图)
│   └── LATEST.jsonl      │  (约束)
└───────────┬─────────────┘
            │
    ① prepare_crystal_inputs.py
            │
            ▼
┌─────────────────────────────────┐
│  {BP}/crystal_inputs/            │
│   ├── bd_checklist.md            │   ← 按 stage 分组的全部 BD
│   ├── constraint_checklist.md    │   ← 按 severity 分组的全部约束
│   ├── uc_checklist.md            │   ← 全部 UC
│   └── coverage_targets.json      │   ← 机器可读目标 ID 全集
└──────────────┬──────────────────┘
               │
    ② compile_crystal_skeleton.py
               │
               ▼
┌──────────────────────────────────────┐
│  {BP}-{VERSION}.seed.md              │  ← 骨架（100 pct ID 引用覆盖）
│  {BP}-{VERSION}.ir.yaml              │  ← Crystal IR
│  {BP}/validate.py                    │  ← Output Validator（可执行）
└──────────────┬──────────────────────┘
               │
    ③ crystal_quality_gate.py --strict
               │
               ▼
┌──────────────────────────────────────┐
│  {BP}-{VERSION}.seed.quality_report  │  ← 机械质量证据
│  退出码 0 = PASS / 1 = FAIL          │
└──────────────┬──────────────────────┘
               │
    ④ 主线程 Edit 填充 SOUL_TODO
       (Human Summary / 阶段叙事)
               │
               ▼
    ⑤ 重跑 crystal_quality_gate.py
       PASS → 晶体可入库
```

---

## 三个脚本的职责

### 1. `scripts/prepare_crystal_inputs.py` — 输入预处理

**为什么需要**：`LATEST.jsonl` 原始约束文件可能超过 Read 工具 token 限制（v5 版本 255 KB / ~69K tokens）。agent 读不完就会被迫摘要化，导致虚报。

**做什么**：从 `LATEST.yaml` + `LATEST.jsonl` 生成 agent 友好的分块清单（78 KB 总量，每文件 < 40 KB），agent / 主线程可一次性装入 context。

**产出 4 文件**（写入 `{BP}/crystal_inputs/`）：

| 文件 | 行数 | 用途 |
|------|-----|------|
| `bd_checklist.md` | ~400 | 全部 BD 按 stage 分组，每条含 ID/type/content/evidence |
| `constraint_checklist.md` | ~600 | 全部约束按 severity 分组，每条含 ID/when/action/kind/stages |
| `uc_checklist.md` | ~150 | 全部 UC 含 intent_keywords / data_domain / not_suitable_for |
| `coverage_targets.json` | — | 机器可读的目标 ID 全集 + counts，供 quality_gate 对比 |

### 2. `scripts/compile_crystal_skeleton.py` — 骨架编译

**为什么需要**：机械保证"100 pct ID 引用覆盖"——让 agent 无机会虚报。

**做什么**：读取 `crystal_inputs/` + 宿主规范，按 SOP v3.1 Step 8a 段落结构机械生成 `seed.md` 骨架（所有 164 BD / 147 约束 / 31 UC 的 ID 引用齐全）+ `ir.yaml` + `validate.py`（独立可执行）。

**产出**：

| 文件 | 完成度 | 需主线程补充的部分 |
|------|-------|------------------|
| `{BP}-{VER}.seed.md` | 80 pct | Human Summary（哆啦A梦人设）+ 6 段主 stage 叙事（每段 2-4 句） |
| `{BP}-{VER}.ir.yaml` | 100 pct | 无（机器生成元数据）|
| `validate.py` | 100 pct | 无（6 条 OV 断言：MACD 锁 + 物理合理性 + 先卖后买）|

**SOUL_TODO 标记**：骨架中的 `<!-- SOUL_TODO: ... -->` 是明确的"等主线程填充"占位，不影响 quality_gate 通过。

### 3. `scripts/crystal_quality_gate.py` — 质量门禁

**为什么需要**：外部事实基线。不依赖 agent 自评，用 grep/正则实测覆盖率。

**做什么**：读 `LATEST.yaml` + `LATEST.jsonl` + `seed.md`，用正则提取唯一 ID 引用数 vs 蓝图/约束源文件的总数，计算覆盖率；检查段落结构、5 控制块、Scaffold 锚点、Hard Gate G1-G4；输出 JSON 报告 + 人可读 summary + 退出码。

**门禁条件**：

- BD 覆盖 = 100 pct
- 约束覆盖 = 100 pct（Fatal + Non-fatal 分别达标）
- UC 覆盖 = 100 pct
- 必须段落齐全（8 个，Rationalization Guards 条件性省略合规）
- 5 控制块齐全
- Output Validator Scaffold 完整（DO NOT MODIFY 围栏 + from validate import + Enforcement Protocol）
- Hard Gate G1-G4 齐全

任一不通过 → 退出码 1，FAIL。

---

## 快速入口（Makefile）

```bash
# 一键完成：prepare + compile + gate
make crystal-full BP=finance-bp-009--zvt VERSION=v3.3

# 分步执行
make crystal-prepare BP=finance-bp-009--zvt
make crystal-compile BP=finance-bp-009--zvt VERSION=v3.3
make crystal-gate    BP=finance-bp-009--zvt VERSION=v3.3

# 切换宿主
make crystal-compile BP=finance-bp-009--zvt VERSION=v3.3 HOST=claude_code

# 清理
make crystal-clean BP=finance-bp-009--zvt VERSION=v3.3
```

**BP 命名约定**：`{blueprint-id}--{project-slug}`（两个连字符分隔）。对应 `knowledge/sources/finance/{BP}/` 目录。例如 `finance-bp-009--zvt` 对应 `knowledge/sources/finance/finance-bp-009--zvt/`。

---

## 完整工作流（推荐）

### Step A: 首次编译某蓝图（新蓝图 / 首版晶体）

```bash
# 1. 机械生成骨架（~10 秒）
make crystal-full BP=finance-bp-085--freqtrade VERSION=v3.3

# 2. 门禁通过后，主线程 Edit 填充 SOUL_TODO：
#    - Human Summary（哆啦A梦人设：替用户做选择，有吐槽，有边界）
#    - 6 段主 stage 叙事（做什么 / 关键决策 / 常见陷阱）

# 3. 重跑门禁确认填充后仍 100 pct
make crystal-gate BP=finance-bp-085--freqtrade VERSION=v3.3

# 4. 入库（手动或 script）
cp knowledge/sources/finance/finance-bp-085--freqtrade/finance-bp-085-v3.3.seed.md \
   knowledge/crystals/finance-bp-085/PRODUCTION.seed.md
```

### Step B: 增量更新（蓝图或约束版本升级）

```bash
# 蓝图/约束文件更新后，一键重编
make crystal-clean BP=finance-bp-009--zvt VERSION=v3.3
make crystal-full  BP=finance-bp-009--zvt VERSION=v3.4

# 对比 diff
diff finance-bp-009-v3.3.seed.md finance-bp-009-v3.4.seed.md
```

### Step C: 批量编译（后续 53 个蓝图）

```bash
for bp in finance-bp-085--freqtrade finance-bp-087--qlib finance-bp-088--zipline-reloaded ; do
    make crystal-full BP=$bp VERSION=v3.3 || echo "FAIL: $bp"
done
```

---

## Agent 协作规范

若用 sonnet / 其它子代理执行编译，必须遵守 `docs/agent-protocols/crystal-compilation-agent.md`：

1. **必先运行 `make crystal-prepare`**（或手动跑 `prepare_crystal_inputs.py`）
2. **只读 `crystal_inputs/` 下的 checklist**，不读 LATEST.yaml / LATEST.jsonl 原始大文件
3. **编译完成后必须跑 `make crystal-gate`**，贴出完整 stdout
4. **退出码 1 时禁止声称"编译完成"**，按 partial 格式诚实报告

---

## 设计决策溯源

| 设计 | 原因 | 宪法依据 |
|------|------|---------|
| 脚本骨架 + 主线程填充（非纯 agent / 非纯脚本） | 机械保证覆盖率 + 保留"有立场的专家"判断 | §1.8 #2 有立场的专家 + #5 完整交付 |
| checklist 预处理（非直读 JSONL） | 绕过 Read 工具 token 限制 | §1.6 #2 不编造不猜测 |
| 外部 quality_gate（非 agent 自检） | 让虚报结构性不可能 | §1.8 #3 能力显性（暗默 = 不信任） |
| 退出码门禁（非评分排序） | 二值确定性 + 可集成 CI | §1.6 #5 质量不妥协 |

---

## 工具链扩展点

未来版本可加：

- `scripts/crystal_diff.py` — 两版晶体的语义 diff（不只是 text diff）
- `scripts/crystal_publish.py` — 从 `sources/` 入库到 `crystals/` + 生成 changelog
- `scripts/crystal_batch_compile.sh` — 批量编译多个蓝图 + 汇总报告
- `scripts/crystal_efficacy_test.py` — 晶体 vs 无晶体 A/B 对照（SOP Step 10）

---

## 参考文档

- SOP: `sops/finance/crystal-compilation-sop.md`（v3.1，含 D34-D38 确定性 D-check）
- Agent 协议: `docs/agent-protocols/crystal-compilation-agent.md`
- 产品宪法: `PRODUCT_CONSTITUTION.md`（§1.3 晶体公式，§1.8 六原则）
- v3.3 实战报告: `knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v3.3.compilation-report.md`

---

*v1.0 | 2026-04-18 | 编写者: Doramagic 主线程 | 适用于: Doramagic 晶体编译 v3.1+*
