"""End-to-end tests for the Doramagic bridge pipeline.

Based on S2-Codex R07 test suite, adapted for official paths.
"""
from __future__ import annotations

import json
from pathlib import Path


def _parse_stdout_json(stdout: str) -> dict:
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def test_pipeline_with_mock_data(run_pipeline, good_repo_path: Path) -> None:
    """Use calorie-tracking fixture to run full pipeline."""
    need = {
        "user_need": "calorie tracking app",
        "keywords": ["calorie", "nutrition"],
        "domain": "health",
    }
    repos = [
        {
            "name": "calorie-tracking",
            "path": str(good_repo_path),
            "stars": 42,
            "url": "https://github.com/example/calorie-tracking",
        }
    ]

    result = run_pipeline(need, repos)

    assert result.returncode == 0, result.stderr
    payload = _parse_stdout_json(result.stdout)
    assert payload["status"] == "success"
    assert payload["repos_extracted"] == 1
    assert payload["repos_failed"] == 0

    skill_info = payload["delivery"]["SKILL.md"]
    assert Path(skill_info["path"]).exists()
    assert skill_info["size_bytes"] >= 500


def test_pipeline_handles_empty_repos(run_pipeline) -> None:
    """Empty repos list should exit 1 with error JSON."""
    need = {
        "user_need": "calorie tracking app",
        "keywords": ["calorie"],
        "domain": "health",
    }

    result = run_pipeline(need, [])

    assert result.returncode == 1
    payload = _parse_stdout_json(result.stdout)
    assert payload["status"] == "error"


def test_pipeline_handles_bad_repo_path(run_pipeline, good_repo_path: Path) -> None:
    """Bad repo path should be skipped; good repo should still produce output."""
    need = {
        "user_need": "calorie tracking app",
        "keywords": ["calorie", "nutrition"],
        "domain": "health",
    }
    repos = [
        {
            "name": "missing-repo",
            "path": str(good_repo_path.parent / "missing-repo"),
            "stars": 1,
            "url": "https://github.com/example/missing-repo",
        },
        {
            "name": "calorie-tracking",
            "path": str(good_repo_path),
            "stars": 42,
            "url": "https://github.com/example/calorie-tracking",
        },
    ]

    result = run_pipeline(need, repos)

    assert result.returncode == 0, result.stderr
    payload = _parse_stdout_json(result.stdout)
    assert payload["status"] == "success"
    assert payload["repos_extracted"] == 1
    assert payload["repos_failed"] == 1
    assert any("missing-repo" in w for w in payload["warnings"])
