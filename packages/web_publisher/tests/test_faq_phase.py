"""Tests for FaqPhase — FAQ count, Chinese/English length limits, CTA presence.

Uses fake_adapter (no real LLM calls). Tests parse_result validation.
"""

from __future__ import annotations

import copy

import pytest
from doramagic_web_publisher.errors import PhaseParsingError
from doramagic_web_publisher.phases.faq import FaqPhase, _classify_faq

# ---- Fixtures ----

GOOD_FAQ = {
    "question": "这个配方能帮我做什么？",
    "answer": (
        "这个配方帮你在 A 股市场回测 MACD 金叉策略，覆盖 147 条防坑规则，"
        "避免 T+1 延迟和印花税费率等常见陷阱。"
    ),
    "question_en": "What can this recipe do for me?",
    "answer_en": (
        "This recipe helps you backtest MACD crossover strategies on A-share markets, "
        "covering 147 pitfall rules to avoid T+1 delays, stamp tax errors, "
        "and volatility calculation mistakes."
    ),
}

GOOD_FAQ_2 = {
    "question": "使用时有哪些常见失败？",
    "answer": "最常见的错误是用 365 天年化 A 股波动率，正确应用 242 交易日，否则低估约 22.7%。",
    "question_en": "What are the common failure modes?",
    "answer_en": (
        "The most common failure is using 365 days instead of 242 trading days "
        "when annualizing volatility for A-shares, causing a 22.7% underestimation."
    ),
}

GOOD_FAQ_3 = {
    "question": "这个配方支持哪些 AI 环境？",
    "answer": "支持 openclaw 和 claude_code，两个宿主均已通过官方自测，加载时间不超过 1 分钟。",
    "question_en": "Which AI environments does this recipe support?",
    "answer_en": (
        "Supports openclaw and claude_code. Both have been officially verified "
        "and load in under 1 minute."
    ),
}

GOOD_FAQ_4 = {
    "question": "使用这个配方需要准备什么？",
    "answer": "无需额外输入，直接加载配方文件即可。seed.md 约 14KB，下载后 1 分钟内即可开始使用。",
    "question_en": "What do I need to use this recipe?",
    "answer_en": (
        "No additional inputs required. Load the recipe file directly. "
        "The seed.md is approximately 14KB and ready to use in under 1 minute."
    ),
}

CTA_FAQ = {
    "question": "如何获取完整配方？",
    "answer": (
        "完整配方请访问 doramagic.ai/r/macd-backtest-a-shares，"
        "下载 seed.md 文件并在 1 分钟内加载到 claude_code。"
    ),
    "question_en": "How do I get the full recipe?",
    "answer_en": (
        "Get the full recipe at doramagic.ai/r/macd-backtest-a-shares. "
        "Download seed.md and load it into claude_code in under 1 minute."
    ),
}


@pytest.fixture
def phase():
    return FaqPhase()


@pytest.fixture
def good_faqs():
    return [
        copy.deepcopy(GOOD_FAQ),
        copy.deepcopy(GOOD_FAQ_2),
        copy.deepcopy(GOOD_FAQ_3),
        copy.deepcopy(GOOD_FAQ_4),
        copy.deepcopy(CTA_FAQ),
    ]


# ---- Tests ----


class TestFaqCount:
    def test_five_faqs_pass(self, phase, good_faqs):
        result = phase.parse_result({"faqs": good_faqs})
        assert result.success is True

    def test_eight_faqs_pass(self, phase, good_faqs):
        """8 FAQs should pass (maximum allowed)."""
        extra_faqs = [copy.deepcopy(GOOD_FAQ)] * 3
        # Adjust to avoid duplicates causing length issues
        for i, f in enumerate(extra_faqs):
            f["question"] = f"问题 {i + 6}？"
            f["question_en"] = f"Question {i + 6}?"
        all_faqs = good_faqs + extra_faqs
        result = phase.parse_result({"faqs": all_faqs[:8]})
        assert result.success is True

    def test_four_faqs_fail(self, phase, good_faqs):
        """4 FAQs is below minimum (5)."""
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": good_faqs[:4]})
        assert "5-8" in str(exc_info.value) or "5" in str(exc_info.value)

    def test_nine_faqs_fail(self, phase, good_faqs):
        """9 FAQs exceeds maximum (8)."""
        extra = copy.deepcopy(GOOD_FAQ)
        extra["question"] = "第九个问题？"
        extra["question_en"] = "Question nine?"
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": good_faqs + [extra] * 4})
        assert "8" in str(exc_info.value) or "5-8" in str(exc_info.value)


class TestAnswerLength:
    def test_chinese_answer_too_short_fails(self, phase, good_faqs):
        """Chinese answer < 30 chars fails."""
        good_faqs[0]["answer"] = "太短了，不够30字。"  # < 30 chars
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": good_faqs})
        assert "answer" in str(exc_info.value)

    def test_chinese_answer_too_long_fails(self, phase, good_faqs):
        """Chinese answer > 200 chars fails."""
        good_faqs[0]["answer"] = "这是一段非常长的中文回答，" * 20  # >> 200 chars
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": good_faqs})
        assert "answer" in str(exc_info.value)

    def test_english_answer_too_short_fails(self, phase, good_faqs):
        """English answer_en < 50 chars fails."""
        good_faqs[0]["answer_en"] = "Too short."  # 10 chars
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": good_faqs})
        assert "answer_en" in str(exc_info.value)

    def test_english_answer_too_long_fails(self, phase, good_faqs):
        """English answer_en > 400 chars fails."""
        good_faqs[0]["answer_en"] = "x" * 401
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": good_faqs})
        assert "answer_en" in str(exc_info.value)


class TestCtaPresence:
    def test_no_cta_fails(self, phase, good_faqs):
        """At least 1 answer must contain 'doramagic.ai'."""
        # Remove CTA from all faqs
        for f in good_faqs:
            f["answer"] = f["answer"].replace("doramagic.ai", "REMOVED")
            f["answer_en"] = f["answer_en"].replace("doramagic.ai", "REMOVED")
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": good_faqs})
        assert "doramagic.ai" in str(exc_info.value) or "GEO-FAQ-CTA" in str(exc_info.value)

    def test_cta_in_english_only_passes(self, phase, good_faqs):
        """CTA in answer_en alone satisfies the rule."""
        # Remove from all Chinese answers, keep in last English
        for f in good_faqs[:-1]:
            f["answer"] = f["answer"].replace("doramagic.ai", "example.com")
            f["answer_en"] = f["answer_en"].replace("doramagic.ai", "example.com")
        # Last FAQ keeps doramagic.ai in answer_en
        result = phase.parse_result({"faqs": good_faqs})
        assert result.success is True


class TestMockResult:
    def test_mock_result_passes_parse(self, phase):
        """mock_result should pass parse_result validation."""
        mock = phase.mock_result()
        result = phase.parse_result(mock.fields)
        assert result.success is True
        assert len(result.fields["faqs"]) >= 5

    def test_mock_result_has_cta(self, phase):
        """mock_result must have at least 1 FAQ with doramagic.ai."""
        mock = phase.mock_result()
        faqs = mock.fields["faqs"]
        has_cta = any(
            "doramagic.ai" in (f.get("answer", "") or "")
            or "doramagic.ai" in (f.get("answer_en", "") or "")
            for f in faqs
        )
        assert has_cta


# ---- Variety Tests (Fix #2) ----


def _make_faq(question: str, answer: str, cta: bool = False) -> dict:
    """Helper to build a FAQ dict with minimal valid fields."""
    suffix = " doramagic.ai/r/test" if cta else ""
    return {
        "question": question,
        "answer": answer + suffix,
        "question_en": "English question placeholder for length purposes?",
        "answer_en": (
            "English answer placeholder covering at minimum fifty characters total."
            + (" Visit doramagic.ai/r/test for more." if cta else "")
        ),
    }


class TestFaqVarietyCoverage:
    """Tests for GEO-FAQ-VARIETY: 5-category coverage gate (Fix #2)."""

    def test_faq_variety_all_5_categories_pass(self, phase):
        """test_faq_variety_all_5_categories_pass: 5 categories covered → passes."""
        faqs = [
            _make_faq(
                "这个配方能帮我做什么？",
                "帮你做A股MACD金叉回测，覆盖50条防坑规则，避免T+1延迟陷阱。",
            ),  # core
            _make_faq(
                "使用时有哪些常见失败？",
                "最常见错误是波动率计算用365天，正确应用242交易日，否则低估22.7%。",
            ),  # pitfall
            _make_faq(
                "这个配方支持哪些 AI 环境？",
                "支持 openclaw 和 claude_code 两个宿主，均已通过官方自测。",
            ),  # host
            _make_faq(
                "使用这个配方需要准备什么？",
                "需要准备A股股票代码和回测日期范围，无需其他额外输入参数即可运行。",
            ),  # inputs
            _make_faq(
                "如何获取完整配方？",
                "访问网站即可下载完整版seed.md文件，1分钟内加载完成。",
                cta=True,
            ),  # domain (CTA)
        ]
        result = phase.parse_result({"faqs": faqs})
        assert result.success is True

    def test_faq_variety_4_categories_pass(self, phase):
        """test_faq_variety_4_categories_pass: 4 categories covered → passes."""
        # core, pitfall, host, domain (no inputs) → 4 categories
        faqs = [
            _make_faq(
                "这个配方能帮我做什么？",
                "帮你做A股MACD金叉回测，覆盖50条防坑规则，避免T+1延迟陷阱。",
            ),  # core
            _make_faq(
                "使用时有哪些常见失败？",
                "最常见错误是波动率计算用365天，正确应用242交易日，否则低估22.7%。",
            ),  # pitfall
            _make_faq(
                "这个配方支持哪些 AI 环境？",
                "支持 openclaw 和 claude_code 两个宿主，均已通过官方自测。",
            ),  # host
            _make_faq(
                "A股量化回测有哪些特殊规定？",
                "A股T+1制度和印花税费率需要特别处理，否则回测结果会有明显偏差。",
            ),  # domain
            _make_faq(
                "如何获取完整配方？",
                "访问网站即可下载完整版seed.md文件，1分钟内加载完成。",
                cta=True,
            ),  # domain
        ]
        result = phase.parse_result({"faqs": faqs})
        assert result.success is True

    def test_faq_variety_only_3_categories_fail(self, phase):
        """test_faq_variety_only_3_categories_fail: only 3 categories → PhaseParsingError."""
        # Only core + pitfall + domain (missing host and inputs) → 3 categories
        faqs = [
            _make_faq(
                "这个配方能帮我做什么？",
                "帮你做A股MACD金叉回测，覆盖50条防坑规则，完全避免T+1延迟陷阱。",
            ),  # core
            _make_faq(
                "这个配方还能帮我做什么具体的？",
                "还能帮你规避常见的量化回测错误，有效提升策略可靠性约30%。",
            ),  # core again
            _make_faq(
                "使用时有哪些常见失败？",
                "最常见错误是波动率计算用365天，正确应用242交易日，否则低估22.7%。",
            ),  # pitfall
            _make_faq(
                "A股量化回测有哪些特殊规定和注意事项？",
                "A股T+1制度要求持仓次日才能卖出，必须纳入回测逻辑中正确处理。",
            ),  # domain
            _make_faq(
                "如何获取完整配方？",
                "访问网站即可下载完整版seed.md文件，1分钟内加载完成。",
                cta=True,
            ),  # domain
        ]
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"faqs": faqs})
        error_str = str(exc_info.value)
        assert "GEO-FAQ-VARIETY" in error_str
        assert "3" in error_str

    def test_classify_faq_core_category(self):
        """_classify_faq correctly identifies core capability questions."""
        category = _classify_faq("这个配方能帮我做什么？", "帮你做A股回测。")
        assert category == "core"

    def test_classify_faq_pitfall_category(self):
        """_classify_faq correctly identifies pitfall questions."""
        category = _classify_faq("使用时有哪些常见失败？", "避免常见错误。")
        assert category == "pitfall"

    def test_classify_faq_host_category(self):
        """_classify_faq correctly identifies host/scope questions."""
        category = _classify_faq("这个配方支持哪些 AI 环境？", "支持 openclaw。")
        assert category == "host"

    def test_classify_faq_inputs_category(self):
        """_classify_faq correctly identifies input requirement questions."""
        category = _classify_faq("使用这个配方需要准备什么？", "需要准备股票代码。")
        assert category == "inputs"

    def test_classify_faq_domain_fallback(self):
        """_classify_faq falls back to 'domain' for unrecognized questions."""
        category = _classify_faq("如何获取完整配方？", "访问网站。")
        assert category == "domain"
