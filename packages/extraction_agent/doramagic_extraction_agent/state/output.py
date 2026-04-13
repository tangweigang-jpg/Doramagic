"""Output manager — writes extraction results with versioned naming.

v6 naming scheme:
  knowledge/sources/{domain}/{bp_id}--{repo_slug}/
    blueprint.v{N}.yaml       — versioned, never overwritten
    constraints.v{N}.jsonl     — versioned, never overwritten
    LATEST.yaml                — symlink → current blueprint version
    LATEST.jsonl               — symlink → current constraint version
    manifest.json              — schema v2.0, full version history
    _history/                  — archived pre-migration files
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically: temp file -> fsync -> rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _update_symlink(link_path: Path, target_name: str) -> None:
    """Create or update a symlink atomically."""
    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
    link_path.symlink_to(target_name)


class OutputManager:
    """Manages versioned output files for one extraction project.

    Directory naming: ``{bp_id}--{repo_slug}``
    File naming: ``blueprint.v{N}.yaml``, ``constraints.v{N}.jsonl``
    LATEST pointers: symlinks to current production versions
    """

    def __init__(
        self,
        output_dir: Path,
        blueprint_id: str,
        repo_slug: str = "",
    ):
        self._blueprint_id = blueprint_id
        self._repo_slug = repo_slug

        # If output_dir doesn't already have --slug suffix, add it
        if repo_slug and f"--{repo_slug}" not in output_dir.name:
            self._output_dir = output_dir.parent / f"{blueprint_id}--{repo_slug}"
        else:
            self._output_dir = output_dir

        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._manifest = self._load_manifest()

    # ------------------------------------------------------------------
    # Blueprint
    # ------------------------------------------------------------------

    def write_blueprint(
        self,
        yaml_content: str,
        *,
        version_meta: dict[str, Any] | None = None,
    ) -> Path:
        """Write a versioned blueprint YAML. Never overwrites existing versions."""
        next_v = self._next_blueprint_version()
        filename = f"blueprint.v{next_v}.yaml"
        path = self._output_dir / filename
        _atomic_write(path, yaml_content)

        # Update LATEST symlink
        _update_symlink(self._output_dir / "LATEST.yaml", filename)

        # Update manifest
        self._manifest["latest"]["blueprint"] = filename
        entry = {
            "file": filename,
            "version": next_v,
            "extracted_at": datetime.now(UTC).isoformat(),
            **(version_meta or {}),
        }
        self._manifest["blueprint_versions"].insert(0, entry)
        self._save_manifest()

        return path

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def write_constraints(
        self,
        constraints: list[dict],
        *,
        version_meta: dict[str, Any] | None = None,
    ) -> Path:
        """Write versioned constraints JSONL."""
        next_v = self._next_constraint_version()
        filename = f"constraints.v{next_v}.jsonl"
        path = self._output_dir / filename
        content = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in constraints)
        _atomic_write(path, content)

        # Update LATEST symlink
        _update_symlink(self._output_dir / "LATEST.jsonl", filename)

        # Update manifest
        self._manifest["latest"]["constraints"] = filename
        entry = {
            "file": filename,
            "version": next_v,
            "collected_at": datetime.now(UTC).isoformat(),
            **(version_meta or {}),
        }
        self._manifest["constraint_versions"].insert(0, entry)
        self._save_manifest()

        return path

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def write_manifest(
        self,
        *,
        blueprint_id: str = "",
        domain: str = "",
        repo_url: str = "",
        commit_hash: str = "",
        sop_blueprint_version: str = "3.4",
        sop_constraint_version: str = "2.2",
        llm_model: str = "",
        total_tokens: int = 0,
        blueprint_stats: dict[str, Any] | None = None,
        constraint_stats: dict[str, Any] | None = None,
        quality_gates: dict[str, Any] | None = None,
    ) -> Path:
        """Update manifest metadata fields (preserves version history)."""
        m = self._manifest
        m["blueprint_id"] = blueprint_id or m.get("blueprint_id", self._blueprint_id)
        m["domain"] = domain or m.get("domain", "")
        m["repo_url"] = repo_url or m.get("repo_url", "")
        m["repo_slug"] = self._repo_slug or m.get("repo_slug", "")

        # Update latest blueprint version entry with stats if available
        if m["blueprint_versions"] and (blueprint_stats or quality_gates):
            latest_entry = m["blueprint_versions"][0]
            if blueprint_stats:
                latest_entry["stats"] = blueprint_stats
            if quality_gates:
                latest_entry["quality_gate"] = quality_gates
            latest_entry.setdefault("commit_hash", commit_hash)
            latest_entry.setdefault("sop_version", sop_blueprint_version)
            latest_entry.setdefault("llm_model", llm_model)
            latest_entry.setdefault("total_tokens", total_tokens)

        self._save_manifest()
        return self._output_dir / "manifest.json"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, Any]:
        manifest_path = self._output_dir / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        # Initialize empty v2.0 manifest
        return {
            "schema_version": "2.0",
            "blueprint_id": self._blueprint_id,
            "repo_slug": self._repo_slug,
            "repo_url": "",
            "domain": "",
            "display_name": "",
            "subdomains": [],
            "latest": {"blueprint": "", "constraints": ""},
            "blueprint_versions": [],
            "constraint_versions": [],
        }

    def _save_manifest(self) -> None:
        path = self._output_dir / "manifest.json"
        _atomic_write(path, json.dumps(self._manifest, indent=2, ensure_ascii=False) + "\n")

    def _next_blueprint_version(self) -> int:
        versions = [e.get("version", 0) for e in self._manifest.get("blueprint_versions", [])]
        return max(versions, default=0) + 1

    def _next_constraint_version(self) -> int:
        versions = [e.get("version", 0) for e in self._manifest.get("constraint_versions", [])]
        return max(versions, default=0) + 1

    @property
    def output_dir(self) -> Path:
        return self._output_dir
