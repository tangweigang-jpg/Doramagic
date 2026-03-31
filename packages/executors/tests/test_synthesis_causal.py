"""Synthesis 因果推理测试。

验证 SynthesisRunner 保留 "X because Y" 因果链，
Iron Law 门禁标注缺少 WHY 的情况，compile_brief 注入真实因果。
"""

from __future__ import annotations

import asyncio

from doramagic_contracts.base import NeedProfile, RepoExtractionEnvelope
from doramagic_contracts.cross_project import SynthesisInput
from doramagic_contracts.envelope import RunMetrics
from doramagic_executors.synthesis_runner import SynthesisRunner


def _make_input(envelopes: list) -> SynthesisInput:
    """构造最小 SynthesisInput — 用 model_construct 跳过非核心字段验证。

    SynthesisRunner 内部只使用 need_profile 和 extraction_aggregate，
    其他字段不参与因果推理逻辑。
    """
    # SynthesisRunner 内部对 extraction_aggregate 调用 model_dump() 或直接当 dict
    # 用一个支持 model_dump() 返回 dict 的简单包装
    aggregate_data = {
        "repo_envelopes": [e.model_dump() for e in envelopes],
        "success_count": len(envelopes),
        "failed_count": 0,
        "coverage_matrix": {},
        "conflict_map": {},
        "ready_for_synthesis": True,
    }

    class _FakeAggregate:
        def model_dump(self):
            return aggregate_data

    need_profile = NeedProfile(
        raw_input="帮我做一个记录卡路里的 skill",
        intent="Build a calorie tracking skill",
        domain="health",
        keywords=["calorie", "tracker"],
        search_directions=[],
        constraints=[],
        quality_expectations={},
    )
    return SynthesisInput.model_construct(
        need_profile=need_profile,
        extraction_aggregate=_FakeAggregate(),
        discovery_result=None,
        project_summaries=[],
        comparison_result=None,
        community_knowledge=None,
    )


def _metrics() -> RunMetrics:
    return RunMetrics(
        wall_time_ms=100,
        llm_calls=1,
        prompt_tokens=500,
        completion_tokens=200,
        estimated_cost_usd=0.01,
    )


def _envelope(
    *,
    design_philosophy: str = "Use explicit state transitions",
    mental_model: str = "Failures become visible early",
    why_hypotheses: list[str] | None = None,
    anti_patterns: list[str] | None = None,
    repo_name: str = "acme/ledger",
    repo_url: str = "https://github.com/acme/ledger",
) -> RepoExtractionEnvelope:
    return RepoExtractionEnvelope(
        worker_id="w-001",
        repo_name=repo_name,
        repo_url=repo_url,
        repo_type="TOOL",
        status="ok",
        design_philosophy=design_philosophy,
        mental_model=mental_model,
        why_hypotheses=why_hypotheses or [],
        anti_patterns=anti_patterns or [],
        evidence_cards=[],
        repo_facts={},
        extraction_confidence=0.8,
        evidence_count=5,
        metrics=_metrics(),
    )


class _FakeConfig:
    pass


def _run(input: SynthesisInput):
    """同步运行 async execute。"""
    runner = SynthesisRunner()
    return asyncio.run(runner.execute(input, adapter=None, config=_FakeConfig()))


# ---------------------------------------------------------------------------
# 注入点 1: 主决策因果链
# ---------------------------------------------------------------------------


class TestMainDecisionCausalChain:
    def test_merges_philosophy_and_model(self):
        """design_philosophy + mental_model 合并为因果声明。"""
        env = _envelope(
            design_philosophy="Use explicit state transitions",
            mental_model="Failures become visible early",
        )
        result = _run(_make_input([env]))
        main_decision = result.data.selected_knowledge[0]
        assert "Use explicit state transitions" in main_decision.statement
        assert "Failures become visible early" in main_decision.statement

    def test_no_data_mental_model_not_merged(self):
        """mental_model 为 [NO_DATA] 时不合并。"""
        env = _envelope(
            design_philosophy="Use explicit state transitions",
            mental_model="[NO_DATA]",
        )
        result = _run(_make_input([env]))
        main_decision = result.data.selected_knowledge[0]
        assert "[NO_DATA]" not in main_decision.statement


# ---------------------------------------------------------------------------
# 注入点 2: why_hypotheses 因果拆分
# ---------------------------------------------------------------------------


class TestWhyHypothesesCausalSplit:
    def test_because_clause_extracted(self):
        """包含 because 的假说被拆分为 statement + rationale。"""
        env = _envelope(
            why_hypotheses=[
                "Prefer immutable data because mutations cause hidden bugs",
            ],
        )
        result = _run(_make_input([env]))
        # 第二个 decision（第一个是主决策）
        why_decision = next(
            d for d in result.data.selected_knowledge if d.decision_id.endswith("-00")
        )
        assert "Prefer immutable data" in why_decision.statement
        assert "mutations cause hidden bugs" in why_decision.rationale

    def test_no_because_keeps_original(self):
        """无 because 的假说保留原文。"""
        env = _envelope(
            why_hypotheses=["Always validate user input"],
        )
        result = _run(_make_input([env]))
        why_decision = next(
            d for d in result.data.selected_knowledge if d.decision_id.endswith("-00")
        )
        assert "Always validate user input" in why_decision.statement
        assert "Design pattern from" in why_decision.rationale


# ---------------------------------------------------------------------------
# 注入点 3: anti_patterns 因果
# ---------------------------------------------------------------------------


class TestAntiPatternsCausal:
    def test_trap_because_extracted(self):
        """anti_pattern 包含 because 时提取风险原因。"""
        env = _envelope(
            anti_patterns=[
                "Avoid global mutable state because race conditions are hard to debug",
            ],
        )
        result = _run(_make_input([env]))
        trap = next(d for d in result.data.selected_knowledge if "[TRAP]" in d.statement)
        assert "Avoid global mutable state" in trap.statement
        assert "race conditions" in trap.rationale

    def test_trap_no_because(self):
        """无 because 的 anti_pattern 使用通用 rationale。"""
        env = _envelope(anti_patterns=["Never use eval()"])
        result = _run(_make_input([env]))
        trap = next(d for d in result.data.selected_knowledge if "[TRAP]" in d.statement)
        assert "Never use eval()" in trap.statement
        assert "Anti-pattern from" in trap.rationale


# ---------------------------------------------------------------------------
# Iron Law 门禁
# ---------------------------------------------------------------------------


class TestIronLaw:
    def test_iron_law_triggers_on_no_causal(self):
        """所有 rationale 都是 generic 时触发 Iron Law 警告且阻断编译。"""
        env = _envelope(
            design_philosophy="Some architecture pattern",
            mental_model="[NO_DATA]",
            why_hypotheses=["Another fact without because"],
        )
        result = _run(_make_input([env, env]))
        warning_codes = [w.code for w in result.warnings]
        assert "IRON_LAW" in warning_codes
        # compile_ready 应为 False（真正阻断编译）
        assert result.data.compile_ready is False
        # compile_brief workflow 包含警告
        workflow = result.data.compile_brief_by_section.get("workflow", [])
        assert any("WARNING" in line for line in workflow)

    def test_iron_law_not_triggered_with_causal(self):
        """有因果链时不触发，compile_ready 为 True。"""
        env = _envelope(
            design_philosophy="Use explicit state transitions",
            mental_model="Failures become visible early and repairable in production",
        )
        result = _run(_make_input([env]))
        warning_codes = [w.code for w in result.warnings]
        assert "IRON_LAW" not in warning_codes
        assert result.data.compile_ready is True


# ---------------------------------------------------------------------------
# compile_brief 因果注入
# ---------------------------------------------------------------------------


class TestCompileBriefCausal:
    def test_workflow_contains_why(self):
        """compile_brief workflow 包含 Why 行。"""
        env = _envelope(
            design_philosophy="Use explicit state transitions",
            mental_model="Failures become visible early and repairable in production",
        )
        result = _run(_make_input([env]))
        workflow = result.data.compile_brief_by_section["workflow"]
        assert any("Why:" in line for line in workflow)

    def test_common_why_has_causal_chain(self):
        """common_why 包含 "事实 — 原因" 格式。"""
        env = _envelope(
            design_philosophy="Use explicit state transitions",
            mental_model="Failures become visible early and repairable in production",
        )
        result = _run(_make_input([env]))
        assert any("—" in w for w in result.data.common_why)
