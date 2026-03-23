"""Tests for domain-graph.snapshot_builder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "contracts"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "domain_graph"))

from doramagic_contracts.domain_graph import DomainSnapshot, SnapshotBuilderInput  # noqa: E402
from doramagic_contracts.envelope import ErrorCodes  # noqa: E402
from doramagic_domain_graph.snapshot_builder import run_snapshot_builder  # noqa: E402

FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "sim2_snapshot_input.json"


def _model_validate(model_class, payload):
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(payload)
    return model_class(**payload)


def _fixture_input(tmp_path: Path) -> SnapshotBuilderInput:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["config"]["output_dir"] = str(tmp_path / payload["domain_id"])
    return _model_validate(SnapshotBuilderInput, payload)


def test_run_snapshot_builder_success_flow(tmp_path: Path) -> None:
    input_data = _fixture_input(tmp_path)

    result = run_snapshot_builder(input_data)

    assert result.status == "ok"
    assert result.data is not None
    assert result.data.stats.brick_count >= 3

    output_dir = Path(input_data.config.output_dir)
    snapshot_path = output_dir / result.data.domain_bricks_path
    manifest_path = output_dir / result.data.snapshot_manifest_path

    assert snapshot_path.exists()
    assert manifest_path.exists()

    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot = _model_validate(DomainSnapshot, snapshot_payload)
    assert len(snapshot.bricks) >= 3
    assert all(brick.brick_id.startswith("B-calorie-tracking-") for brick in snapshot.bricks)
    assert all(brick.signal not in ("CONTESTED", "DIVERGENT") for brick in snapshot.bricks)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["snapshot_version"]
    assert manifest["stats"]["brick_count"] == len(snapshot.bricks)


def test_empty_fingerprints_returns_blocked(tmp_path: Path) -> None:
    input_data = _fixture_input(tmp_path)
    input_data.fingerprints = []

    result = run_snapshot_builder(input_data)

    assert result.status == "blocked"
    assert result.error_code == ErrorCodes.INPUT_INVALID
    assert result.data is None


def test_high_min_support_returns_degraded(tmp_path: Path) -> None:
    input_data = _fixture_input(tmp_path)
    input_data.config.min_support_for_brick = 99

    result = run_snapshot_builder(input_data)

    assert result.status == "degraded"
    assert result.data is not None
    assert result.data.stats.brick_count == 0

    snapshot_path = Path(input_data.config.output_dir) / result.data.domain_bricks_path
    snapshot = _model_validate(
        DomainSnapshot,
        json.loads(snapshot_path.read_text(encoding="utf-8")),
    )
    assert snapshot.bricks == []


def test_domain_truth_is_non_empty_and_mentions_domain(tmp_path: Path) -> None:
    input_data = _fixture_input(tmp_path)

    result = run_snapshot_builder(input_data)

    assert result.data is not None
    truth_path = Path(input_data.config.output_dir) / result.data.domain_truth_path
    truth_md = truth_path.read_text(encoding="utf-8")

    assert truth_md.strip()
    assert "卡路里追踪" in truth_md
    assert "Use AI-based food recognition for calorie estimation" in truth_md
