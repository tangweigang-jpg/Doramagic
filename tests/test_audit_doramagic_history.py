from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "audit_doramagic_history.py"
SPEC = importlib.util.spec_from_file_location("audit_doramagic_history", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class AuditHistoryTests(unittest.TestCase):
    def test_audit_complete_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project_root = Path(td)
            run_dir = project_root / "runs" / "20260320-085856-skill-a5fcccfb"
            run_dir.mkdir(parents=True)

            write_json(
                run_dir / "run_summary.json",
                {
                    "created_at": "2026-03-20T02:02:55Z",
                    "validation_status": "PASS",
                    "warnings": [],
                },
            )
            write_json(
                run_dir / "need_profile.json",
                {
                    "intent": "我想做一个管理家庭菜谱的 skill",
                    "raw_input": "我想做一个管理家庭菜谱的 skill",
                },
            )
            write_json(
                run_dir / "discovery_result.json",
                {
                    "candidates": [
                        {"selected_for_phase_c": True, "selected_for_phase_d": True},
                        {"selected_for_phase_c": False, "selected_for_phase_d": True},
                    ],
                    "search_coverage": [{"direction": "recipe", "status": "covered"}],
                },
            )
            write_json(run_dir / "community_knowledge.json", {"skills": []})
            write_json(
                run_dir / "synthesis_report.json",
                {
                    "selected_knowledge": [{"statement": "x"}],
                    "consensus": [{"statement": "y"}],
                    "unique_knowledge": [{"statement": "z"}],
                    "excluded_knowledge": [{"statement": "n"}],
                    "open_questions": [],
                },
            )
            for relative in [
                "delivery/SKILL.md",
                "delivery/README.md",
                "delivery/PROVENANCE.md",
                "delivery/LIMITATIONS.md",
                "delivery/validation_report.json",
            ]:
                touch(run_dir / relative, "{}" if relative.endswith(".json") else "# file")

            record = MODULE.audit_run(run_dir, project_root)

            self.assertEqual(record["overall_status"], "pass")
            self.assertEqual(record["stage_status"]["delivery"], "complete")
            self.assertEqual(record["stage_status"]["validation"], "pass")
            self.assertEqual(record["discovery"]["candidate_count"], 2)
            self.assertEqual(record["discovery"]["selected_for_phase_c_count"], 1)
            self.assertEqual(record["synthesis"]["selected_knowledge_count"], 1)
            self.assertEqual(record["missing_artifacts"], [])

    def test_audit_partial_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project_root = Path(td)
            run_dir = project_root / "runs" / "run-20260320-091051-122146"
            run_dir.mkdir(parents=True)

            write_json(run_dir / "need_profile.json", {"raw_input": "partial run"})
            write_json(run_dir / "discovery_result.json", {"candidates": []})

            record = MODULE.audit_run(run_dir, project_root)

            self.assertEqual(record["overall_status"], "broken")
            self.assertEqual(record["stage_status"]["need_profile"], "complete")
            self.assertEqual(record["stage_status"]["synthesis"], "missing")
            self.assertIn("run_summary", record["missing_artifacts"])
            self.assertIn("synthesis_report", record["missing_artifacts"])

    def test_render_markdown_mentions_no_active_doramagic(self) -> None:
        process_snapshot = MODULE.ProcessSnapshot(
            active_doramagic_processes=[],
            active_openclaw_processes=["123 00:05 openclaw-node"],
            active_launch_agents=["24631\t0\tai.openclaw.node"],
        )
        report = MODULE.render_markdown_report(
            generated_at="2026-03-25T00:00:00Z",
            runs_dir=Path("/tmp/runs"),
            process_snapshot=process_snapshot,
            run_records=[],
        )

        self.assertIn("No active Doramagic process detected", report)
        self.assertIn("openclaw-node", report)


if __name__ == "__main__":
    unittest.main()
