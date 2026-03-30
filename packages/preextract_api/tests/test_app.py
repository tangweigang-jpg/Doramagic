"""
Tests for Doramagic Pre-extract API (api.read)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 插入依赖路径
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 设置环境变量以指向正确的测试数据
os.environ["DORAMAGIC_API_DATA_DIR"] = "data/fixtures/snapshots"

from doramagic_preextract_api.app import app, load_snapshots

client = TestClient(app)


@pytest.fixture(autouse=True)
def reload_data():
    load_snapshots()


def test_get_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_domains():
    response = client.get("/domains")
    assert response.status_code == 200
    data = response.json()
    assert "domains" in data
    assert data["total_count"] >= 1

    domain_ids = [d["domain_id"] for d in data["domains"]]
    assert "calorie-tracking" in domain_ids


def test_get_bricks():
    response = client.get("/domains/calorie-tracking/bricks")
    assert response.status_code == 200
    data = response.json()
    assert data["domain_id"] == "calorie-tracking"
    assert "bricks" in data
    assert len(data["bricks"]) > 0
    assert data["bricks"][0]["brick_id"].startswith("B-calorie-tracking")


def test_get_truth():
    response = client.get("/domains/calorie-tracking/truth")
    assert response.status_code == 200
    data = response.json()
    assert data["domain_id"] == "calorie-tracking"
    assert "truth_md" in data
    assert "# Domain Truth" in data["truth_md"]


def test_get_not_found():
    response = client.get("/domains/nonexistent/bricks")
    assert response.status_code == 404
    assert "Domain not found" in response.json()["detail"]


def test_query_atoms_empty(tmp_path, monkeypatch):
    # 因为 fixture 里没有 atoms.json，所以默认应该返回空列表
    response = client.get("/domains/calorie-tracking/atoms")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert len(data["atoms"]) == 0


def test_query_atoms_with_data(tmp_path, monkeypatch):
    # 手动创建一个带 atoms 的 mock 领域
    mock_dir = tmp_path / "mock-domain"
    mock_dir.mkdir()

    manifest = {
        "schema_version": "dm.snapshot-builder-output.v1",
        "domain_id": "mock-domain",
        "snapshot_version": "2026-03-19T21:00:00Z",
        "domain_bricks_path": "DOMAIN_BRICKS.json",
        "domain_truth_path": "DOMAIN_TRUTH.md",
        "atoms_parquet_path": None,
        "snapshot_manifest_path": "snapshot_manifest.json",
        "stats": {
            "project_count": 1,
            "atom_count": 2,
            "cluster_count": 0,
            "brick_count": 0,
            "deprecation_count": 0,
            "coverage_ratio": 1.0,
        },
    }
    with open(mock_dir / "snapshot_manifest.json", "w") as f:
        json.dump(manifest, f)

    bricks = {
        "schema_version": "dm.domain-snapshot.v1",
        "domain_id": "mock-domain",
        "domain_display_name": "Mock Domain",
        "snapshot_version": "2026-03-19T21:00:00Z",
        "bricks": [],
        "atom_clusters": [],
        "stats": manifest["stats"],
    }
    with open(mock_dir / "DOMAIN_BRICKS.json", "w") as f:
        json.dump(bricks, f)

    atoms = [
        {
            "atom_id": "A1",
            "knowledge_type": "capability",
            "subject": "AI",
            "predicate": "does",
            "object": "coding",
            "scope": "test",
            "normative_force": "must",
            "confidence": "high",
            "evidence_refs": [],
            "source_card_ids": [],
        },
        {
            "atom_id": "A2",
            "knowledge_type": "constraint",
            "subject": "Storage",
            "predicate": "is",
            "object": "local",
            "scope": "test",
            "normative_force": "must",
            "confidence": "medium",
            "evidence_refs": [],
            "source_card_ids": [],
        },
    ]
    with open(mock_dir / "atoms.json", "w") as f:
        json.dump(atoms, f)

    monkeypatch.setenv("DORAMAGIC_API_DATA_DIR", str(tmp_path))
    load_snapshots()

    # 测试基本查询
    response = client.get("/domains/mock-domain/atoms")
    assert response.status_code == 200
    assert response.json()["total_count"] == 2

    # 测试类型过滤
    response = client.get("/domains/mock-domain/atoms?knowledge_type=capability")
    assert response.json()["total_count"] == 1
    assert response.json()["atoms"][0]["atom_id"] == "A1"

    # 测试置信度过滤
    response = client.get("/domains/mock-domain/atoms?confidence_min=high")
    assert response.json()["total_count"] == 1
    assert response.json()["atoms"][0]["atom_id"] == "A1"

    # 测试关键字过滤
    response = client.get("/domains/mock-domain/atoms?keyword=local")
    assert response.json()["total_count"] == 1
    assert response.json()["atoms"][0]["atom_id"] == "A2"


def test_get_deprecations():
    response = client.get("/domains/calorie-tracking/deprecations")
    assert response.status_code == 200
    data = response.json()
    assert data["domain_id"] == "calorie-tracking"
    assert "deprecations" in data


def test_get_project_health():
    # 测试已知项目
    response = client.get("/domains/calorie-tracking/health/ai_calorie_tracker")
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "healthy"

    # 测试未知项目
    response = client.get("/domains/calorie-tracking/health/unknown_p")
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "unknown"
