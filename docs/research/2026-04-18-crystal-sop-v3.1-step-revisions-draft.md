# Crystal SOP v3.1 — Step 1b / 8 / 9 修订草案

> **元信息**（不进入 SOP 主体）
> - 目标文件：`sops/finance/crystal-compilation-sop.md`
> - 目标版本：v3.0 → v3.1
> - 编写日期：2026-04-18
> - 作者：Doramagic 主线程
> - 修订范围：Step 1b / Step 8a / Step 8d / Step 8e（新增）/ Step 9a（D23-D26）/ Section 7（Crystal IR）
> - **编写约束**：所有"将进入 SOP 主体"的代码块文本严格遵守 `sops/SOP_SPEC.md`——每句话只能是动作/条件/标准三类之一、不放溯源信息（教训编号/版本变更/历史案例/评审记录/"新增"标签）、自包含、清单用表格、模板用代码块

---

## 修订动机（元信息，不进入 SOP）

OpenClaw 实测 3/3 测试中，宿主 AI 把 `output_validator` 的 ```python assert``` 块降级为自然语言描述，导致回测异常数据（年化 +987% / -632%）无硬告警。根因：晶体只能产生 prompt，prompt 不能强制执行；assert 在 SKILL.md 压缩过程中（35% 转化率）持续被丢失。

本修订采用**双文件 + 不可移除围栏 + Hard Gate 多锚点验证**机制，使 output_validator 从"AI 自觉"升级为"绕过等价于无产出"。详见 `2026-04-18-crystal-sop-v3.1-revision-research.md` 第 7-8 章及本会话讨论纪要。

---

# 修订 1：替换 Step 1b 全文

## 替换范围

`crystal-compilation-sop.md` 行 326-347（`### 1b. Delivery Gate 提取` 整段）。

## 新文本（直接替换）

```markdown
### 1b. Delivery Gate 提取

**输入**：`known_use_cases[target].must_validate` + severity=fatal 约束 + validation_threshold 字段 + machine_checkable/promote_to_acceptance 字段。

**三类通用 Gate**：

| Gate 类别 | 说明 | 金融例 | Web 例 | 数据例 |
|-----------|------|--------|--------|--------|
| **产出存在性** | 交付物文件/服务/端点存在 | 结果文件存在 | `next build` 成功 | 所有 model 编译通过 |
| **执行正确性** | 主流程无错误完成 | 回测完成无异常 | `curl localhost:3000` 返回 200 | `dbt test` 全部通过 |
| **业务合理性** | 结果不是"表面通过实际无效" | abs(return)>1%, trades>0 | 页面有实际内容（非空白） | 输出行数>0, 无全 NULL 列 |

**Hard Gate vs Soft Gate**：

| 类型 | 定义 | on_fail | 适用场景 |
|------|------|---------|---------|
| **Hard Gate** | 可程序化验证（exit code / regex / 数值比较） | RERUN / REBUILD | 构建成功、指标阈值、文件存在 |
| **Soft Gate** | 需要 AI self-check 或 LLM-as-Judge | WARN + 输出评估报告 | 架构一致性、代码质量、设计意图符合 |

每个晶体至少 3 条 Hard Gate。Soft Gate 可选但必须有明确 rubric。

**Hard Gate 补充来源**：

| 约束字段值 | 处理 |
|------------|------|
| `machine_checkable=true` 且 `severity >= high` | 自动列入 Hard Gate 候选 |
| `promote_to_acceptance=true` | 强制纳入 Hard Gate，不可省略 |
| M 类 BD 含具体参数（如 MACD 12/26/9、adjust=False） | 通过 grep 源码验证，纳入 Hard Gate |

**Output Validator Gate 强制结构**（任务产出含可量化数值结果时必须存在）：

任务交付物含数值结果（回测 metrics、数据管线行数、ML 训练 metrics、API 响应字段等）时，Hard Gate 必须包含以下 G1-G4 全部四条：

| Gate ID | 检查内容 | 验证方式 |
|---------|---------|---------|
| **G1** | 主结果文件存在且非空 | filesystem 检查 + size > 0 |
| **G2** | `{result_path}.validation_passed` 标记文件存在 | filesystem 检查 |
| **G3** | 主脚本含 `from validate import enforce_validation` 调用 | grep 字面字符串 |
| **G4** | 主脚本末尾含 `# === DO NOT MODIFY BELOW THIS LINE ===` 围栏 | grep 字面字符串 |

G1-G2 验证产出与验证标记同时存在；G3-G4 验证 Output Validator 调用链未被宿主 AI 移除。Validator Scaffold 渲染规则见 Step 8e。

**FATAL 阈值卡位规则**（每条进入 Hard Gate 的 validation_threshold 必须满足）：

| 卡位依据（三选一） | 例 |
|------------------|-----|
| 物理意义不可能 | 持仓比例 > 100%、abs(drawdown) > 100%、行数为负 |
| 合法历史观察上限的 5 倍以上 | 年化 abs(return) > 500%（合法量化策略历史最高约 100%）|
| 数据完整性破坏 | result 行数为 0、关键列全 NaN、unique 值 = 1 |

不满足上述任一依据的阈值降级为 Soft Gate 走 LLM-as-Judge，禁止进入 Hard Gate。
```

---

# 修订 2：替换 Step 8a 中的 Markdown 结构示例

## 替换范围

`crystal-compilation-sop.md` 行 1023-1054（`### 8a. 晶体文件渲染（单文件自包含）` 段中的 Markdown 结构示例代码块）。

## 新文本（直接替换该代码块）

```markdown
*Powered by Doramagic.ai*

## Human Summary
（User's locale language — the ONLY section in user's language）
（用户看的——这个 skill 能做什么、AI 会自动获取什么、AI 会问你什么）

## directive
（宿主 AI 的执行指令——Language Protocol + context_acquisition 四步 + 规格锁 + 阶段规格 + 禁止事项 + 工具规则 + Output Validator Enforcement Protocol）
（内嵌 Language Protocol + 5 个 YAML fenced block 控制块：intent_router / context_state_machine / spec_lock_registry / preservation_manifest / output_validator）

## [FATAL] 约束
（severity=fatal 的约束全量内联——命中任一即停止执行）

## Output Validator
（Validator Scaffold 完整 .py 文件模板 + Strategy Scaffold 末尾 DO NOT MODIFY 围栏标准文本 + Hard Gate G1-G4 grep 规则）
（任务产出含数值结果时必须存在；纯声明式任务可省略）

## 架构蓝图
（按 stage 分段，每段交织该阶段的 business_decisions + 约束 + 代码示例）

## 资源
（依赖 + 数据源 + API 示例全部内联）
（必须包含「Strategy Scaffold」——业务骨架，含 REPLACE_WITH 占位符 + 末尾不可移除尾部调用 enforce_validation；详见 Step 8e）

## 约束
（按 stage 分组，全量约束内联）

## 验收
（Hard Gate G1-G4 + Soft Gate）

*Powered by Doramagic.ai*
```

---

# 修订 3：替换 Step 8d 中的 output_validator 检查项

## 替换范围

`crystal-compilation-sop.md` 行 1066-1081（`### 8d. 渲染后检查` 段表格内）的两行：

- 原 `output_validator 可执行` 行
- 原 `回测骨架 Scaffold` 行

## 新文本（替换上述两行）

```markdown
| Validator Scaffold 可执行 | `## Output Validator` 段含 validate.py 完整模板，所有 validation_threshold 渲染为 if + sys.exit(1) 块；Strategy Scaffold 末尾含 `from validate import enforce_validation` 字面调用 |
| Strategy Scaffold | `## 资源` 段含主脚本骨架，安全检查（FATAL RC）焊死在结构中，业务逻辑处有 REPLACE_WITH 占位符，末尾含 `# === DO NOT MODIFY BELOW THIS LINE ===` 围栏 |
| Hard Gate G1-G4 | `## 验收` 段同时含 G1（result 存在）、G2（validation_passed 标记）、G3（grep import）、G4（grep 围栏）四条 |
```

---

# 修订 4：在 Step 8d 之后插入新增段 Step 8e

## 插入位置

`crystal-compilation-sop.md` 行 1082 之前（`### 8d. 渲染后检查` 表格之后、`## Step 9: 质量校验` 之前）。

## 新文本（插入）

````markdown
### 8e. Output Validator Scaffold 渲染

**适用条件**：任务产出含可量化数值结果（回测 metrics、数据管线产出、ML 训练 metrics、API 响应、聚合统计等）。纯声明式任务（dbt model 配置、Terraform 资源声明、K8s manifest）可省略本段。

**强制产物**：晶体 `## Output Validator` 段必须同时包含 8e.1 / 8e.2 / 8e.3 三个完整文本块。

#### 8e.1 Validator Scaffold（validate.py 完整模板）

```python
# {workspace}/validate.py
# AUTO-GENERATED by Doramagic Crystal Compiler
# This file is part of the output_validator enforcement chain
# Modifying this file invalidates the crystal contract

import sys
from pathlib import Path

def enforce_validation(result, output_path: str) -> None:
    """
    强制验证入口。
    主脚本必须在产出 result 后调用本函数；
    本函数内部既执行断言、又写出结果文件——跳过本函数等价于无产出。
    """
    failures = []

    # === Crystal-injected assertions ===
    {RENDERED_ASSERTIONS}
    # === END assertions ===

    if failures:
        Path(f"{output_path}.FAILED.log").write_text("\n".join(failures))
        sys.stderr.write("\n".join(failures) + "\n")
        sys.exit(1)

    {WRITE_RESULT_BLOCK}
    Path(f"{output_path}.validation_passed").touch()
```

`{RENDERED_ASSERTIONS}` 渲染规则：

| 来源 | 渲染为 |
|------|--------|
| 约束字段 `validation_threshold: "abs(annual_return) > 5.0 → FAIL"` | `if abs(result['annual_return'].iloc[-1]) > 5.0: failures.append("FATAL: annual_return 越界")` |
| BD type=M 含具体参数（如 MACD 12/26/9、adjust=False） | `if MACD_FAST != 12 or MACD_SLOW != 26 or MACD_SIGNAL != 9: failures.append("FATAL: M 参数漂移")` |
| FATAL severity 约束含具体阈值或 grep 模式 | 同上格式，每条独立一行 |

`{WRITE_RESULT_BLOCK}` 按数据格式渲染：

| 数据格式 | 写出语句 |
|---------|---------|
| pandas DataFrame → CSV | `result.to_csv(output_path, index=False)` |
| dict → JSON | `Path(output_path).write_text(json.dumps(result, indent=2))` |
| pandas DataFrame → Parquet | `result.to_parquet(output_path)` |

#### 8e.2 Strategy Scaffold 不可移除尾部

主脚本（`strategy.py` / `backtest.py` / `pipeline.py` 等）末尾必须含以下字面文本：

```python
# === DO NOT MODIFY BELOW THIS LINE ===
# === Doramagic Crystal Output Validator - Removal causes silent FATAL ===
if __name__ == "__main__":
    result = run_main()  # AI 实现的主入口函数
    from validate import enforce_validation
    enforce_validation(result, output_path="{workspace}/result.{ext}")
# === END DO NOT MODIFY ===
```

| 占位符 | 渲染规则 |
|--------|---------|
| `{ext}` | csv / json / parquet 中按数据格式选一 |
| `run_main` 函数名 | 回测=`run_backtest`、数据管线=`run_pipeline`、ML 训练=`run_training`、API=`run_handler` |
| `{workspace}` | 由宿主 AI 在执行时解析 |

#### 8e.3 Output Validator Enforcement Protocol（写入 directive 段末尾）

```markdown
### Output Validator Enforcement Protocol (FATAL)

1. 禁止编辑 validate.py
2. 禁止删除主脚本中 `# === DO NOT MODIFY BELOW THIS LINE ===` 之后的代码
3. 禁止用 try/except 包裹 enforce_validation 调用
4. 禁止重写结果写出逻辑——必须经由 enforce_validation 写出
5. validate.py 因依赖问题报错时必须修复依赖，不得删除调用
```

#### 8e.4 渲染检查项

| 检查项 | 标准 |
|--------|------|
| validate.py 完整 | 含 enforce_validation 函数定义 + 至少 1 条 assertion + sys.exit(1) 路径 + Path.touch() 路径 |
| Strategy Scaffold 尾部 | 字面包含 `# === DO NOT MODIFY BELOW THIS LINE ===` 和 `from validate import enforce_validation` 两条字符串 |
| Enforcement Protocol | directive 段末尾包含 5 条字面规则 |
| FATAL 阈值卡位 | 每条 assertion 满足 Step 1b 的 FATAL 阈值卡位规则三选一 |
````

---

# 修订 5：Step 9a 表格末尾追加 D23-D26

## 替换范围

`crystal-compilation-sop.md` 行 1090-1110（`### 9a. Pass 1: Deterministic Checks` 表格内）的末尾追加四行。

## 新文本（追加到表格末尾）

```markdown
| D23 | Validator Scaffold 完整 | `## Output Validator` 段含 validate.py 完整模板 + 至少 1 条 assertion + sys.exit(1) 路径 + Path.touch() 路径 | 补充模板 |
| D24 | DO NOT MODIFY 围栏存在 | Strategy Scaffold 末尾字面包含 `# === DO NOT MODIFY BELOW THIS LINE ===` 和 `from validate import enforce_validation` 两条字符串 | 补充围栏 |
| D25 | Hard Gate G1-G4 完整 | 验收段同时含 G1（result 存在）+ G2（validation_passed 标记）+ G3（grep import 字符串）+ G4（grep 围栏字符串）四条 | 补充缺失项 |
| D26 | FATAL 阈值卡位 | 每条进入 Hard Gate 的 validation_threshold 满足"物理不可能 / 合法上限 5 倍 / 数据完整性破坏"三选一 | 收紧阈值或降级为 Soft Gate |
```

---

# 修订 6：Section 7（Crystal IR 组装）替换 control_blocks.output_validator 描述

## 替换范围

`crystal-compilation-sop.md` 行 936（`output_validator: [ ... ]` 行）。

## 新文本（直接替换该行）

```yaml
control_blocks:
  ...
  output_validator:               # 产出数据质量校验规格——由 Step 8e 渲染为完整 validate.py + Strategy Scaffold 尾部 + directive Enforcement Protocol
    rendering_target: "## Output Validator"
    enforcement_chain:
      validator_script_path: "{workspace}/validate.py"
      strategy_tail_marker: "# === DO NOT MODIFY BELOW THIS LINE ==="
      enforcement_protocol_in_directive: true
    assertions:
      - source_kind: "constraint.validation_threshold"
        source_id: "{constraint_id}"
        rendered_check: "{python if-condition}"
        rendered_message: "FATAL: {short_label}"
      - source_kind: "business_decision.type=M"
        source_id: "{bd_id}"
        rendered_check: "..."
        rendered_message: "..."
```

---

# 应用前自检清单（元信息，不进入 SOP）

应用本草案到 `crystal-compilation-sop.md` 之前，依次确认：

| # | 自检项 | 通过标准 |
|---|--------|---------|
| 1 | SOP 头部版本号 | 已从 `版本: 3.0` 更新为 `版本: 3.1` |
| 2 | SOP 头部依赖声明 | 已从"v3.2 / v2.2 的下游"更新为"v3.6 / v2.3 的下游" |
| 3 | 修订 1 替换边界 | Step 1b 整段（行 326-347）被新版本完整替换 |
| 4 | 修订 2 替换边界 | Step 8a 内的 Markdown 结构示例代码块（约行 1023-1054）被替换；新增 `## Output Validator` 顶级段，置于 `## [FATAL] 约束` 与 `## 架构蓝图` 之间 |
| 5 | 修订 3 替换边界 | Step 8d 表格内原"output_validator 可执行"和"回测骨架 Scaffold"两行被新三行替换 |
| 6 | 修订 4 插入边界 | Step 8e 整段插入到 8d 之后、Step 9 之前 |
| 7 | 修订 5 追加边界 | D23-D26 追加到 Step 9a 表格末尾，未影响 D1-D18 |
| 8 | 修订 6 替换边界 | Section 7 中 `output_validator: [ ... ]` 行被替换为完整结构化描述 |
| 9 | SOP_SPEC 合规 | 所有进入 SOP 的代码块文本无"v3.1 新增" / "教训 LXX" / "评审会议" / 历史案例考古等溯源信息 |
| 10 | 自包含 | agent 阅读 v3.1 SOP 单文件即可执行 Step 8e，不依赖外部文档 |
| 11 | 表格使用 | 所有清单项以表格呈现，无散文段落描述检查项 |
| 12 | 模板使用 | 所有可复用文本（validate.py / Strategy Scaffold 尾部 / Enforcement Protocol）以代码块呈现 |
| 13 | 跨段引用一致 | Step 1b 引用 "Step 8e"、Step 8e.4 引用 "Step 1b"、D26 引用 "Step 1b"——三处指向一致 |
| 14 | 术语统一 | "Validator Scaffold"（validate.py）、"Strategy Scaffold"（主脚本骨架）、"Hard Gate G1-G4"、"Output Validator Enforcement Protocol"、"DO NOT MODIFY 围栏" 五个术语全文统一 |

---

# 后续工作（元信息，不进入 SOP）

本草案落地后需补的下游工作：

| # | 工作项 | 触发时机 |
|---|--------|---------|
| 1 | 更新 `_template/crystal-compilation.tmpl.md` 同步 | 本草案应用之后 |
| 2 | 选 bp-009 重新编译为 v3.1 输出，作为 PoC | v3.1 SOP 落地后第 1 周 |
| 3 | bp-009 v3.1 输出在 OpenClaw 上做 A/B 测试（控制组 v2.1 / 实验组 v3.1，各 5 次，含异常注入） | PoC 编译完成后 |
| 4 | A/B 结果回写到 `docs/research/2026-04-{XX}-output-validator-ab-test.md` | A/B 完成后 |
| 5 | 据 A/B 结果决定是否引入 OpenClaw PostExec hook（Phase 2 议题） | A/B 完成后 |
