#!/usr/bin/env python3
"""
Rubric v5 classifier — Shard 2 (alphabetical indices 25-49).
Outputs: constraints_audit_v5_shard_2.jsonl
"""

import json
import os
import re
from collections import Counter
from datetime import UTC, datetime

# ── Blueprint list (0-based; pick indices 25-49) ──────────────────────────────
SOURCES_DIR = "/Users/tangsir/Documents/openclaw/Doramagic/knowledge/sources/finance"
OUTPUT_PATH = os.path.join(SOURCES_DIR, "_shared", "constraints_audit_v5_shard_2.jsonl")
DECIDED_BY = "sonnet_rubric_v5_shard2"

# All alphabetically sorted dirs (excluding _shared, STATUS.md)
ALL_DIRS_SORTED = sorted(
    d
    for d in os.listdir(SOURCES_DIR)
    if not d.startswith("_") and d != "STATUS.md" and os.path.isdir(os.path.join(SOURCES_DIR, d))
)
SHARD_DIRS = ALL_DIRS_SORTED[25:50]  # indices 25-49 inclusive

# ── A.1 CamelCase detection ───────────────────────────────────────────────────
A1_WHITELIST = {
    "DataFrame",
    "Series",
    "DatetimeIndex",
    "Decimal",
    "ndarray",
    "Candlestick",
    "Path",
    "Timestamp",
    "Timedelta",
    "MultiIndex",
}
# Matches true CamelCase multi-word (e.g. MyClass) OR single-capital words flagged
A1_MULTI_CAMEL = re.compile(r"\b([A-Z][a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+)\b")
# Spec also flags single-word capital terms: Factor, Trader, Recorder, Accumulator
# Spec says "etc." but is conservative — only include the explicitly-cited pattern
# (agent nouns typically used as project class names)
A1_SINGLE_WORDS = {
    "Factor",
    "Trader",
    "Recorder",
    "Accumulator",
    "Fetcher",
    "Loader",
    "Runner",
    "Manager",
    "Handler",
    "Builder",
    "Processor",
    "Parser",
    "Provider",
    "Formatter",
    "Reporter",
    "Writer",
    "Reader",
    "Executor",
    "Transformer",
    "Extractor",
    "Validator",
    "Scheduler",
    "Dispatcher",
    "Subscriber",
    "Publisher",
    "Observer",
    "Listener",
    "Connector",
    "Adapter",
    "Wrapper",
    "Proxy",
    "Controller",
    "Repository",
    "Factory",
    "Registry",
    "Broker",
    "Pipeline",
    "Collector",
    "Emitter",
    "Analyzer",
    "Aggregator",
    "Serializer",
    "Deserializer",
}


def check_a1(text: str) -> tuple[bool, str | None]:
    """Returns (pass, reason). pass=True means gate passes (no violation)."""
    # Check multi-word CamelCase
    for m in A1_MULTI_CAMEL.finditer(text):
        token = m.group(1)
        if token not in A1_WHITELIST:
            return False, f'A.1 FAILS: CamelCase "{token}" in when/action'
    # Check single-capital words in A1_SINGLE_WORDS that are NOT whitelisted
    for word in re.findall(r"\b([A-Z][a-z][a-z0-9]*)\b", text):
        if word in A1_SINGLE_WORDS and word not in A1_WHITELIST:
            return False, f'A.1 FAILS: single-word class name "{word}" in when/action'
    return True, None


# ── A.2 project-specific snake_case method/function calls ────────────────────
A2_WHITELIST = {
    "groupby",
    "concat",
    "merge",
    "astype",
    "to_datetime",
    "apply",
    "rolling",
    "resample",
    "shift",
    "dropna",
    "fillna",
    "isna",
    "notna",
    "reset_index",
    "set_index",
    "iloc",
    "loc",
    "commit",
    "rollback",
}
# snake_case token (≥2 parts) followed by ( or preceded by . — method call context
A2_PATTERN = re.compile(r"(?<![/\w])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\s*\(")


def check_a2(text: str) -> tuple[bool, str | None]:
    for m in A2_PATTERN.finditer(text):
        token = m.group(1)
        if token not in A2_WHITELIST:
            return False, f'A.2 FAILS: snake_case method call "{token}()" in when/action'
    return True, None


# ── A.3 module/file paths ─────────────────────────────────────────────────────
# Slash-separated paths, including "Word/Word" connections like "Plotly/Dash"
A3_PATTERN = re.compile(r"(?<!\w)[\w.-]+/[\w.-]+")


def check_a3(text: str) -> tuple[bool, str | None]:
    for m in A3_PATTERN.finditer(text):
        return False, f'A.3 FAILS: path/slash "{m.group()}" in when/action'
    return True, None


# ── A.4 project-specific snake_case variables (≥2 tokens) ────────────────────
A4_WHITELIST = {
    "start_date",
    "end_date",
    "timestamp",
    "datetime",
    "price",
    "volume",
    "open",
    "high",
    "low",
    "close",
    "ohlcv",
    "trading_day",
    "market_close",
    "look_ahead",
    "survivorship_bias",
}
# snake_case ≥2 tokens (not a method call — no leading . or trailing ()
A4_PATTERN = re.compile(r"(?<![./\w])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?!\s*\()(?!\w)")


def check_a4(text: str) -> tuple[bool, str | None]:
    seen = set()
    for m in A4_PATTERN.finditer(text):
        token = m.group(1)
        if token in seen:
            continue
        seen.add(token)
        if token not in A4_WHITELIST and token not in A2_WHITELIST:
            return False, f'A.4 FAILS: project-specific snake_case "{token}" in when/action'
    return True, None


# ── A.5 magic numbers ─────────────────────────────────────────────────────────
# Percentages, decimals (non-zero/one), tuples, time literals
A5_PERCENT = re.compile(r"\b\d+\.?\d*%")
A5_DECIMAL = re.compile(r"\b0\.\d*[2-9]\d*\b|\b[2-9]\d*\.\d+\b|\b1\.\d{2,}\b")
A5_TUPLE = re.compile(r"\(\s*\d+\.?\d*\s*,\s*\d+\.?\d*\s*\)")
A5_TIME_LIT = re.compile(r"\b\d+\s+(?:minute|second|hour|day|week|month)s?\b", re.IGNORECASE)


def check_a5(text: str) -> tuple[bool, str | None]:
    m = A5_PERCENT.search(text)
    if m:
        return False, f'A.5 FAILS: percentage literal "{m.group()}" in action'
    m = A5_DECIMAL.search(text)
    if m:
        return False, f'A.5 FAILS: decimal literal "{m.group()}" in action'
    m = A5_TUPLE.search(text)
    if m:
        return False, f'A.5 FAILS: tuple literal "{m.group()}" in action'
    m = A5_TIME_LIT.search(text)
    if m:
        return False, f'A.5 FAILS: time literal "{m.group()}" in action'
    return True, None


# ── A.6 blocked project-internal name tokens ─────────────────────────────────
# Full tokens (no word-boundary restriction needed for most)
A6_BLOCKED_FULL = [
    "zvt",
    "freqtrade",
    "rqalpha",
    "xalpha",
    "QUANTAXIS",
    "vnpy",
    "tqsdk",
    "wealthbot",
    "AMLSim",
    "TradingAgents",
    "FinDKG",
    "hummingbot",
    "OpenBB",
    "Open_Source_Economic_Model",
    "Economic-Dashboard",
    "insurance_python",
    "pyliferisk",
    "firesale_stresstest",
    "ifrs9",
    "openLGD",
    "FinRL-Meta",
    "edgar-crawler",
    "eastmoney",
    "joinquant",
    "jq",
    "sina",
    "daily_stock_analysis",
    "lending",
    "FinRobot",
    "beancount",
    "ledger",
    "open-climate-investing",
    "opensanctions",
    "edgartools",
]
# Short tokens requiring word-boundary match
# Note: 'arch' is whitelisted as a third-party library (NOT blocked per spec)
# 'em' is blocked (eastmoney/em shorthand) with word-boundary
A6_WORD_BOUNDARY = ["em"]

# Build combined regex for A.6 (when+action only)
_a6_full_patterns = [re.compile(re.escape(t), re.IGNORECASE) for t in A6_BLOCKED_FULL]
_a6_wb_patterns = [
    re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in A6_WORD_BOUNDARY
]


def check_a6(text: str) -> tuple[bool, str | None]:
    for i, p in enumerate(_a6_full_patterns):
        m = p.search(text)
        if m:
            return False, f'A.6 FAILS: blocked token "{A6_BLOCKED_FULL[i]}" in when/action'
    for i, p in enumerate(_a6_wb_patterns):
        m = p.search(text)
        if m:
            return (
                False,
                f'A.6 FAILS: blocked token "{A6_WORD_BOUNDARY[i]}" (word-boundary) in when/action',
            )
    return True, None


# ── B.1 finance keywords ──────────────────────────────────────────────────────
B1_KEYWORDS = [
    "backtest",
    "live trading",
    "look-ahead",
    "look ahead",
    "lookahead",
    "survivorship",
    "slippage",
    "settlement",
    "Decimal",
    "compliance",
    "regulatory",
    "timezone",
    "UTC",
    "trading day",
    "corporate action",
    "dividend adjustment",
    "split adjustment",
    "market close",
    "session boundary",
    "fee simulation",
    "bid-ask spread",
    "liquidity",
    "leverage",
    "margin call",
    "drawdown",
    "Sharpe",
    "PnL",
    "commission",
]
_b1_patterns = [(kw, re.compile(re.escape(kw), re.IGNORECASE)) for kw in B1_KEYWORDS]


def check_b1(action: str, consequence_desc: str) -> tuple[str | None, str | None]:
    """Returns (location, keyword) where location is 'action', 'consequence', or None."""
    for kw, p in _b1_patterns:
        if p.search(action):
            return "action", kw
    for kw, p in _b1_patterns:
        if p.search(consequence_desc):
            return "consequence", kw
    return None, None


# ── B.3 consequence.kind check ────────────────────────────────────────────────
B3_KINDS = {"compliance", "false_claim", "financial_loss"}


def check_b3(consequence_kind: str) -> bool:
    return consequence_kind in B3_KINDS


# ── Main classification logic ─────────────────────────────────────────────────
def classify(constraint: dict) -> dict:
    core = constraint.get("core", {})
    when = core.get("when", "") or ""
    action = core.get("action", "") or ""
    consq = core.get("consequence", {}) or {}
    c_kind = consq.get("kind", "") or ""
    c_desc = consq.get("description", "") or ""

    # Gate A: applied to BOTH when AND action combined
    when_action = when + " " + action
    gate_failures = []
    fail_rationale = None

    for gate_name, gate_fn in [
        ("A.1", lambda: check_a1(when_action)),
        ("A.2", lambda: check_a2(when_action)),
        ("A.3", lambda: check_a3(when_action)),
        ("A.4", lambda: check_a4(when_action)),
        ("A.5", lambda: check_a5(action)),  # A.5: action only (per spec "in action")
        ("A.6", lambda: check_a6(when_action)),
    ]:
        passed, reason = gate_fn()
        if not passed:
            gate_failures.append(gate_name)
            if fail_rationale is None:
                fail_rationale = reason

    if gate_failures:
        return {
            "class": "project_specific",
            "decided_by": DECIDED_BY,
            "decided_at": datetime.now(UTC).isoformat(),
            "rationale": fail_rationale,
            "gate_failures": gate_failures,
            "b_hit": None,
            "confidence": 1.0,
            "needs_review": False,
        }

    # Gate B: need at least B.1 or B.3
    b1_loc, b1_kw = check_b1(action, c_desc)
    b3_pass = check_b3(c_kind)

    if b1_loc == "action":
        # Highest priority: B.1 in action
        b_hit = f"B.1:action:{b1_kw}"
        confidence = 1.0
        needs_review = False
    elif b3_pass:
        # B.3 gives 0.9 regardless of B.1 consequence status
        b_hit = f"B.3:{c_kind}"
        if b1_loc == "consequence":
            b_hit += f"+B.1:consequence:{b1_kw}"
        confidence = 0.9
        needs_review = False
    elif b1_loc == "consequence":
        # B.1 only in consequence → 0.8 + needs_review
        b_hit = f"B.1:consequence:{b1_kw}"
        confidence = 0.8
        needs_review = True
    else:
        # No B hit → project_specific (failed Gate B)
        return {
            "class": "project_specific",
            "decided_by": DECIDED_BY,
            "decided_at": datetime.now(UTC).isoformat(),
            "rationale": "Gate B FAILS: no B.1 finance keyword and no B.3 consequence kind",
            "gate_failures": ["B"],
            "b_hit": None,
            "confidence": 0.7,
            "needs_review": False,
        }

    return {
        "class": "universal",
        "decided_by": DECIDED_BY,
        "decided_at": datetime.now(UTC).isoformat(),
        "rationale": f"Gates A clean; {b_hit}",
        "gate_failures": [],
        "b_hit": b_hit,
        "confidence": confidence,
        "needs_review": needs_review,
    }


# ── Run ───────────────────────────────────────────────────────────────────────
def main():
    # Stats
    total = 0
    universal_count = 0
    project_count = 0
    needs_review_count = 0
    gate_fail_hist = Counter()
    b_hit_hist = Counter()
    conf_hist = Counter()
    bp_stats = {}

    # Truncate output
    with open(OUTPUT_PATH, "w") as out:
        for idx, dirname in enumerate(SHARD_DIRS, start=25):
            bp_path = os.path.join(SOURCES_DIR, dirname, "LATEST.jsonl")
            bp_stats[dirname] = {"total": 0, "universal": 0, "project": 0}

            if not os.path.exists(bp_path):
                print(f"  [SKIP] {dirname}: LATEST.jsonl not found")
                continue

            with open(bp_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        constraint = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    cls = classify(constraint)

                    # Write output row (keep original fields + _classification)
                    out_row = {
                        "id": constraint.get("id"),
                        "hash": constraint.get("hash"),
                        "core": constraint.get("core"),
                        "constraint_kind": constraint.get("constraint_kind"),
                        "applies_to": constraint.get("applies_to"),
                        "severity": constraint.get("severity"),
                        "source_blueprint": constraint.get("source_blueprint"),
                        "_classification": cls,
                    }
                    out.write(json.dumps(out_row, ensure_ascii=False) + "\n")

                    total += 1
                    bp_stats[dirname]["total"] += 1

                    if cls["class"] == "universal":
                        universal_count += 1
                        bp_stats[dirname]["universal"] += 1
                    else:
                        project_count += 1
                        bp_stats[dirname]["project"] += 1

                    if cls.get("needs_review"):
                        needs_review_count += 1

                    for gf in cls.get("gate_failures", []):
                        gate_fail_hist[gf] += 1

                    if cls.get("b_hit"):
                        # Normalize b_hit to just the gate+location key
                        bh = (
                            cls["b_hit"].split(":")[0] + ":" + cls["b_hit"].split(":")[1]
                            if ":" in cls["b_hit"]
                            else cls["b_hit"]
                        )
                        b_hit_hist[bh] += 1

                    conf_val = cls.get("confidence", 0)
                    conf_hist[f"{conf_val:.1f}"] += 1

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RUBRIC v5 SHARD 2 REPORT")
    print("=" * 70)
    print(f"BP indices:          25-49 ({len(SHARD_DIRS)} blueprints)")
    print(f"Total constraints:   {total}")
    print(f"Universal:           {universal_count}  ({100 * universal_count / max(total, 1):.1f}%)")
    print(f"Project-specific:    {project_count}   ({100 * project_count / max(total, 1):.1f}%)")
    print(f"Needs review:        {needs_review_count}")
    print()

    print("── Per-BP breakdown ──────────────────────────────────────────────")
    print(f"{'idx':>4}  {'BP dir':<40} {'total':>6} {'univ':>6} {'proj':>6}")
    for i, (d, s) in enumerate(bp_stats.items(), start=25):
        print(f"  {i:>2}  {d:<40} {s['total']:>6} {s['universal']:>6} {s['project']:>6}")
    print()

    print("── Gate failure histogram ────────────────────────────────────────")
    for gate, count in sorted(gate_fail_hist.items()):
        print(f"  {gate}: {count}")
    print()

    print("── B hit histogram ──────────────────────────────────────────────")
    for bh, count in sorted(b_hit_hist.items(), key=lambda x: -x[1]):
        print(f"  {bh}: {count}")
    print()

    print("── Confidence distribution ──────────────────────────────────────")
    for conf, count in sorted(conf_hist.items(), reverse=True):
        print(f"  {conf}: {count}")
    print()
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
