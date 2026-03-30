"""Real-data smoke test: clone ai-calorie-tracker, run stage0 → stage1_scan, verify output.

Usage:
    python scripts/real_data_smoke_test.py

Exit codes:
    0 — all steps passed
    1 — at least one step failed
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback
from pathlib import Path

# ── sys.path ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "contracts"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "extraction"))

# ── constants ────────────────────────────────────────────────────────────────
SMOKE_DIR = Path("/tmp/doramagic_smoke")
REPO_URL = "https://github.com/nicholasgriffintn/ai-calorie-tracker.git"
REPO_DIR = SMOKE_DIR / "ai-calorie-tracker"

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
SKIP = "[SKIP]"


# ── helpers ──────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _serialise(obj: object) -> object:
    """Convert Pydantic models to plain dicts for json.dumps."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_serialise(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    return obj


def pp(obj: object) -> None:
    """Pretty-print any object as JSON."""
    print(json.dumps(_serialise(obj), indent=2, ensure_ascii=False))


# ── Step 1: setup workspace ──────────────────────────────────────────────────

def step_setup_workspace() -> bool:
    section("Step 1: Setup workspace")
    try:
        SMOKE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"{PASS} Workspace ready: {SMOKE_DIR}")
        return True
    except Exception as exc:
        print(f"{FAIL} Cannot create workspace: {exc}")
        return False


# ── Step 2: git clone ────────────────────────────────────────────────────────

def step_clone() -> bool:
    section("Step 2: git clone ai-calorie-tracker")

    if REPO_DIR.exists():
        print(f"{SKIP} Repo already exists at {REPO_DIR} — skipping clone.")
        return True

    print(f"{INFO} Cloning {REPO_URL} → {REPO_DIR} (shallow --depth 1)")
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"{FAIL} git clone failed (exit {result.returncode})")
            print("  stdout:", result.stdout.strip())
            print("  stderr:", result.stderr.strip())
            print()
            print("  Possible causes:")
            print("    - No internet connection")
            print("    - GitHub is unreachable from this network")
            print("    - Repository URL has changed or been deleted")
            return False

        print(f"{PASS} Clone succeeded.")
        return True

    except subprocess.TimeoutExpired:
        print(f"{FAIL} git clone timed out after 120 s.")
        return False
    except FileNotFoundError:
        print(f"{FAIL} 'git' command not found — is git installed?")
        return False
    except Exception as exc:
        print(f"{FAIL} Unexpected error during clone: {exc}")
        traceback.print_exc()
        return False


# ── Step 3: run stage0 ───────────────────────────────────────────────────────

def step_stage0():
    """Returns (success: bool, repo_facts_or_None)."""
    section("Step 3: Run stage0 (deterministic extraction)")

    try:
        from doramagic_extraction.stage0 import extract_repo_facts  # type: ignore[import]
    except ImportError as exc:
        print(f"{FAIL} Cannot import stage0: {exc}")
        traceback.print_exc()
        return False, None

    try:
        repo_facts = extract_repo_facts(str(REPO_DIR))
        print(f"{PASS} stage0 completed successfully.")
        print()
        print("  --- stage0 output summary ---")
        print(f"  languages   : {repo_facts.languages}")
        print(f"  frameworks  : {repo_facts.frameworks}")
        print(f"  entrypoints : {repo_facts.entrypoints}")
        print(f"  commands    : {repo_facts.commands}")
        print(f"  storage_paths: {repo_facts.storage_paths}")
        print(f"  dependencies ({len(repo_facts.dependencies)} total, first 10):")
        for d in repo_facts.dependencies[:10]:
            print(f"    - {d}")
        print(f"  repo_summary: {repo_facts.repo_summary!r}")
        print()
        print("  Full stage0 JSON:")
        pp(repo_facts)
        return True, repo_facts

    except ValueError as exc:
        print(f"{FAIL} stage0 raised ValueError: {exc}")
        return False, None
    except Exception as exc:
        print(f"{FAIL} stage0 raised unexpected error: {exc}")
        traceback.print_exc()
        return False, None


# ── Step 4: run stage1_scan ──────────────────────────────────────────────────

def step_stage1_scan(repo_facts) -> bool:
    section("Step 4: Run stage1_scan")

    try:
        from doramagic_extraction.stage1_scan import run_stage1_scan  # type: ignore[import]
        from doramagic_contracts.extraction import Stage1ScanConfig, Stage1ScanInput  # type: ignore[import]
    except ImportError as exc:
        print(f"{FAIL} Cannot import stage1_scan or contracts: {exc}")
        traceback.print_exc()
        return False

    try:
        scan_input = Stage1ScanInput(
            repo_facts=repo_facts,
            config=Stage1ScanConfig(
                max_llm_calls=8,
                max_prompt_tokens=24000,
                generate_hypotheses=True,
                include_domain_bricks=False,
            ),
        )
    except Exception as exc:
        print(f"{FAIL} Failed to construct Stage1ScanInput: {exc}")
        traceback.print_exc()
        return False

    try:
        envelope = run_stage1_scan(scan_input)
    except Exception as exc:
        print(f"{FAIL} run_stage1_scan raised unexpected error: {exc}")
        traceback.print_exc()
        return False

    # ── envelope-level check ─────────────────────────────────────────────────
    print(f"  status     : {envelope.status}")
    print(f"  module     : {envelope.module_name}")
    print(f"  error_code : {envelope.error_code}")
    if envelope.warnings:
        for w in envelope.warnings:
            print(f"  warning    : [{w.code}] {w.message}")
    print(f"  wall_time  : {envelope.metrics.wall_time_ms} ms")

    if envelope.status == "blocked":
        print(f"{FAIL} stage1_scan returned status=blocked (error_code={envelope.error_code})")
        return False

    if envelope.data is None:
        print(f"{FAIL} stage1_scan envelope.data is None — no output produced.")
        return False

    output = envelope.data

    # ── findings ─────────────────────────────────────────────────────────────
    print()
    print(f"  Total findings: {len(output.findings)}")
    for f in output.findings:
        print(f"    [{f.question_key}] {f.finding_id}  |  {f.title}")
        # print first 120 chars of statement
        stmt_preview = f.statement[:120].replace("\n", " ")
        print(f"           {stmt_preview}...")

    # ── hypotheses ───────────────────────────────────────────────────────────
    print()
    print(f"  Total hypotheses: {len(output.hypotheses)}")
    for h in output.hypotheses:
        print(f"    [{h.priority}] {h.hypothesis_id}  |  {h.statement[:100].replace(chr(10), ' ')}...")

    # ── coverage ─────────────────────────────────────────────────────────────
    print()
    print(f"  Coverage:")
    print(f"    answered  : {output.coverage.answered_questions}")
    print(f"    partial   : {output.coverage.partial_questions}")
    print(f"    uncovered : {output.coverage.uncovered_questions}")
    print(f"  recommended_for_stage15: {output.recommended_for_stage15}")

    # ── full JSON ─────────────────────────────────────────────────────────────
    print()
    print("  Full stage1 JSON:")
    pp(output)

    if envelope.status in ("ok", "degraded"):
        verdict = PASS if envelope.status == "ok" else f"{PASS} (degraded — check warnings)"
        print(f"\n{verdict} stage1_scan completed with status={envelope.status!r}")
        return True

    print(f"\n{FAIL} stage1_scan returned unexpected status={envelope.status!r}")
    return False


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print("Doramagic Real-Data Smoke Test")
    print(f"Target repo : {REPO_URL}")
    print(f"Working dir : {SMOKE_DIR}")

    results: list[bool] = []

    # Step 1
    ok = step_setup_workspace()
    results.append(ok)
    if not ok:
        print(f"\n{FAIL} Cannot proceed without workspace.")
        return 1

    # Step 2
    ok = step_clone()
    results.append(ok)
    if not ok:
        print(f"\n{FAIL} Cannot proceed without cloned repo.")
        return 1

    # Step 3
    ok, repo_facts = step_stage0()
    results.append(ok)
    if not ok:
        print(f"\n{FAIL} Cannot proceed without stage0 output.")
        return 1

    # Step 4
    ok = step_stage1_scan(repo_facts)
    results.append(ok)

    # ── final verdict ─────────────────────────────────────────────────────────
    section("Final Verdict")
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} steps passed.")

    if all(results):
        print(f"\n{PASS} ALL STEPS PASSED — pipeline works on real data.")
        return 0
    else:
        failed_steps = [i + 1 for i, r in enumerate(results) if not r]
        print(f"\n{FAIL} SOME STEPS FAILED — steps {failed_steps}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
