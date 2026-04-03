"""共享工厂函数。"""

from doramagic_judgment_schema.types import (
    ConsensusLevel,
    Consequence,
    ConsequenceKind,
    CrystalSection,
    EvidenceRef,
    EvidenceRefType,
    Freshness,
    Judgment,
    JudgmentCompilation,
    JudgmentConfidence,
    JudgmentCore,
    JudgmentScope,
    Layer,
    Modality,
    ScopeLevel,
    Severity,
    SourceLevel,
)


def make_valid_judgment(**overrides):
    """工厂函数：创建一个完整合法的判断，可通过 overrides 覆盖任意字段。"""
    defaults = {
        "id": "finance-K-001",
        "core": JudgmentCore(
            when="进行金融计算（价格、资金、盈亏）时",
            modality=Modality.MUST_NOT,
            action="使用 IEEE 754 binary float 做算术运算",
            consequence=Consequence(
                kind=ConsequenceKind.FINANCIAL_LOSS,
                description="浮点累积误差导致 PnL 偏差，万次运算后偏差可达 0.01%-0.1%",
            ),
        ),
        "layer": Layer.KNOWLEDGE,
        "scope": JudgmentScope(
            level=ScopeLevel.DOMAIN,
            domains=["finance"],
        ),
        "confidence": JudgmentConfidence(
            source=SourceLevel.S2_CROSS_PROJECT,
            score=0.95,
            consensus=ConsensusLevel.STRONG,
            evidence_refs=[
                EvidenceRef(
                    type=EvidenceRefType.SOURCE_CODE,
                    source="freqtrade",
                    locator="https://github.com/freqtrade/freqtrade/blob/main/freqtrade/persistence/trade_model.py#L45",
                    summary="freqtrade 用 Decimal 处理所有交易金额",
                ),
            ],
        ),
        "compilation": JudgmentCompilation(
            severity=Severity.FATAL,
            crystal_section=CrystalSection.CONSTRAINTS,
            freshness=Freshness.STABLE,
            query_tags=["float", "precision", "decimal"],
        ),
    }
    defaults.update(overrides)
    return Judgment(**defaults)
