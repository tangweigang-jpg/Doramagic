"""Tests for EvaluatorPhase.parse_result — 11-point validation.

Uses fake_adapter (no real LLM calls). Tests the parse_result validation rules
defined in SOP §1.3 H/I/J/K/L and §2.4.
"""

from __future__ import annotations

import copy

import pytest
from doramagic_web_publisher.errors import PhaseParsingError
from doramagic_web_publisher.phases.evaluator import EvaluatorPhase
from doramagic_web_publisher.runtime.models import PhaseContext, PublishManifest

# ---- Fixtures ----

GOOD_ARGS = {
    "sample_output": {
        "format": "trace_url",
        "primary_url": "https://claude.ai/share/test-trace",
        "text_preview": None,
        "caption": "A股MACD回测策略全流程验证",
        "caption_en": "Full MACD backtest verified on A-shares",
    },
    "applicable_scenarios": [
        {
            "text": "散户想验证MACD策略可行性时",
            "text_en": "When retail investors want to validate MACD strategy",
        },
        {
            "text": "量化研究员对比多因子策略时",
            "text_en": "When quant researchers compare multi-factor strategies",
        },
    ],
    "inapplicable_scenarios": [
        {"text": "港股或美股量化回测场景", "text_en": "When backtesting on HK or US stock markets"},
        {
            "text": "高频交易或日内策略开发",
            "text_en": "For high-frequency or intraday strategy development",
        },
    ],
    "host_adapters": [
        {"host": "openclaw", "load_method": "SKILL 文件加载", "notes": None},
        {"host": "claude_code", "load_method": "CLAUDE.md 粘贴", "notes": None},
    ],
    "required_inputs": [],
    "creator_proof": [
        {
            "model": "MiniMax-M2.7-highspeed",
            "host": "claude_code",
            "evidence_type": "trace_url",
            "evidence_url": "https://claude.ai/stub-trace-for-bp-009",
            "tested_at": "2026-04-18",
            "summary": "骨架 vertical slice 自测占位，全流程跑通",
            "summary_en": "Scaffold vertical slice stub proof — full pipeline run through",
        }
    ],
    "model_compatibility": [
        {"model": "MiniMax-M2.7-highspeed", "status": "recommended", "note": None, "note_en": None},
    ],
    "tier": "standard",
    "is_flagship": True,
    "parent_flagship_slug": None,
    "presets": None,
    "core_keywords": [
        "用 Claude 做 A 股 MACD 回测需要什么？",
        "A 股量化回测 AI 配方推荐",
        "how to backtest MACD on a-shares with claude",
        "zvt macd crossover backtest recipe",
        "A 股金叉策略回测防坑指南",
    ],
    "meta_title_suffix": None,
    "og_image_fields": {
        "headline": "回测A股MACD金叉策略",
        "headline_en": "Backtest MACD Crossover on A-Shares",
        "stat_primary": "147 条防坑规则",
        "stat_primary_en": "147 pitfall rules covered",
        "stat_secondary": "27 条 FATAL · 12 处源码",
        "stat_secondary_en": "27 FATAL rules · 12 source files",
    },
}


@pytest.fixture
def phase():
    return EvaluatorPhase()


@pytest.fixture
def good_args():
    return copy.deepcopy(GOOD_ARGS)


@pytest.fixture
def sample_ctx():
    manifest = PublishManifest(
        slug="macd-backtest-a-shares",
        blueprint_id="finance-bp-009",
        blueprint_source="zvtvz/zvt",
        blueprint_commit="f971f00c2181bc7d7fb7987a7875d4ec5960881a",
    )
    return PhaseContext(
        manifest=manifest,
        seed_content="No placeholders here.",
        mock_mode=True,
    )


# ---- Tests ----


class TestTierValidation:
    def test_valid_standard_tier(self, phase, good_args, sample_ctx):
        result = phase.parse_result(good_args, ctx=sample_ctx)
        assert result.success is True
        assert result.fields["tier"] == "standard"

    def test_valid_verified_tier(self, phase, good_args, sample_ctx):
        good_args["tier"] = "verified"
        result = phase.parse_result(good_args, ctx=sample_ctx)
        assert result.success is True

    def test_battle_tested_rejected(self, phase, good_args, sample_ctx):
        good_args["tier"] = "battle_tested"
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "tier" in str(exc_info.value)


class TestFlagshipConsistency:
    def test_flagship_requires_null_parent(self, phase, good_args, sample_ctx):
        """is_flagship=true → parent_flagship_slug must be null."""
        good_args["is_flagship"] = True
        good_args["parent_flagship_slug"] = "some-parent-slug"
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "parent_flagship_slug" in str(exc_info.value)

    def test_non_flagship_requires_parent(self, phase, good_args, sample_ctx):
        """is_flagship=false → parent_flagship_slug must be non-empty."""
        good_args["is_flagship"] = False
        good_args["parent_flagship_slug"] = None
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "parent_flagship_slug" in str(exc_info.value)

    def test_non_flagship_with_parent_passes(self, phase, good_args, sample_ctx):
        good_args["is_flagship"] = False
        good_args["parent_flagship_slug"] = "some-flagship-slug"
        # Should not raise
        result = phase.parse_result(good_args, ctx=sample_ctx)
        assert result.success is True


class TestPresetsValidation:
    def test_presets_non_null_requires_flagship(self, phase, good_args, sample_ctx):
        """Presets non-null when is_flagship=false → error."""
        good_args["is_flagship"] = False
        good_args["parent_flagship_slug"] = "parent-slug"
        good_args["presets"] = [
            {
                "preset_slug": "test-preset",
                "name": "测试预设",
                "name_en": "Test Preset",
                "description": "描述",
                "description_en": "Description",
                "price_model": "free",
                "price_usd": None,
                "variable_overrides": {},
            }
        ]
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "presets" in str(exc_info.value)

    def test_preset_variable_override_must_be_in_required_inputs(
        self, phase, good_args, sample_ctx
    ):
        """preset.variable_overrides keys must be in required_inputs.name."""
        good_args["presets"] = [
            {
                "preset_slug": "test-preset",
                "name": "测试预设",
                "name_en": "Test Preset",
                "description": "描述",
                "description_en": "Description",
                "price_model": "free",
                "price_usd": None,
                "variable_overrides": {"unknown_var": "value"},
            }
        ]
        # required_inputs is empty, so unknown_var is invalid
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "unknown_var" in str(exc_info.value)


class TestScenariosValidation:
    def test_applicable_scenarios_too_few(self, phase, good_args, sample_ctx):
        good_args["applicable_scenarios"] = [
            {"text": "场景一很长一些好", "text_en": "Scenario one is long enough here"},
        ]
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "applicable_scenarios" in str(exc_info.value)

    def test_inapplicable_scenarios_too_many(self, phase, good_args, sample_ctx):
        scenario = {"text": "不适用场景测试用例数量", "text_en": "Inapplicable scenario test case"}
        good_args["inapplicable_scenarios"] = [scenario] * 7  # > 6
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "inapplicable_scenarios" in str(exc_info.value)


class TestCoreKeywordsValidation:
    def test_too_few_keywords(self, phase, good_args, sample_ctx):
        good_args["core_keywords"] = ["中文关键词一", "English keyword"]
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "core_keywords" in str(exc_info.value)

    def test_not_enough_chinese_keywords(self, phase, good_args, sample_ctx):
        good_args["core_keywords"] = [
            "only one Chinese 关键词",
            "english keyword 1",
            "english keyword 2",
            "english keyword 3",
            "english keyword 4",
        ]
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "Chinese" in str(exc_info.value)

    def test_not_enough_english_keywords(self, phase, good_args, sample_ctx):
        good_args["core_keywords"] = [
            "中文关键词一",
            "中文关键词二",
            "中文关键词三",
            "中文关键词四",
            "中文关键词五",
        ]
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "English" in str(exc_info.value)


class TestOgImageFields:
    def test_stat_fields_not_validated_by_evaluator(self, phase, good_args, sample_ctx):
        """stat_primary/stat_secondary injected by Assembler — Evaluator no longer validates them.

        This test documents the new behavior: Evaluator ignores stat fields even if absent/wrong.
        """
        # Remove stat fields — should NOT raise (they're injected by Assembler)
        good_args["og_image_fields"] = {
            "headline": "回测A股MACD金叉策略",
            "headline_en": "Backtest MACD Crossover on A-Shares",
        }
        result = phase.parse_result(good_args, ctx=sample_ctx)
        assert result.success is True

    def test_empty_headline_rejected(self, phase, good_args, sample_ctx):
        good_args["og_image_fields"]["headline"] = ""
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "headline" in str(exc_info.value)

    def test_empty_headline_en_rejected(self, phase, good_args, sample_ctx):
        good_args["og_image_fields"]["headline_en"] = ""
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "headline_en" in str(exc_info.value)


class TestPlaceholderAlignment:
    def test_empty_seed_empty_inputs_passes(self, phase, good_args, sample_ctx):
        """S_seed=∅ and required_inputs=[] should pass."""
        sample_ctx.seed_content = "No placeholders here."
        good_args["required_inputs"] = []
        result = phase.parse_result(good_args, ctx=sample_ctx)
        assert result.success is True

    def test_seed_has_placeholder_but_inputs_empty_fails(self, phase, good_args, sample_ctx):
        """seed.md has {{ticker}} but required_inputs=[] → alignment failure."""
        sample_ctx.seed_content = "Please enter your {{ticker}} symbol."
        good_args["required_inputs"] = []
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "USER-INPUTS-MATCH" in str(exc_info.value)
        assert "ticker" in str(exc_info.value)

    def test_inputs_has_extra_not_in_seed_fails(self, phase, good_args, sample_ctx):
        """required_inputs has extra name not in seed → alignment failure."""
        sample_ctx.seed_content = "No placeholders here."
        good_args["required_inputs"] = [
            {
                "name": "extra_var",
                "type": "string",
                "required": True,
                "default": None,
                "enum_options": None,
                "hint": "额外变量",
                "hint_en": "Extra variable",
                "example": None,
            }
        ]
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(good_args, ctx=sample_ctx)
        assert "USER-INPUTS-MATCH" in str(exc_info.value)


class TestGoodArgsPass:
    def test_all_valid_passes(self, phase, good_args, sample_ctx):
        """Full good args should pass all validation."""
        result = phase.parse_result(good_args, ctx=sample_ctx)
        assert result.success is True
        assert result.phase_name == "evaluator"
        assert "tier" in result.fields
        assert "core_keywords" in result.fields
