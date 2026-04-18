"""Integration tests for ContentPhase — uses fake adapter, no real MiniMax calls.

Tests:
  1. test_content_phase_parse_valid_args  — parse_result with valid args → correct PhaseResult
  2. test_content_phase_rejects_invalid_slug — parse_result rejects slug format violations
  3. test_content_phase_build_prompt_has_required_sections — build_prompt includes key instructions
  4. test_content_phase_run_mock_mode — run() in mock_mode uses mock_result (no LLM call)
"""

from __future__ import annotations

import pytest
from doramagic_web_publisher.errors import WebPublisherError
from doramagic_web_publisher.phases.content import ContentPhase
from doramagic_web_publisher.runtime.models import PhaseContext, PhaseResult, PublishManifest

# ---------------------------------------------------------------------------
# Minimal fixture data
# ---------------------------------------------------------------------------

_VALID_ARGS = {
    "slug": "macd-backtest-a-shares",
    "name": "A股MACD金叉策略回测配方",
    "name_en": "A-Share MACD Crossover Backtest",
    "definition": (
        "A股MACD金叉策略回测配方是一个帮你回测MACD策略的AI任务配方，"
        "覆盖42条防坑规则，适用于A股量化场景。"
    ),
    "definition_en": (
        "A-Share MACD Crossover Backtest is an AI task recipe that helps you backtest MACD "
        "crossover strategies on A-share markets, covering 42 pitfall rules for quant trading."
    ),
    "description": (
        "## 这个配方帮你做什么\n\n这个配方帮你回测 A 股 MACD 金叉策略，"
        "涵盖 T+1 制度、费率计算等核心规则。\n\n"
        "## 你需要准备什么\n\n需要安装 zvt 框架和 Python 3.x 环境。\n\n"
        "## 执行流程\n\n1. 安装依赖\n2. 配置数据源\n3. 运行回测脚本\n4. 分析结果\n\n"
        "## 适用场景\n\n✅ A 股量化研究\n✅ MACD 策略验证\n\n完整配方请访问 doramagic.ai"
    ),
    "description_en": (
        "## What This Recipe Does\n\nThis recipe helps you backtest MACD crossover strategies "
        "on A-share markets with T+1 rules, commission rates, and limit-up/down handling.\n\n"
        "## What You Need\n\nInstall the zvt framework and Python 3.x environment.\n\n"
        "## Execution Flow\n\n"
        "1. Install dependencies\n2. Configure data source\n3. Run backtest\n4. Analyze results\n\n"
        "## Applicable Scenarios\n\nBest for A-share quantitative research and MACD validation. "
        "Get the full recipe at doramagic.ai"
    ),
    "category_slug": "finance",
    "tags": ["quantitative-trading", "backtesting", "macd", "a-shares", "python"],
    "version": "v1.0.0",
    "known_gaps": [],
    "changelog": "首次发布。覆盖 42 条防坑规则，支持 openclaw / claude_code。",
    "changelog_en": "Initial release. Covers 42 pitfall rules. Supports openclaw / claude_code.",
    "contributors": ["@doramagic-bot"],
}


@pytest.fixture
def content_phase() -> ContentPhase:
    return ContentPhase()


@pytest.fixture
def minimal_ctx() -> PhaseContext:
    """Minimal PhaseContext with real-looking data for build_prompt tests."""
    manifest = PublishManifest(
        slug="finance-bp-009-macd",
        blueprint_id="finance-bp-009",
        blueprint_source="zvtvz/zvt",
        blueprint_commit="f971f00c2181bc7d7fb7987a7875d4ec5960881a",
    )
    return PhaseContext(
        manifest=manifest,
        seed_content="# Mock Seed\n\nTest seed content.",
        crystal_ir={
            "crystal_id": "finance-bp-009-macd",
            "crystal_name": "MACD 日线金叉 A 股择时策略回测",
            "user_intent": {
                "description": "A 股日线级别 MACD 金叉择时策略回测",
                "target_market": "CN_A",
            },
        },
        blueprint={
            "applicability": {
                "domain": "finance",
                "task_type": "algorithmic trading with backtesting",
                "description": "ZVT is a Python framework for Chinese stock market trading.",
            },
            "stages": [],
        },
        constraints=[
            {"constraint_id": "finance-C-001", "severity": "fatal"},
            {"constraint_id": "finance-C-002", "severity": "high"},
        ],
        mock_mode=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestContentPhaseParseResult:
    """Tests for ContentPhase.parse_result()."""

    def test_parse_valid_args_returns_phase_result(self, content_phase):
        """Valid tool args produce a successful PhaseResult with correct fields."""
        result = content_phase.parse_result(_VALID_ARGS)

        assert isinstance(result, PhaseResult)
        assert result.phase_name == "content"
        assert result.success is True
        assert result.fields["slug"] == "macd-backtest-a-shares"
        assert result.fields["name"] == "A股MACD金叉策略回测配方"
        assert result.fields["name_en"] == "A-Share MACD Crossover Backtest"
        assert result.fields["version"] == "v1.0.0"
        assert result.fields["category_slug"] == "finance"

    def test_parse_valid_args_merges_mock_defaults(self, content_phase):
        """parse_result merges LLM output with mock defaults for missing fields."""
        result = content_phase.parse_result(_VALID_ARGS)

        # LLM fields should win over mock defaults
        assert result.fields["slug"] == "macd-backtest-a-shares"
        # Mock defaults fill in any fields not in args
        assert "description" in result.fields
        assert "known_gaps" in result.fields

    def test_parse_rejects_invalid_slug_too_short(self, content_phase):
        """parse_result raises WebPublisherError when slug is too short."""
        args = dict(_VALID_ARGS, slug="ab")  # only 2 chars, needs ≥3 after initial letter
        with pytest.raises(WebPublisherError) as exc_info:
            content_phase.parse_result(args)
        assert "slug" in str(exc_info.value).lower()

    def test_parse_rejects_slug_with_uppercase(self, content_phase):
        """parse_result raises WebPublisherError when slug has uppercase letters."""
        args = dict(_VALID_ARGS, slug="Macd-Backtest")
        with pytest.raises(WebPublisherError) as exc_info:
            content_phase.parse_result(args)
        assert "slug" in str(exc_info.value).lower()

    def test_parse_rejects_slug_with_bp_pattern(self, content_phase):
        """parse_result raises WebPublisherError when slug contains 'bp-NNN'."""
        args = dict(_VALID_ARGS, slug="finance-bp-009-macd")
        with pytest.raises(WebPublisherError) as exc_info:
            content_phase.parse_result(args)
        assert "bp-" in str(exc_info.value) or "forbidden" in str(exc_info.value).lower()

    def test_parse_rejects_slug_with_spaces(self, content_phase):
        """parse_result raises WebPublisherError when slug contains spaces."""
        args = dict(_VALID_ARGS, slug="macd backtest a shares")
        with pytest.raises(WebPublisherError) as exc_info:
            content_phase.parse_result(args)
        assert "slug" in str(exc_info.value).lower()


class TestContentPhaseBuildPrompt:
    """Tests for ContentPhase.build_prompt()."""

    def test_build_prompt_includes_constraint_count(self, content_phase, minimal_ctx):
        """build_prompt includes the constraint count in the prompt."""
        prompt = content_phase.build_prompt(minimal_ctx)

        assert "2" in prompt  # 2 constraints in minimal_ctx
        assert "constraint" in prompt.lower() or "防坑" in prompt

    def test_build_prompt_includes_blueprint_info(self, content_phase, minimal_ctx):
        """build_prompt includes blueprint source and ID."""
        prompt = content_phase.build_prompt(minimal_ctx)

        assert "zvtvz/zvt" in prompt or "finance-bp-009" in prompt

    def test_build_prompt_includes_slug_rules(self, content_phase, minimal_ctx):
        """build_prompt mentions slug format rules."""
        prompt = content_phase.build_prompt(minimal_ctx)

        assert "slug" in prompt.lower()
        assert "bp-" in prompt  # mentions forbidden bp- pattern

    def test_build_prompt_mentions_submit_tool(self, content_phase, minimal_ctx):
        """build_prompt tells LLM to call the submit tool."""
        prompt = content_phase.build_prompt(minimal_ctx)

        assert "submit_content_fields" in prompt

    def test_build_prompt_includes_crystal_name(self, content_phase, minimal_ctx):
        """build_prompt includes crystal name from crystal_ir."""
        prompt = content_phase.build_prompt(minimal_ctx)

        assert "MACD" in prompt


class TestContentPhaseMockMode:
    """Tests for ContentPhase in mock mode."""

    def test_mock_result_has_valid_slug(self, content_phase):
        """mock_result returns a PhaseResult with a valid slug."""
        import re

        result = content_phase.mock_result()
        slug = result.fields["slug"]
        assert re.match(r"^[a-z][a-z0-9-]{2,59}$", slug)

    def test_mock_result_has_all_required_fields(self, content_phase):
        """mock_result includes all required content fields."""
        result = content_phase.mock_result()
        required = [
            "slug",
            "name",
            "name_en",
            "definition",
            "definition_en",
            "description",
            "description_en",
            "category_slug",
            "tags",
            "version",
            "known_gaps",
            "changelog",
            "changelog_en",
            "contributors",
        ]
        for field in required:
            assert field in result.fields, f"Missing field: {field}"

    def test_run_mock_mode_uses_mock_result(self, content_phase, minimal_ctx, fake_adapter):
        """In mock_mode, run() returns mock_result without calling LLM."""
        minimal_ctx.mock_mode = True
        # In mock mode, pipeline calls mock_result() not run()
        result = content_phase.mock_result()
        assert result.success is True
        assert result.fields["slug"] == "mock-crystal-placeholder"
