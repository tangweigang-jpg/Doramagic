"""三层完整采集集成测试 — 验证晶体覆盖度。"""

import pytest
from doramagic_crystal_compiler.compiler import compile_crystal
from doramagic_crystal_compiler.retrieve import retrieve
from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import CrystalSection, Judgment, Layer


class TestCrystalCoverage:
    """验证三层判断能正确编译为完整晶体。"""

    @pytest.fixture
    def populated_store(self, tmp_path):
        """创建一个包含三层判断的临时 store。"""
        store = JudgmentStore(base_path=str(tmp_path / "judgments"))

        from doramagic_judgment_schema.types import (
            ConsensusLevel,
            Consequence,
            ConsequenceKind,
            EvidenceRef,
            EvidenceRefType,
            Freshness,
            JudgmentCompilation,
            JudgmentConfidence,
            JudgmentCore,
            JudgmentScope,
            JudgmentVersion,
            LifecycleStatus,
            Modality,
            ScopeLevel,
            Severity,
            SourceLevel,
        )

        def make_judgment(id_str, layer, section, when, action, consequence_desc):
            return Judgment(
                id=id_str,
                core=JudgmentCore(
                    when=when,
                    modality=Modality.MUST,
                    action=action,
                    consequence=Consequence(
                        kind=ConsequenceKind.BUG,
                        description=consequence_desc,
                    ),
                ),
                layer=layer,
                scope=JudgmentScope(level=ScopeLevel.DOMAIN, domains=["finance"]),
                confidence=JudgmentConfidence(
                    source=SourceLevel.S1_SINGLE_PROJECT,
                    score=0.8,
                    consensus=ConsensusLevel.STRONG,
                    evidence_refs=[
                        EvidenceRef(
                            type=EvidenceRefType.DOC, source="test/repo", summary="test evidence"
                        ),
                    ],
                ),
                compilation=JudgmentCompilation(
                    severity=Severity.HIGH,
                    crystal_section=section,
                    freshness=Freshness.SEMI_STABLE,
                    query_tags=["finance"],
                ),
                version=JudgmentVersion(status=LifecycleStatus.DRAFT),
            )

        # 知识层
        store.store(
            make_judgment(
                "finance-K-001",
                Layer.KNOWLEDGE,
                CrystalSection.CODE_SKELETON,
                "处理股票价格时间序列时",
                "基于交易日序列计算指标，禁止对非交易日插值",
                "插值导致指标偏离真实市场状态，回测收益率虚高 5-15%",
            )
        )

        # 资源层
        store.store(
            make_judgment(
                "finance-R-001",
                Layer.RESOURCE,
                CrystalSection.HARD_CONSTRAINTS,
                "使用 yfinance 获取历史数据时",
                "在本地建立缓存层避免重复请求",
                "高频请求触发限流，数据拉取中断导致流水线失败",
            )
        )

        # 经验层
        store.store(
            make_judgment(
                "finance-E-001",
                Layer.EXPERIENCE,
                CrystalSection.HARD_CONSTRAINTS,
                "使用 pandas 的 rolling 函数做回测计算时",
                "检查是否引入了未来数据（look-ahead bias）",
                "look-ahead 导致回测收益虚假，实盘亏损",
            )
        )

        return store

    def test_crystal_has_recipe_structure(self, populated_store):
        """晶体必须包含三段式配方结构。"""
        retrieval = retrieve(store=populated_store, domain="finance")
        crystal = compile_crystal(
            retrieval=retrieval,
            domain="finance",
            task_description="量化投资分析工具",
        )

        assert "## 一、最小可运行样本" in crystal
        assert "## 二、硬约束" in crystal
        assert "## 三、验收标准" in crystal
        assert "## context_acquisition" in crystal

        assert "```python" in crystal
        assert "assert" in crystal or "# 领域规则" in crystal

        assert "| # | 约束 | 原因 | 违反后果 |" in crystal

        assert "交易日序列" in crystal or "balance" in crystal
        assert "yfinance" in crystal or "缓存" in crystal
        assert "look-ahead" in crystal or "rolling" in crystal

        assert "<crystal" not in crystal
        assert "个性化提示" not in crystal

    def test_crystal_context_acquisition(self, populated_store):
        """晶体必须包含 context_acquisition 指令块。"""
        retrieval = retrieve(store=populated_store, domain="finance")
        crystal = compile_crystal(
            retrieval=retrieval,
            domain="finance",
            task_description="量化投资分析工具",
        )
        assert "查阅用户历史会话" in crystal or "查阅当前用户" in crystal
        assert "宿主 AI" in crystal

    def test_three_layer_coverage(self, populated_store):
        """检索结果应覆盖三层。"""
        retrieval = retrieve(store=populated_store, domain="finance")

        layer_values = set()
        for j, _ in retrieval.judgments:
            val = j.layer.value if hasattr(j.layer, "value") else j.layer
            layer_values.add(val)

        assert "knowledge" in layer_values
        assert "resource" in layer_values
        assert "experience" in layer_values

    def test_no_coverage_gaps_with_three_layers(self, populated_store):
        """三层都有判断时，不应报告层级缺口。"""
        retrieval = retrieve(store=populated_store, domain="finance")
        layer_gaps = [g for g in retrieval.coverage_gaps if "缺少" in g and "层判断" in g]
        assert len(layer_gaps) == 0
