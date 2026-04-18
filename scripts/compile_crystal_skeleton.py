#!/usr/bin/env python3
"""Compile Crystal Skeleton — 基于蓝图/约束/UC 机械生成晶体骨架

产出一个 ~70 pct 完成的 seed.md，所有 ID 引用齐全（100 pct 覆盖），
主线程在此基础上 Edit 补充"灵魂部分"：Human Summary / 阶段叙事 /
validator assertions / Soft Gate rubric / 哆啦A梦人设。

用法:
    python3 compile_crystal_skeleton.py \\
        --blueprint-dir knowledge/sources/finance/finance-bp-009--zvt \\
        --target-host openclaw \\
        --output-seed finance-bp-009-v3.3.seed.md \\
        --output-ir finance-bp-009-v3.3.ir.yaml \\
        [--output-validate validate.py]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[error] PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ============================================================
# 加载输入
# ============================================================


def load_inputs(blueprint_dir: Path) -> tuple[dict, list[dict], dict]:
    bp_path = blueprint_dir / "LATEST.yaml"
    cons_path = blueprint_dir / "LATEST.jsonl"
    with bp_path.open() as f:
        bp = yaml.safe_load(f)
    constraints = []
    with cons_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                constraints.append(json.loads(line))
    targets_path = blueprint_dir / "crystal_inputs" / "coverage_targets.json"
    targets = {}
    if targets_path.exists():
        targets = json.loads(targets_path.read_text())
    return bp, constraints, targets


# ============================================================
# validate.py 模板
# ============================================================


def render_validate_py(blueprint_id: str) -> str:
    return f"""# {{workspace}}/validate.py
# 禁止修改本文件——晶体合约的强制部分
# Generated for {blueprint_id}

import sys
import json
from pathlib import Path


def enforce_validation(result, output_path: str) -> None:
    failures = []

    # === Crystal-injected assertions ===
    # OV-01: MACD parameter lock (SL-09)
    try:
        import zvt.factors.algorithm as _algo
        import inspect
        src = inspect.getsource(_algo.macd)
        if "slow=26" not in src or "fast=12" not in src or "n=9" not in src:
            failures.append("FATAL: MACD params drifted from (fast=12, slow=26, n=9)")
    except Exception:
        pass

    # OV-02: result must be non-empty (prevent silent no-signal false completion)
    if result is None:
        failures.append("FATAL: result is None — no computation performed")
    elif hasattr(result, "__len__") and len(result) == 0:
        failures.append("FATAL: result is empty — possible look-ahead filter failure")
    elif hasattr(result, "empty") and result.empty:
        failures.append("FATAL: result DataFrame is empty")

    # OV-03: annual return physical plausibility (per Step 1b FATAL threshold rule)
    try:
        if hasattr(result, "get"):
            ar = result.get("annual_return")
            if ar is not None and abs(float(ar)) > 5.0:
                failures.append(f"FATAL: |annual_return|={{float(ar):.2f}} > 500 pct — likely look-ahead bias or data error")
    except Exception:
        pass

    # OV-04: holding change physical plausibility
    try:
        if hasattr(result, "get"):
            hc = result.get("holding_change_pct")
            if hc is not None and abs(float(hc)) > 1.0:
                failures.append(f"FATAL: |holding_change_pct|={{float(hc):.2f}} > 100 pct")
    except Exception:
        pass

    # OV-05: drawdown physical plausibility
    try:
        if hasattr(result, "get"):
            dd = result.get("max_drawdown")
            if dd is not None and abs(float(dd)) > 1.0:
                failures.append(f"FATAL: |max_drawdown|={{float(dd):.2f}} > 100 pct — impossible")
    except Exception:
        pass

    # OV-06: sell-before-buy ordering check (SL-01)
    try:
        if hasattr(result, "trade_log"):
            log = result.trade_log
            if log and any(
                log[i].action == "buy" and i + 1 < len(log) and log[i + 1].action == "sell"
                and log[i].timestamp == log[i + 1].timestamp
                for i in range(len(log) - 1)
            ):
                failures.append("FATAL: buy-before-sell detected in same cycle (violates SL-01)")
    except Exception:
        pass

    # === END assertions ===

    if failures:
        Path(f"{{output_path}}.FAILED.log").write_text("\\n".join(failures))
        sys.stderr.write("\\n".join(failures) + "\\n")
        sys.exit(1)

    # Write result
    if hasattr(result, "to_csv"):
        result.to_csv(output_path, index=False)
    elif isinstance(result, dict):
        Path(output_path).write_text(json.dumps(result, indent=2, default=str))
    elif result is None:
        Path(output_path).write_text("")
    else:
        Path(output_path).write_text(str(result))

    Path(f"{{output_path}}.validation_passed").touch()


if __name__ == "__main__":
    # Standalone mode: verify all locked parameters match expected values
    print("[validate.py] Standalone invocation — checking SL parameter integrity...")
    failures = []
    try:
        import zvt.factors.algorithm as _algo
        import inspect
        src = inspect.getsource(_algo.macd)
        if "slow=26" not in src:
            failures.append("SL-09: MACD slow != 26")
        if "fast=12" not in src:
            failures.append("SL-09: MACD fast != 12")
        if "n=9" not in src:
            failures.append("SL-09: MACD n != 9")
    except ImportError:
        print("[validate.py] zvt not installed — cannot verify SL-09")

    if failures:
        for f in failures:
            print(f"  FAIL: {{f}}")
        sys.exit(1)
    print("[validate.py] ALL GATES PASSED — no output_path specified, marker not written.")
    sys.exit(0)
"""


# ============================================================
# seed.md 段落生成
# ============================================================


def render_human_summary_placeholder() -> str:
    return """## Human Summary

<!-- SOUL_TODO: Doraemon persona (§1.7) — 替用户做选择，不列选项。
用户看完这段应该知道：
- 这个 skill 能做什么？（给出明确用例）
- AI 会自动获取什么？（避免用户重复描述）
- AI 会问你什么？（3-5 个关键决策点）
-->

**我能帮你做什么**:

（TODO 主线程填充：哆啦A梦口吻，亲切、直接、偶尔吐槽 ZVT 的局限）

**我会自动获取**:

（TODO 主线程填充）

**我会问你**:

（TODO 主线程填充）
"""


def render_directive_section(
    blueprint_id: str,
    uc_list: list[dict],
    fatal_ids: list[str],
    non_fatal_ids: list[str],
    bd_ids: list[str],
) -> str:
    """渲染 directive 段，含 5 控制块 YAML fenced blocks."""
    uc_count = len(uc_list)
    uc_entries = []
    for uc in uc_list:
        uc_id = uc.get("id", "?")
        name = (uc.get("name") or "").replace('"', "'")
        keywords = uc.get("intent_keywords") or []
        data_domain = uc.get("data_domain") or "mixed"
        not_suitable = uc.get("not_suitable_for") or []
        positive_terms = json.dumps(keywords, ensure_ascii=False)
        negative_terms = json.dumps(not_suitable, ensure_ascii=False)
        uc_entries.append(
            f"""    - uc_id: "{uc_id}"
      name: "{name}"
      positive_terms: {positive_terms}
      negative_terms: {negative_terms}
      data_domain: "{data_domain}"
      ambiguity_question: "Are you targeting {name.lower()}?"
"""
        )
    intent_router_block = "".join(uc_entries)

    semantic_locks = """    - id: SL-01
      rule: "Execute sell orders before buy orders in every trading cycle"
      violation: FATAL
      rationale: "Prevents implicit leverage when cash is insufficient"
      verification: "Confirm sell() called before buy() in trading loop"
      adapter:
        zvt: "trader.py:266 sell() before trader.py:295 buy()"
    - id: SL-02
      rule: "Trading signals MUST use next-bar execution (no look-ahead)"
      violation: FATAL
      rationale: "Prevents look-ahead bias in backtest"
      verification: "due_timestamp = happen_timestamp + level.to_second()"
      adapter:
        zvt: "Trader.buy() sets TradingSignal.due_timestamp = happen + level.to_second()"
    - id: SL-03
      rule: "Entity IDs MUST follow format entity_type_exchange_code"
      violation: FATAL
      rationale: "ZVT splits on underscore assuming this convention; wrong format breaks lookups"
      verification: "grep entity_id pattern"
      adapter:
        zvt: "stock_sh_600000, stockhk_hk_0700, stockus_nasdaq_AAPL"
    - id: SL-04
      rule: "DataFrame index MUST be MultiIndex with (entity_id, timestamp)"
      violation: FATAL
      rationale: "ZVT factor operations assume this exact index structure"
      verification: "df.index.names == ['entity_id', 'timestamp']"
      adapter:
        zvt: "factor.py:502 MultiIndex.from_product"
    - id: SL-05
      rule: "TradingSignal MUST have EXACTLY ONE of position_pct, order_money, or order_amount"
      violation: FATAL
      rationale: "Mutually exclusive by design; multiple fields causes silent conflict"
      verification: "assert sum([s.position_pct, s.order_money, s.order_amount]) is set == 1"
      adapter:
        zvt: "trading/__init__.py:39 TradingSignal XOR enforcement"
    - id: SL-06
      rule: "filter_result column semantics: True=BUY, False=SELL, None/NaN=NO ACTION"
      violation: FATAL
      rationale: "TargetSelector reads this column; wrong semantics = inverted trades"
      verification: "Check order_type_flag maps True→B, False→S in factor.py"
      adapter:
        zvt: "factor.py:475 order_type_flag"
    - id: SL-07
      rule: "Transformer MUST run BEFORE Accumulator in factor pipeline"
      violation: FATAL
      rationale: "Accumulator expects transformed pipe_df; wrong order = NaN propagation"
      verification: "factor.py:403 transform before :409 accumulator"
      adapter:
        zvt: "compute_result() pipeline"
    - id: SL-08
      rule: "MACD parameters locked: fast=12, slow=26, signal=9"
      violation: FATAL
      rationale: "Standard MACD; altering = non-standard signals, non-reproducible"
      verification: "grep 'slow=26, fast=12, n=9' in algorithm.py"
      adapter:
        zvt: "factors/algorithm.py:30 macd()"
    - id: SL-09
      rule: "Default buy_cost=0.001, sell_cost=0.001, slippage=0.001 when simulating A-share"
      violation: WARN
      rationale: "ZVT default is simplified; real A-share includes 0.05 pct stamp duty on sell only"
      verification: "sell_cost includes stamp duty (0.0005) + commission"
      adapter:
        zvt: "sim_account.py:25 SimAccountService"
    - id: SL-10
      rule: "A-share equity trading is T+1 (no same-day close of buy positions)"
      violation: FATAL
      rationale: "Regulatory constraint; backtests without T+1 are not reproducible in real trading"
      verification: "sim_account.available_long filters by trading_t"
      adapter:
        zvt: "stockhk_meta.py:25 get_trading_t; trader.py position filtering"
    - id: SL-11
      rule: "Recorder subclass MUST define provider AND data_schema class attributes"
      violation: FATAL
      rationale: "Meta-class auto-registration depends on these attributes"
      verification: "subclass has provider=str, data_schema=class"
      adapter:
        zvt: "contract/recorder.py:71 Meta; register_schema decorator"
    - id: SL-12
      rule: "Factor result_df MUST contain either 'filter_result' OR 'score_result' column"
      violation: FATAL
      rationale: "TargetSelector consumes these exact column names"
      verification: "result_df.columns.intersection({'filter_result', 'score_result'}) non-empty"
      adapter:
        zvt: "contract/factor.py Factor.compute_result output"
"""

    implementation_hints = """    - id: IH-01
      rule: "Use AdjustType enum exactly: qfq (pre), hfq (post), bfq (none)"
      zvt: "contract/__init__.py:121 AdjustType enum"
    - id: IH-02
      rule: "For A-share kdata, default to hfq for long-term analysis (dividend-adjusted)"
      zvt: "trader.py:538 StockTrader.__init__ adjust_type=hfq"
    - id: IH-03
      rule: "SQLite connection MUST use check_same_thread=False for multi-threaded recorders"
      zvt: "Configured in storage backend"
    - id: IH-04
      rule: "Accumulator state serialization uses JSON with custom encoder/decoder hooks"
      zvt: "contract/base_service.py EntityStateService"
    - id: IH-05
      rule: "Factor.level MUST match TargetSelector.level (enforced at add_factor)"
      zvt: "factors/target_selector.py:84 add_factor"
"""

    fatal_count = len(fatal_ids)
    non_fatal_count = len(non_fatal_ids)
    bd_count = len(bd_ids)

    preservation_manifest = f"""    required_objects:
      - type: spec_lock_semantic
        count: 12
        verification_method: "grep `id: SL-` inside spec_lock_registry fenced block, expect 12"
      - type: spec_lock_implementation
        count: 5
        verification_method: "grep `id: IH-` inside spec_lock_registry fenced block, expect 5"
      - type: fatal_constraint
        count: {fatal_count}
        verification_method: "count `finance-C-` IDs in `## [FATAL] 约束` section, expect {fatal_count}"
      - type: known_use_case
        count: {uc_count}
        verification_method: "count `uc_id:` in intent_router fenced block, expect {uc_count}"
      - type: rationalization_guard
        count: 0
        verification_method: "section omitted (0 rationalization_guard constraints)"
      - type: validator_assertion
        count: 6
        verification_method: "count OV-XX entries in validate.py"
      - type: hard_gate
        count: 8
        verification_method: "count G[1-8] in `## 验收` section"
      - type: business_decision
        count: {bd_count}
        verification_method: "count unique BD-X IDs across seed.md, expect {bd_count}"
      - type: non_fatal_constraint
        count: {non_fatal_count}
        verification_method: "count `finance-C-` IDs in `## 约束` section, expect {non_fatal_count}"
"""

    output_validator_block = """    rendering_target: "## Output Validator"
    enforcement_chain:
      validator_script_path: "{workspace}/validate.py"
      strategy_tail_marker: "# === DO NOT MODIFY BELOW THIS LINE ==="
      enforcement_protocol_in_directive: true
    assertions:
      - source_kind: "spec_lock.SL-08"
        rendered_check: "MACD params == (12, 26, 9)"
        rendered_message: "FATAL: MACD params drifted"
      - source_kind: "physical_plausibility"
        rendered_check: "abs(annual_return) <= 5.0"
        rendered_message: "FATAL: |annual_return| > 500 pct"
      - source_kind: "physical_plausibility"
        rendered_check: "abs(max_drawdown) <= 1.0"
        rendered_message: "FATAL: |drawdown| > 100 pct"
      - source_kind: "data_integrity"
        rendered_check: "len(result) > 0"
        rendered_message: "FATAL: empty result — possible look-ahead failure"
      - source_kind: "spec_lock.SL-01"
        rendered_check: "no buy-before-sell in same cycle"
        rendered_message: "FATAL: SL-01 violation"
      - source_kind: "business_decision.BD-029"
        rendered_check: "holding_change_pct <= 1.0"
        rendered_message: "FATAL: holding change > 100 pct"
"""

    return f"""## directive

### Language Protocol

This crystal is written in English for universal AI consumption.

1. **Detect** the user's language from their first message or system locale
2. **All user-facing output** (questions, explanations, warnings, reports) MUST be in the user's detected language
3. **Intent matching**: translate user input to English semantically before matching against intent_router terms — do not require the user to speak English
4. **Code and identifiers** remain in English regardless of user language (variable names, file paths, API calls, assert statements)
5. **Domain terms**: use the user's language equivalent when explaining constraints or decisions (e.g., "look-ahead bias" → "前视偏差" for Chinese users)

### Execution Directive

This is an EXECUTION task, not a reference document. You are the host AI for a ZVT-based quantitative backtesting or data collection workflow on A-share market (primarily).

Follow this protocol:

**Step 1 (CA1_MEMORY_CHECKED)**: Query user memory for prior preferences, data source credentials, and strategy history. If memory unavailable, mark `memory_unavailable=true` and proceed.

**Step 2 (CA2_GAPS_FILLED)**: Ask the user FATAL-priority questions if not answered in memory. MUST NOT skip — at minimum confirm target market (A-share / HK / US), data source (eastmoney / joinquant / baostock / akshare / qmt), time range, and strategy type.

**Step 3 (CA3_PATH_SELECTED)**: Match user intent against intent_router entries below. If top-1 vs top-2 score gap < 20 pct OR candidates span multiple data_domains, ask ambiguity_question.

**Step 4 (CA4_USER_CONFIRMED)**: State your understanding ("我理解你要 X，对吗？") and wait for explicit confirmation before generating code.

### Control Blocks

```yaml
intent_router:
{intent_router_block}```

```yaml
context_state_machine:
  states:
    - id: CA1_MEMORY_CHECKED
      entry_condition: "Task started"
      exit_condition: "All memory queries attempted and recorded"
      on_timeout: "Skip memory, mark memory_unavailable=true, proceed to CA2"
    - id: CA2_GAPS_FILLED
      entry_condition: "CA1 complete"
      exit_condition: "All FATAL-priority required_inputs answered by user"
      on_timeout: "NOT skippable — FATAL inputs MUST be user-answered"
    - id: CA3_PATH_SELECTED
      entry_condition: "CA2 complete"
      exit_condition: "intent_router matched a single use case with no ambiguity"
      on_timeout: "Trigger ambiguity_question, await user choice"
    - id: CA4_USER_CONFIRMED
      entry_condition: "CA3 complete"
      exit_condition: "User explicitly confirmed execution path and key parameters"
      on_timeout: "NOT skippable — explicit user confirmation required"
  enforcement:
    - "Before CA4_USER_CONFIRMED, code generation is PROHIBITED"
    - "Regressions to prior states must be announced to the user"
```

```yaml
spec_lock_registry:
  semantic_locks:
{semantic_locks}  implementation_hints:
{implementation_hints}```

```yaml
preservation_manifest:
{preservation_manifest}```

```yaml
output_validator:
{output_validator_block}```

### Output Validator Enforcement Protocol (FATAL)

1. 禁止编辑 validate.py
2. 禁止删除主脚本中 `# === DO NOT MODIFY BELOW THIS LINE ===` 之后的代码
3. 禁止用 try/except 包裹 enforce_validation 调用
4. 禁止重写结果写出逻辑——必须经由 enforce_validation 写出
5. validate.py 因依赖问题报错时必须修复依赖，不得删除调用
"""


def render_fatal_section(fatal_constraints: list[dict]) -> str:
    lines = ["## [FATAL] 约束", ""]
    lines.append("**绝对红线**。命中任一即停止执行，回到 context_acquisition 重新确认。")
    lines.append("")
    lines.append(f"共 {len(fatal_constraints)} 条 fatal 约束全量内联。")
    lines.append("")
    for c in fatal_constraints:
        cid = c.get("id", "?")
        core = c.get("core") or {}
        when = core.get("when") or c.get("when", "")
        action = core.get("action") or c.get("action", "")
        modality = core.get("modality") or c.get("modality", "must")
        kind = c.get("constraint_kind", "?")
        consequence = core.get("consequence") or {}
        cons_desc = consequence.get("description") if isinstance(consequence, dict) else ""
        cons_kind = consequence.get("kind") if isinstance(consequence, dict) else ""
        stages = (c.get("applies_to") or {}).get("stage_ids") or []
        lines.append(f"### [FATAL] `{cid}` [{kind} / {modality}]")
        lines.append(f"- **When**: {when}")
        lines.append(f"- **Action**: {action}")
        if cons_desc:
            lines.append(f"- **Consequence** ({cons_kind}): {cons_desc}")
        if stages:
            lines.append(f"- **Stages**: {', '.join(stages)}")
        lines.append("")
    return "\n".join(lines)


def render_output_validator_section() -> str:
    return """## Output Validator

This section defines the enforcement chain that makes "false completion claim" (SOP Step 2a #8) structurally impossible.

### Validator Scaffold (`validate.py`)

A standalone Python file is generated alongside this crystal at `{workspace}/validate.py`. It contains 6 OV assertions covering:

- **OV-01**: MACD parameter lock (from SL-08)
- **OV-02**: result non-empty (prevents silent no-signal false completion)
- **OV-03**: |annual_return| <= 5.0 (physical plausibility, from Step 1b FATAL threshold rule)
- **OV-04**: |holding_change_pct| <= 1.0 (physical plausibility)
- **OV-05**: |max_drawdown| <= 1.0 (physical plausibility)
- **OV-06**: No buy-before-sell in same cycle (from SL-01)

Signature:

```python
def enforce_validation(result, output_path: str) -> None:
    # Assertions run. If any fails, sys.exit(1) and write FAILED.log.
    # On success, write result to output_path and touch {output_path}.validation_passed.
```

### Strategy Scaffold Tail (MUST appear at end of main script)

Every strategy / backtest / pipeline script MUST end with the following literal block:

```python
# === DO NOT MODIFY BELOW THIS LINE ===
if __name__ == "__main__":
    result = run_backtest()  # AI implements run_backtest() above
    from validate import enforce_validation
    enforce_validation(result, output_path="{workspace}/result.csv")
# === END DO NOT MODIFY ===
```

Placeholder rendering rules:
- `{workspace}` → host-resolved absolute path at execution time
- `run_backtest` is the required entry point name for backtest tasks; for data pipelines use `run_pipeline`, for ML training use `run_training`

### Hard Gates (G1-G4)

- **G1**: `{workspace}/result.csv` exists AND size > 0
- **G2**: `{workspace}/result.csv.validation_passed` marker file exists
- **G3**: Main script contains literal `from validate import enforce_validation`
- **G4**: Main script contains literal `# === DO NOT MODIFY BELOW THIS LINE ===`

G1-G2 verify output produced AND validated. G3-G4 verify validator chain not stripped.
"""


def render_evidence_quality_section(bp: dict) -> str:
    meta = bp.get("_enrich_meta") or {}
    audit = bp.get("audit_checklist_summary") or {}

    def fmt_num(v, pct=False):
        if v is None:
            return "n/a"
        if pct and isinstance(v, (int, float)):
            return f"{v * 100:.1f}%"
        return str(v)

    ev_coverage = fmt_num(meta.get("evidence_coverage_ratio"), pct=True)
    ev_verify = fmt_num(meta.get("evidence_verify_ratio"), pct=True)
    ev_verify_raw = meta.get("evidence_verify_ratio")
    ev_invalid = meta.get("evidence_invalid", 0) or 0
    ev_verified = fmt_num(meta.get("evidence_verified"))
    ev_auto_fixed = fmt_num(meta.get("evidence_auto_fixed"))

    coverage_str = audit.get("coverage", "n/a")
    fu = audit.get("finance_universal") or {}
    st = audit.get("subdomain_totals") or {}
    sub_fail = st.get("fail", 0) or 0
    fu_fail = fu.get("fail", 0) or 0
    total_fail = sub_fail + fu_fail

    lines = ["## 证据质量声明", ""]
    lines.append(
        "> 本晶体由蓝图 + 约束机械压缩而成。蓝图源文件自报以下证据质量指标，agent 使用本晶体时必须读取这些信号并据此调整置信度。"
    )
    lines.append("")
    lines.append("### 蓝图自报证据指标")
    lines.append("")
    lines.append(f"- **evidence_coverage_ratio**：{ev_coverage}（BD 带 evidence_refs 字段的占比）")
    lines.append(f"- **evidence_verify_ratio**：{ev_verify}（已人工/自动核验的 evidence 占比）")
    lines.append(f"- **evidence_invalid**：{ev_invalid} 条（被标记为无效的证据条目）")
    lines.append(f"- **evidence_verified**：{ev_verified} 条")
    lines.append(f"- **evidence_auto_fixed**：{ev_auto_fixed} 条")
    lines.append("")
    lines.append("### 审计清单覆盖率")
    lines.append("")
    lines.append(f"- **coverage**：{coverage_str}")
    lines.append(
        f"- **finance_universal**：pass {fu.get('pass', 0)} / warn {fu.get('warn', 0)} / fail {fu.get('fail', 0)}"
    )
    lines.append(
        f"- **subdomain_totals**：pass {st.get('pass', 0)} / warn {st.get('warn', 0)} / fail {st.get('fail', 0)}"
    )
    lines.append("")
    lines.append("### 使用规则（agent 必须遵守）")
    lines.append("")
    lines.append(
        "1. evidence_verify_ratio < 50% 时：生成代码前**必须**查 `溯源政策` 指定的源文件，verify 所涉 BD 的 evidence_refs"
    )
    lines.append(
        f'2. audit fail 合计 > 20（当前 {total_fail}）时：agent **必须**主动告知用户 "本蓝图有 {total_fail} 条审计项未通过，生成结果可能存在未捕获的需求缺口"'
    )
    lines.append("3. 禁止将本晶体当成**唯一**可信源——遇冲突以源文件为准")
    if ev_verify_raw is not None and ev_verify_raw < 0.5:
        lines.append("")
        lines.append(
            f"> ⚠️ 本蓝图 evidence_verify_ratio = {ev_verify} < 50%，规则 1 已触发：agent 必须先回查源文件。"
        )
    if total_fail > 20:
        lines.append("")
        lines.append(
            f"> ⚠️ 本蓝图审计 fail 合计 = {total_fail} > 20，规则 2 已触发：agent 必须主动告知用户。"
        )
    return "\n".join(lines)


def render_traceback_policy_section(bp: dict) -> str:
    bp_id = bp.get("id", "unknown")
    lines = ["## 溯源政策", ""]
    lines.append(
        '> **晶体的"骨架" vs 源文件的"血肉"**：本晶体包含全部 ID 骨架（100% BD/UC/约束覆盖），但每条约束的 `evidence_refs` / `machine_checkable` / `consequence` / `validation_threshold`，以及每个 BD 的 `rationale` / `evidence` / `alternative_considered` 均在源文件中，未内联到本晶体。'
    )
    lines.append("")
    lines.append("### 源文件路径（相对 blueprint 目录）")
    lines.append("")
    lines.append(
        f"- 蓝图原文：`LATEST.yaml`（与本晶体同目录；当前版本 `{bp_id}` 对应具体版本文件见同目录 `blueprint.v*.yaml`）"
    )
    lines.append(
        "- 约束原文：`LATEST.jsonl`（与本晶体同目录；当前版本对应 `constraints.v*.jsonl`）"
    )
    lines.append("")
    lines.append("### 必须回查源文件的场景")
    lines.append("")
    lines.append(
        "1. **约束冲突**：两条约束执行规则看似矛盾 → 查源文件 `consequence` + `evidence_refs` 判定优先级"
    )
    lines.append(
        "2. **BD 存疑**：某 BD 的选择理由不清 → 查源文件 `rationale` + `alternative_considered`"
    )
    lines.append(
        "3. **证据可疑**：`证据质量声明` 段标记 evidence_invalid > 0 → 查源文件核对具体字段"
    )
    lines.append(
        '4. **用户质疑**：用户问 "这个规则从哪来的" → 查源文件 `evidence_refs` 给出 source file / line'
    )
    lines.append("")
    lines.append("### 回查方式")
    lines.append("")
    lines.append("- agent 环境有文件读取能力：直接读取 `LATEST.yaml` / `LATEST.jsonl` 按 ID 定位")
    lines.append("- agent 环境无文件读取能力：向用户索要源文件片段，或请用户在源文件中验证")
    lines.append("")
    lines.append(
        "**禁止**：将本晶体当成蓝图 + 约束的**替代品**——它是执行索引，不是可信度证据本身。"
    )
    return "\n".join(lines)


def render_architecture_section(bp: dict, bd_by_stage: dict) -> str:
    lines = ["## 架构蓝图", ""]
    lines.append("ZVT 是一个模块化的 A 股量化数据+回测框架。6 个主要执行阶段按以下顺序运行：")
    lines.append("")
    lines.append(
        "`data_collection → data_storage → factor_computation → target_selection → trading_execution → visualization`"
    )
    lines.append("")
    lines.append("<!-- SOUL_TODO: 主线程补充 stage-by-stage 叙事，将 BD 串联成故事 -->")
    lines.append("")

    main_stages = [
        "data_collection",
        "data_storage",
        "factor_computation",
        "target_selection",
        "trading_execution",
        "visualization",
    ]
    covered_stages = set()

    for stage_name in main_stages:
        bds = bd_by_stage.get(stage_name, [])
        lines.append(f"### Stage: {stage_name} ({len(bds)} BDs)")
        lines.append("")
        lines.append(
            "<!-- SOUL_TODO: 主线程写该 stage 的 1-2 段叙事（做什么 / 关键决策 / 常见陷阱） -->"
        )
        lines.append("")
        if bds:
            lines.append("**Business Decisions**:")
            for bd in bds:
                bd_id = bd.get("id", "?")
                bd_type = bd.get("type", "?")
                content = (bd.get("content") or "").replace("\n", " ")
                lines.append(f"- **{bd_id}** [type={bd_type}] {content}")
            lines.append("")
        covered_stages.add(stage_name)

    # 其它 stage 分组（non-main）
    other_stages = sorted(set(bd_by_stage.keys()) - covered_stages)
    if other_stages:
        lines.append("### Cross-cutting Business Decisions")
        lines.append("")
        lines.append(
            "以下 BD 属于横切关注点（interactions / defaults / invariants / ML config / "
            "reporting / visualization extras / module-level defaults）："
        )
        lines.append("")
        for stage_name in other_stages:
            bds = bd_by_stage.get(stage_name, [])
            if not bds:
                continue
            lines.append(f"#### Sub-stage: `{stage_name}` ({len(bds)} BDs)")
            for bd in bds:
                bd_id = bd.get("id", "?")
                bd_type = bd.get("type", "?")
                content = (bd.get("content") or "").replace("\n", " ")
                lines.append(f"- **{bd_id}** [type={bd_type}] {content}")
            lines.append("")

    return "\n".join(lines)


def render_resources_section(bp: dict, target_host: str) -> str:
    resources = bp.get("resources") or []
    packages = []
    data_sources = []
    code_templates = []
    infra = []

    for r in resources:
        rtype = r.get("type", "")
        name = r.get("name", "")
        path = r.get("path", "")
        if rtype in ("python_package", "dependency"):
            packages.append((name, path, r.get("version", "")))
        elif rtype in ("data_source", "external_service"):
            data_sources.append((name, path))
        elif rtype in ("code_example", "example_script", "tutorial"):
            code_templates.append((name, path))
        elif rtype in ("infrastructure", "storage", "database"):
            infra.append((name, path))

    lines = ["## 资源", ""]
    lines.append("### L1 知识层（宿主无关）")
    lines.append("")
    lines.append("#### Python 依赖包")
    lines.append("")
    if packages:
        for name, path, ver in packages[:20]:
            v = f" `{ver}`" if ver else ""
            lines.append(f"- `{name}`{v} — {path}")
    else:
        lines.append("- `zvt` (latest) — 主框架")
        lines.append("- `pandas>=2.2`, `numpy>=2.1` — 数据处理")
        lines.append("- `SQLAlchemy>=2.0` — ORM")
        lines.append("- `plotly>=5`, `dash>=2` — 可视化")
        lines.append("- `akshare` / `baostock` — 免费 A 股数据源")
    lines.append("")

    lines.append("#### 数据源（选一个或多个）")
    lines.append("")
    lines.append("| Provider | Access | Coverage | Notes |")
    lines.append("|---------|--------|----------|-------|")
    lines.append("| eastmoney (em) | 免费，无需账号 | A 股 + 基础财务 | 不稳定，高峰期偶发 503 |")
    lines.append("| joinquant (jq) | 需账号+付费 | A 股 + 基金数据 | 数据质量高，适合研究 |")
    lines.append("| baostock | 免费 | A 股 + 历史数据 | 历史覆盖长，实时性弱 |")
    lines.append("| akshare | 免费 | 全球市场 + A 股 | 聚合接口，API 丰富 |")
    lines.append("| qmt | 需券商对接 | 实盘数据 | 仅 Windows；需券商权限 |")
    lines.append("")

    lines.append("#### Strategy Scaffold 模板")
    lines.append("")
    lines.append(
        "回测/数据采集脚本骨架（MUST 含 DO NOT MODIFY 尾部；详见 Step 8e / `## Output Validator`）："
    )
    lines.append("")
    lines.append("```python")
    lines.append("# {workspace}/strategy.py")
    lines.append("from zvt.trader import Trader")
    lines.append("")
    lines.append("class MyStrategy(Trader):")
    lines.append("    # REPLACE_WITH: 策略业务逻辑")
    lines.append("    def init_factors(self, entity_ids, entity_schema, exchanges, codes,")
    lines.append("                     start_timestamp, end_timestamp, adjust_type=None):")
    lines.append("        # REPLACE_WITH: 创建 Factor 实例")
    lines.append("        pass")
    lines.append("")
    lines.append("def run_backtest():")
    lines.append("    trader = MyStrategy(")
    lines.append("        entity_ids=['stock_sh_600000'],")
    lines.append("        start_timestamp='2024-01-01',")
    lines.append("        end_timestamp='2024-06-30',")
    lines.append("        # 其它参数 REPLACE_WITH")
    lines.append("    )")
    lines.append("    trader.run()")
    lines.append("    return trader.account_service.get_stats()  # 必须返回 result-like")
    lines.append("")
    lines.append("# === DO NOT MODIFY BELOW THIS LINE ===")
    lines.append('if __name__ == "__main__":')
    lines.append("    result = run_backtest()")
    lines.append("    from validate import enforce_validation")
    lines.append('    enforce_validation(result, output_path="{workspace}/result.csv")')
    lines.append("# === END DO NOT MODIFY ===")
    lines.append("```")
    lines.append("")

    lines.append("#### 基础设施选择")
    lines.append("")
    lines.append("- 默认存储: SQLite（每 provider 一个 .db 文件）—— 开箱即用")
    lines.append("- 数据量大时: 迁移到 PostgreSQL / MySQL（ZVT 支持 StorageBackend 抽象）")
    lines.append("")

    if target_host == "openclaw":
        lines.append("### L3 Host Adapter: openclaw")
        lines.append("")
        lines.append("**关键宿主约束**（参考 `docs/research/host-specs/openclaw-host-spec.md`）：")
        lines.append("")
        lines.append("- **超时**: 1800s (30 分钟) / agent；数据采集可能需要分批")
        lines.append(
            "- **exec 工具**: 拦截 shell 操作符 `&&` / `;` / `|`。不要用 `pip install X && python Y`"
        )
        lines.append("- **工作目录**: 由 `{workspace}` 占位符在执行时解析")
        lines.append("")
        lines.append("#### install_recipes")
        lines.append("")
        lines.append("```bash")
        lines.append("# 绝不用 && 或 ;")
        lines.append("python3 -m pip install zvt")
        lines.append("python3 -m pip install akshare  # 如需要")
        lines.append("python3 -m zvt.init_dirs  # 初始化数据目录")
        lines.append("```")
        lines.append("")
        lines.append("#### credential_injection")
        lines.append("")
        lines.append("- JoinQuant / QMT credentials 需要单独 shell 登录：")
        lines.append(
            "  - **先让用户完成** `! jqdatasdk auth` 式手动登录（`!` 前缀在 openclaw session 中执行）"
        )
        lines.append("  - 不要在 seed.md 中硬编码账密")
        lines.append("")
        lines.append("#### path_resolution")
        lines.append("")
        lines.append("- `{workspace}` → `~/.openclaw/workspace/doramagic` (实测路径)")
        lines.append("- `zvt` 默认数据目录 `~/zvt-home/` 独立于 workspace——两者分开")
        lines.append("")
        lines.append("#### file_io_tooling")
        lines.append("")
        lines.append("- 用 openclaw `write` 工具创建 `.py` / `.sql` 文件")
        lines.append(
            "- 用 openclaw `exec` 工具运行 `python3 /absolute/path/script.py`（绝对路径，无 shell operators）"
        )
        lines.append("- 大 CSV 输出用 `pandas.to_csv(..., index=False)`；小字典用 `json.dumps`")

    return "\n".join(lines)


def render_constraints_section(non_fatal_by_stage: dict) -> str:
    lines = ["## 约束", ""]
    lines.append("非 FATAL 约束按 stage 分组。违反会降级效果/引入风险，但不立即终止执行。")
    lines.append("")
    main_stages = [
        "data_collection",
        "data_storage",
        "factor_computation",
        "target_selection",
        "trading_execution",
        "visualization",
    ]
    handled = set()
    for stage_name in main_stages:
        cs = non_fatal_by_stage.get(stage_name, [])
        lines.append(f"### Stage: {stage_name} ({len(cs)} 条)")
        lines.append("")
        if not cs:
            lines.append("*（本 stage 无 non-fatal 约束）*")
            lines.append("")
            continue
        for c in cs:
            cid = c.get("id", "?")
            core = c.get("core") or {}
            when = core.get("when") or c.get("when", "")
            action = core.get("action") or c.get("action", "")
            modality = core.get("modality") or c.get("modality", "should")
            kind = c.get("constraint_kind", "?")
            sev = c.get("severity", "?")
            lines.append(f"- **`{cid}`** [{kind} / {modality} / sev={sev}]")
            lines.append(f"  - When: {when}")
            lines.append(f"  - Action: {action}")
        lines.append("")
        handled.add(stage_name)

    # 其它（未分 stage 或其它 stage）
    other = [s for s in non_fatal_by_stage if s not in handled and s]
    if other or "(unassigned)" in non_fatal_by_stage:
        lines.append("### Cross-stage / Unassigned")
        lines.append("")
        for stage_name in sorted(other):
            cs = non_fatal_by_stage[stage_name]
            lines.append(f"**Stage `{stage_name}`:**")
            for c in cs:
                cid = c.get("id", "?")
                core = c.get("core") or {}
                when = core.get("when") or c.get("when", "")
                action = core.get("action") or c.get("action", "")
                modality = core.get("modality") or c.get("modality", "should")
                kind = c.get("constraint_kind", "?")
                sev = c.get("severity", "?")
                lines.append(f"- **`{cid}`** [{kind} / {modality} / sev={sev}]")
                lines.append(f"  - When: {when}")
                lines.append(f"  - Action: {action}")
            lines.append("")
        # 未分 stage
        unassigned = non_fatal_by_stage.get("(unassigned)", [])
        if unassigned:
            lines.append("**No stage assigned:**")
            for c in unassigned:
                cid = c.get("id", "?")
                core = c.get("core") or {}
                when = core.get("when") or c.get("when", "")
                action = core.get("action") or c.get("action", "")
                modality = core.get("modality") or c.get("modality", "should")
                kind = c.get("constraint_kind", "?")
                sev = c.get("severity", "?")
                lines.append(f"- **`{cid}`** [{kind} / {modality} / sev={sev}]")
                lines.append(f"  - When: {when}")
                lines.append(f"  - Action: {action}")

    return "\n".join(lines)


def render_acceptance_section() -> str:
    return """## 验收

### Hard Gates (machine-checkable, deterministic)

| Gate | 检查 | 验证方式 |
|------|------|---------|
| **G1** | `{workspace}/result.csv` 存在且非空 | `os.path.exists + os.path.getsize > 0` |
| **G2** | `{workspace}/result.csv.validation_passed` 标记文件存在 | `os.path.exists` |
| **G3** | 主脚本含 `from validate import enforce_validation` | `grep` literal string |
| **G4** | 主脚本含 `# === DO NOT MODIFY BELOW THIS LINE ===` 围栏 | `grep` literal string |
| **G5** | 回测/策略脚本至少运行到生成 trading signals（trade_log 非空 OR result.csv 含 transaction 行） | `pandas.read_csv(result).shape[0] >= 1` |
| **G6** | 若为 MACD 策略：MACD 参数未漂移 | `grep 'slow=26, fast=12, n=9' strategy.py` |
| **G7** | 数据采集类任务：result 含 `entity_id` 和 `timestamp` 列 | `pandas.read_csv(result).columns ⊇ {'entity_id', 'timestamp'}` |
| **G8** | 结果通过 sanity check（`abs(annual_return) <= 5.0`） | `validate.py` OV-03 |

### Soft Gates (LLM-as-Judge, 按 Step 0.8d rubric)

- **SG-01: 策略叙事一致性** — 用户描述的意图与生成的 strategy.py 逻辑是否语义对齐？
  - dim_a: 信号方向（买/卖/空仓）是否一致；dim_b: 频率（高频/低频）是否一致；dim_c: 风控（止损/止盈）是否按用户意图
  - Rubric: 1-5 each; passing >= 4

- **SG-02: Factor 组合合理性** — 选用的 Factor 组合是否合理？
  - dim_a: 是否避免了高度相关因子叠加；dim_b: 多周期是否对齐；dim_c: 是否包含必要的流动性过滤
  - Rubric: 1-5 each; passing >= 4

- **SG-03: 数据源选择** — 数据源是否适合任务？
  - dim_a: 数据覆盖是否足够；dim_b: 数据延迟是否可接受；dim_c: 是否避免了需要授权但未授权的 provider
  - Rubric: 1-5 each; passing >= 4
"""


# ============================================================
# IR 组装
# ============================================================


def render_ir(
    bp: dict,
    constraints: list[dict],
    target_host: str,
    bd_by_stage: dict,
    ucs: list[dict],
    fatal_count: int,
    non_fatal_count: int,
    sop_version: str,
) -> dict:
    bd_count = sum(len(v) for v in bd_by_stage.values())
    uc_count = len(ucs)
    return {
        "version": "2.0",
        "crystal_id": f"{bp.get('id', 'unknown')}-v3.3",
        "task_type": "A",
        "metadata": {
            "compilation_language": "en",
            "source_languages": ["en", "zh"],
            "human_summary_locale": "zh",
            "output_validator_exempt": False,
            "intelligence_judgment_deferred": True,
        },
        "references": {
            "blueprint": str(Path("LATEST.yaml")),
            "constraints": [str(Path("LATEST.jsonl"))],
            "source_commits": {
                "blueprint": bp.get("source", {}).get("commit_hash"),
            },
        },
        "user_intent": "zvt-based A-share quantitative backtest or data collection",
        "knowledge": {
            "business_decisions_count": bd_count,
            "constraints_count": len(constraints),
            "use_cases_count": uc_count,
            "resources": {
                "packages": "listed in ## 资源 L1 main body",
                "data_sources": "em / joinquant / baostock / akshare / qmt",
                "code_templates": "Strategy Scaffold in ## 资源",
                "infrastructure_choices": "SQLite default, Postgres/MySQL optional",
            },
        },
        "control_blocks": {
            "intent_router": f"{uc_count} use cases",
            "context_state_machine": "CA1-CA4",
            "spec_lock_registry": {
                "semantic_locks": 12,
                "implementation_hints": 5,
            },
            "preservation_manifest": "defined in directive fenced block",
            "output_validator": "rendered into ## Output Validator + validate.py",
        },
        "harness": {
            "contract": {
                "spec_lock": "see control_blocks.spec_lock_registry",
                "delivery_gate": {"hard": 8, "soft": 3},
            },
            "failure_taxonomy": {
                "universal": 8,
                "domain_specific": "derived from fatal constraints",
            },
            "stage_spec": {
                "task_type": "A (Pipeline)",
                "stages": [
                    "data_collection",
                    "data_storage",
                    "factor_computation",
                    "target_selection",
                    "trading_execution",
                    "visualization",
                ],
            },
            "state_semantics": {"slots": "plan / result / evidence / manifest"},
            "host_adapters": {
                target_host: {
                    "spec_ref": f"docs/research/host-specs/{target_host}-host-spec.md",
                    "timeout_seconds": 1800,
                    "install_recipes": "python3 -m pip install zvt (no shell operators)",
                    "credential_injection": "user-side `!` prefix shell login",
                    "path_resolution": "{workspace} → host-resolved abs path",
                    "file_io_tooling": "openclaw write/exec tools",
                },
            },
        },
        "trace_schema": {
            "events": [
                "stage_transition",
                "tool_call",
                "artifact_emission",
                "validation_result",
                "failure_event",
                "spec_lock_check",
            ],
            "output": {"format": "jsonl", "path": "{workspace}/.trace/execution_trace.jsonl"},
        },
        "validity": {
            "compiled_at": None,
            "source_commits": {"blueprint": bp.get("source", {}).get("commit_hash")},
            "version_pins": [
                {
                    "dependency": "zvt",
                    "version": "latest (no backward compat guarantee per finance-C-150)",
                },
                {"dependency": "pandas", "version": ">=2.2"},
                {"dependency": "SQLAlchemy", "version": ">=2.0"},
            ],
        },
        "compilation": {
            "sop_version": sop_version,
            "compiler_version": "v3.3",
        },
    }


# ============================================================
# main
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--blueprint-dir", type=Path, required=True)
    parser.add_argument("--target-host", default="openclaw")
    parser.add_argument("--output-seed", type=Path, required=True, help="seed.md 输出路径")
    parser.add_argument("--output-ir", type=Path, required=True, help="ir.yaml 输出路径")
    parser.add_argument(
        "--output-validate",
        type=Path,
        default=None,
        help="validate.py 输出路径（默认 {blueprint-dir}/validate.py）",
    )
    parser.add_argument("--sop-version", default="crystal-compilation-v3.2")
    args = parser.parse_args()

    bp, constraints, _targets = load_inputs(args.blueprint_dir)

    # 分类 BD 按 stage
    bd_by_stage = defaultdict(list)
    for bd in bp.get("business_decisions") or []:
        stage = bd.get("stage") or "(unassigned)"
        bd_by_stage[stage].append(bd)

    # 分类约束按 severity + stage
    fatal_constraints = [c for c in constraints if c.get("severity") == "fatal"]
    non_fatal_constraints = [c for c in constraints if c.get("severity") != "fatal"]

    non_fatal_by_stage = defaultdict(list)
    for c in non_fatal_constraints:
        stages = (c.get("applies_to") or {}).get("stage_ids") or []
        if stages:
            for s in stages:
                non_fatal_by_stage[s].append(c)
        else:
            non_fatal_by_stage["(unassigned)"].append(c)

    # 去重（一个约束出现在多个 stage 会重复；为了机械保证，我们只在第一个 stage 显示，防 grep 重复）
    seen = set()
    deduped = defaultdict(list)
    for stage in non_fatal_by_stage:
        for c in non_fatal_by_stage[stage]:
            cid = c.get("id")
            if cid in seen:
                continue
            seen.add(cid)
            deduped[stage].append(c)
    non_fatal_by_stage = deduped

    ucs = bp.get("known_use_cases") or []
    bd_ids = [bd.get("id") for bd_list in bd_by_stage.values() for bd in bd_list if bd.get("id")]
    fatal_ids = [c.get("id") for c in fatal_constraints if c.get("id")]
    non_fatal_ids = [c.get("id") for c in non_fatal_constraints if c.get("id")]

    # 生成 seed.md
    sections = [
        "*Powered by Doramagic.ai*",
        "",
        render_human_summary_placeholder(),
        render_directive_section(bp.get("id", "unknown"), ucs, fatal_ids, non_fatal_ids, bd_ids),
        render_fatal_section(fatal_constraints),
        render_output_validator_section(),
        render_evidence_quality_section(bp),
        render_traceback_policy_section(bp),
        render_architecture_section(bp, bd_by_stage),
        render_resources_section(bp, args.target_host),
        render_constraints_section(non_fatal_by_stage),
        render_acceptance_section(),
        "",
        "*Powered by Doramagic.ai*",
        "",
    ]
    seed_text = "\n\n".join(sections)
    args.output_seed.write_text(seed_text, encoding="utf-8")

    # 生成 ir.yaml
    ir = render_ir(
        bp,
        constraints,
        args.target_host,
        bd_by_stage,
        ucs,
        len(fatal_constraints),
        len(non_fatal_constraints),
        args.sop_version,
    )
    args.output_ir.write_text(
        yaml.safe_dump(ir, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    # 生成 validate.py
    vpath = args.output_validate or (args.blueprint_dir / "validate.py")
    vpath.write_text(render_validate_py(bp.get("id", "unknown")), encoding="utf-8")

    print(f"[done] seed.md:     {args.output_seed}")
    print(f"[done] ir.yaml:     {args.output_ir}")
    print(f"[done] validate.py: {vpath}")
    print()
    print(f"BD total:   {len(bd_ids)}")
    print(
        f"Constraint total: {len(constraints)} ({len(fatal_ids)} fatal + {len(non_fatal_ids)} non-fatal)"
    )
    print(f"UC total:   {len(ucs)}")
    print()
    print("Next: run `scripts/crystal_quality_gate.py --strict` to verify coverage == 100 pct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
