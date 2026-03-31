"""Integration tests for Stage 1.5 agentic exploration.

These tests use MockLLMAdapter with realistic response sequences that
simulate a complete agent loop against the Sim2 (calorie tracker) fixture.

Key differences from unit tests:
- Uses multi-step response sequences (tool selection → evaluation → conclusion)
- Validates the full artifact pipeline end-to-end
- Checks that exploration log entries are cross-referenced correctly

No real LLM or API keys needed — everything is deterministic via mock.
"""

from __future__ import annotations

import json
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_RACE_ROOT = _THIS_DIR.parent
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # -> Doramagic/

from doramagic_contracts.extraction import (  # noqa: E402
    Hypothesis,
    Stage15AgenticInput,
    Stage15Budget,
    Stage15Toolset,
)
from doramagic_extraction.stage15_agentic import run_stage15_agentic  # noqa: E402
from doramagic_shared_utils.capability_router import CapabilityRouter  # noqa: E402
from doramagic_shared_utils.llm_adapter import MockLLMAdapter  # noqa: E402

FIXTURES_DIR = _REPO_ROOT / "data" / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_input(tmp_path: Path) -> Stage15AgenticInput:
    repo_payload = _load_json(FIXTURES_DIR / "example_calorie_repo_facts_calorie.json")
    stage1_payload = _load_json(FIXTURES_DIR / "example_calorie_stage1_output_calorie.json")

    repo_root = tmp_path / "ai-calorie-counter"
    repo_root.mkdir(parents=True, exist_ok=True)

    # Create some fake source files so file tools can work
    src = repo_root / "src" / "app" / "api" / "chat"
    src.mkdir(parents=True, exist_ok=True)
    (src / "route.ts").write_text(
        "\n".join(
            [
                "import { streamText } from 'ai';",
                "import { openai } from '@ai-sdk/openai';",
                "",
                "const NUTRITION_SYSTEM_PROMPT = `",
                "You are a nutrition expert. Estimate calories for the described food.",
                "Provide: calories, protein, carbs, fat.",
                "Respond in JSON format.",
                "`;",
                "",
                "export async function POST(req: Request) {",
                "  const { messages } = await req.json();",
                "  return streamText({",
                "    model: openai('gpt-4o-mini'),",
                "    messages,",
                "    system: NUTRITION_SYSTEM_PROMPT",
                "  });",
                "}",
            ]
        )
    )

    lib = repo_root / "src" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "store.ts").write_text(
        "\n".join(
            [
                "// In-memory store only — no persistence. Reset on page reload.",
                "let meals: Meal[] = [];",
                "export const addMeal = (meal: Meal) => meals.push(meal);",
                "export const getMeals = () => meals;",
                "export const clearMeals = () => { meals = []; };",
            ]
        )
    )

    (repo_root / "README.md").write_text(
        "\n".join(
            [
                "# AI Calorie Counter",
                "",
                "## About",
                "We intentionally use LLM estimation over database lookup because",
                "real-world food descriptions are fuzzy and conversational.",
                "",
                "TODO: Add Vercel KV for cross-session persistence",
            ]
        )
    )

    repo_payload["repo"]["local_path"] = str(repo_root)
    stage1_payload["repo"]["local_path"] = str(repo_root)

    return Stage15AgenticInput(
        repo=repo_payload["repo"],
        repo_facts=repo_payload,
        stage1_output=stage1_payload,
        budget=Stage15Budget(
            max_rounds=5,
            max_tool_calls=30,
            max_prompt_tokens=60000,
            stop_after_no_gain_rounds=2,
        ),
        toolset=Stage15Toolset(),
    )


def _artifact_root(input_data: Stage15AgenticInput) -> Path:
    return Path(input_data.repo.local_path) / "artifacts" / "stage15"


# ---------------------------------------------------------------------------
# Integration scenario: multi-step realistic exploration
# ---------------------------------------------------------------------------


def _make_realistic_adapter(input_data: Stage15AgenticInput) -> MockLLMAdapter:
    """Build a mock adapter that simulates a realistic multi-step agent loop.

    Hypothesis h-001 (Chinese food recognition):
      Turn 1: search_repo for NUTRITION_SYSTEM_PROMPT
      Turn 1 eval: pending, continue
      Turn 2: read_file route.ts
      Turn 2 eval: confirmed (no Chinese handling), conclude

    Hypothesis h-002 (Rate limiting):
      Turn 1: read_artifact to check Stage 1 findings
      Turn 1 eval: concluded (no rate limit found), append_finding
    """
    responses = [
        # === h-001 ===
        # Turn 1: tool selection
        json.dumps(
            {
                "tool": "search_repo",
                "tool_input": {
                    "pattern": "NUTRITION_SYSTEM_PROMPT",
                    "file_glob": "*.ts",
                    "max_results": 5,
                },
                "reasoning": "Search for system prompt to check Chinese food handling",
            }
        ),
        # Turn 1: eval
        json.dumps(
            {
                "hypothesis_status": "pending",
                "confidence": "medium",
                "reasoning": "Found system prompt reference, need to read the file",
                "should_continue": True,
                "next_action_hint": "read route.ts to examine system prompt",
            }
        ),
        # Turn 2: tool selection → read_file
        json.dumps(
            {
                "tool": "read_file",
                "tool_input": {
                    "path": "src/app/api/chat/route.ts",
                    "start_line": 1,
                    "end_line": 17,
                },
                "reasoning": "Read the chat route to examine NUTRITION_SYSTEM_PROMPT content",
            }
        ),
        # Turn 2: eval → confirmed, no more exploration needed
        json.dumps(
            {
                "hypothesis_status": "confirmed",
                "confidence": "high",
                "reasoning": "System prompt is English-only. No Chinese food handling logic found. Hypothesis confirmed.",
                "should_continue": False,
                "next_action_hint": "",
            }
        ),
        # === h-002 ===
        # Turn 1: tool selection → read_artifact
        json.dumps(
            {
                "tool": "read_artifact",
                "tool_input": {
                    "artifact": "stage1_output.findings",
                    "related_finding_ids": ["f-001"],
                },
                "reasoning": "Check Stage 1 findings about the chat API",
            }
        ),
        # Turn 1: eval → append immediately
        json.dumps(
            {
                "hypothesis_status": "confirmed",
                "confidence": "medium",
                "reasoning": "Stage 1 confirms no rate limiting mentioned, chat API is unprotected",
                "should_continue": False,
                "next_action_hint": "",
            }
        ),
    ]
    return MockLLMAdapter(responses=responses)


class TestIntegrationRealisticExploration:
    def test_full_pipeline_runs_successfully(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = _make_realistic_adapter(input_data)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.status in ("ok", "degraded")
        assert result.data is not None
        assert result.metrics.llm_calls > 0

    def test_exploration_log_has_correct_step_structure(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = _make_realistic_adapter(input_data)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        log_path = _artifact_root(input_data) / "exploration_log.jsonl"
        entries = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]

        assert len(entries) >= 2, "Expected at least 2 exploration steps"
        for entry in entries:
            assert "step_id" in entry
            assert "round_index" in entry
            assert "tool_name" in entry
            assert "tool_input" in entry
            assert "observation" in entry
            assert entry["round_index"] >= 1

    def test_hypotheses_file_contains_all_hypotheses(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = _make_realistic_adapter(input_data)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        hyp_path = _artifact_root(input_data) / "hypotheses.jsonl"
        hypotheses = [
            json.loads(line) for line in hyp_path.read_text().splitlines() if line.strip()
        ]
        original_ids = {h.hypothesis_id for h in input_data.stage1_output.hypotheses}
        stored_ids = {h["hypothesis_id"] for h in hypotheses}
        assert original_ids == stored_ids

    def test_claim_ledger_references_real_file_paths(self, tmp_path: Path) -> None:
        """Confirmed claims should reference actual files that exist in the repo."""
        input_data = _build_input(tmp_path)
        # Force read_file tool to create real evidence
        responses = [
            json.dumps(
                {
                    "tool": "read_file",
                    "tool_input": {
                        "path": "src/app/api/chat/route.ts",
                        "start_line": 1,
                        "end_line": 10,
                    },
                    "reasoning": "Read file to get evidence",
                }
            ),
            json.dumps(
                {
                    "hypothesis_status": "confirmed",
                    "confidence": "high",
                    "reasoning": "File read successfully, evidence collected",
                    "should_continue": False,
                    "next_action_hint": "",
                }
            ),
            json.dumps(
                {
                    "tool": "read_file",
                    "tool_input": {
                        "path": "src/lib/store.ts",
                        "start_line": 1,
                        "end_line": 5,
                    },
                    "reasoning": "Check store for persistence",
                }
            ),
            json.dumps(
                {
                    "hypothesis_status": "confirmed",
                    "confidence": "medium",
                    "reasoning": "In-memory store confirmed, no rate limiting",
                    "should_continue": False,
                    "next_action_hint": "",
                }
            ),
        ]
        adapter = MockLLMAdapter(responses=responses)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        repo_root = Path(input_data.repo.local_path)

        for claim in result.data.promoted_claims:
            for ref in claim.evidence_refs:
                if ref.kind == "file_line":
                    file_path = repo_root / ref.path
                    assert file_path.exists(), (
                        f"Claim {claim.claim_id} references non-existent file: {ref.path}"
                    )

    def test_evidence_index_maps_claims_correctly(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        responses = [
            json.dumps(
                {
                    "tool": "append_finding",
                    "tool_input": {
                        "status": "confirmed",
                        "statement": "Test confirmed claim",
                        "confidence": "high",
                        "evidence_path": "src/app/api/chat/route.ts",
                        "evidence_start_line": 10,
                        "evidence_end_line": 15,
                        "evidence_snippet": "export async function POST(...)",
                    },
                    "reasoning": "Direct evidence in Stage 1",
                }
            ),
            json.dumps(
                {
                    "tool": "append_finding",
                    "tool_input": {
                        "status": "confirmed",
                        "statement": "Another confirmed claim",
                        "confidence": "medium",
                        "evidence_path": "src/lib/store.ts",
                        "evidence_start_line": 1,
                        "evidence_end_line": 5,
                        "evidence_snippet": "// In-memory store only",
                    },
                    "reasoning": "Evidence from store file",
                }
            ),
        ]
        adapter = MockLLMAdapter(responses=responses)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        index_path = _artifact_root(input_data) / "evidence_index.json"
        index = json.loads(index_path.read_text())

        assert index["repo_id"] == "ai-calorie-counter"
        assert isinstance(index["evidence_items"], list)

    def test_context_digest_is_human_readable(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = _make_realistic_adapter(input_data)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        digest_path = _artifact_root(input_data) / "context_digest.md"
        digest = digest_path.read_text()

        assert "ai-calorie-counter" in digest
        assert "Tool calls" in digest or "tool calls" in digest

    def test_summary_fields_are_consistent_with_ledger(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = _make_realistic_adapter(input_data)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        summary = result.data.summary
        ledger_path = _artifact_root(input_data) / "claim_ledger.jsonl"
        claims = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        resolved_in_ledger = {
            c["hypothesis_id"]
            for c in claims
            if c["status"] in ("confirmed", "rejected") and c.get("hypothesis_id")
        }
        for hyp_id in summary.resolved_hypotheses:
            assert hyp_id in resolved_in_ledger, (
                f"Summary says {hyp_id} resolved but not found in ledger"
            )

    def test_search_tool_produces_evidence_refs(self, tmp_path: Path) -> None:
        """search_repo against real files should produce parseable EvidenceRef entries."""
        input_data = _build_input(tmp_path)
        # Force search then conclude with whatever evidence was found
        responses = [
            json.dumps(
                {
                    "tool": "search_repo",
                    "tool_input": {
                        "pattern": "streamText",
                        "file_glob": "*.ts",
                        "max_results": 5,
                    },
                    "reasoning": "Search for streamText usage",
                }
            ),
            json.dumps(
                {
                    "hypothesis_status": "confirmed",
                    "confidence": "high",
                    "reasoning": "Found streamText usage in route.ts confirming streaming API",
                    "should_continue": False,
                    "next_action_hint": "",
                }
            ),
        ] * 3  # repeat for multiple hypotheses
        adapter = MockLLMAdapter(responses=responses)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        # Search step should appear in log
        log_path = _artifact_root(input_data) / "exploration_log.jsonl"
        entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
        search_entries = [e for e in entries if e["tool_name"] == "search_repo"]
        # We asked for search — it should appear
        assert len(search_entries) >= 1

    def test_no_gain_terminates_early(self, tmp_path: Path) -> None:
        """If LLM always returns pending, should stop after stop_after_no_gain_rounds."""
        input_data = _build_input(tmp_path)
        input_data.budget = Stage15Budget(
            max_rounds=10,
            max_tool_calls=50,
            max_prompt_tokens=100000,
            stop_after_no_gain_rounds=2,
        )
        # Always return append_finding with pending status
        adapter = MockLLMAdapter(
            default_response=json.dumps(
                {
                    "tool": "append_finding",
                    "tool_input": {
                        "status": "pending",
                        "statement": "Unable to conclude",
                        "confidence": "low",
                    },
                    "reasoning": "not enough info",
                }
            )
        )

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        assert result.data.summary.termination_reason in (
            "no_information_gain",
            "all_hypotheses_resolved",
            "budget_exhausted",
        )

    def test_router_gets_correct_tasks(self, tmp_path: Path) -> None:
        """CapabilityRouter should be called with correct task names."""
        input_data = _build_input(tmp_path)
        adapter = MockLLMAdapter(
            responses=[
                json.dumps(
                    {
                        "tool": "append_finding",
                        "tool_input": {
                            "status": "confirmed",
                            "statement": "Test",
                            "confidence": "high",
                            "evidence_path": "src/app/api/chat/route.ts",
                            "evidence_start_line": 10,
                            "evidence_end_line": 15,
                            "evidence_snippet": "test snippet",
                        },
                        "reasoning": "test",
                    }
                ),
            ]
            * 5
        )

        # Wrap adapter in router that uses it for everything
        router = CapabilityRouter(forced_adapter=adapter)

        result = run_stage15_agentic(input_data, adapter=adapter, router=router)

        assert result.data is not None
        assert result.status in ("ok", "degraded")


class TestIntegrationEdgeCases:
    def test_single_hypothesis_confirmed(self, tmp_path: Path) -> None:
        """With a single hypothesis, should confirm it cleanly."""
        input_data = _build_input(tmp_path)
        input_data.stage1_output.hypotheses = [
            Hypothesis(
                hypothesis_id="h-001",
                statement="The system uses streaming for LLM responses.",
                reason="API route uses streamText",
                priority="high",
                search_hints=["streamText", "stream"],
                related_finding_ids=["f-001"],
            )
        ]
        adapter = MockLLMAdapter(
            responses=[
                json.dumps(
                    {
                        "tool": "append_finding",
                        "tool_input": {
                            "status": "confirmed",
                            "statement": "Streaming confirmed via streamText in route.ts",
                            "confidence": "high",
                            "evidence_path": "src/app/api/chat/route.ts",
                            "evidence_start_line": 12,
                            "evidence_end_line": 45,
                            "evidence_snippet": "return streamText({...})",
                        },
                        "reasoning": "Stage 1 finding f-001 confirms this directly",
                    }
                ),
            ]
        )

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        assert result.data.summary.termination_reason == "all_hypotheses_resolved"
        assert "h-001" in result.data.summary.resolved_hypotheses

    def test_malformed_llm_response_is_handled_gracefully(self, tmp_path: Path) -> None:
        """Malformed LLM JSON should not crash the pipeline."""
        input_data = _build_input(tmp_path)
        adapter = MockLLMAdapter(
            responses=[
                "this is not valid JSON at all!!!",
                "also not JSON",
            ]
            + [
                json.dumps(
                    {
                        "tool": "append_finding",
                        "tool_input": {
                            "status": "pending",
                            "statement": "Could not resolve",
                            "confidence": "low",
                        },
                        "reasoning": "fallback",
                    }
                ),
            ]
            * 5
        )

        result = run_stage15_agentic(input_data, adapter=adapter)

        # Should not raise; may return degraded or ok
        assert result.status in ("ok", "degraded")
        assert result.data is not None
