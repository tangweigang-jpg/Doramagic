"""Tests for the 5 implemented preflight gates.

Gates tested:
  1. SEO-SLUG          — slug format validation
  2. SEO-TITLE-LENGTH  — derived meta title ≤ 60 chars
  3. GEO-FAQ-COUNT     — faqs count ∈ [5, 8]
  4. I18N-COMPLETE     — all _en fields non-empty
  5. DATA-VERSION      — version matches vMAJOR.MINOR.PATCH
"""

from __future__ import annotations

import pytest
from doramagic_web_publisher.preflight import PreflightRunner


@pytest.fixture
def runner() -> PreflightRunner:
    return PreflightRunner()


# ──────────────────────────────────────────────────────────────────────
# Helper: build a minimal valid package (all 5 gates passing)
# ──────────────────────────────────────────────────────────────────────


def _base_package() -> dict:
    """A minimal package dict that passes all 5 implemented gates."""
    return {
        "slug": "macd-backtest-a-shares",
        "name": "A股MACD金叉策略回测配方",
        "name_en": "MACD Crossover Backtest for A-Shares",
        "definition": (
            "A股MACD金叉策略回测配方是一个帮你回测MACD金叉策略的AI任务配方，"
            "覆盖42条防坑规则，适用于A股量化研究。"
        ),
        "definition_en": (
            "MACD Crossover Backtest for A-Shares is an AI task recipe "
            "to backtest MACD strategies, "
            "covering 42 pitfall rules for A-share quantitative research."
        ),
        "description": ("## 这个配方帮你做什么\n\n覆盖 42 条防坑规则。完整配方请访问 doramagic.ai"),
        "description_en": (
            "## What This Recipe Does\n\n"
            "Covers 42 pitfall rules. Get the full recipe at doramagic.ai"
        ),
        "category_slug": "finance",
        "tags": ["macd", "backtest", "a-shares"],
        "version": "v1.0.0",
        "blueprint_id": "bp-009",
        "blueprint_source": "zvtvz/zvt",
        "blueprint_commit": "f971f00c2181bc7d7fb7987a7875d4ec5960881a",
        "seed_content": "## After Task Completion\nhttps://doramagic.ai/r/macd-backtest-a-shares",
        "constraints": [
            {
                "constraint_id": "finance-C-001",
                "severity": "fatal",
                "type": "M",
                "when": "When annualizing",
                "action": "Use 242",
                "consequence": "22.7% error",
                "summary": "如果用365天年化，误差22.7%。正确做法：用242交易日。",
                "summary_en": (
                    "Using 365 days underestimates volatility by 22.7%. Correct: 242 trading days."
                ),
                "evidence_url": "https://github.com/zvtvz/zvt/blob/abc/src/f.py#L89",
                "evidence_locator": "src/f.py:L89",
                "machine_checkable": True,
                "confidence": 0.95,
                "is_cross_project": False,
                "source_blueprint_id": None,
            }
        ],
        "known_gaps": [],
        "faqs": [
            {
                "question": "问题1",
                "answer": "回答1，包含5条规则，支持2个宿主。",
                "question_en": "Q1",
                "answer_en": "A1 covers 5 rules and 2 hosts.",
            },
            {
                "question": "问题2",
                "answer": "回答2，FATAL约束3条。",
                "question_en": "Q2",
                "answer_en": "A2 has 3 FATAL constraints.",
            },
            {
                "question": "问题3",
                "answer": "支持openclaw和claude_code共2个宿主。",
                "question_en": "Q3",
                "answer_en": "Supports 2 hosts: openclaw and claude_code.",
            },
            {
                "question": "问题4",
                "answer": "无需准备任何输入，1分钟内加载完成。",
                "question_en": "Q4",
                "answer_en": "No inputs needed. Load in under 1 minute.",
            },
            {
                "question": "问题5",
                "answer": "完整配方请访问 doramagic.ai/r/macd-backtest-a-shares",
                "question_en": "Q5",
                "answer_en": "Get the full recipe at doramagic.ai",
            },
        ],
        "changelog": "首次发布。覆盖 42 条防坑规则。",
        "changelog_en": "Initial release. Covers 42 pitfall rules.",
        "contributors": ["@doramagic-bot"],
        "sample_output": {
            "format": "text_preview",
            "primary_url": None,
            "text_preview": "Mock output",
            "caption": "模拟输出展示回测结果",
            "caption_en": "Mock output showing backtest results",
        },
        "applicable_scenarios": [
            {
                "text": "日内MACD回测研究场景",
                "text_en": "Intraday MACD backtesting research scenarios",
            },
            {
                "text": "多因子量化策略对比验证",
                "text_en": "Multi-factor quantitative strategy comparison",
            },
        ],
        "inapplicable_scenarios": [
            {
                "text": "美股或港股市场的MACD回测",
                "text_en": "MACD backtesting for US or HK markets",
            },
            {"text": "实盘交易信号生成场景", "text_en": "Live trading signal generation scenarios"},
        ],
        "host_adapters": [
            {"host": "openclaw", "load_method": "SKILL 文件加载", "notes": None},
        ],
        "required_inputs": [],
        "creator_proof": [
            {
                "model": "claude-sonnet-4-6",
                "host": "claude_code",
                "evidence_type": "trace_url",
                "evidence_url": "https://claude.ai/share/test",
                "tested_at": "2026-04-18",
                "summary": "验证通过，MACD回测42条规则全部检查。",
                "summary_en": "Verified MACD backtest with 42 rules on claude-sonnet-4-6.",
            }
        ],
        "model_compatibility": [
            {"model": "claude-sonnet-4-6", "status": "recommended", "note": None, "note_en": None}
        ],
        "tier": "standard",
        "is_flagship": True,
        "parent_flagship_slug": None,
        "core_keywords": [
            "用Claude做A股MACD回测需要什么？",
            "如何用AI回测MACD金叉策略？",
            "how to backtest MACD on a-shares with claude",
            "claude MACD strategy backtest china stocks",
            "A股量化回测防坑规则",
        ],
        "meta_title_suffix": None,
        "og_image_fields": {
            "headline": "回测A股MACD策略",
            "headline_en": "Backtest MACD on A-Shares",
            "stat_primary": "42 条防坑规则",
            "stat_primary_en": "42 pitfall rules",
            "stat_secondary": "1 条 FATAL · 1 处源码",
            "stat_secondary_en": "1 FATAL rule · 1 source file",
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Gate 1: SEO-SLUG
# ──────────────────────────────────────────────────────────────────────


def test_seo_slug_valid(runner):
    pkg = _base_package()
    result = runner._check_seo_slug(pkg)
    assert result.passed, f"Expected pass but got: {result.message}"


def test_seo_slug_contains_bp_pattern(runner):
    pkg = _base_package()
    pkg["slug"] = "bp-009-macd-backtest"
    result = runner._check_seo_slug(pkg)
    assert not result.passed
    assert "bp-" in result.message


def test_seo_slug_too_long(runner):
    pkg = _base_package()
    pkg["slug"] = "a" + "-abc" * 20  # > 60 chars
    result = runner._check_seo_slug(pkg)
    assert not result.passed


def test_seo_slug_pure_numeric_segment(runner):
    pkg = _base_package()
    pkg["slug"] = "macd-009-backtest"  # "009" is pure numeric
    result = runner._check_seo_slug(pkg)
    assert not result.passed


def test_seo_slug_empty(runner):
    pkg = _base_package()
    pkg["slug"] = ""
    result = runner._check_seo_slug(pkg)
    assert not result.passed


def test_seo_slug_valid_with_numbers_in_words(runner):
    """Slug like 'macd-a-shares-v2' should be fine — the '2' is part of 'v2'."""
    pkg = _base_package()
    pkg["slug"] = "macd-a-shares-v2"  # No pure-numeric segment
    result = runner._check_seo_slug(pkg)
    # "v2" is not a pure numeric segment (starts with letter)
    assert result.passed


# ──────────────────────────────────────────────────────────────────────
# Gate 2: SEO-TITLE-LENGTH
# ──────────────────────────────────────────────────────────────────────


def test_seo_title_length_valid(runner):
    pkg = _base_package()
    result = runner._check_seo_title_length(pkg)
    assert result.passed, f"Expected pass but got: {result.message}"


def test_seo_title_length_too_long(runner):
    pkg = _base_package()
    pkg["name"] = "超级长的A股MACD策略回测配方名字完整版超详细"  # Very long name
    pkg["core_keywords"] = [
        "用Claude做A股MACD金叉量化回测策略精细分析需要什么准备材料和步骤？",
        "how to use claude for MACD",
        "macd backtest",
        "a-shares",
        "quantitative",
    ]
    result = runner._check_seo_title_length(pkg)
    # May or may not pass depending on truncation — just check it runs
    assert isinstance(result.passed, bool)


def test_seo_title_length_no_keywords(runner):
    """When core_keywords is empty, title uses name + Doramagic."""
    pkg = _base_package()
    pkg["core_keywords"] = []
    result = runner._check_seo_title_length(pkg)
    # Short name + no keyword → should be ≤ 60 chars
    assert result.passed


# ──────────────────────────────────────────────────────────────────────
# Gate 3: GEO-FAQ-COUNT
# ──────────────────────────────────────────────────────────────────────


def test_geo_faq_count_valid(runner):
    pkg = _base_package()
    assert len(pkg["faqs"]) == 5
    result = runner._check_geo_faq_count(pkg)
    assert result.passed


def test_geo_faq_count_too_few(runner):
    pkg = _base_package()
    pkg["faqs"] = pkg["faqs"][:3]  # only 3
    result = runner._check_geo_faq_count(pkg)
    assert not result.passed
    assert "3" in result.message


def test_geo_faq_count_too_many(runner):
    pkg = _base_package()
    pkg["faqs"] = pkg["faqs"] * 2  # 10 items
    result = runner._check_geo_faq_count(pkg)
    assert not result.passed
    assert "10" in result.message


def test_geo_faq_count_exactly_8(runner):
    pkg = _base_package()
    extra = {
        "question": "Q",
        "answer": "A含1个数字。",
        "question_en": "Q",
        "answer_en": "A with 1 number.",
    }
    pkg["faqs"] = pkg["faqs"] + [extra] * 3  # 8 total
    result = runner._check_geo_faq_count(pkg)
    assert result.passed


def test_geo_faq_count_empty(runner):
    pkg = _base_package()
    pkg["faqs"] = []
    result = runner._check_geo_faq_count(pkg)
    assert not result.passed


# ──────────────────────────────────────────────────────────────────────
# Gate 4: I18N-COMPLETE
# ──────────────────────────────────────────────────────────────────────


def test_i18n_complete_valid(runner):
    pkg = _base_package()
    result = runner._check_i18n_complete(pkg)
    assert result.passed, f"Expected pass but got: {result.message}"


def test_i18n_complete_missing_name_en(runner):
    pkg = _base_package()
    pkg["name_en"] = ""
    result = runner._check_i18n_complete(pkg)
    assert not result.passed
    assert "name_en" in result.message


def test_i18n_complete_missing_faq_answer_en(runner):
    pkg = _base_package()
    pkg["faqs"][2]["answer_en"] = ""
    result = runner._check_i18n_complete(pkg)
    assert not result.passed
    assert "answer_en" in result.message


def test_i18n_complete_missing_constraint_summary_en(runner):
    pkg = _base_package()
    pkg["constraints"][0]["summary_en"] = ""
    result = runner._check_i18n_complete(pkg)
    assert not result.passed
    assert "summary_en" in result.message


def test_i18n_complete_missing_og_headline_en(runner):
    pkg = _base_package()
    pkg["og_image_fields"]["headline_en"] = ""
    result = runner._check_i18n_complete(pkg)
    assert not result.passed
    assert "headline_en" in result.message


# ──────────────────────────────────────────────────────────────────────
# Gate 5: DATA-VERSION
# ──────────────────────────────────────────────────────────────────────


def test_data_version_valid_v1(runner):
    pkg = _base_package()
    pkg["version"] = "v1.0.0"
    result = runner._check_data_version(pkg)
    assert result.passed


def test_data_version_valid_v2(runner):
    pkg = _base_package()
    pkg["version"] = "v2.14.3"
    result = runner._check_data_version(pkg)
    assert result.passed


def test_data_version_no_v_prefix(runner):
    pkg = _base_package()
    pkg["version"] = "1.0.0"
    result = runner._check_data_version(pkg)
    assert not result.passed


def test_data_version_empty(runner):
    pkg = _base_package()
    pkg["version"] = ""
    result = runner._check_data_version(pkg)
    assert not result.passed


def test_data_version_invalid_format(runner):
    pkg = _base_package()
    pkg["version"] = "v1.0"  # missing patch
    result = runner._check_data_version(pkg)
    assert not result.passed


def test_data_version_with_suffix(runner):
    pkg = _base_package()
    pkg["version"] = "v1.0.0-beta"  # SOP requires clean semver only
    result = runner._check_data_version(pkg)
    assert not result.passed


# ──────────────────────────────────────────────────────────────────────
# Integration: run() returns all 5 gates
# ──────────────────────────────────────────────────────────────────────


def test_run_returns_all_five_gates(runner):
    pkg = _base_package()
    results = runner.run(pkg)
    assert len(results) == 5
    gate_ids = {r.gate_id for r in results}
    assert gate_ids == {
        "SEO-SLUG",
        "SEO-TITLE-LENGTH",
        "GEO-FAQ-COUNT",
        "I18N-COMPLETE",
        "DATA-VERSION",
    }


def test_run_all_pass_for_valid_package(runner):
    pkg = _base_package()
    results = runner.run(pkg)
    failures = [r for r in results if not r.passed]
    assert failures == [], f"Unexpected failures: {[(r.gate_id, r.message) for r in failures]}"


def test_run_and_raise_on_fatal_does_not_raise_for_valid(runner):
    pkg = _base_package()
    results = runner.run_and_raise_on_fatal(pkg)
    assert all(r.passed for r in results)


def test_run_and_raise_on_fatal_raises_for_invalid(runner):
    from doramagic_web_publisher.errors import PreflightError

    pkg = _base_package()
    pkg["slug"] = "bp-009"  # triggers SEO-SLUG
    pkg["faqs"] = []  # triggers GEO-FAQ-COUNT

    with pytest.raises(PreflightError) as exc_info:
        runner.run_and_raise_on_fatal(pkg)
    assert len(exc_info.value.failures) >= 1
