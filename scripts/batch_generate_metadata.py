#!/usr/bin/env python3
"""batch_generate_metadata.py — Generate batch-v1 bilingual metadata.

Generates structure-complete metadata for the 65 slugs that have a
Chinese description in descriptions_map.py but no locked entry in
skill_metadata.yaml.

Quality tier: `batch-v1` — passes spec §1 field completeness, but
likely needs human review for tagline creativity and English polish.
Markers embedded so future audits can find these entries.

Usage:
    python3 scripts/batch_generate_metadata.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from descriptions_map import FINAL_DESCRIPTIONS  # noqa: E402
from naming_map import FINAL_SLUG_MAP  # noqa: E402

LOCKED_SLUGS = {
    "a-stock-quant-lab",
    "qlib-ai-quant",
    "insurance-loss-reserving",
    "opensanctions-watchlist",
    "pyfolio-performance",
}

# Brand acronyms that should stay uppercase in English Title Case
BRAND_UPPER = {
    "zvt",
    "ccxt",
    "bsm",
    "gs",
    "ifrs9",
    "aml",
    "kyc",
    "pep",
    "abs",
    "lgd",
    "ml",
    "kg",
    "rl",
    "api",
    "sec",
    "ta",
    "qa",
    "pr",
    "cn",
    "us",
    "hk",
    "etl",
    "ws",
    "rest",
    "csv",
    "json",
    "bt",
    "vnpy",
    "czsc",
    "finrl",
    "xalpha",
    "qlib",
    "dbt",
    "tqsdk",
    "ecl",
    "xva",
    "cva",
    "dva",
    "fva",
}

# Pretty-case brand names (override CapitalCase)
BRAND_PRETTY = {
    "qlib": "Qlib",
    "finrl": "FinRL",
    "vnpy": "VnPy",
    "czsc": "CZSC",
    "xalpha": "xalpha",
    "pyfolio": "Pyfolio",
    "alphalens": "Alphalens",
    "openbb": "OpenBB",
    "arcticdb": "ArcticDB",
    "empyrical": "Empyrical",
    "backtrader": "Backtrader",
    "zipline": "Zipline",
    "rqalpha": "RQAlpha",
    "quantaxis": "QuantAxis",
    "vectorbt": "VectorBT",
    "lean": "LEAN",
    "financepy": "FinancePy",
    "quantlib": "QuantLib",
    "lifelines": "Lifelines",
    "arch": "ARCH",
    "darts": "Darts",
    "nautilus": "Nautilus",
    "hummingbot": "Hummingbot",
    "rotki": "Rotki",
    "ledger": "Ledger",
    "beancount": "Beancount",
    "fava": "Fava",
    "tensortrade": "TensorTrade",
    "finrobot": "FinRobot",
    "freqtrade": "Freqtrade",
    "talib": "TA-Lib",
    "edgar": "EDGAR",
    "pandas": "Pandas",
    "tqsdk": "TqSdk",
    "cryptofeed": "CryptoFeed",
    "easytrader": "EasyTrader",
    "akshare": "AkShare",
    "eastmoney": "Eastmoney",
    "riskfolio": "Riskfolio",
    "skorecard": "Skorecard",
    "absbox": "AbsBox",
    "chainladder": "ChainLadder",
}

DOMAIN_TAGS = ["doramagic-crystal", "finance"]

# Keyword → Level 3+4 tag mapping
TAG_HINTS = {
    # Quant / trading
    "quant": "quant",
    "backtest": "quant",
    "backtesting": "quant",
    "strategy": "quant",
    "trading": "trading",
    "回测": "quant",
    "量化": "quant",
    "策略": "quant",
    # Risk / credit
    "credit": "credit",
    "risk": "risk",
    "lgd": "credit",
    "违约": "credit",
    "信用": "credit",
    "风险": "risk",
    # Insurance / actuarial
    "insurance": "insurance",
    "actuarial": "actuarial",
    "ibnr": "insurance",
    "reserving": "insurance",
    "保险": "insurance",
    "精算": "actuarial",
    "准备金": "insurance",
    # Compliance
    "aml": "aml",
    "kyc": "kyc",
    "sanctions": "compliance",
    "制裁": "compliance",
    "合规": "compliance",
    "regtech": "compliance",
    # Data / analytics
    "data": "data",
    "timeseries": "timeseries",
    "dataframe": "data",
    "数据": "data",
    "时序": "timeseries",
    # Portfolio / analytics
    "portfolio": "portfolio",
    "performance": "analytics",
    "attribution": "analytics",
    "组合": "portfolio",
    "绩效": "analytics",
    # Markets
    "a-share": "a-share",
    "a 股": "a-share",
    "a股": "a-share",
    "crypto": "crypto",
    "加密货币": "crypto",
    "比特币": "crypto",
    # AI / ML
    "ml": "ml",
    "machine learning": "ml",
    "ai": "ai",
    "reinforcement": "rl",
    "rl": "rl",
    "神经": "ml",
    "机器学习": "ml",
    "深度学习": "ml",
    # Derivatives
    "derivatives": "derivatives",
    "option": "derivatives",
    "期权": "derivatives",
    "衍生品": "derivatives",
    "futures": "futures",
    "期货": "futures",
    # Accounting
    "accounting": "accounting",
    "ledger": "accounting",
    "记账": "accounting",
    "会计": "accounting",
}


def derive_name_en(slug: str) -> str:
    tokens = slug.split("-")
    out = []
    for t in tokens:
        if t in BRAND_PRETTY:
            out.append(BRAND_PRETTY[t])
        elif t.lower() in BRAND_UPPER:
            out.append(t.upper())
        elif t.isdigit() or re.match(r"^\d+$", t):
            out.append(t)
        else:
            out.append(t.capitalize())
    return " ".join(out)


_CHINESE_RE = re.compile(r"[一-鿿]")


def _first_sentence_cn(desc: str) -> str:
    # Split on Chinese 。 or English period; grab up to "触发场景" marker
    desc = desc.strip()
    # Cut at 触发场景 if present
    cut = desc.split("触发场景")[0].strip().rstrip("。.")
    # Take first sentence
    parts = re.split(r"[。.]", cut)
    first = parts[0].strip() if parts else cut
    return first[:110]  # Cap for tagline length


def _trim_description_cn(desc: str, max_len: int = 120) -> str:
    """Trim existing Chinese description to ≤max_len chars, preferring sentence boundaries."""
    desc = desc.replace("\n", " ").strip()
    # Remove 触发场景 tail
    head = desc.split("触发场景")[0].rstrip("。.").strip() + "。"
    if len(head) <= max_len:
        return head
    # Truncate on sentence boundary before max_len
    parts = re.split(r"([。.])", head)
    acc = ""
    for p in parts:
        if len(acc) + len(p) > max_len:
            break
        acc += p
    return acc or head[:max_len]


def _extract_triggers(desc: str) -> list[str]:
    """Extract 4-6 trigger phrases from '触发场景：(1)...(2)...(3)...' section."""
    triggers: list[str] = []
    m = re.search(r"触发场景[:：]\s*(.+)", desc, re.DOTALL)
    if not m:
        return []
    tail = m.group(1)
    # Split on (1)(2)(3)... markers
    scenarios = re.split(r"\(\d+\)|（\d+）", tail)
    for s in scenarios[1:6]:  # up to 5
        s = s.strip().rstrip("。.").strip()
        if not s:
            continue
        # Extract a short noun phrase: take first clause
        short = re.split(r"[，,；;。.]", s)[0].strip()
        short = short.replace("用户要", "").replace("用户希望", "").strip()
        if short and len(short) < 30:
            triggers.append(short)
    return triggers[:5]


def _derive_name_zh(slug: str, desc: str) -> str:
    """Pick a 4-8 字 Chinese name from the description."""
    desc = desc.strip()
    # Heuristic: first sentence's subject noun phrase
    cut = desc.split("触发场景")[0].strip()
    first = re.split(r"[，,。.：:]", cut)[0].strip()

    # If first phrase is ≤8 Chinese chars, use it
    zh_only = "".join(_CHINESE_RE.findall(first))
    if 3 <= len(zh_only) <= 8:
        return zh_only

    # Else, try to compose: extract 2-char action + 2-char object
    tokens = re.findall(r"[一-鿿]{2,8}", first)
    if tokens:
        # Pick shortest meaningful token
        tokens.sort(key=len)
        for t in tokens:
            if 3 <= len(t) <= 8:
                return t
        return tokens[0][:8]

    # Fallback: slug Title Case as is
    return derive_name_en(slug)


def _derive_tagline_en(name_en: str, triggers: list[str]) -> str:
    """Build a simple English tagline from name + first 2 triggers."""
    if not triggers:
        return f"{name_en}: domain-specific skill for quant finance workflows."
    # Translate Chinese triggers roughly via keyword mapping
    return (
        f"{name_en}: specialized toolkit for {len(triggers)}+ "
        "finance workflows covered in the triggers section."
    )


def _derive_description_en(name_en: str, desc_cn: str, triggers: list[str]) -> str:
    """Placeholder English description derived from slug + triggers count."""
    trig_count = len(triggers)
    # Infer domain from keywords
    domain = "finance analytics"
    for kw, _hint in [
        ("回测", "backtesting"),
        ("量化", "quant research"),
        ("信用", "credit risk"),
        ("保险", "insurance actuarial"),
        ("合规", "compliance screening"),
        ("期货", "futures trading"),
        ("期权", "options pricing"),
        ("制裁", "sanctions compliance"),
        ("crypto", "crypto trading"),
        ("加密", "crypto trading"),
        ("记账", "accounting"),
        ("会计", "accounting"),
        ("机器学习", "ML research"),
        ("factor", "factor research"),
        ("因子", "factor research"),
        ("绩效", "performance analytics"),
    ]:
        if kw in desc_cn or kw in name_en.lower():
            domain = domain if domain != "finance analytics" else f"{domain} + {kw}"
            domain = kw if domain == "finance analytics" else domain
            if domain != "finance analytics":
                break
    scenarios = f" Covers {trig_count}+ use cases." if trig_count > 0 else ""
    return f"{name_en} skill for {domain}.{scenarios} (batch-v1 draft, needs English review)"


def _derive_tags(slug: str, desc_cn: str) -> list[str]:
    tags = list(DOMAIN_TAGS)
    seen = set(tags)
    text = (slug + " " + desc_cn).lower()
    for kw, tag in TAG_HINTS.items():
        if kw.lower() in text and tag not in seen:
            tags.append(tag)
            seen.add(tag)
            if len(tags) >= 6:  # 1+2 + 2-4 extra
                break
    return tags


def generate_entry(slug: str, desc: str, bp_id: str) -> dict:
    name_en = derive_name_en(slug)
    name_zh = _derive_name_zh(slug, desc)
    triggers = _extract_triggers(desc)
    description_zh = _trim_description_cn(desc, 120)
    tagline_zh = _first_sentence_cn(desc) + "。"
    tagline_en = _derive_tagline_en(name_en, triggers)
    description_en = _derive_description_en(name_en, desc, triggers)
    tags = _derive_tags(slug, desc)

    return {
        "bp_id": bp_id,
        "generation_source": "batch-v1",
        "name_zh": name_zh,
        "name_en": name_en,
        "tagline_zh": tagline_zh,
        "tagline_en": tagline_en,
        "description_zh": description_zh,
        "description_en": description_en,
        "triggers": [*triggers, slug.replace("-", " ")],
        "tags": tags,
    }


def main() -> int:
    # Build reverse map: slug → bp_id
    slug_to_bp: dict[str, str] = {}
    for bp_dir, slug in FINAL_SLUG_MAP.items():
        bp_id = bp_dir.split("--", 1)[0]  # finance-bp-004
        slug_to_bp[slug] = bp_id

    entries: dict[str, dict] = {}
    for slug, desc in sorted(FINAL_DESCRIPTIONS.items()):
        if slug in LOCKED_SLUGS:
            continue
        bp_id = slug_to_bp.get(slug)
        if not bp_id:
            print(f"  ⚠ {slug}: no bp_id in naming_map, skipping")
            continue
        entries[slug] = generate_entry(slug, desc, bp_id)
        print(f"  ✓ {slug}")

    print(f"\nGenerated: {len(entries)} entries")

    # Load existing yaml, append new entries, write back
    meta_path = SCRIPTS_DIR / "skill_metadata.yaml"
    with meta_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Preserve locked ordering; append batch-v1 after
    locked_entries = {k: v for k, v in data["skills"].items() if k in LOCKED_SLUGS}
    data["skills"] = {**locked_entries, **entries}
    data["batch_v1_generated_at"] = "2026-04-23"

    # Write preserving Unicode
    with meta_path.open("w", encoding="utf-8") as f:
        f.write("---\n")
        f.write("# skill_metadata.yaml — Bilingual metadata for Doramagic skills\n")
        f.write("#\n")
        f.write("# 5 locked (CTO-authored, spec-compliant) + batch-v1 (script-derived).\n")
        f.write("# batch-v1 entries have `generation_source: batch-v1` marker and\n")
        f.write("# need human review for tagline creativity / English polish.\n")
        f.write("#\n")
        f.write("# Spec: docs/designs/2026-04-23-skill-naming-bilingual-spec.md\n")
        f.write("---\n")
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False, width=120)

    print(f"Wrote {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
