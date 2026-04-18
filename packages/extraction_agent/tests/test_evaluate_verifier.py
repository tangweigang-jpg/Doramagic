"""Regression tests for Bug 2: evidence verifier false positives.

Covers two fixes in evaluate_v9.deterministic_eval():
- Fix 1 (defect-1): fn_name containing non-identifier chars → skip exact-match, treat as VALID
- Fix 2 (defect-2): file not at direct path → basename rglob fallback (unique match → accept)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from doramagic_extraction_agent.sop.evaluate_v9 import deterministic_eval

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bd(
    bd_id: str,
    evidence: str,
    bd_type: str = "B",
) -> dict[str, Any]:
    return {
        "id": bd_id,
        "type": bd_type,
        "content": "Some decision.",
        "rationale": "Reason. Breaks under X.",
        "evidence": evidence,
        "stage": "risk_management",
    }


def _run(coro: Any) -> Any:
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fix 1: non-identifier fn_name skips exact-match
# ---------------------------------------------------------------------------


class TestFix1NonIdentifierFnName:
    """Regression: fn_name with special chars → should skip exact-match and return VALID."""

    def _make_repo(self, tmp_path: Path, filename: str, content: str) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / filename).write_text(content, encoding="utf-8")
        return repo

    def test_fn_name_with_space_skipped(self, tmp_path: Path) -> None:
        """fn_name='warning docstring' (space) → file+line valid → VALID."""
        repo = self._make_repo(
            tmp_path,
            "risk.py",
            "# risk module\n" * 10,
        )
        bd = _bd("BD-001", "risk.py:5(warning docstring)")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "VALID", (
            f"Expected VALID for space in fn_name, got {v['verdict']}: {v.get('note', '')}"
        )
        assert v["function_found"] is True

    def test_fn_name_with_comma_skipped(self, tmp_path: Path) -> None:
        """fn_name='CRR_SS, Moodys_SS, etc.' (comma) → VALID."""
        repo = self._make_repo(
            tmp_path,
            "models.py",
            "def CRR_SS():\n    pass\n" * 5,
        )
        bd = _bd("BD-002", "models.py:1(CRR_SS, Moodys_SS, etc.)")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "VALID", (
            f"Expected VALID for comma in fn_name, got {v['verdict']}: {v.get('note', '')}"
        )

    def test_fn_name_with_bracket_skipped(self, tmp_path: Path) -> None:
        """fn_name='etm[:, :, 0] = np.eye(state_dim)' (brackets+equals) → VALID."""
        repo = self._make_repo(
            tmp_path,
            "kalman.py",
            "import numpy as np\n" + "etm = np.zeros((3, 3, 3))\n" * 3,
        )
        bd = _bd("BD-003", "kalman.py:2(etm[:, :, 0] = np.eye(state_dim))")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "VALID", (
            f"Expected VALID for bracket/equals in fn_name, got {v['verdict']}: {v.get('note', '')}"
        )

    def test_fn_name_with_colon_skipped(self, tmp_path: Path) -> None:
        """fn_name containing colon → non-identifier → skip exact-match → VALID."""
        repo = self._make_repo(
            tmp_path,
            "util.py",
            "# utility\n" * 8,
        )
        bd = _bd("BD-004", "util.py:3(key: value mapping)")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "VALID", (
            f"Expected VALID for colon in fn_name, got {v['verdict']}: {v.get('note', '')}"
        )

    def test_fn_name_real_identifier_still_checked(self, tmp_path: Path) -> None:
        """fn_name='normalize_data' (valid identifier) but absent in file → FUNCTION_MISSING."""
        repo = self._make_repo(
            tmp_path,
            "preprocess.py",
            "def scale_data():\n    pass\n" * 5,
        )
        bd = _bd("BD-005", "preprocess.py:1(normalize_data)")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "FUNCTION_MISSING", (
            f"Expected FUNCTION_MISSING for absent identifier, got {v['verdict']}"
        )
        assert v["function_found"] is False

    def test_fn_name_with_backslash_skipped(self, tmp_path: Path) -> None:
        """fn_name containing backslash → non-identifier → skip exact-match → VALID."""
        repo = self._make_repo(
            tmp_path,
            "formula.py",
            "alpha = 0.05\nbeta = 0.95\n" * 4,
        )
        bd = _bd("BD-006", "formula.py:1(P(x\\mid y))")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "VALID", (
            f"Expected VALID for backslash in fn_name, got {v['verdict']}: {v.get('note', '')}"
        )


# ---------------------------------------------------------------------------
# Fix 2: basename rglob fallback
# ---------------------------------------------------------------------------


class TestFix2BasenameRglobFallback:
    """Regression: evidence references bare filename → rglob fallback resolves it."""

    def _make_deep_repo(self, tmp_path: Path) -> Path:
        """Create a repo with a file nested deep in subdirectories."""
        repo = tmp_path / "repo"
        target_dir = repo / "financetoolkit" / "options"
        target_dir.mkdir(parents=True)
        (target_dir / "black_scholes_model.py").write_text(
            "def black_scholes(S, K, T, r, sigma):\n    pass\n",
            encoding="utf-8",
        )
        return repo

    def test_truncated_path_unique_match_accepted(self, tmp_path: Path) -> None:
        """Bare filename found uniquely via rglob → VALID."""
        repo = self._make_deep_repo(tmp_path)
        # Evidence uses bare filename, not full path
        bd = _bd("BD-010", "black_scholes_model.py:1(black_scholes)")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "VALID", (
            f"Expected VALID for unique basename match, got {v['verdict']}: {v.get('note', '')}"
        )
        assert v["file_exists"] is True

    def test_truncated_path_multiple_matches_rejected(self, tmp_path: Path) -> None:
        """basename matches 2+ files → FILE_MISSING with N-matches note."""
        repo = tmp_path / "repo"
        # Create two files with the same basename in different dirs
        dir_a = repo / "module_a"
        dir_b = repo / "module_b"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)
        (dir_a / "common.py").write_text("x = 1\n", encoding="utf-8")
        (dir_b / "common.py").write_text("y = 2\n", encoding="utf-8")

        bd = _bd("BD-011", "common.py:1(some_func)")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "FILE_MISSING", (
            f"Expected FILE_MISSING for multiple matches, got {v['verdict']}"
        )
        # Note should mention the number of matches
        note = v.get("note", "")
        assert "2 matches" in note or "matches" in note, (
            f"Note should mention match count, got: {note!r}"
        )

    def test_truncated_path_zero_matches_rejected(self, tmp_path: Path) -> None:
        """Basename not found at all → FILE_MISSING."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "other_file.py").write_text("pass\n", encoding="utf-8")

        bd = _bd("BD-012", "completely_nonexistent_file.py:1(fn)")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        assert v["verdict"] == "FILE_MISSING", (
            f"Expected FILE_MISSING for zero basename matches, got {v['verdict']}"
        )
        assert v["file_exists"] is False

    def test_path_with_correct_prefix_not_rglob(self, tmp_path: Path) -> None:
        """When direct path exists, file is resolved without rglob (behavior check via result)."""
        repo = self._make_deep_repo(tmp_path)
        # Use the full path — direct resolution should work
        bd = _bd(
            "BD-013",
            "financetoolkit/options/black_scholes_model.py:1(black_scholes)",
        )
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 1
        v = verdicts[0]
        # Should be VALID via direct path lookup, no need for rglob
        assert v["verdict"] == "VALID", (
            f"Expected VALID for correct full path, got {v['verdict']}: {v.get('note', '')}"
        )

    def test_t_type_bd_is_skipped(self, tmp_path: Path) -> None:
        """BD of type T is skipped entirely — no verdict emitted."""
        repo = tmp_path / "repo"
        repo.mkdir()
        bd = _bd("BD-T01", "some_file.py:1(fn)", bd_type="T")
        verdicts = _run(deterministic_eval([bd], repo))

        assert len(verdicts) == 0, f"T-type BD should be skipped, got {verdicts}"
