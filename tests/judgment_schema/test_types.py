"""测试 Judgment Pydantic 模型的基本行为。"""

import sys
from pathlib import Path

import pytest
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
from pydantic import ValidationError

# 把 tests/judgment_schema 加入 sys.path 以便导入 helpers
sys.path.insert(0, str(Path(__file__).parent))
from helpers import make_valid_judgment


class TestJudgmentCreation:
    def test_valid_judgment_creates_successfully(self) -> None:
        j = make_valid_judgment()
        assert j.id == "finance-K-001"
        assert j.hash != ""  # auto-computed

    def test_hash_is_deterministic(self) -> None:
        j1 = make_valid_judgment()
        j2 = make_valid_judgment()
        assert j1.hash == j2.hash

    def test_hash_changes_with_content(self) -> None:
        j1 = make_valid_judgment()
        j2 = make_valid_judgment(
            core=JudgmentCore(
                when="不同的条件描述内容",
                modality=Modality.MUST,
                action="不同的行为描述内容",
                consequence=Consequence(
                    kind=ConsequenceKind.BUG,
                    description="不同的后果描述内容信息",
                ),
            )
        )
        assert j1.hash != j2.hash

    def test_invalid_id_format_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_valid_judgment(id="bad-format")

    def test_empty_domains_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_valid_judgment(scope=JudgmentScope(level=ScopeLevel.DOMAIN, domains=[]))

    def test_confidence_score_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_valid_judgment(
                confidence=JudgmentConfidence(
                    source=SourceLevel.S2_CROSS_PROJECT,
                    score=1.5,
                    consensus=ConsensusLevel.STRONG,
                )
            )
