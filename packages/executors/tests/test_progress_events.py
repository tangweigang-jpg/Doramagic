"""Tests for fine-grained progress event emission."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Add packages to path for direct test execution.
_root = Path(__file__).resolve().parent.parent.parent.parent
from doramagic_contracts.base import NeedProfile
from doramagic_contracts.cross_project import (
    CommunityKnowledge,
    CompareMetrics,
    CompareOutput,
    DiscoveryResult,
    SynthesisInput,
)
from doramagic_contracts.envelope import RunMetrics
from doramagic_executors.discovery_runner import DiscoveryRunner
from doramagic_executors.synthesis_runner import SynthesisRunner


def _metrics() -> RunMetrics:
    return RunMetrics(
        wall_time_ms=10,
        llm_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
    )


def _need_profile() -> NeedProfile:
    return NeedProfile(
        raw_input="find alpha tool",
        keywords=["alpha"],
        intent="find alpha tool",
        search_directions=[],
        constraints=[],
        github_queries=["alpha-tool"],
        max_projects=2,
    )


def _discovery_input() -> object:
    from doramagic_contracts.cross_project import DiscoveryConfig, DiscoveryInput

    return DiscoveryInput(
        need_profile=_need_profile(),
        routing=None,
        api_hint=None,
        config=DiscoveryConfig(),
    )


def _synthesis_input() -> SynthesisInput:
    discovery_result = DiscoveryResult(candidates=[], search_coverage=[], candidate_count=0)
    compare_output = CompareOutput(
        domain_id="alpha",
        compared_projects=[],
        signals=[],
        metrics=CompareMetrics(
            project_count=1,
            atom_count=0,
            aligned_count=0,
            missing_count=0,
            original_count=0,
            drifted_count=0,
        ),
    )

    class _FakeAggregate:
        def model_dump(self):
            return {
                "repo_envelopes": [
                    {
                        "repo_name": "acme/alpha-one",
                        "repo_url": "https://github.com/acme/alpha-one",
                        "status": "ok",
                        "design_philosophy": "Use explicit state transitions",
                        "mental_model": "Failures become visible early",
                        "why_hypotheses": ["Prefer small steps because they are easier to review"],
                        "anti_patterns": ["Avoid hidden state because it increases debugging time"],
                    },
                    {
                        "repo_name": "acme/alpha-two",
                        "repo_url": "https://github.com/acme/alpha-two",
                        "status": "ok",
                        "design_philosophy": "Prefer observable workflows",
                        "mental_model": "Telemetry shortens feedback loops",
                        "why_hypotheses": ["Prefer explicit logs"],
                        "anti_patterns": ["Never bury errors"],
                    },
                ],
                "success_count": 2,
                "failed_count": 0,
                "coverage_matrix": {},
                "conflict_map": {},
                "ready_for_synthesis": True,
            }

    return SynthesisInput.model_construct(
        need_profile=_need_profile(),
        discovery_result=discovery_result,
        extraction_aggregate=_FakeAggregate(),
        project_summaries=[],
        comparison_result=compare_output,
        community_knowledge=CommunityKnowledge(),
    )


class TestProgressEvents:
    def test_discovery_emits_sub_progress(self):
        bus = MagicMock()
        config = SimpleNamespace(event_bus=bus)

        runner = DiscoveryRunner()
        with patch(
            "doramagic_executors.discovery_runner.search_github",
            return_value=[
                {
                    "name": "acme/alpha-one",
                    "url": "https://github.com/acme/alpha-one",
                    "description": "alpha repository",
                    "stars": 100,
                    "forks": 10,
                    "updated_at": "2026-03-29",
                },
                {
                    "name": "acme/alpha-two",
                    "url": "https://github.com/acme/alpha-two",
                    "description": "another alpha repository",
                    "stars": 90,
                    "forks": 5,
                    "updated_at": "2026-03-29",
                },
            ],
        ):
            asyncio.run(runner.execute(_discovery_input(), adapter=None, config=config))

        bus.emit.assert_called_once()
        event_type, message = bus.emit.call_args.args[:2]
        assert event_type == "sub_progress"
        assert message == "搜索 GitHub: 'alpha-tool'... 找到 2 个候选"

    def test_synthesis_emits_sub_progress(self):
        bus = MagicMock()
        config = SimpleNamespace(event_bus=bus)
        runner = SynthesisRunner()

        async def _fake_quality_filter(adapter, intent, domain, real_decisions):
            return real_decisions[:1], 1, 10, 5

        with patch.object(
            runner, "_llm_quality_filter", new=AsyncMock(side_effect=_fake_quality_filter)
        ):
            asyncio.run(runner.execute(_synthesis_input(), adapter=object(), config=config))

        bus.emit.assert_called_once()
        event_type, message = bus.emit.call_args.args[:2]
        assert event_type == "sub_progress"
        assert message == "评估 6 条知识的质量... 过滤了 5 条"
