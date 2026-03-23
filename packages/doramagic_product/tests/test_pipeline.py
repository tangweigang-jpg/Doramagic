"""Tests for the Doramagic product pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "contracts"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "doramagic_product"))

from doramagic_contracts.base import CandidateQualitySignals, DiscoveryCandidate, SearchCoverageItem  # noqa: E402
from doramagic_contracts.cross_project import DiscoveryResult  # noqa: E402
from doramagic_product.pipeline import CandidateInfo, DoramagicProductPipeline  # noqa: E402


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.content = b""

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None, **kwargs):
        self.calls.append({"url": url, "params": params, "headers": headers, "kwargs": kwargs})
        return _FakeResponse(self.payload)


def _make_local_repo(path: Path, readme_title: str, storage_file: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text(
        "# {0}\n\nA local-first app for recipe planning and household meal tracking.\n".format(readme_title),
        encoding="utf-8",
    )
    (path / "app.py").write_text(
        "def main():\n    return 'ok'\n",
        encoding="utf-8",
    )
    (path / storage_file).write_text("{}", encoding="utf-8")
    (path / "requirements.txt").write_text("fastapi\nsqlite3\n", encoding="utf-8")
    return path


def test_build_need_profile_heuristic_extracts_keywords() -> None:
    pipeline = DoramagicProductPipeline(runs_dir=PROJECT_ROOT / "tmp-test-runs")

    profile = pipeline.build_need_profile("我想做一个管理家庭菜谱的 skill")

    assert profile.raw_input == "我想做一个管理家庭菜谱的 skill"
    assert any(keyword in profile.keywords for keyword in ["家庭菜谱", "菜谱", "家庭", "管理"])
    assert profile.search_directions
    assert any(direction.priority == "high" for direction in profile.search_directions)


def test_discover_candidates_maps_github_response(tmp_path: Path) -> None:
    payload = {
        "items": [
            {
                "name": "mealie",
                "full_name": "demo/mealie",
                "html_url": "https://github.com/demo/mealie",
                "description": "Recipe manager and meal planner",
                "stargazers_count": 4200,
                "forks_count": 120,
                "updated_at": "2026-03-01T00:00:00Z",
                "default_branch": "main",
                "license": {"spdx_id": "MIT"},
                "topics": ["recipe", "meal-planner", "kitchen"],
            }
        ]
    }
    fake_client = _FakeHttpClient(payload)
    pipeline = DoramagicProductPipeline(runs_dir=tmp_path / "runs", http_client=fake_client)
    profile = pipeline.build_need_profile("我想做一个管理家庭菜谱的 skill")

    discovery, candidate_infos, warnings = pipeline.discover_candidates(profile)

    assert not warnings
    assert len(discovery.candidates) == 1
    assert discovery.candidates[0].url == "https://github.com/demo/mealie"
    assert candidate_infos[0].owner == "demo"
    assert candidate_infos[0].repo == "mealie"
    assert fake_client.calls


def test_pipeline_run_writes_delivery_bundle(tmp_path: Path, monkeypatch) -> None:
    repo_a = _make_local_repo(tmp_path / "repo_a", "Recipe Slate", "recipes.json")
    repo_b = _make_local_repo(tmp_path / "repo_b", "Meal Ledger", "storage.sqlite")

    pipeline = DoramagicProductPipeline(runs_dir=tmp_path / "runs")
    monkeypatch.setattr(pipeline, "_try_subprocess", lambda *args, **kwargs: None)

    def fake_discover(need_profile):
        candidates = [
            DiscoveryCandidate(
                candidate_id="cand-001",
                name="recipe-slate",
                url="https://github.com/example/recipe-slate",
                type="github_repo",
                relevance="high",
                contribution="Recipe planning reference",
                quick_score=9.1,
                quality_signals=CandidateQualitySignals(
                    stars=150,
                    forks=12,
                    last_updated="2026-03-01",
                    has_readme=True,
                    issue_activity="medium",
                    license="MIT",
                ),
                selected_for_phase_c=True,
                selected_for_phase_d=True,
            ),
            DiscoveryCandidate(
                candidate_id="cand-002",
                name="meal-ledger",
                url="https://github.com/example/meal-ledger",
                type="github_repo",
                relevance="high",
                contribution="Meal tracking reference",
                quick_score=8.7,
                quality_signals=CandidateQualitySignals(
                    stars=120,
                    forks=8,
                    last_updated="2026-02-27",
                    has_readme=True,
                    issue_activity="medium",
                    license="Apache-2.0",
                ),
                selected_for_phase_c=True,
                selected_for_phase_d=True,
            ),
        ]
        infos = [
            CandidateInfo(
                candidate=candidates[0],
                owner="example",
                repo="recipe-slate",
                default_branch="main",
                description="Recipe planning reference",
                license_name="MIT",
                local_source=repo_a,
            ),
            CandidateInfo(
                candidate=candidates[1],
                owner="example",
                repo="meal-ledger",
                default_branch="main",
                description="Meal tracking reference",
                license_name="Apache-2.0",
                local_source=repo_b,
            ),
        ]
        discovery = DiscoveryResult(
            candidates=candidates,
            search_coverage=[
                SearchCoverageItem(direction="recipe", status="covered", notes=None),
                SearchCoverageItem(direction="meal planner", status="covered", notes=None),
            ],
            no_candidate_reason=None,
        )
        return discovery, infos, []

    monkeypatch.setattr(pipeline, "discover_candidates", fake_discover)

    result = pipeline.run("我想做一个管理家庭菜谱的 skill")

    assert result.validation_status == "PASS"
    assert result.skill_path.exists()
    assert result.provenance_path.exists()
    assert result.limitations_path.exists()

    skill_md = result.skill_path.read_text(encoding="utf-8")
    provenance_md = result.provenance_path.read_text(encoding="utf-8")
    validation_report = result.delivery_dir.joinpath("validation_report.json").read_text(encoding="utf-8")

    assert "## Why This Skill Exists" in skill_md
    assert "## Community Gotchas" in skill_md
    assert "https://github.com/example/recipe-slate" in provenance_md
    assert "\"status\": \"PASS\"" in validation_report
