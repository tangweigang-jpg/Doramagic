"""Git worktree helpers for Doramagic race rounds."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .race_config import (
    RacerName,
    canonical_module_name,
    module_branch_slug,
    module_name_from_slug,
)

RACE_METADATA_FILENAME = ".doramagic-race.json"


@dataclass(frozen=True)
class ActiveRace:
    round_num: int
    module_name: str
    module_slug: str
    racer: RacerName
    branch_name: str
    path: Path
    head_sha: str


def _run_git(repo_root: Path, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        ["git", "-C", str(repo_root)] + args,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or "unknown git error"
        raise RuntimeError("git {0} failed: {1}".format(" ".join(args), detail))
    return completed


def _resolve_repo_root(start_path: Optional[Path] = None) -> Path:
    override = os.environ.get("DORAMAGIC_RACE_REPO_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    probe_path = (start_path or Path.cwd()).expanduser().resolve()
    completed = subprocess.run(
        ["git", "-C", str(probe_path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Unable to resolve git repo root from {0}".format(probe_path))
    return Path(completed.stdout.strip()).resolve()


def _resolve_output_root(repo_root: Path) -> Path:
    override = os.environ.get("DORAMAGIC_RACE_OUTPUT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return (repo_root / "races").resolve()


def _resolve_worktree_root(repo_root: Path) -> Path:
    override = os.environ.get("DORAMAGIC_RACE_WORKTREE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return (repo_root.parent / "{0}-races".format(repo_root.name)).resolve()


def _branch_name(round_num: int, module_name: str, racer: RacerName) -> str:
    return "race/r{0:02d}/{1}/{2}".format(round_num, module_branch_slug(module_name), racer.value)


def _parse_worktree_blocks(raw_text: str) -> List[Dict[str, str]]:
    blocks = []
    current: Dict[str, str] = {}
    for line in raw_text.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue

        key, _, value = line.partition(" ")
        current[key] = value

    if current:
        blocks.append(current)
    return blocks


def _read_race_metadata(worktree_path: Path, branch_name: str, head_sha: str) -> Optional[ActiveRace]:
    metadata_path = worktree_path / RACE_METADATA_FILENAME
    if not metadata_path.exists():
        return None

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    return ActiveRace(
        round_num=int(data["round_num"]),
        module_name=str(data["module_name"]),
        module_slug=str(data["module_slug"]),
        racer=RacerName.coerce(str(data["racer_name"])),
        branch_name=str(data["branch_name"]),
        path=worktree_path,
        head_sha=head_sha,
    )


def _fallback_active_race(worktree_path: Path, branch_name: str, head_sha: str) -> Optional[ActiveRace]:
    prefix = "race/"
    if not branch_name.startswith(prefix):
        return None

    segments = branch_name.split("/")
    if len(segments) != 4 or not segments[1].startswith("r"):
        return None

    round_num = int(segments[1][1:])
    module_slug = segments[2]
    racer = RacerName.coerce(segments[3])
    return ActiveRace(
        round_num=round_num,
        module_name=module_name_from_slug(module_slug),
        module_slug=module_slug,
        racer=racer,
        branch_name=branch_name,
        path=worktree_path,
        head_sha=head_sha,
    )


def create_race_worktree(round_num: int, module_name: str, racer_name: str) -> Path:
    """Create or reuse a dedicated git worktree for a racer."""

    repo_root = _resolve_repo_root()
    worktree_root = _resolve_worktree_root(repo_root)
    racer = RacerName.coerce(racer_name)
    resolved_module_name = canonical_module_name(module_name)
    module_slug = module_branch_slug(resolved_module_name)
    branch_name = _branch_name(round_num, resolved_module_name, racer)
    target_path = worktree_root / "r{0:02d}".format(round_num) / module_slug / racer.value

    for race in list_active_races():
        if race.branch_name == branch_name:
            return race.path

    if target_path.exists():
        raise FileExistsError("Worktree path already exists: {0}".format(target_path))

    worktree_root.mkdir(parents=True, exist_ok=True)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    branch_exists = _run_git(
        repo_root,
        ["rev-parse", "--verify", "--quiet", branch_name],
        check=False,
    ).returncode == 0

    if branch_exists:
        _run_git(repo_root, ["worktree", "add", str(target_path), branch_name])
    else:
        _run_git(repo_root, ["worktree", "add", "-b", branch_name, str(target_path), "HEAD"])

    metadata = {
        "round_num": round_num,
        "module_name": resolved_module_name,
        "module_slug": module_slug,
        "racer_name": racer.name,
        "branch_name": branch_name,
        "repo_root": str(repo_root),
    }
    (target_path / RACE_METADATA_FILENAME).write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return target_path


def cleanup_race_worktree(path: Path) -> None:
    """Remove a previously created git worktree."""

    repo_root = _resolve_repo_root()
    resolved_path = Path(path).expanduser().resolve()
    active_paths = {race.path for race in list_active_races()}
    if resolved_path not in active_paths:
        raise ValueError("Not an active race worktree: {0}".format(resolved_path))

    _run_git(repo_root, ["worktree", "remove", "--force", str(resolved_path)])
    _run_git(repo_root, ["worktree", "prune"])

    if resolved_path.exists():
        shutil.rmtree(resolved_path, ignore_errors=True)


def list_active_races() -> List[ActiveRace]:
    """List active race worktrees tracked by git."""

    repo_root = _resolve_repo_root()
    completed = _run_git(repo_root, ["worktree", "list", "--porcelain"])
    races: List[ActiveRace] = []

    for block in _parse_worktree_blocks(completed.stdout):
        branch_ref = block.get("branch")
        if not branch_ref:
            continue

        branch_name = branch_ref.replace("refs/heads/", "", 1)
        worktree_path = Path(block["worktree"]).resolve()
        head_sha = block.get("HEAD", "")

        race = _read_race_metadata(worktree_path, branch_name, head_sha)
        if race is None:
            race = _fallback_active_race(worktree_path, branch_name, head_sha)

        if race is not None:
            races.append(race)

    races.sort(key=lambda item: (item.round_num, item.module_slug, item.racer.value))
    return races
