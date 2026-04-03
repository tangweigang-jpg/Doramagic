"""测试判断质量校验器。"""

import sys
from pathlib import Path

from doramagic_judgment_schema.types import (
    ConsensusLevel,
    Consequence,
    ConsequenceKind,
    JudgmentConfidence,
    JudgmentCore,
    JudgmentScope,
    Modality,
    ScopeLevel,
    SourceLevel,
)
from doramagic_judgment_schema.validators import validate_judgment

sys.path.insert(0, str(Path(__file__).parent))
from helpers import make_valid_judgment


class TestValidateJudgment:
    def test_valid_judgment_passes(self) -> None:
        j = make_valid_judgment()
        result = validate_judgment(j)
        assert result.valid is True
        assert result.errors == []

    def test_vague_action_rejected(self) -> None:
        """action 中包含模糊词应产出错误。"""
        j = make_valid_judgment(
            core=JudgmentCore(
                when="使用浮点数时需要特别关注",
                modality=Modality.SHOULD,
                action="注意精度问题可能导致的偏差",
                consequence=Consequence(
                    kind=ConsequenceKind.BUG,
                    description="精度偏差导致计算错误的结果",
                ),
            )
        )
        result = validate_judgment(j)
        assert result.valid is False
        assert any("模糊词" in e for e in result.errors)

    def test_missing_evidence_rejected(self) -> None:
        """非 S4_reasoning 来源缺少 evidence_refs 应产出错误。"""
        j = make_valid_judgment(
            confidence=JudgmentConfidence(
                source=SourceLevel.S3_COMMUNITY,
                score=0.8,
                consensus=ConsensusLevel.STRONG,
                evidence_refs=[],
            )
        )
        result = validate_judgment(j)
        assert result.valid is False
        assert any("evidence_refs" in e for e in result.errors)

    def test_s4_reasoning_high_score_warned(self) -> None:
        """S4_reasoning 来源 score >= 0.6 应产出警告。"""
        j = make_valid_judgment(
            confidence=JudgmentConfidence(
                source=SourceLevel.S4_REASONING,
                score=0.8,
                consensus=ConsensusLevel.MIXED,
            )
        )
        result = validate_judgment(j)
        assert result.valid is True
        assert len(result.warnings) > 0

    def test_non_atomic_warned(self) -> None:
        """when 中包含以及应产出非原子警告。"""
        j = make_valid_judgment(
            core=JudgmentCore(
                when="处理价格数据以及计算仓位比例时",
                modality=Modality.MUST_NOT,
                action="使用 float 类型做算术运算",
                consequence=Consequence(
                    kind=ConsequenceKind.FINANCIAL_LOSS,
                    description="精度偏差导致资金计算错误",
                ),
            )
        )
        result = validate_judgment(j)
        assert any("非原子" in w for w in result.warnings)

    def test_context_scope_without_context_requires_rejected(self) -> None:
        """scope.level=context 但缺少 context_requires 应产出错误。"""
        j = make_valid_judgment(
            scope=JudgmentScope(
                level=ScopeLevel.CONTEXT,
                domains=["finance"],
                context_requires=None,
            )
        )
        result = validate_judgment(j)
        assert result.valid is False
