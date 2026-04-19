"""Tests for cli._safe_int and _scan_stale_projects defensive handling.

Covers the P0 blocker where source_blueprint_version is None (never written)
or a filename string, which would cause TypeError on `int > None` comparison.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the package is importable
_pkg_dir = Path(__file__).resolve().parents[3] / "packages" / "constraint_agent"
if str(_pkg_dir) not in sys.path:
    sys.path.insert(0, str(_pkg_dir))

from doramagic_constraint_agent.cli import _safe_int, _scan_stale_projects  # noqa: E402

# ---------------------------------------------------------------------------
# _safe_int unit tests
# ---------------------------------------------------------------------------


class TestSafeInt:
    def test_integer_passthrough(self) -> None:
        assert _safe_int(17) == 17

    def test_string_integer(self) -> None:
        assert _safe_int("5") == 5

    def test_none_returns_default(self) -> None:
        assert _safe_int(None) == 0

    def test_none_custom_default(self) -> None:
        assert _safe_int(None, default=-1) == -1

    def test_filename_string_returns_default(self) -> None:
        # "blueprint.v17.yaml" is non-numeric — must not crash, return default
        assert _safe_int("blueprint.v17.yaml") == 0

    def test_filename_string_custom_default(self) -> None:
        assert _safe_int("blueprint.v2.yaml", default=-1) == -1

    def test_float_truncates(self) -> None:
        assert _safe_int(3.9) == 3

    def test_zero(self) -> None:
        assert _safe_int(0) == 0

    def test_empty_string_returns_default(self) -> None:
        assert _safe_int("", default=99) == 99


# ---------------------------------------------------------------------------
# _scan_stale_projects — None / string source_blueprint_version must not crash
# ---------------------------------------------------------------------------


def _make_manifest(
    bp_version: int,
    source_bp_version: object,  # intentionally None or str to test edge cases
    status: str = "done",
    tmp_path: Path | None = None,
) -> dict:
    """Return a minimal manifest dict for testing."""
    return {
        "schema_version": "2.0",
        "blueprint_id": "finance-bp-test",
        "domain": "finance",
        "blueprint_versions": [
            {
                "file": f"blueprint.v{bp_version}.yaml",
                "version": bp_version,
            }
        ],
        "constraint_versions": [
            {
                "file": "constraints.v1.jsonl",
                "version": 1,
                "source_blueprint_version": source_bp_version,
            }
        ],
        "constraint_extraction_status": status,
    }


class TestScanStaleProjectsDefensive:
    """_scan_stale_projects must not raise TypeError for None/string sbv."""

    def _write_project(
        self,
        tmp_path: Path,
        bp_version: int,
        source_bp_version: object,
        status: str = "done",
    ) -> Path:
        """Create a minimal project dir with manifest.json + LATEST.yaml."""
        proj = tmp_path / "finance-bp-test--repo"
        proj.mkdir()
        manifest = _make_manifest(bp_version, source_bp_version, status)
        (proj / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        # Minimal valid LATEST.yaml (source.projects is optional)
        (proj / "LATEST.yaml").write_text("source:\n  projects: []\n", encoding="utf-8")
        return proj

    def test_none_source_bp_version_does_not_crash(self, tmp_path: Path) -> None:
        """source_blueprint_version=None must not raise TypeError."""
        self._write_project(tmp_path, bp_version=5, source_bp_version=None)
        # Must not raise
        result = _scan_stale_projects(tmp_path, tmp_path)
        # None is treated as -1, so bp_version=5 > -1 → stale
        assert len(result) == 1
        assert result[0]["blueprint_id"] == "finance-bp-test"

    def test_string_source_bp_version_does_not_crash(self, tmp_path: Path) -> None:
        """source_blueprint_version='blueprint.v17.yaml' must not raise TypeError."""
        self._write_project(tmp_path, bp_version=17, source_bp_version="blueprint.v17.yaml")
        # Must not raise
        result = _scan_stale_projects(tmp_path, tmp_path)
        # string → _safe_int → 0, so bp_version=17 > 0 → stale
        assert len(result) == 1

    def test_up_to_date_int_source_bp_version_not_stale(self, tmp_path: Path) -> None:
        """Integer source_bp_version == latest_bp_version → not stale."""
        self._write_project(tmp_path, bp_version=3, source_bp_version=3)
        result = _scan_stale_projects(tmp_path, tmp_path)
        assert result == []

    def test_stale_int_source_bp_version_is_stale(self, tmp_path: Path) -> None:
        """Integer source_bp_version < latest_bp_version → stale."""
        self._write_project(tmp_path, bp_version=5, source_bp_version=2)
        result = _scan_stale_projects(tmp_path, tmp_path)
        assert len(result) == 1
