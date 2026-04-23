#!/usr/bin/env python3
"""publish_to_doramagic.py — Build Crystal Package JSON for Doramagic.ai API.

Reads skill_metadata.yaml + seed.yaml + hard-coded per-skill supplemental
data (FAQs, definition, blueprint provenance) and emits a JSON file that
conforms to the POST /api/publish/crystal contract.

Does NOT make the HTTP call — the JSON is saved to /tmp/{slug}.crystal.json
and the operator runs:
    curl -X POST https://doramagic.ai/api/publish/crystal \\
        -H "Authorization: Bearer $DORAMAGIC_PUBLISH_KEY" \\
        -H "Content-Type: application/json" \\
        -d @/tmp/{slug}.crystal.json

Usage:
    python3 scripts/publish_to_doramagic.py a-stock-quant-lab
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from naming_map import FINAL_SLUG_MAP  # noqa: E402

REPO_ROOT = SCRIPTS_DIR.parent
FINANCE_ROOT = REPO_ROOT / "knowledge" / "sources" / "finance"
METADATA_YAML = SCRIPTS_DIR / "skill_metadata.yaml"


# ─── Per-skill supplemental data ──────────────────────────────────────────────
# Only locked samples have hand-written entries; batch-v1 slugs fall back to
# defaults and need human review per-FAQ before publishing to Doramagic.ai.

SUPPLEMENTAL = {
    "a-stock-quant-lab": {
        "definition_zh": (
            "基于 zvt 框架的 A 股量化一站式实验室：覆盖数据采集、因子研究、"
            "回测执行 31 个典型场景，内置 47 条 anti-pattern 约束。仅限中国 A 股。"
        ),
        "definition_en": (
            "A-share quantitative research lab powered by the ZVT framework: "
            "data collection, factor research, and backtest execution across "
            "31 use cases, with 47 built-in anti-pattern guards. China A-share only."
        ),
        "description_zh": (
            "A 股量化实验室是基于 zvt（github.com/zvtvz/zvt）框架的一站式中国 A 股"
            "量化研究工具。从数据采集、因子研究到回测执行，全流程打通。覆盖 31 个典型"
            "用例：跟踪机构和基金持仓变动、批量采集上市公司财报、同步指数成分股"
            "（SZ1000/SZ2000 等），以及 MACD 金叉死叉、均线多头排列、量能突破等择时策略。"
            "\n\n"
            "支持数据源包括 eastmoney（免费）、joinquant（付费）、baostock（免费历史"
            "数据）、akshare（聚合）、qmt（券商接口）。框架原生支持 A 股、港股、数字"
            "货币，但美股数据质量一般不推荐。"
            "\n\n"
            "本 skill 自带 47 条 anti-pattern 约束，覆盖除权因子异常、Token 失效静默"
            "失败、API 限流吞噬异常等常见陷阱。宿主 AI（Claude Code / Cursor 等）装载"
            "后自动应用这些规则，避免生成常见错误代码。"
        ),
        "description_en": (
            "A-Share Quant Lab is a one-stop quantitative finance toolkit for China "
            "A-share markets, built on the ZVT framework (github.com/zvtvz/zvt). "
            "It covers the entire research pipeline: data collection, factor research, "
            "and backtest execution.\n\n"
            "Supports 31 common use cases: tracking institutional and fund holding "
            "changes, bulk collection of company financial statements, synchronizing "
            "index constituents (SZ1000/SZ2000, etc.), and timing strategies based on "
            "MACD golden/death cross, MA bullish alignment, and volume breakouts.\n\n"
            "Data sources include Eastmoney (free), JoinQuant (paid), Baostock (free "
            "historical data), AkShare (aggregated), and qmt (broker interface). "
            "Natively supports A-share, Hong Kong stocks, and cryptocurrencies; "
            "however, US stock data quality is mediocre and not recommended.\n\n"
            "This skill embeds 47 anti-pattern constraints covering common pitfalls "
            "such as adjustment factor anomalies, silent failures on expired API "
            "tokens, and exception swallowing under API rate limits. Host AIs (Claude "
            "Code, Cursor, etc.) automatically apply these rules after installation "
            "to prevent common code errors."
        ),
        "category_slug": "quant-finance",
        "tags": ["quant-finance", "zvt", "a-share"],
        "version": "v0.1.3",
        "blueprint_source": "zvtvz/zvt",
        "blueprint_commit": "f971f00c2181bc7d7fb7987a7875d4ec5960881a",
        "contributors": ["tangweigang-jpg"],
        "changelog_zh": (
            "v0.1.3: 首次发布到 Doramagic.ai。双语元数据 + 47 条 anti-pattern "
            "约束（均有 GitHub issue 来源）+ 3 条 FAQ。中国 A 股量化研究全流程覆盖。"
        ),
        "changelog_en": (
            "v0.1.3: Initial release on Doramagic.ai. Bilingual metadata, 47 "
            "anti-pattern constraints (each with GitHub issue provenance), and 3 "
            "FAQs. Full-pipeline coverage for China A-share quant research."
        ),
        "faqs": [
            {
                "question_zh": "这个 skill 适合什么用户？能做哪些任务？",
                "answer_zh": (
                    "适合做中国 A 股量化研究的工程师和研究员：基于 zvt 框架的数据采集、"
                    "因子研究、回测执行全流程。覆盖 31 个典型场景——机构持仓追踪、财报"
                    "采集、MACD/MA/量能择时等。访问 doramagic.ai/r/a-stock-quant-lab "
                    "查看完整用例和中英双语说明。"
                ),
                "question_en": "Who is this skill for, and what can it do?",
                "answer_en": (
                    "Built for engineers and researchers working on China A-share "
                    "quantitative finance, powered by the ZVT framework. Covers 31 "
                    "use cases including data collection, factor research, backtest "
                    "execution, institutional holdings tracking, and MACD/MA/volume "
                    "timing strategies. See doramagic.ai/r/a-stock-quant-lab for the "
                    "full catalog with bilingual documentation."
                ),
            },
            {
                "question_zh": "需要准备什么环境？数据源有要求吗？",
                "answer_zh": (
                    "Python 3.10+ 环境，zvt 框架（pip install zvt），数据源可选 "
                    "eastmoney（免费）或 joinquant（付费账号）、baostock、akshare 等。"
                    "首次运行 zvt 会在 ~/.zvt/ 创建本地数据目录。宿主 AI 读完 SKILL.md "
                    "后会指导完成环境初始化，不需要你提前配置。"
                ),
                "question_en": ("What environment and data sources does this skill require?"),
                "answer_en": (
                    "Python 3.10+ with the ZVT framework (pip install zvt). Data "
                    "sources include Eastmoney (free), JoinQuant (paid), Baostock, "
                    "and AkShare. On first run, ZVT creates a local data directory "
                    "at ~/.zvt/. The host AI guides you through environment setup "
                    "after reading SKILL.md — no manual prep required."
                ),
            },
            {
                "question_zh": "会踩哪些坑？这个 skill 怎么防护？",
                "answer_zh": (
                    "本 skill 内置 47 条 anti-pattern 约束，最典型的 3 个：(1) 除权"
                    "因子为 inf/NaN 时直接参与乘法导致复权静默失败；(2) Token 失效后"
                    "数据查询返回空 DataFrame 而非报错；(3) 第三方数据接口限流后异常"
                    "被吞噬，数据静默缺失。宿主 AI 装载后自动应用这些约束。"
                ),
                "question_en": ("What are the common pitfalls, and how does this skill guard?"),
                "answer_en": (
                    "This skill embeds 47 anti-pattern constraints. Top 3: (1) "
                    "adjustment factor as inf/NaN causing silent backfill failure "
                    "during multiplication; (2) expired API tokens returning empty "
                    "DataFrames instead of raising errors; (3) third-party rate "
                    "limit exceptions being silently swallowed, leading to missing "
                    "data. The host AI applies these constraints automatically."
                ),
            },
        ],
    },
}


def _load_metadata() -> dict:
    content = METADATA_YAML.read_text(encoding="utf-8")
    return yaml.safe_load(content.split("---\n", 2)[2])["skills"]


def _load_seed(slug: str) -> tuple[dict, str, Path]:
    """Return (seed_dict, seed_raw_text, path)."""
    # Reverse: slug → bp_dir_name
    for _bp_dir, mapped_slug in FINAL_SLUG_MAP.items():
        if mapped_slug == slug:
            bp_dir = _bp_dir
            break
    else:
        raise ValueError(f"slug not in naming_map: {slug}")
    bp_dir_path = FINANCE_ROOT / bp_dir
    # Prefer v6 seed
    seeds = sorted(bp_dir_path.glob("*v6*.seed.yaml"))
    if not seeds:
        seeds = sorted(bp_dir_path.glob("*.seed.yaml"))
    if not seeds:
        raise FileNotFoundError(f"no seed.yaml in {bp_dir_path}")
    seed_path = seeds[-1]
    raw = seed_path.read_text(encoding="utf-8")
    return yaml.safe_load(raw), raw, seed_path


def _build_constraints(seed: dict, blueprint_source: str, blueprint_commit: str) -> list[dict]:
    """Map seed anti_patterns + fatal constraints to API constraint schema."""
    out: list[dict] = []
    blob_url = f"https://github.com/{blueprint_source}/blob/{blueprint_commit}"

    # 1. Fatal domain constraints (from seed.constraints.fatal)
    fatal_list = (seed.get("constraints") or {}).get("fatal") or []
    for c in fatal_list:
        cid = c.get("id") or "finance-C-unknown"
        when = (c.get("when") or "").strip() or f"When working on {cid}"
        action = (c.get("action") or "").strip() or "follow domain rule"
        conseq = (c.get("consequence") or "").strip() or "undefined behavior"
        summary = f"{when} — {action}."
        out.append(
            {
                "constraint_id": cid,
                "severity": "fatal",
                "type": c.get("kind") or "domain_rule",
                "when": when,
                "action": action,
                "consequence": conseq,
                "summary": summary[:500],
                "summary_en": summary[:500],  # fatal constraints in seed are already English
                "evidence_url": f"{blob_url}/README.md",
                "evidence_locator": "domain-constraint",
                "machine_checkable": False,
                "confidence": 0.9,
            }
        )

    # 2. Anti-patterns (each with real GitHub issue URL as evidence)
    for ap in seed.get("anti_patterns") or []:
        cid = ap.get("id") or "AP-unknown"
        title = (ap.get("title") or "").strip()
        desc = (ap.get("description") or "").strip()
        # Title is Chinese, description is Chinese — use them as summary
        summary = f"{title}. {desc}"[:500] if title else desc[:500]
        when = f"When encountering scenario described by {cid}"
        action = "avoid this anti-pattern and follow the guarded approach"
        consequence = desc[:300] or "silent failure or incorrect result"
        # For summary_en, synthesize a brief English version
        summary_en = (
            f"Anti-pattern {cid}: {title[:100]}. Mitigation: follow the "
            f"guarded approach described in issue {ap.get('issue_link', '')}."
        )[:500]
        out.append(
            {
                "constraint_id": cid,
                "severity": "high",
                "type": "anti_pattern",
                "when": when,
                "action": action,
                "consequence": consequence,
                "summary": summary,
                "summary_en": summary_en,
                "evidence_url": ap.get("issue_link"),
                "evidence_locator": f"github-issue:{cid}",
                "machine_checkable": False,
                "confidence": 0.85,
            }
        )

    return out


def _inject_backflow(seed_text: str, slug: str) -> str:
    """Append backflow notice to seed_content per SAFE-BACKFLOW gate."""
    backflow = f"\n\n# Published by Doramagic\n# Full documentation: doramagic.ai/r/{slug}\n"
    if f"doramagic.ai/r/{slug}" in seed_text:
        return seed_text
    return seed_text + backflow


def build_package(slug: str) -> dict:
    if slug not in SUPPLEMENTAL:
        raise ValueError(
            f"No supplemental data for {slug}. Only locked samples with full "
            f"FAQs/definition are publishable. Add to SUPPLEMENTAL dict first."
        )
    supp = SUPPLEMENTAL[slug]

    metadata_all = _load_metadata()
    meta_entry = metadata_all.get(slug)
    if not meta_entry:
        raise ValueError(f"{slug} not in skill_metadata.yaml")

    seed, seed_raw, _seed_path = _load_seed(slug)

    constraints = _build_constraints(seed, supp["blueprint_source"], supp["blueprint_commit"])

    seed_content = _inject_backflow(seed_raw, slug)

    package = {
        "slug": slug,
        "name": meta_entry["name_zh"],
        "name_en": meta_entry["name_en"],
        "definition": supp["definition_zh"],
        "definition_en": supp["definition_en"],
        "description": supp["description_zh"],
        "description_en": supp["description_en"],
        "category_slug": supp["category_slug"],
        "tags": supp["tags"],
        "version": supp["version"],
        "blueprint_id": meta_entry["bp_id"],
        "blueprint_source": supp["blueprint_source"],
        "blueprint_commit": supp["blueprint_commit"],
        "seed_content": seed_content,
        "constraints": constraints,
        "known_gaps": [],
        "faqs": [
            {
                "question": f["question_zh"],
                "answer": f["answer_zh"],
                "question_en": f["question_en"],
                "answer_en": f["answer_en"],
            }
            for f in supp["faqs"]
        ],
        "changelog": supp["changelog_zh"],
        "changelog_en": supp["changelog_en"],
        "contributors": supp["contributors"],
    }
    return package


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("slug")
    p.add_argument("--out", type=Path, default=None, help="Output JSON path")
    args = p.parse_args()

    pkg = build_package(args.slug)
    out_path = args.out or Path(f"/tmp/{args.slug}.crystal.json")
    out_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print quick stats
    print(f"Wrote {out_path}")
    print(f"  constraints: {len(pkg['constraints'])}")
    print(f"  faqs: {len(pkg['faqs'])}")
    print(f"  seed_content: {len(pkg['seed_content']):,} chars")
    print(f"  description_zh: {len(pkg['description'])} chars")
    print(f"  description_en: {len(pkg['description_en'])} chars")
    print(f"  definition_zh: {len(pkg['definition'])} chars")
    print(f"  definition_en: {len(pkg['definition_en'])} chars")
    print()
    print("Publish with:")
    print("    curl -X POST https://doramagic.ai/api/publish/crystal \\")
    print('      -H "Authorization: Bearer $DORAMAGIC_PUBLISH_KEY" \\')
    print('      -H "Content-Type: application/json" \\')
    print(f"      -d @{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
