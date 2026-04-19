"""Tests for QG-10/11/12 content quality warnings in _con_validate_v2_handler.

QG-10: placeholder detection — unexpanded {file}/{path}/etc. tokens
QG-11: modality/consequence logic reversal heuristic
QG-12: evidence_refs type/locator consistency
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest
from doramagic_agent_core.state.schema import AgentState
from doramagic_constraint_agent.sop.constraint_phases_v2 import (
    _con_validate_v2_handler,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_ALL_KINDS = (
    "domain_rule",
    "architecture_guardrail",
    "claim_boundary",
    "operational_lesson",
    "resource_boundary",
)


def _make_valid_jsonl(n_total: int = 100) -> str:
    """Build JSONL with n_total constraints that pass all hard gates.

    Distribution guarantees:
    - QG-01: n_total >= 80
    - QG-02: all 5 kinds present
    - QG-03: claim_boundary >= 5% (every 5th is claim_boundary)
    - QG-04: domain_rule + architecture_guardrail combined > 50%
    - QG-09: no fatal+machine_checkable, so gate never fires
    """
    constraints = []
    for i in range(n_total):
        if i % 5 == 2:
            kind = "claim_boundary"
        elif i % 2 == 0:
            kind = "domain_rule"
        else:
            kind = "architecture_guardrail"
        # Ensure all 5 kinds appear at least once
        if i < len(_ALL_KINDS):
            kind = _ALL_KINDS[i]
        constraints.append(
            {
                "constraint_id": f"C-{i:04d}",
                "constraint_kind": kind,
                "severity": "medium",
                "modality": "should",
                "core": {
                    "action": "设置合理的超时参数",
                    "when": "初始化连接时",
                },
                "consequence_description": "可以提升系统稳定性",
                "validation_threshold": None,
                "machine_checkable": False,
                "tags": [],
                "confidence": {
                    "evidence_refs": [],
                },
            }
        )
    return "\n".join(json.dumps(c) for c in constraints)


def _build_run_dir(tmp_path: Path, jsonl_content: str) -> Path:
    """Write JSONL to output/LATEST.jsonl and create the artifacts dir."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "LATEST.jsonl").write_text(jsonl_content, encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True)
    return tmp_path


def _make_state(run_dir: Path) -> AgentState:
    return AgentState(
        blueprint_id="test-bp-000",
        run_dir=str(run_dir),
    )


def _run(coro):  # type: ignore[no-untyped-def]
    """Synchronous helper to run a coroutine via asyncio.run."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# QG-10 — placeholder detection
# ---------------------------------------------------------------------------


class TestQG10PlaceholderDetection:
    """QG-10 WARN fires when any constraint field contains an unexpanded placeholder."""

    def test_qg10_placeholder_detection_file_in_validation_threshold(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """validation_threshold containing {file} triggers QG-10 WARN."""
        constraints = json.loads("[" + _make_valid_jsonl().replace("\n", ",") + "]")
        constraints[0]["validation_threshold"] = "grep pattern {file} | wc -l"

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed", f"Hard gate unexpectedly failed: {result.error}"
        qg10_warnings = [r for r in caplog.records if "QG-10" in r.message]
        assert len(qg10_warnings) > 0, "Expected QG-10 WARN but none emitted"

    def test_qg10_placeholder_detection_path_in_locator(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """{path} placeholder inside evidence_refs[].locator triggers QG-10."""
        constraints = json.loads("[" + _make_valid_jsonl().replace("\n", ",") + "]")
        constraints[1]["confidence"] = {
            "evidence_refs": [
                {
                    "type": "source_code",
                    "locator": "{path}/module.py:42",
                    "summary": "relevant code",
                }
            ]
        }

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg10_warnings = [r for r in caplog.records if "QG-10" in r.message]
        assert len(qg10_warnings) > 0, "Expected QG-10 WARN for {path} in locator"

    def test_qg10_placeholder_detection_todo_in_action(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """<TODO> placeholder in core.action triggers QG-10."""
        constraints = json.loads("[" + _make_valid_jsonl().replace("\n", ",") + "]")
        constraints[2]["core"]["action"] = "使用 <TODO> 方法处理数据"

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg10_warnings = [r for r in caplog.records if "QG-10" in r.message]
        assert len(qg10_warnings) > 0, "Expected QG-10 WARN for <TODO> in action"

    def test_qg10_clean_no_warn(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """No placeholder tokens → QG-10 must NOT emit a WARN."""
        run_dir = _build_run_dir(tmp_path, _make_valid_jsonl())
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg10_warn_msgs = [r for r in caplog.records if "QG-10" in r.message and "WARN" in r.message]
        assert len(qg10_warn_msgs) == 0, "Unexpected QG-10 WARN on clean fixture"

    def test_qg10_shell_dollar_var_not_flagged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Real shell ${VAR} syntax must NOT trigger QG-10."""
        constraints = json.loads("[" + _make_valid_jsonl().replace("\n", ",") + "]")
        constraints[0]["validation_threshold"] = "echo ${HOME}/config.json | wc -c"

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg10_warn_msgs = [r for r in caplog.records if "QG-10" in r.message and "WARN" in r.message]
        assert len(qg10_warn_msgs) == 0, "${VAR} incorrectly flagged as placeholder"


# ---------------------------------------------------------------------------
# QG-11 — modality / consequence logic reversal
# ---------------------------------------------------------------------------


class TestQG11LogicReversal:
    """QG-11 WARN fires when modality+action direction contradicts consequence."""

    def test_qg11_logic_reversal_must_plus_negative_consequence(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """must + positive action + negative consequence → QG-11 WARN above 2% threshold."""
        constraints = json.loads("[" + _make_valid_jsonl(100).replace("\n", ",") + "]")
        # Inject 5 reversals — 5% > threshold of max(1, int(100*0.02))=2 → warn
        for i in range(5):
            constraints[i]["modality"] = "must"
            constraints[i]["core"]["action"] = "使用该方法处理请求"
            constraints[i]["consequence_description"] = "会导致系统崩溃和数据丢失"

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg11_warnings = [r for r in caplog.records if "QG-11" in r.message]
        assert len(qg11_warnings) > 0, "Expected QG-11 WARN but none emitted"

    def test_qg11_no_warn_below_threshold(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Only 1 reversal out of 100 constraints → below 2% threshold → no WARN."""
        constraints = json.loads("[" + _make_valid_jsonl(100).replace("\n", ",") + "]")
        # 1 reversal: threshold = max(1, int(100*0.02)) = 2; 1 is NOT > 2
        constraints[0]["modality"] = "must"
        constraints[0]["core"]["action"] = "使用该方法处理请求"
        constraints[0]["consequence_description"] = "会导致系统崩溃和数据丢失"

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg11_warn_msgs = [r for r in caplog.records if "QG-11" in r.message and "WARN" in r.message]
        assert len(qg11_warn_msgs) == 0, "Unexpected QG-11 WARN (count=1 <= threshold=2)"

    def test_qg11_must_with_negative_consequence_fires(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """modality=must + positive-verb action + negative consequence → QG-11 WARN."""
        constraints = json.loads("[" + _make_valid_jsonl(100).replace("\n", ",") + "]")
        for i in range(6):
            constraints[i]["modality"] = "must"
            constraints[i]["core"]["action"] = "启用该功能"
            constraints[i]["consequence_description"] = "引起内存泄露和系统错误"

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg11_warnings = [r for r in caplog.records if "QG-11" in r.message]
        assert len(qg11_warnings) > 0, (
            "QG-11 must fire for must+positive-action+negative-consequence"
        )


# ---------------------------------------------------------------------------
# QG-12 — evidence_refs type/locator consistency
# ---------------------------------------------------------------------------


class TestQG12EvidenceTypeMismatch:
    """QG-12 WARN fires when evidence_refs[].type does not match locator extension."""

    def test_qg12_evidence_type_mismatch_source_code_with_md(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """type='source_code' with locator='SKILL.md' → mismatch → QG-12 WARN."""
        constraints = json.loads("[" + _make_valid_jsonl(100).replace("\n", ",") + "]")
        # Inject 8 mismatches → 8% > 5% threshold
        for i in range(8):
            constraints[i]["confidence"] = {
                "evidence_refs": [
                    {
                        "type": "source_code",
                        "locator": "SKILL.md",
                        "summary": "documentation file",
                    }
                ]
            }

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg12_warnings = [r for r in caplog.records if "QG-12" in r.message]
        assert len(qg12_warnings) > 0, "Expected QG-12 WARN for source_code+.md mismatch"

    def test_qg12_evidence_type_mismatch_document_with_py(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """type='document' with locator='module.py:42' → mismatch → QG-12 WARN."""
        constraints = json.loads("[" + _make_valid_jsonl(100).replace("\n", ",") + "]")
        for i in range(8):
            constraints[i]["confidence"] = {
                "evidence_refs": [
                    {
                        "type": "document",
                        "locator": "src/module.py:42",
                        "summary": "source code line",
                    }
                ]
            }

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg12_warnings = [r for r in caplog.records if "QG-12" in r.message]
        assert len(qg12_warnings) > 0, "Expected QG-12 WARN for document+.py mismatch"

    def test_qg12_no_warn_correct_source_code_locator(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """type='source_code' with .py locator → correct → no QG-12 WARN."""
        constraints = json.loads("[" + _make_valid_jsonl(100).replace("\n", ",") + "]")
        for i in range(10):
            constraints[i]["confidence"] = {
                "evidence_refs": [
                    {
                        "type": "source_code",
                        "locator": "src/data/loader.py:123",
                        "summary": "data loader code",
                    }
                ]
            }

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg12_warn_msgs = [r for r in caplog.records if "QG-12" in r.message and "WARN" in r.message]
        assert len(qg12_warn_msgs) == 0, "Unexpected QG-12 WARN for correct source_code locator"

    def test_qg12_no_warn_below_5pct_threshold(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Only 3 mismatches out of 100 (3%) → below 5% threshold → no WARN."""
        constraints = json.loads("[" + _make_valid_jsonl(100).replace("\n", ",") + "]")
        for i in range(3):
            constraints[i]["confidence"] = {
                "evidence_refs": [
                    {
                        "type": "source_code",
                        "locator": "README.md",
                        "summary": "doc",
                    }
                ]
            }

        run_dir = _build_run_dir(tmp_path, "\n".join(json.dumps(c) for c in constraints))
        state = _make_state(run_dir)

        with caplog.at_level(logging.WARNING):
            result = _run(_con_validate_v2_handler(state, run_dir))

        assert result.status == "completed"
        qg12_warn_msgs = [r for r in caplog.records if "QG-12" in r.message and "WARN" in r.message]
        assert len(qg12_warn_msgs) == 0, "Unexpected QG-12 WARN (3 mismatches <= threshold of 5)"
