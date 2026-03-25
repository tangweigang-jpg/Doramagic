from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "data" / "fixtures"
PIPELINE_SCRIPT = PROJECT_ROOT / "skills" / "doramagic" / "scripts" / "doramagic_pipeline.py"


@pytest.fixture()
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture()
def pipeline_script() -> Path:
    return PIPELINE_SCRIPT


@pytest.fixture()
def good_repo_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "snapshots" / "calorie-tracking"


@pytest.fixture()
def run_pipeline(tmp_path: Path, pipeline_script: Path, project_root: Path):
    def _run(need: Dict[str, Any], repos: List[Dict[str, Any]]) -> subprocess.CompletedProcess[str]:
        need_path = tmp_path / "need_profile.json"
        repos_path = tmp_path / "repos.json"
        run_dir = tmp_path / "run"
        output_dir = tmp_path / "delivery"

        need_path.write_text(json.dumps(need, ensure_ascii=False, indent=2), encoding="utf-8")
        repos_path.write_text(json.dumps(repos, ensure_ascii=False, indent=2), encoding="utf-8")

        return subprocess.run(
            [
                sys.executable,
                str(pipeline_script),
                "--need-profile",
                str(need_path),
                "--repos",
                str(repos_path),
                "--run-dir",
                str(run_dir),
                "--bricks-dir",
                str(project_root / "bricks"),
                "--output",
                str(output_dir),
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )

    return _run
