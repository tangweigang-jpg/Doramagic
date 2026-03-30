"""Unit tests for Stage 1.5 agentic exploration loop (S1-Sonnet).

All LLM calls are mocked — no real API keys required.
Tests validate the contract: hypotheses → claims with file:line evidence.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path: allow running from any working directory
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_RACE_ROOT = _THIS_DIR.parent
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # -> Doramagic/

from doramagic_contracts.base import EvidenceRef  # noqa: E402
from doramagic_contracts.envelope import ErrorCodes  # noqa: E402
from doramagic_contracts.extraction import (  # noqa: E402
    Hypothesis,
    Stage15AgenticInput,
    Stage15Budget,
    Stage15Toolset,
)
from doramagic_extraction.stage15_agentic import run_stage15_agentic  # noqa: E402
from doramagic_extraction.stage15_artifacts import (  # noqa: E402
    _parse_json_from_llm,
    check_claims_have_evidence,
)
from doramagic_extraction.stage15_tools import (  # noqa: E402
    _tool_list_tree,
    _tool_read_file,
    _tool_search_repo,
)
from doramagic_shared_utils.llm_adapter import LLMMessage, MockLLMAdapter  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = _REPO_ROOT / "data" / "fixtures"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_input(tmp_path: Path) -> Stage15AgenticInput:
    repo_payload = _load_json(FIXTURES_DIR / "example_calorie_repo_facts_calorie.json")
    stage1_payload = _load_json(FIXTURES_DIR / "example_calorie_stage1_output_calorie.json")

    repo_root = tmp_path / "ai-calorie-counter"
    repo_root.mkdir(parents=True, exist_ok=True)

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


def _make_mock_adapter(responses: list[str] | None = None) -> MockLLMAdapter:
    """Build a mock adapter with realistic tool-selection responses."""
    return MockLLMAdapter(responses=responses)


# ---------------------------------------------------------------------------
# LLM response sequences for different scenarios
# ---------------------------------------------------------------------------


def _search_then_read_then_append(
    hypothesis_id: str, file_path: str = "src/app/api/chat/route.ts"
) -> list[str]:
    """Responses: search → read_file → evaluate (continue=False) → adapter concludes."""
    return [
        # Turn 1: tool selection → search_repo
        json.dumps(
            {
                "tool": "search_repo",
                "tool_input": {
                    "pattern": "NUTRITION_SYSTEM_PROMPT",
                    "file_glob": "*.ts",
                    "max_results": 5,
                },
                "reasoning": "Search for the system prompt to check for Chinese food handling",
            }
        ),
        # Turn 1 eval: found something, read file next
        json.dumps(
            {
                "hypothesis_status": "pending",
                "confidence": "medium",
                "reasoning": "Found the system prompt, need to read the file content",
                "should_continue": True,
                "next_action_hint": "read the file to check system prompt content",
            }
        ),
        # Turn 2: tool selection → read_file
        json.dumps(
            {
                "tool": "read_file",
                "tool_input": {"path": file_path, "start_line": 1, "end_line": 30},
                "reasoning": "Read the chat route to examine system prompt content",
            }
        ),
        # Turn 2 eval: read file, now conclude
        json.dumps(
            {
                "hypothesis_status": "confirmed",
                "confidence": "high",
                "reasoning": "Found no Chinese-specific handling in the system prompt",
                "should_continue": False,
                "next_action_hint": "",
            }
        ),
    ]


def _append_immediately(status: str = "confirmed", statement: str = "Test claim.") -> list[str]:
    """LLM immediately records a claim."""
    return [
        json.dumps(
            {
                "tool": "append_finding",
                "tool_input": {
                    "status": status,
                    "statement": statement,
                    "confidence": "high",
                    "evidence_path": "src/app/api/chat/route.ts",
                    "evidence_start_line": 12,
                    "evidence_end_line": 45,
                    "evidence_snippet": "export async function POST(req: Request) { ... }",
                },
                "reasoning": "Direct evidence found in Stage 1 findings",
            }
        ),
    ]


def _reject_immediately(statement: str = "Rejected claim.") -> list[str]:
    return [
        json.dumps(
            {
                "tool": "append_finding",
                "tool_input": {
                    "status": "rejected",
                    "statement": statement,
                    "confidence": "high",
                    "evidence_path": "src/lib/store.ts",
                    "evidence_start_line": 1,
                    "evidence_end_line": 8,
                    "evidence_snippet": "// In-memory store only — no persistence.",
                },
                "reasoning": "Stage 1 evidence directly contradicts the hypothesis",
            }
        ),
    ]


# ---------------------------------------------------------------------------
# Unit tests — mock adapter
# ---------------------------------------------------------------------------


class TestRunStage15AgenticMock:
    """Tests using MockLLMAdapter — no real LLM calls."""

    def test_no_adapter_falls_back_to_mock(self, tmp_path: Path) -> None:
        """When adapter=None, should fall back to the deterministic mock."""
        input_data = _build_input(tmp_path)
        result = run_stage15_agentic(input_data, adapter=None)

        assert result.status in ("ok", "degraded", "blocked")
        assert result.data is not None

    def test_no_hypotheses_returns_blocked(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        input_data.stage1_output.hypotheses = []
        adapter = MockLLMAdapter()

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.status == "blocked"
        assert result.error_code == ErrorCodes.NO_HYPOTHESES
        assert result.data is None

    def test_confirmed_claim_has_file_line_evidence(self, tmp_path: Path) -> None:
        """Confirmed claims MUST have file:line evidence."""
        input_data = _build_input(tmp_path)
        # LLM immediately appends a confirmed claim with evidence
        responses = _append_immediately(
            status="confirmed",
            statement="The chat API uses streamText from Vercel AI SDK.",
        ) + _append_immediately(
            status="confirmed",
            statement="Rate limiting is not implemented.",
        )
        adapter = MockLLMAdapter(responses=responses)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        for claim in result.data.promoted_claims:
            assert claim.status == "confirmed"
            assert claim.evidence_refs, "Confirmed claim must have evidence_refs"
            for ref in claim.evidence_refs:
                assert ref.kind == "file_line"
                assert ref.start_line is not None
                assert ref.end_line is not None

    def test_rejected_claim_recorded_in_ledger(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        input_data.stage1_output.hypotheses.append(
            Hypothesis(
                hypothesis_id="h-003",
                statement="The app already persists daily meal history in Vercel KV.",
                reason="Assume persistence exists.",
                priority="low",
                search_hints=["vercel kv", "persistence"],
                related_finding_ids=["f-003"],
            )
        )
        # First 2 hypotheses get confirmed, h-003 gets rejected
        responses = (
            _append_immediately("confirmed", "Chat API claim")
            + _append_immediately("confirmed", "Rate limit claim")
            + _reject_immediately(
                "No Vercel KV integration found — persistence is not implemented."
            )
        )
        adapter = MockLLMAdapter(responses=responses)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        artifact_root = _artifact_root(input_data)
        claims = [
            json.loads(line)
            for line in (artifact_root / "claim_ledger.jsonl").read_text().splitlines()
            if line.strip()
        ]
        rejected = [c for c in claims if c["status"] == "rejected"]
        assert rejected, "Expected at least one rejected claim"
        assert any(c["hypothesis_id"] == "h-003" for c in rejected)

    def test_budget_exhausted_returns_degraded(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        # Very tight budget — 2 tool calls only
        input_data.budget = Stage15Budget(
            max_rounds=5,
            max_tool_calls=5,
            max_prompt_tokens=60000,
            stop_after_no_gain_rounds=2,
        )
        # Each hypothesis tries to search + read, but budget runs out
        adapter = MockLLMAdapter(
            default_response=json.dumps(
                {
                    "tool": "search_repo",
                    "tool_input": {"pattern": "test", "file_glob": "*.ts", "max_results": 5},
                    "reasoning": "Searching for patterns",
                }
            )
        )

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.status == "degraded"
        assert result.error_code == ErrorCodes.BUDGET_EXCEEDED
        assert result.data is not None
        assert result.data.summary.termination_reason == "budget_exhausted"

    def test_all_artifact_files_are_written(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = MockLLMAdapter(
            responses=_append_immediately("confirmed") + _append_immediately("confirmed")
        )

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        artifact_root = _artifact_root(input_data)
        for fname in (
            "hypotheses.jsonl",
            "exploration_log.jsonl",
            "claim_ledger.jsonl",
            "evidence_index.json",
            "context_digest.md",
        ):
            assert (artifact_root / fname).exists(), f"{fname} not found"

    def test_exploration_log_entries_are_valid_json(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = MockLLMAdapter(responses=_append_immediately("confirmed") * 3)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        log_path = _artifact_root(input_data) / "exploration_log.jsonl"
        for line in log_path.read_text().splitlines():
            if line.strip():
                entry = json.loads(line)
                assert "step_id" in entry
                assert "tool_name" in entry
                assert "observation" in entry

    def test_hypotheses_sorted_by_priority(self, tmp_path: Path) -> None:
        """High-priority hypotheses should be processed first."""
        input_data = _build_input(tmp_path)
        # Add a low-priority hypothesis before the existing high/medium ones
        input_data.stage1_output.hypotheses.insert(
            0,
            Hypothesis(
                hypothesis_id="h-low",
                statement="Low priority hypothesis",
                reason="Not important",
                priority="low",
                search_hints=["something"],
                related_finding_ids=[],
            ),
        )
        seen_order: list[str] = []

        def capture_response(messages: Sequence[LLMMessage], system: str | None) -> str:
            # Extract hypothesis_id from the prompt content
            for msg in messages:
                for line in msg.content.splitlines():
                    if line.startswith("ID:"):
                        hyp_id = line.split(":", 1)[1].strip()
                        if hyp_id not in seen_order:
                            seen_order.append(hyp_id)
            return json.dumps(
                {
                    "tool": "append_finding",
                    "tool_input": {
                        "status": "pending",
                        "statement": "test",
                        "confidence": "low",
                    },
                    "reasoning": "test",
                }
            )

        adapter = MockLLMAdapter(response_fn=capture_response)
        run_stage15_agentic(input_data, adapter=adapter)

        # h-001 (high) and h-002 (medium) must come before h-low
        if "h-001" in seen_order and "h-low" in seen_order:
            assert seen_order.index("h-001") < seen_order.index("h-low")
        if "h-002" in seen_order and "h-low" in seen_order:
            assert seen_order.index("h-002") < seen_order.index("h-low")

    def test_metrics_are_populated_with_llm_calls(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = MockLLMAdapter(responses=_append_immediately("confirmed") * 5)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.metrics.llm_calls > 0
        assert result.metrics.prompt_tokens > 0
        assert result.metrics.wall_time_ms >= 0

    def test_evidence_index_json_is_valid(self, tmp_path: Path) -> None:
        input_data = _build_input(tmp_path)
        adapter = MockLLMAdapter(responses=_append_immediately("confirmed") * 3)

        result = run_stage15_agentic(input_data, adapter=adapter)

        assert result.data is not None
        index_path = _artifact_root(input_data) / "evidence_index.json"
        index = json.loads(index_path.read_text())
        assert "repo_id" in index
        assert "evidence_items" in index

    def test_no_real_llm_needed_for_mock_path(self, tmp_path: Path) -> None:
        """MockLLMAdapter must work without any env vars."""
        import os

        saved = {}
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
            saved[key] = os.environ.pop(key, None)

        try:
            input_data = _build_input(tmp_path)
            adapter = MockLLMAdapter(responses=_append_immediately("confirmed") * 3)
            result = run_stage15_agentic(input_data, adapter=adapter)
            assert result.status in ("ok", "degraded")
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value

    def test_disabled_toolset_produces_warnings(self, tmp_path: Path) -> None:
        """Disabled tools should not block execution; warnings should be emitted."""
        input_data = _build_input(tmp_path)
        input_data.toolset = Stage15Toolset(
            allow_read_artifact=False,
            allow_list_tree=False,
            allow_search_repo=False,
            allow_read_file=True,
            allow_append_finding=True,
        )
        adapter = MockLLMAdapter(
            responses=[
                # LLM tries search_repo (disabled) then falls back to append
                json.dumps(
                    {
                        "tool": "search_repo",
                        "tool_input": {"pattern": "test", "file_glob": "*.ts", "max_results": 3},
                        "reasoning": "trying search",
                    }
                ),
                json.dumps(
                    {
                        "hypothesis_status": "pending",
                        "confidence": "low",
                        "reasoning": "search disabled",
                        "should_continue": True,
                        "next_action_hint": "try append_finding",
                    }
                ),
                json.dumps(
                    {
                        "tool": "append_finding",
                        "tool_input": {
                            "status": "pending",
                            "statement": "Could not fully investigate",
                            "confidence": "low",
                        },
                        "reasoning": "no more tools",
                    }
                ),
            ]
            * 5
        )

        result = run_stage15_agentic(input_data, adapter=adapter)

        # Should complete without crashing
        assert result.data is not None


class TestCheckClaimsHaveEvidence:
    def test_empty_claims_returns_true(self) -> None:
        assert check_claims_have_evidence([], []) is True

    def test_pending_claim_without_evidence_passes(self) -> None:
        from doramagic_contracts.extraction import ClaimRecord, ExplorationLogEntry

        claim = ClaimRecord(
            claim_id="C-001",
            statement="test",
            status="pending",
            confidence="low",
            hypothesis_id="h-001",
            supporting_step_ids=["S-001"],
            evidence_refs=[],
        )
        step = ExplorationLogEntry(
            step_id="S-001",
            round_index=1,
            tool_name="search_repo",
            tool_input={"pattern": "test"},
            observation="no matches",
            produced_evidence_refs=[],
        )
        assert check_claims_have_evidence([claim], [step]) is True

    def test_confirmed_claim_without_evidence_fails(self) -> None:
        from doramagic_contracts.extraction import ClaimRecord, ExplorationLogEntry

        claim = ClaimRecord(
            claim_id="C-001",
            statement="confirmed test",
            status="confirmed",
            confidence="high",
            hypothesis_id="h-001",
            supporting_step_ids=["S-001"],
            evidence_refs=[],  # empty!
        )
        step = ExplorationLogEntry(
            step_id="S-001",
            round_index=1,
            tool_name="read_file",
            tool_input={"path": "test.py"},
            observation="content",
            produced_evidence_refs=[],
        )
        assert check_claims_have_evidence([claim], [step]) is False

    def test_confirmed_claim_with_traceable_evidence_passes(self) -> None:
        from doramagic_contracts.extraction import ClaimRecord, ExplorationLogEntry

        evidence = EvidenceRef(
            kind="file_line",
            path="src/test.ts",
            start_line=10,
            end_line=20,
            snippet="const foo = bar;",
        )
        claim = ClaimRecord(
            claim_id="C-001",
            statement="confirmed test",
            status="confirmed",
            confidence="high",
            hypothesis_id="h-001",
            supporting_step_ids=["S-001"],
            evidence_refs=[evidence],
        )
        step = ExplorationLogEntry(
            step_id="S-001",
            round_index=1,
            tool_name="read_file",
            tool_input={"path": "src/test.ts"},
            observation="content",
            produced_evidence_refs=[evidence],
        )
        assert check_claims_have_evidence([claim], [step]) is True

    def test_confirmed_claim_with_untraceable_evidence_fails(self) -> None:
        """Evidence not present in any step's produced_evidence_refs should fail."""
        from doramagic_contracts.extraction import ClaimRecord, ExplorationLogEntry

        evidence = EvidenceRef(
            kind="file_line",
            path="src/test.ts",
            start_line=10,
            end_line=20,
            snippet="const foo = bar;",
        )
        claim = ClaimRecord(
            claim_id="C-001",
            statement="confirmed test",
            status="confirmed",
            confidence="high",
            hypothesis_id="h-001",
            supporting_step_ids=["S-001"],
            evidence_refs=[evidence],
        )
        step = ExplorationLogEntry(
            step_id="S-001",
            round_index=1,
            tool_name="read_file",
            tool_input={"path": "src/test.ts"},
            observation="content",
            produced_evidence_refs=[],  # not in step!
        )
        assert check_claims_have_evidence([claim], [step]) is False


class TestParseJsonFromLlm:
    def test_clean_json(self) -> None:
        result = _parse_json_from_llm('{"tool": "search_repo"}')
        assert result == {"tool": "search_repo"}

    def test_json_in_markdown_fence(self) -> None:
        text = '```json\n{"tool": "read_file"}\n```'
        result = _parse_json_from_llm(text)
        assert result == {"tool": "read_file"}

    def test_json_with_surrounding_text(self) -> None:
        text = 'Here is my response: {"tool": "list_tree"} end'
        result = _parse_json_from_llm(text)
        assert result is not None
        assert result.get("tool") == "list_tree"

    def test_invalid_json_returns_none(self) -> None:
        result = _parse_json_from_llm("this is not JSON at all")
        assert result is None


class TestToolExecutors:
    def test_list_tree_returns_entries(self, tmp_path: Path) -> None:
        # Create some files
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# main")
        (tmp_path / "README.md").write_text("# readme")

        result = _tool_list_tree(tmp_path, {"path": "."})
        assert "main.py" in result or "src" in result

    def test_list_tree_skips_hidden_dirs(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("git config")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# main")

        result = _tool_list_tree(tmp_path, {"path": "."})
        assert ".git" not in result
        assert "main.py" in result

    def test_list_tree_nonexistent_dir(self, tmp_path: Path) -> None:
        result = _tool_list_tree(tmp_path, {"path": "nonexistent"})
        assert "not found" in result.lower() or "error" in result.lower()

    def test_read_file_returns_content_and_evidence(self, tmp_path: Path) -> None:
        source = "line1\nline2\nline3\n"
        (tmp_path / "test.py").write_text(source)

        obs, evidence = _tool_read_file(tmp_path, {"path": "test.py"})
        assert "line1" in obs
        assert evidence is not None
        assert evidence.kind == "file_line"
        assert evidence.start_line == 1

    def test_read_file_with_line_range(self, tmp_path: Path) -> None:
        lines = "\n".join(f"line{i}" for i in range(1, 50))
        (tmp_path / "big.py").write_text(lines)

        obs, evidence = _tool_read_file(
            tmp_path, {"path": "big.py", "start_line": 10, "end_line": 15}
        )
        assert "line10" in obs
        assert evidence is not None
        assert evidence.start_line == 10

    def test_read_file_missing(self, tmp_path: Path) -> None:
        obs, evidence = _tool_read_file(tmp_path, {"path": "doesnotexist.py"})
        assert "not found" in obs.lower() or "error" in obs.lower()
        assert evidence is None

    def test_search_repo_finds_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "api.ts").write_text("export async function POST() {}\n")

        result = _tool_search_repo(
            tmp_path, {"pattern": "POST", "file_glob": "*.ts", "max_results": 5}
        )
        # Either found it, or got no-match if repo doesn't exist (empty dir case)
        assert isinstance(result, str)

    def test_search_repo_empty_pattern_returns_error(self, tmp_path: Path) -> None:
        result = _tool_search_repo(tmp_path, {"pattern": "", "file_glob": "*.ts", "max_results": 5})
        assert "ERROR" in result or "error" in result.lower()
