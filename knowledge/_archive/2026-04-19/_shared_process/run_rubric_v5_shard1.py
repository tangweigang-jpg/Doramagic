#!/usr/bin/env python3
"""
Rubric v5 classifier for finance blueprint constraints — Shard 1 (indices 0-24).
Deterministic gate-based classifier; no LLM calls.
"""

import json
import os
import re
from datetime import UTC, datetime

# ─── Constants ───────────────────────────────────────────────────────────────

DECIDED_BY = "sonnet_rubric_v5_shard1"
DECIDED_AT = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

SOURCE_BASE = "/Users/tangsir/Documents/openclaw/Doramagic/knowledge/sources/finance"
OUTPUT_PATH = os.path.join(SOURCE_BASE, "_shared/constraints_audit_v5_shard_1.jsonl")

# ─── Rubric Whitelists ─────────────────────────────────────────────────────────

# A.1: CamelCase whitelist (external libraries — do NOT fail on these)
# Rubric v5 explicit whitelist (exact words)
A1_CAMELCASE_WHITELIST = {
    # Rubric v5 explicit
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
    # Plural/variant forms of whitelisted words
    "DataFrames",
    "Timestamps",
    "Paths",
    "Decimals",
    # Third-party libraries (NOT blocked per rubric A.6 notes)
    "Plotly",
    "Dash",
    "Yfinance",
    "Ccxt",
    "Zipline",
    "Pyfolio",
    "Empyrical",
    "Alphalens",
    "Backtrader",
    "Vectorbt",
    "Quantlib",
    "Arch",
    "Mlfinlab",
    "Finrl",
    "Stockstats",
    "Talib",
    "Tushare",
    "Akshare",
    "Darts",
    "Cryptofeed",
    "Lifelines",
    "Tensortrade",
    "Chainladder",
    "Riskfolio",
    "Skorecard",
    "Transitionmatrix",
    "FinRL",
    "FinanceToolkit",
    # Common English words that appear in when/action descriptions
    # (verbs used as imperatives at sentence start, or common English nouns/adjectives)
    "When",
    "Use",
    "Verify",
    "Apply",
    "Assume",
    "Claim",
    "Implement",
    "Calculate",
    "Validate",
    "Set",
    "Execute",
    "Check",
    "Skip",
    "Maintain",
    "Include",
    "False",
    "True",
    "None",
    "Call",
    "Handle",
    "Enforce",
    "Present",
    "Provide",
    "Store",
    "Convert",
    "Create",
    "Filter",
    "Normalize",
    "Define",
    "Replace",
    "Map",
    "Change",
    "Select",
    "Assign",
    "Parse",
    "Raise",
    "Exclude",
    "Access",
    "Extract",
    "Process",
    "Allow",
    "Trigger",
    "Configure",
    "Write",
    "Run",
    "Start",
    "Open",
    "Only",
    "Assert",
    "Perform",
    "Specify",
    "Modify",
    "Initialize",
    "Remove",
    "Add",
    "Output",
    "Sort",
    "Form",
    "Compute",
    "Return",
    "Pass",
    "Do",
    "Index",
    "Rely",
    "Off",
    "Closed",
    "Generic",
    "Normal",
    "Position",
    "Security",
    "Rate",
    "Account",
    "Interest",
    "Company",
    "Credit",
    "Price",
    "Context",
    "Dataset",
    "Event",
    "Stage",
    "Finance",
    "Document",
    "Information",
    "Time",
    "White",
    "Person",
    "English",
    "Chinese",
    "China",
    "Python",
    "Basel",
    "Yahoo",
    "Monte",
    "Carlo",
    "Cholesky",
    "Brownian",
    "Vasicek",
    "Wilson",
    "Mack",
    "Smith",
    "Actuarial",
    "Explicitly",
    "Triangle",
    "Development",
    "Repayment",
    "Solvency",
    "Disbursement",
    "Initiated",
    # Additional English verbs used as imperatives in action sentences
    "Restructure",
    "Treat",
    "Preserve",
    "Update",
    "Read",
    "Support",
    "Detect",
    "Separate",
    "Accept",
    "Recognize",
    "Aggregate",
    "Bypass",
    "Load",
    "Require",
    "Derive",
    "Compare",
    "Respect",
    "Cache",
    "Demand",
    "Limit",
    "Match",
    "Retrieve",
    "Swap",
    "Enclose",
    "Encode",
    "Decode",
    "Ensure",
    "Avoid",
    "Enable",
    "Disable",
    "Expose",
    "Propagate",
    "Capture",
    "Inherit",
    "Override",
    "Register",
    "Serialize",
    "Deserialize",
    "Subscribe",
    "Publish",
    "Emit",
    "Log",
    "Monitor",
    "Retry",
    "Timeout",
    "Throttle",
    "Batch",
    "Stream",
    "Poll",
    "Push",
    "Pull",
    "Sync",
    "Dispatch",
    "Resolve",
    "Reject",
    "Cancel",
    "Abort",
    "Reset",
    "Flush",
    "Drain",
    "Wrap",
    "Unwrap",
    "Pack",
    "Unpack",
    "Compress",
    "Decompress",
    "Insert",
    "Delete",
    "Fetch",
    "Post",
    "Put",
    "Patch",
    "Sign",
    "Hash",
    "Encrypt",
    "Decrypt",
    "Authenticate",
    "Authorize",
    "Grant",
    "Revoke",
    "Deny",
    "Permit",
    "Collect",
    "Gather",
    "Merge",
    "Split",
    "Join",
    "Group",
    "Order",
    "Bind",
    "Link",
    "Connect",
    "Disconnect",
    "Route",
    "Forward",
    "Schedule",
    "Queue",
    "Dequeue",
    "Enqueue",
    "Stack",
    "Heap",
    "Freeze",
    "Unfreeze",
    "Lock",
    "Unlock",
    "Block",
    "Unblock",
    "Generate",
    "Produce",
    "Consume",
    "Transform",
    "Migrate",
    "Import",
    "Export",
    "Upload",
    "Download",
    "Backup",
    "Restore",
    "Sanitize",
    "Truncate",
    "Pad",
    "Trim",
    "Strip",
    "Bootstrap",
    "Install",
    "Deploy",
    "Release",
    "Rollback",
    "Rebuild",
    "Refresh",
    "Reload",
    "Restart",
    "Shutdown",
    "Toggle",
    "Switch",
    "Deselect",
    "Approve",
    "Review",
    "Submit",
    "Track",
    "Trace",
    "Debug",
    "Profile",
    "Benchmark",
    "Optimize",
    "Tune",
    "Scale",
    "Replicate",
    "Shard",
    "Report",
    "Notify",
    "Alert",
    "Warn",
    "Pause",
    "Resume",
    "Continue",
    "Stop",
    "Terminate",
    "Append",
    "Prepend",
    "Seek",
    "Close",
    "Tell",
    "Send",
    "Receive",
    "Reply",
    "Broadcast",
    "Render",
    "Display",
    "Show",
    "Hide",
    "Format",
    "Print",
    "Test",
    "Mock",
    "Stub",
    "Spy",
    "Describe",
    "Explain",
    "Comment",
    "Annotate",
    "Diff",
    "Rebase",
    "Commit",
    "Deprecate",
    "Archive",
    # Common English nouns/adjectives in constraint context
    "Docs",
    "Note",
    "Example",
    "Warning",
    "Caution",
    "Entity",
    "Bank",
    "Node",
    "Graph",
    "Edge",
    "Tree",
    "Type",
    "Kind",
    "Class",
    "Interface",
    "Abstract",
    "Key",
    "Value",
    "Pair",
    "Tuple",
    "Struct",
    "Union",
    "Header",
    "Body",
    "Footer",
    "Meta",
    "Base",
    "Public",
    "Private",
    "Protected",
    "Static",
    "Final",
    "Async",
    "Concurrent",
    "Parallel",
    "Serial",
    "Optional",
    "Required",
    "Default",
    "Custom",
    "Global",
    "Internal",
    "External",
    "Remote",
    "Local",
    "Cached",
    "Raw",
    "Parsed",
    "Formatted",
    "Encoded",
    "Decoded",
    "Valid",
    "Invalid",
    "Empty",
    "Null",
    "Undefined",
    "Active",
    "Inactive",
    "Pending",
    "Complete",
    "Failed",
    "Info",
    "Error",
    "Fatal",
    # Common single-word class-like words that are generic (not project-specific)
    "Result",
    "Mode",
    "Level",
    "Status",
    "State",
    "Date",
    "List",
    "Dict",
    "Model",
    "Manager",
    "Handler",
    "Client",
    "Server",
    "Config",
    "Request",
    "Response",
    "Exception",
    "Sequence",
    "Generator",
    "Iterator",
    "Protocol",
    "Schema",
    "Registry",
    "Database",
    "Record",
    "Field",
    "Column",
    "Table",
    "Query",
    "Session",
    "Connection",
    "Transaction",
    "Engine",
    "Backend",
    # Standard Python/programming exceptions and special values
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "AttributeError",
    "RuntimeError",
    "StopIteration",
    "NotImplementedError",
    "OverflowError",
    "FileNotFoundError",
    "PermissionError",
    "TimeoutError",
    "IOError",
    "BaseException",
    "UserWarning",
    # Math/statistics terms
    "Matrix",
    "Vector",
    "Scalar",
    "Tensor",
    "Distribution",
    "Function",
    "Parameter",
    "Variable",
    "Constant",
    # Financial/domain terms (common, not project-specific)
    "Loan",
    "Sharpe",
    "Ledger",
    "Alpaca",
    "Tradier",
    "Fava",
    "Numscript",
    "Formance",
    "Marquee",
    "Beancount",
    # Proper nouns: databases, products, technologies (not project class names)
    "PostgreSQL",
    "Github",
    "GitHub",
    "SQLite",
    "LevelDB",
    "Redis",
    "MongoDB",
    "MySQL",
    "Postgres",
    "Oracle",
    "Cassandra",
    "Linux",
    "Windows",
    "MacOS",
    "Ubuntu",
    "Docker",
    "Kubernetes",
    "Amazon",
    "Google",
    "Microsoft",
    "Apple",
    "Alibaba",
    # third-party tool/service names
    "BeautifulSoup",
    "OpenSanctions",
    # NaN/special values and common finance acronyms
    "NaN",
    "WoE",
    "VaR",
    "PnL",
    # Finance domain terms used as common English in constraint text
    "Backtest",
    "Kdata",
    # "AKShare" is project token (akshare blocked) but also proper noun variant
    # Keep it out - it SHOULD fail A.6 if akshare is blocked
    # Common Chinese surnames in finance researcher names
    "Yang",
    "Zhang",
    "Chen",
    "Wang",
    "Li",
    "Liu",
    # Finance domain terms (not project-specific)
    "Balance",
    "Accrual",
    "Product",
    "Assignment",
    "Portfolio",
    "Dividend",
    "Coupon",
    "Principal",
    "Premium",
    "Discount",
    "Settlement",
    "Clearing",
    "Custody",
    "Margin",
    "Collateral",
    "Hedge",
    "Option",
    "Future",
    "Bond",
    "Equity",
    "Asset",
    "Liability",
    "Capital",
    "Reserve",
    "Provision",
    "Charge",
    "Revenue",
    "Expense",
    "Income",
    "Loss",
    "Profit",
    "Risk",
    "Volatility",
    "Duration",
    "Convexity",
    "Sensitivity",
    "Spread",
    "Yield",
    "Curve",
    "Surface",
    "Smile",
    # Additional English verbs and common action words
    "Divide",
    "Multiply",
    "Subtract",
    "Increment",
    "Decrement",
    "Iterate",
    "Enumerate",
    "Traverse",
    "Visit",
    "Search",
    "Extend",
    "Clear",
    "Clone",
    "Copy",
    "Move",
    "Rename",
    "Listen",
    "Acquire",
    "Cast",
    "Coerce",
    "Escape",
    "Delay",
    "Wait",
    "Sleep",
    "Interrupt",
    "Fork",
    "Spawn",
    "Kill",
    "Mount",
    "Unmount",
    "Attach",
    "Detach",
    # Financial reporting / accounting domain terms
    "Impairment",
    "Amortization",
    "Depreciation",
    "Writeoff",
    "Reconciliation",
    "Consolidation",
    "Elimination",
    # Common nouns in finance/tech context
    "Tenor",
    "Maturity",
    "Expiry",
    "Notional",
    "Trade",
    "Strategy",
    "Universe",
    "Coverage",
    "Sector",
    "Industry",
    "Region",
    "Country",
    "Market",
    "Exchange",
    "Broker",
    "Dealer",
    "Custodian",
    "Customer",
    "User",
    "Admin",
    "Operator",
    "Statement",
    "Summary",
    "Version",
    "Build",
    "Config",
    # More English verbs used as imperatives in action sentences
    "Populate",
    "Integrate",
    "Amortize",
    "Depreciate",
    "Capitalize",
    "Indicate",
    "Determine",
    "Accumulate",
    "Distribute",
    "Allocate",
    "Estimate",
    "Approximate",
    "Interpolate",
    "Extrapolate",
    "Simulate",
    "Calibrate",
    "Fit",
    "Train",
    "Predict",
    "Forecast",
    "Classify",
    "Cluster",
    "Regress",
    "Minimize",
    "Maximize",
    "Finalize",
    "Persist",
    "Label",
    "Tag",
    "Flag",
    "Mark",
    "Highlight",
    "Expand",
    "Collapse",
    "Flatten",
    "Nest",
    "Reshape",
    "Pivot",
    "Chunk",
    "Partition",
    "Segment",
    "Slice",
    "Window",
    "Bucket",
    "Round",
    "Ceil",
    "Floor",
    "Clip",
    "Clamp",
    "Mask",
    "Drop",
    "Keep",
    "Retain",
    "Backward",
    "Backfill",
    "Forwardfill",
    "Standardize",
    "Center",
    "Winsorize",
    "Transpose",
    "Invert",
    "Negate",
    "Conjugate",
    "Measure",
    "Catch",
    "Throw",
    "Propagate",
    # More English nouns/adjectives
    "Coefficient",
    "Effective",
    "Input",
    "Penal",
    "Nominal",
    "Real",
    "Adjusted",
    "Normalized",
    "Rolling",
    "Trailing",
    "Leading",
    "Intraday",
    "Interday",
    "Monthly",
    "Weekly",
    "Daily",
    "Annual",
    "Primary",
    "Secondary",
    "Tertiary",
    "Absolute",
    "Relative",
    "Conditional",
    "Unconditional",
    "Linear",
    "Nonlinear",
    "Logarithmic",
    "Exponential",
    "Simple",
    "Compound",
    "Continuous",
    "Discrete",
    "Gross",
    "Net",
    "Clean",
    "Dirty",
    "Historical",
    "Realized",
    "Implied",
    "Expected",
    "Individual",
    "Systematic",
    "Idiosyncratic",
    "Upstream",
    "Downstream",
    "Midstream",
    "Third",
    "Weighted",
    "Unweighted",
    "Equal",
    "Long",
    "Short",
    "Neutral",
    "Beta",
    "Senior",
    "Junior",
    "Subordinated",
    "Secured",
    "Unsecured",
    # Financial accounting / actuarial terms
    "Mortality",
    "Morbidity",
    "Lapse",
    "Surrender",
    "Reinsurance",
    "Annuity",
    "Pension",
    "Endowment",
    "Whole",
    "Term",
    "Incurred",
    "Reported",
    "Unreported",
    "Ultimate",
    "Earned",
    "Written",
    "Unearned",
    "Incurred",
    # Geographic/proper name context
    "European",
    "American",
    "Asian",
    "African",
    "British",
    "German",
    "French",
    "Japanese",
    "International",
    "Domestic",
    "Local",
    # Technical standards
    "Ifrs",
    "Gaap",
    "Fasb",
}

# A.2: Whitelisted method/function names (do NOT fail on these)
A2_METHOD_WHITELIST = {
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

# A.4: Whitelisted snake_case names (do NOT fail on these)
A4_SNAKE_WHITELIST = {
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

# A.6: Blocked project-internal name tokens (case-insensitive, exact word for short ones)
A6_BLOCKED_TOKENS = [
    "zvt",
    "freqtrade",
    "rqalpha",
    "xalpha",
    "quantaxis",
    "vnpy",
    "tqsdk",
    "gs-quant",
    "wealthbot",
    "amlsim",
    "tradingagents",
    "findkg",
    "hummingbot",
    "openbb",
    "open_source_economic_model",
    "economic-dashboard",
    "insurance_python",
    "pyliferisk",
    "firesale_stresstest",
    "ifrs9",
    "openlgd",
    "finrl-meta",
    "edgar-crawler",
    "eastmoney",
    "joinquant",
    "jq",
    "sina",
    "daily_stock_analysis",
    "lending",
    "finrobot",
    "beancount",
    "ledger",
    "open-climate-investing",
    "opensanctions",
    "edgartools",
]
# Word-boundary tokens (short blocked tokens that might match in longer words)
# Note: "arch" is NOT blocked (it's in the third-party allowlist); only "em" needs word-boundary
A6_WORD_BOUNDARY_TOKENS = {"em"}

# B.1: Finance keywords for gate B.1
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

# B.3: consequence kinds
B3_KINDS = {"compliance", "false_claim", "financial_loss"}


# ─── Gate Functions ────────────────────────────────────────────────────────────


def extract_text_fields(core: dict) -> tuple[str, str, str]:
    """Extract (when, action, consequence_description)."""
    when = core.get("when", "") or ""
    action = core.get("action", "") or ""
    consequence = core.get("consequence", {}) or {}
    desc = consequence.get("description", "") or ""
    return when, action, desc


def check_a1_camelcase(text: str) -> list[str]:
    """Find CamelCase project class names not in whitelist.

    Two patterns fail A.1:
    1. Compound CamelCase (mixed-case, not all-caps): BaseFetcher, EntityEventRecorder
       — always project-specific unless in whitelist
    2. Single-word PascalCase (all lowercase after first char): Recorder, Factor, Trader
       — project-specific unless in A1_CAMELCASE_WHITELIST
    """
    violations = []

    # Pattern 1: Compound CamelCase — starts uppercase, has lowercase char, then another uppercase
    # This catches: DataReader, StorageBackend, BaseFetcher but NOT API, APIs, MUST, NOT
    # A compound CamelCase word must: start with uppercase, contain at least one lowercase, have another uppercase
    compound_pattern = re.compile(r"\b([A-Z][a-zA-Z]*)\b")
    for m in compound_pattern.findall(text):
        # Skip pure all-caps (acronyms like API, MUST, SQL, JSON, UTC)
        if m == m.upper():
            continue
        # Skip words where all chars except a trailing 's' are uppercase (e.g., APIs, SQLs, REITs)
        if m.endswith("s") and m[:-1] == m[:-1].upper():
            continue
        # Must have internal uppercase (real compound CamelCase)
        # e.g., DataReader: D-a-t-a-R (has uppercase after first char in non-first position)
        has_internal_upper = any(c.isupper() for c in m[1:])
        if not has_internal_upper:
            continue
        # Now it's compound CamelCase — check whitelist
        if m not in A1_CAMELCASE_WHITELIST:
            violations.append(m)

    # Pattern 2: Single-word PascalCase that is not whitelisted
    # e.g., Recorder, Factor, Trader, Mixin, Accumulator
    # These start uppercase, continue with 2+ lowercase chars, no internal uppercase
    single_pattern = re.compile(r"\b([A-Z][a-z]{2,})\b")
    for m in single_pattern.findall(text):
        if m not in A1_CAMELCASE_WHITELIST:
            violations.append(m)

    # Deduplicate preserving first occurrence order
    seen = set()
    result = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


def check_a2_methods(text: str) -> list[str]:
    """Find project-specific method calls (with trailing () pattern)."""
    # Pattern: word() — method call pattern
    pattern = re.compile(r"\b([a-z][a-z0-9_]*)\(\)")
    matches = pattern.findall(text)
    violations = []
    for m in matches:
        if m not in A2_METHOD_WHITELIST:
            violations.append(m + "()")
    return violations


def check_a3_paths(text: str) -> list[str]:
    """Find module/file paths or slash-separated paths."""
    violations = []
    # Module paths: word.word.word pattern (dotted)
    if re.search(r"\b[a-z][a-z0-9_]+\.[a-z][a-z0-9_]+\.[a-z]", text, re.IGNORECASE):
        violations.append("dotted_module_path")
    # File paths: contains .py or slash-separated: word/word
    if re.search(r"\b\w+\.py\b", text):
        violations.append("dotted_py_file")
    # Slash-connected terms (including Plotly/Dash prose — conservative)
    if re.search(r"\b\w+/\w+\b", text):
        violations.append("slash_path")
    return violations


def check_a4_snake_case(text: str) -> list[str]:
    """Find project-specific snake_case identifiers (≥2 tokens)."""
    # Pattern: two or more lowercase_word tokens joined by underscore
    pattern = re.compile(r"\b([a-z][a-z0-9]*_[a-z][a-z0-9_]*)\b")
    matches = pattern.findall(text)
    violations = []
    seen = set()
    for m in matches:
        if m not in A4_SNAKE_WHITELIST and m not in seen:
            seen.add(m)
            violations.append(m)
    return violations


def check_a5_magic_numbers(text: str) -> list[str]:
    """Find magic numbers in action text."""
    violations = []
    # Numeric percentages: 3%, 20%, -0.3%
    if re.search(r"-?\d+\.?\d*%", text):
        violations.append("numeric_percentage")
    # Decimal defaults: 0.8, 0.2, 1.5, -0.3, 0.001 (NOT standalone 0 or 1)
    # Match decimals with fractional part, or multi-digit integers that are specific values
    if re.search(r"\b-?(?:0\.\d+|[2-9]\d*\.\d+|1\.[1-9]\d*|\d{2,}\.\d+)\b", text):
        violations.append("decimal_default")
    # Parenthesized numeric tuples: (0.8, 0.2)
    if re.search(r"\(\s*-?\d+\.?\d*\s*,\s*-?\d+\.?\d*\s*\)", text):
        violations.append("numeric_tuple")
    # Time literals: 15 minutes, 72h (but not "5 samples")
    if re.search(
        r"\b\d+\s*(?:minute|minutes|hour|hours|second|seconds|ms|h|min)\b", text, re.IGNORECASE
    ):
        violations.append("time_literal")
    return violations


def check_a6_blocked_tokens(text: str) -> list[str]:
    """Find blocked project-internal tokens."""
    violations = []
    text_lower = text.lower()
    for token in A6_BLOCKED_TOKENS:
        if token in text_lower:
            violations.append(f"repo_token:{token}")
    for token in A6_WORD_BOUNDARY_TOKENS:
        if re.search(r"\b" + re.escape(token) + r"\b", text_lower):
            violations.append(f"repo_token:{token}")
    return violations


def check_b1_keywords(text: str) -> str | None:
    """Find first B.1 finance keyword hit. Case-insensitive."""
    text_lower = text.lower()
    for kw in B1_KEYWORDS:
        if kw.lower() in text_lower:
            return kw.lower()
    return None


# ─── Classification Logic ───────────────────────────────────────────────────


def classify(constraint: dict, source_bp: str) -> dict:
    """Apply rubric v5 to a single constraint. Returns output dict."""
    core = constraint.get("core", {})
    when, action, consequence_desc = extract_text_fields(core)
    consequence_kind = (core.get("consequence", {}) or {}).get("kind", "")

    # Texts for gate checks
    when_and_action = (when + " " + action).strip()

    gate_failures = []
    first_failure = None

    # ── Gate A ───────────────────────────────────────────────────────────────

    # A.1 — CamelCase check on when + action
    a1_viol = check_a1_camelcase(when_and_action)
    if a1_viol:
        gate_failures.append("A.1")
        if first_failure is None:
            first_failure = ("A.1", f'A.1 FAILS: CamelCase "{a1_viol[0]}" in when/action')

    # A.2 — Method calls
    if first_failure is None:
        a2_viol = check_a2_methods(when_and_action)
        if a2_viol:
            gate_failures.append("A.2")
            first_failure = (
                "A.2",
                f'A.2 FAILS: project-specific method "{a2_viol[0]}" in when/action',
            )

    # A.3 — Module/file paths
    if first_failure is None:
        a3_viol = check_a3_paths(when_and_action)
        if a3_viol:
            gate_failures.append("A.3")
            first_failure = ("A.3", "A.3 FAILS: slash/module path detected in when/action")

    # A.4 — snake_case names
    if first_failure is None:
        a4_viol = check_a4_snake_case(when_and_action)
        if a4_viol:
            gate_failures.append("A.4")
            first_failure = (
                "A.4",
                f'A.4 FAILS: project-specific snake_case "{a4_viol[0]}" in when/action',
            )

    # A.5 — Magic numbers in action only
    if first_failure is None:
        a5_viol = check_a5_magic_numbers(action)
        if a5_viol:
            gate_failures.append("A.5")
            first_failure = ("A.5", f'A.5 FAILS: magic number "{a5_viol[0]}" in action')

    # A.6 — Blocked tokens (skip if only in consequence.description)
    if first_failure is None:
        a6_in_when_action = check_a6_blocked_tokens(when_and_action)
        if a6_in_when_action:
            gate_failures.append("A.6")
            first_failure = ("A.6", f"A.6 FAILS: {a6_in_when_action[0]} in when/action")

    # ── If any gate A failed → PROJECT ───────────────────────────────────────
    if first_failure is not None:
        return _make_output(
            constraint,
            source_bp,
            cls="project_specific",
            rationale=first_failure[1],
            gate_failures=gate_failures[:1],  # first failure gate only per spec
            b_hit=None,
            confidence=1.0,
            needs_review=False,
        )

    # ── Gate B ────────────────────────────────────────────────────────────────
    # Gate A passed cleanly. Check B.1 and B.3.

    # B.1 check in action
    b1_in_action = check_b1_keywords(action)
    # B.1 check in when
    b1_in_when = check_b1_keywords(when)
    # B.1 check in consequence_desc
    b1_in_desc = check_b1_keywords(consequence_desc)

    # B.3 check
    b3_hit = consequence_kind in B3_KINDS

    b_hit = None
    confidence = 0.0
    needs_review = False

    if b1_in_action:
        b_hit = f"B.1:{b1_in_action}"
        confidence = 1.0
        needs_review = False
    elif b1_in_when:
        b_hit = f"B.1:{b1_in_when}"
        confidence = 0.9
        needs_review = False
    elif b3_hit:
        b_hit = f"B.3:{consequence_kind}"
        confidence = 0.9
        needs_review = False
    elif b1_in_desc:
        b_hit = f"B.1:{b1_in_desc}"
        confidence = 0.8
        needs_review = True

    if b_hit:
        if needs_review:
            rationale = f'Gate A passes cleanly; B.1 keyword: "{b_hit}" (keyword appears in consequence description, borderline)'
        elif b_hit.startswith("B.3:"):
            rationale = f'Gate A passes cleanly; B.3 hit on "{consequence_kind}"'
        else:
            rationale = f"Gate A passes cleanly; B.1 keyword hit in action/when: {b_hit}"
        return _make_output(
            constraint,
            source_bp,
            cls="universal",
            rationale=rationale,
            gate_failures=[],
            b_hit=b_hit,
            confidence=confidence,
            needs_review=needs_review,
        )
    else:
        # Neither B.1 nor B.3 matched → PROJECT
        return _make_output(
            constraint,
            source_bp,
            cls="project_specific",
            rationale=f'Gate A passes but no B match; kind="{consequence_kind}"',
            gate_failures=["B.all"],
            b_hit=None,
            confidence=1.0,
            needs_review=False,
        )


def _make_output(
    constraint: dict,
    source_bp: str,
    cls: str,
    rationale: str,
    gate_failures: list,
    b_hit,
    confidence: float,
    needs_review: bool,
) -> dict:
    """Build the output record in the schema specified by rubric v5."""
    return {
        "id": constraint.get("id"),
        "hash": constraint.get("hash"),
        "core": constraint.get("core"),
        "constraint_kind": constraint.get("constraint_kind"),
        "applies_to": constraint.get("applies_to"),
        "severity": constraint.get("severity"),
        "source_blueprint": source_bp,
        "_classification": {
            "class": cls,
            "decided_by": DECIDED_BY,
            "decided_at": DECIDED_AT,
            "rationale": rationale,
            "gate_failures": gate_failures,
            "b_hit": b_hit,
            "confidence": confidence,
            "needs_review": needs_review,
        },
    }


# ─── Main ──────────────────────────────────────────────────────────────────────


def main():
    # Get sorted list of BP directories (all finance-bp-*)
    dirs = sorted(
        [
            d
            for d in os.listdir(SOURCE_BASE)
            if d.startswith("finance-bp-") and os.path.isdir(os.path.join(SOURCE_BASE, d))
        ]
    )

    # Shard 1: indices 0-24
    shard_dirs = dirs[:25]
    print(f"Processing {len(shard_dirs)} BPs (indices 0-24):")
    for i, d in enumerate(shard_dirs):
        print(f"  [{i}] {d}")

    # Truncate output
    with open(OUTPUT_PATH, "w") as f:
        pass  # truncate

    total = 0
    universal_count = 0
    project_count = 0
    needs_review_count = 0
    gate_histogram = {}
    b_histogram = {}
    confidence_buckets = {1.0: 0, 0.9: 0, 0.8: 0, "<=0.7": 0}
    bp_stats = []

    for bp_dir in shard_dirs:
        latest_path = os.path.join(SOURCE_BASE, bp_dir, "LATEST.jsonl")
        if not os.path.exists(latest_path):
            print(f"  SKIP (no LATEST.jsonl): {bp_dir}")
            continue

        # Derive source_blueprint from directory name (e.g., finance-bp-004)
        bp_id = bp_dir.split("--")[0]  # "finance-bp-004"

        with open(latest_path) as f:
            lines = [l.strip() for l in f if l.strip()]

        bp_u = 0
        bp_p = 0
        outputs = []
        for line in lines:
            constraint = json.loads(line)
            out = classify(constraint, bp_id)
            outputs.append(out)
            cls = out["_classification"]["class"]
            if cls == "universal":
                universal_count += 1
                bp_u += 1
            else:
                project_count += 1
                bp_p += 1
            if out["_classification"]["needs_review"]:
                needs_review_count += 1
            gf = out["_classification"]["gate_failures"]
            for g in gf:
                gate_histogram[g] = gate_histogram.get(g, 0) + 1
            bh = out["_classification"]["b_hit"]
            if bh:
                b_histogram[bh] = b_histogram.get(bh, 0) + 1
            conf = out["_classification"]["confidence"]
            if conf == 1.0:
                confidence_buckets[1.0] += 1
            elif conf == 0.9:
                confidence_buckets[0.9] += 1
            elif conf == 0.8:
                confidence_buckets[0.8] += 1
            else:
                confidence_buckets["<=0.7"] += 1

        total += len(outputs)
        bp_stats.append((bp_dir, len(outputs), bp_u, bp_p))

        # Append to output
        with open(OUTPUT_PATH, "a") as f:
            for out in outputs:
                f.write(json.dumps(out, ensure_ascii=False) + "\n")

        print(f"  {bp_dir}: {len(outputs)} constraints → U={bp_u} P={bp_p}")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total} constraints")
    print(f"Universal: {universal_count} ({universal_count / total * 100:.1f}%)")
    print(f"Project:   {project_count} ({project_count / total * 100:.1f}%)")
    print(f"Needs review: {needs_review_count} ({needs_review_count / total * 100:.1f}%)")
    print(f"\nGate failure histogram: {dict(sorted(gate_histogram.items()))}")
    print(f"B hit histogram: {dict(sorted(b_histogram.items()))}")
    print(f"Confidence distribution: {confidence_buckets}")


if __name__ == "__main__":
    main()
