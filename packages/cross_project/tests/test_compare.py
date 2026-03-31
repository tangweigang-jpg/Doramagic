"""Compare module tests."""

from __future__ import annotations

import json
from pathlib import Path

from doramagic_contracts.base import (
    EvidenceRef,
    KnowledgeAtom,
    ProjectFingerprint,
    RepoRef,
)
from doramagic_contracts.cross_project import CompareConfig, CompareInput
from doramagic_contracts.envelope import ErrorCodes
from doramagic_cross_project.compare import run_compare


def _repo(repo_id: str) -> RepoRef:
    return RepoRef(
        repo_id=repo_id,
        full_name=f"example/{repo_id}",
        url=f"https://github.com/example/{repo_id}",
        default_branch="main",
        commit_sha="abc123",
        local_path=f"/tmp/{repo_id}",
    )


def _evidence(path: str, line: int) -> EvidenceRef:
    return EvidenceRef(
        kind="file_line",
        path=path,
        start_line=line,
        end_line=line + 2,
        snippet="evidence",
    )


def _atom(
    atom_id: str,
    knowledge_type: str,
    subject: str,
    predicate: str,
    object_value: str,
    evidence_path: str,
) -> KnowledgeAtom:
    return KnowledgeAtom(
        atom_id=atom_id,
        knowledge_type=knowledge_type,
        subject=subject,
        predicate=predicate,
        object=object_value,
        scope="runtime",
        normative_force="must",
        confidence="high",
        evidence_refs=[_evidence(evidence_path, 10)],
        source_card_ids=[atom_id],
    )


def _fingerprint(
    repo_id: str,
    atoms: list[KnowledgeAtom],
    issue_activity: str = "medium",
    sentiment: str = "positive",
) -> ProjectFingerprint:
    return ProjectFingerprint(
        project=_repo(repo_id),
        code_fingerprint={"deps": ["openai"]},
        knowledge_atoms=atoms,
        soul_graph={},
        community_signals={
            "issue_activity": issue_activity,
            "pr_merge_velocity": "fast",
            "changelog_frequency": "monthly",
            "sentiment": sentiment,
        },
    )


def _compare_input() -> CompareInput:
    fp_a = _fingerprint(
        "acc",
        [
            _atom("A-001", "interface", "food_input", "parsed_as", "json_contract", "a/parser.ts"),
            _atom(
                "A-002",
                "assembly_pattern",
                "meal_text",
                "direct_llm_parse",
                "json_macro_response",
                "a/chat.ts",
            ),
        ],
        issue_activity="low",
        sentiment="positive",
    )
    fp_b = _fingerprint(
        "foodyo",
        [
            _atom(
                "B-001",
                "interface",
                "food input",
                "parses into",
                "structured schema",
                "b/parser.ts",
            ),
            _atom("B-002", "constraint", "daily_log", "stored_in", "session_memory", "b/store.ts"),
        ],
        issue_activity="high",
        sentiment="mixed",
    )
    fp_c = _fingerprint(
        "ont",
        [
            _atom("C-001", "constraint", "daily_log", "stored_in", "browser_memory", "c/store.ts"),
        ],
        issue_activity="medium",
        sentiment="positive",
    )
    return CompareInput(
        domain_id="nutrition-calorie",
        fingerprints=[fp_a, fp_b, fp_c],
        config=CompareConfig(),
    )


class TestRunCompare:
    def test_returns_aligned_and_original_signals(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DORAMAGIC_COMPARE_OUTPUT_DIR", str(tmp_path))
        input_data = _compare_input()

        result = run_compare(input_data)

        assert result.status == "ok"
        assert result.data is not None
        signal_kinds = {signal.signal for signal in result.data.signals}
        assert "ALIGNED" in signal_kinds
        assert "ORIGINAL" in signal_kinds

    def test_single_fingerprint_returns_blocked_input_invalid(self) -> None:
        input_data = _compare_input()
        input_data.fingerprints = input_data.fingerprints[:1]

        result = run_compare(input_data)

        assert result.status == "blocked"
        assert result.error_code == ErrorCodes.INPUT_INVALID
        assert result.data is None

    def test_same_atom_wording_change_is_not_marked_original(self) -> None:
        input_data = _compare_input()

        result = run_compare(input_data)

        assert result.data is not None
        originals = [signal for signal in result.data.signals if signal.signal == "ORIGINAL"]
        assert not any(
            "food input parse schema runtime must" in signal.normalized_statement
            for signal in originals
        )

    def test_signal_ids_are_stable(self) -> None:
        first = run_compare(_compare_input())
        second = run_compare(_compare_input())

        assert first.data is not None
        assert second.data is not None
        assert [signal.signal_id for signal in first.data.signals] == [
            signal.signal_id for signal in second.data.signals
        ]

    def test_original_notes_record_second_pass_confirmation(self) -> None:
        result = run_compare(_compare_input())

        assert result.data is not None
        original_notes = [
            signal.notes for signal in result.data.signals if signal.signal == "ORIGINAL"
        ]
        assert original_notes
        assert all("second-pass retrieval" in (note or "") for note in original_notes)

    def test_schema_mismatch_returns_blocked(self) -> None:
        input_data = _compare_input()
        input_data.fingerprints[0].schema_version = "dm.project-fingerprint.v0"

        result = run_compare(input_data)

        assert result.status == "blocked"
        assert result.error_code == ErrorCodes.SCHEMA_MISMATCH

    def test_writes_fixed_comparison_result_file(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("DORAMAGIC_COMPARE_OUTPUT_DIR", str(tmp_path))

        result = run_compare(_compare_input())

        assert result.data is not None
        output_path = tmp_path / "nutrition-calorie" / "comparison_result.json"
        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["domain_id"] == "nutrition-calorie"
