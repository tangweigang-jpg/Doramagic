"""测试词汇归一化和 canonical signature。"""

import sys
from pathlib import Path

from doramagic_judgment_schema.normalizer import compute_signature, normalize_text
from doramagic_judgment_schema.types import JudgmentScope, ScopeLevel

sys.path.insert(0, str(Path(__file__).parent))
from helpers import make_valid_judgment


class TestNormalizeText:
    def test_float_normalization(self) -> None:
        assert "binary_float" in normalize_text("使用 float 类型")
        assert "binary_float" in normalize_text("IEEE 754 double 精度")

    def test_trading_normalization(self) -> None:
        assert "live_trading" in normalize_text("实盘交易")
        assert "backtest" in normalize_text("回测系统")

    def test_case_insensitive(self) -> None:
        assert normalize_text("Float") == normalize_text("float")


class TestCanonicalSignature:
    def test_same_judgment_same_signature(self) -> None:
        j = make_valid_judgment()
        sig1 = compute_signature(j)
        sig2 = compute_signature(j)
        assert sig1.scope_sig == sig2.scope_sig
        assert sig1.rule_sig == sig2.rule_sig
        assert sig1.cause_sig == sig2.cause_sig

    def test_different_domain_different_scope_sig(self) -> None:
        j1 = make_valid_judgment()
        j2 = make_valid_judgment(
            scope=JudgmentScope(level=ScopeLevel.DOMAIN, domains=["healthcare"])
        )
        sig1 = compute_signature(j1)
        sig2 = compute_signature(j2)
        assert sig1.scope_sig != sig2.scope_sig
