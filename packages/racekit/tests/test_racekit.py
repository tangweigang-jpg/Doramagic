"""Racekit tests for Round 0 tooling."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "packages" / "racekit"))

from doramagic_racekit import (
    ROUND_RACE_CONFIGS,
    RacerName,
    cleanup_race_worktree,
    create_race_worktree,
    generate_brief,
    generate_review_template,
    get_round_config,
    list_active_races,
    module_branch_slug,
    score_submission,
)


def _run(args, cwd):
    completed = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed


def _init_git_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo_root)
    _run(["git", "config", "user.name", "Racekit Test"], cwd=repo_root)
    _run(["git", "config", "user.email", "racekit@example.com"], cwd=repo_root)
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=repo_root)
    _run(["git", "commit", "-m", "seed"], cwd=repo_root)
    return repo_root


class TestRaceWorkspace:
    def test_create_list_cleanup_worktree(self, tmp_path, monkeypatch):
        repo_root = _init_git_repo(tmp_path)
        worktree_root = tmp_path / "worktrees"

        monkeypatch.setenv("DORAMAGIC_RACE_REPO_ROOT", str(repo_root))
        monkeypatch.setenv("DORAMAGIC_RACE_WORKTREE_ROOT", str(worktree_root))

        path = create_race_worktree(1, "extraction.stage15_agentic", "S2_CODEX")
        assert path.exists()
        assert path == worktree_root / "r01" / "stage15_agentic" / "s2-codex"

        branch_name = _run(["git", "branch", "--show-current"], cwd=path).stdout.strip()
        assert branch_name == "race/r01/stage15_agentic/s2-codex"

        races = list_active_races()
        assert len(races) == 1
        assert races[0].round_num == 1
        assert races[0].module_name == "extraction.stage15_agentic"
        assert races[0].racer == RacerName.S2_CODEX

        cleanup_race_worktree(path)
        assert list_active_races() == []
        assert not path.exists()


class TestRaceBrief:
    def test_generate_brief_from_spec(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DORAMAGIC_RACE_REPO_ROOT", str(REPO_ROOT))
        monkeypatch.setenv("DORAMAGIC_RACE_OUTPUT_ROOT", str(tmp_path / "races"))

        brief_path = generate_brief(
            1,
            "extraction.stage15_agentic",
            "Codex",
            str(REPO_ROOT / "docs" / "dev-plan-codex-module-specs.md"),
        )

        content = brief_path.read_text(encoding="utf-8")
        assert brief_path.exists()
        assert "Module: `extraction.stage15_agentic`" in content
        assert "## 模块职责" in content
        assert "## 输入 Schema" in content
        assert "## 输出 Schema" in content
        assert "## 验收标准" in content
        assert "## 设计自由度" in content
        assert "`data/fixtures/sim2_need_profile.json`" in content


class TestRaceReview:
    def test_generate_review_template_and_score_submission(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DORAMAGIC_RACE_REPO_ROOT", str(REPO_ROOT))
        monkeypatch.setenv("DORAMAGIC_RACE_OUTPUT_ROOT", str(tmp_path / "races"))

        review_path = generate_review_template(2, "cross-project.compare")
        content = review_path.read_text(encoding="utf-8")
        assert "Contract 正确性 | weight=25 | score=" in content

        filled = content.replace("Contract 正确性 | weight=25 | score=", "Contract 正确性 | weight=25 | score=9")
        filled = filled.replace("可验证性 | weight=20 | score=", "可验证性 | weight=20 | score=8")
        filled = filled.replace("集成适配度 | weight=20 | score=", "集成适配度 | weight=20 | score=7.5")
        filled = filled.replace("代码清晰度 | weight=15 | score=", "代码清晰度 | weight=15 | score=8")
        filled = filled.replace("性能成本 | weight=10 | score=", "性能成本 | weight=10 | score=7")
        filled = filled.replace("运维稳定性 | weight=10 | score=", "运维稳定性 | weight=10 | score=9")
        review_path.write_text(filled, encoding="utf-8")

        assert score_submission(str(review_path)) == pytest.approx(81.5)


class TestRaceConfig:
    def test_round_configs_cover_rounds_one_to_five(self):
        assert sorted(ROUND_RACE_CONFIGS) == [1, 2, 3, 4, 5]

    def test_round_one_and_round_five_pairings(self):
        round_one = get_round_config(1)
        assert round_one.tracks[0].module_name == "extraction.stage1_scan"
        assert round_one.tracks[0].racers == (RacerName.S1_SONNET, RacerName.S4_GLM5)
        assert round_one.tracks[1].module_name == "extraction.stage15_agentic"
        assert round_one.tracks[1].racers == (RacerName.S2_CODEX, RacerName.S3_GEMINI)

        round_five = get_round_config(5)
        assert round_five.tracks[0].module_name == "domain-graph.snapshot_builder"
        assert round_five.tracks[0].racers == (RacerName.S2_CODEX, RacerName.S4_GLM5)
        assert round_five.tracks[1].module_name == "api.read"
        assert round_five.tracks[1].racers == (RacerName.S1_SONNET, RacerName.S3_GEMINI)

    def test_module_branch_slug_uses_canonical_aliases(self):
        assert module_branch_slug("cross_project.compare") == "compare"
        assert module_branch_slug("apps.preextract_api.read") == "api_read"
