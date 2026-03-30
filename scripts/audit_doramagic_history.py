#!/usr/bin/env python3
"""Audit historical Doramagic runs and emit detailed execution logs."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple


ARTIFACT_PATHS = {
    "run_summary": "run_summary.json",
    "need_profile": "need_profile.json",
    "discovery_result": "discovery_result.json",
    "community_knowledge": "community_knowledge.json",
    "synthesis_report": "synthesis_report.json",
    "delivery_skill": "delivery/SKILL.md",
    "delivery_readme": "delivery/README.md",
    "delivery_provenance": "delivery/PROVENANCE.md",
    "delivery_limitations": "delivery/LIMITATIONS.md",
    "delivery_validation_report": "delivery/validation_report.json",
}


class ProcessSnapshot(NamedTuple):
    active_doramagic_processes: list[str]
    active_openclaw_processes: list[str]
    active_launch_agents: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit historical Doramagic runs")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Doramagic project root. Defaults to the repository that contains this script.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Run directory to audit. Defaults to <project-root>/runs.",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=Path.home() / "Documents" / "openclaw" / "logs",
        help="Directory where the audit logs will be written.",
    )
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Date stamp for output file names, e.g. 2026-03-25.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    runs_dir = (args.runs_dir or (project_root / "runs")).resolve()
    logs_dir = args.logs_dir.resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    run_records = [audit_run(run_dir, project_root) for run_dir in iter_run_dirs(runs_dir)]
    run_records.sort(key=sort_key_for_record, reverse=True)

    process_snapshot = capture_process_snapshot()
    generated_at = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )

    markdown_path = logs_dir / f"doramagic-history-audit-{args.date}.md"
    jsonl_path = logs_dir / f"doramagic-history-audit-{args.date}.jsonl"

    markdown_path.write_text(render_markdown_report(generated_at, runs_dir, process_snapshot, run_records), encoding="utf-8")
    write_jsonl(jsonl_path, run_records)

    print(f"Wrote Markdown report to {markdown_path}")
    print(f"Wrote JSONL report to {jsonl_path}")
    print(f"Audited {len(run_records)} run(s) from {runs_dir}")
    return 0


def iter_run_dirs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    run_dirs: list[Path] = []
    for path in sorted(runs_dir.iterdir()):
        if not path.is_dir():
            continue
        if any((path / relative_path).exists() for relative_path in ARTIFACT_PATHS.values()):
            run_dirs.append(path)
    return run_dirs


def sort_key_for_record(record: dict[str, Any]) -> tuple[str, str]:
    created_at = str(record.get("created_at") or "")
    return created_at, str(record["run_id"])


def audit_run(run_dir: Path, project_root: Path) -> dict[str, Any]:
    artifact_presence = {name: (run_dir / relative_path).exists() for name, relative_path in ARTIFACT_PATHS.items()}

    run_summary = load_json(run_dir / ARTIFACT_PATHS["run_summary"])
    need_profile = load_json(run_dir / ARTIFACT_PATHS["need_profile"])
    discovery_result = load_json(run_dir / ARTIFACT_PATHS["discovery_result"])
    synthesis_report = load_json(run_dir / ARTIFACT_PATHS["synthesis_report"])

    warnings = run_summary.get("warnings")
    selected_for_phase_c = [
        candidate
        for candidate in discovery_result.get("candidates", [])
        if candidate.get("selected_for_phase_c") is True
    ]
    selected_for_phase_d = [
        candidate
        for candidate in discovery_result.get("candidates", [])
        if candidate.get("selected_for_phase_d") is True
    ]

    stage_status = {
        "need_profile": stage_from_required(artifact_presence["need_profile"]),
        "discovery": stage_from_required(artifact_presence["discovery_result"]),
        "community": stage_from_optional(artifact_presence["community_knowledge"]),
        "synthesis": stage_from_required(artifact_presence["synthesis_report"]),
        "delivery": stage_from_delivery(artifact_presence),
        "validation": stage_from_validation(
            artifact_presence["delivery_validation_report"],
            run_summary.get("validation_status"),
        ),
    }

    overall_status = infer_overall_status(artifact_presence, run_summary.get("validation_status"))

    record = {
        "run_id": run_dir.name,
        "run_path": str(run_dir),
        "run_path_relative": str(run_dir.relative_to(project_root)),
        "created_at": run_summary.get("created_at"),
        "intent": need_profile.get("intent") or need_profile.get("raw_input"),
        "raw_input": need_profile.get("raw_input"),
        "validation_status": run_summary.get("validation_status", "unknown"),
        "warnings": warnings if isinstance(warnings, list) else [],
        "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        "artifact_presence": artifact_presence,
        "missing_artifacts": [name for name, exists in artifact_presence.items() if not exists],
        "stage_status": stage_status,
        "discovery": {
            "candidate_count": len(discovery_result.get("candidates", [])),
            "selected_for_phase_c_count": len(selected_for_phase_c),
            "selected_for_phase_d_count": len(selected_for_phase_d),
            "search_coverage_count": len(discovery_result.get("search_coverage", [])),
            "no_candidate_reason": discovery_result.get("no_candidate_reason"),
        },
        "synthesis": {
            "selected_knowledge_count": len(synthesis_report.get("selected_knowledge", [])),
            "consensus_count": len(synthesis_report.get("consensus", [])),
            "unique_knowledge_count": len(synthesis_report.get("unique_knowledge", [])),
            "excluded_knowledge_count": len(synthesis_report.get("excluded_knowledge", [])),
            "open_question_count": len(synthesis_report.get("open_questions", [])),
        },
        "delivery": {
            "required_files_complete": delivery_required_files_complete(artifact_presence),
            "validation_report_present": artifact_presence["delivery_validation_report"],
        },
        "overall_status": overall_status,
        "notes": build_notes(artifact_presence, run_summary),
    }
    return record


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_parse_error": str(exc)}


def stage_from_required(exists: bool) -> str:
    return "complete" if exists else "missing"


def stage_from_optional(exists: bool) -> str:
    return "complete" if exists else "not_present"


def stage_from_delivery(artifact_presence: dict[str, bool]) -> str:
    required = [
        artifact_presence["delivery_skill"],
        artifact_presence["delivery_readme"],
        artifact_presence["delivery_provenance"],
        artifact_presence["delivery_limitations"],
    ]
    if all(required):
        return "complete"
    if any(required):
        return "partial"
    return "missing"


def stage_from_validation(validation_report_present: bool, validation_status: Any) -> str:
    if validation_status in {"PASS", "FAIL"}:
        return str(validation_status).lower()
    if validation_report_present:
        return "report_only"
    return "unknown"


def delivery_required_files_complete(artifact_presence: dict[str, bool]) -> bool:
    return all(
        artifact_presence[key]
        for key in [
            "delivery_skill",
            "delivery_readme",
            "delivery_provenance",
            "delivery_limitations",
        ]
    )


def infer_overall_status(artifact_presence: dict[str, bool], validation_status: Any) -> str:
    if validation_status == "PASS":
        return "pass"
    if validation_status == "FAIL":
        return "fail"
    if artifact_presence["run_summary"] and delivery_required_files_complete(artifact_presence):
        return "partial"
    return "broken"


def build_notes(artifact_presence: dict[str, bool], run_summary: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    missing = [name for name, exists in artifact_presence.items() if not exists]
    if missing:
        notes.append("Missing artifacts: " + ", ".join(missing))
    if "_parse_error" in run_summary:
        notes.append(f"run_summary parse error: {run_summary['_parse_error']}")
    return notes


def run_command_lines(command: list[str]) -> list[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except (FileNotFoundError, PermissionError, OSError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def capture_process_snapshot() -> ProcessSnapshot:
    ps_lines = run_command_lines(["ps", "-Ao", "pid=,etime=,command="])
    active_doramagic = [
        line
        for line in ps_lines
        if "doramagic" in line.lower()
        and "audit_doramagic_history.py" not in line.lower()
        and "test_audit_doramagic_history.py" not in line.lower()
        and "pytest" not in line.lower()
    ]
    active_openclaw = [
        line
        for line in ps_lines
        if "openclaw" in line.lower() and "audit_doramagic_history" not in line.lower()
    ]
    launch_agents = [
        line
        for line in run_command_lines(["launchctl", "list"])
        if "openclaw" in line.lower() or "doramagic" in line.lower()
    ]
    return ProcessSnapshot(
        active_doramagic_processes=active_doramagic,
        active_openclaw_processes=active_openclaw,
        active_launch_agents=launch_agents,
    )


def render_markdown_report(
    generated_at: str,
    runs_dir: Path,
    process_snapshot: ProcessSnapshot,
    run_records: list[dict[str, Any]],
) -> str:
    lines = [
        "# Doramagic Historical Run Audit",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Runs directory: `{runs_dir}`",
        f"- Audited runs: `{len(run_records)}`",
        "",
        "## Current Execution State",
        "",
    ]

    if process_snapshot.active_doramagic_processes:
        lines.append("- Active Doramagic processes detected:")
        for proc in process_snapshot.active_doramagic_processes:
            lines.append(f"  - `{proc}`")
    else:
        lines.append("- No active Doramagic process detected at audit time.")

    if process_snapshot.active_openclaw_processes:
        lines.append("- Active OpenClaw processes:")
        for proc in process_snapshot.active_openclaw_processes:
            lines.append(f"  - `{proc}`")
    else:
        lines.append("- No active OpenClaw process detected at audit time.")

    if process_snapshot.active_launch_agents:
        lines.append("- Launch agents related to OpenClaw/Doramagic:")
        for agent in process_snapshot.active_launch_agents:
            lines.append(f"  - `{agent}`")

    lines.extend(["", "## Run Summaries", ""])

    if not run_records:
        lines.append("- No run directories found.")
        return "\n".join(lines) + "\n"

    for record in run_records:
        lines.extend(render_run_markdown(record))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_run_markdown(record: dict[str, Any]) -> list[str]:
    lines = [
        f"### `{record['run_id']}`",
        "",
        f"- Overall status: `{record['overall_status']}`",
        f"- Created at: `{record['created_at'] or 'unknown'}`",
        f"- Intent: {record['intent'] or 'unknown'}",
        f"- Validation status: `{record['validation_status']}`",
        f"- Warnings: `{record['warning_count']}`",
        f"- Candidates: `{record['discovery']['candidate_count']}` total, `{record['discovery']['selected_for_phase_c_count']}` selected for phase C, `{record['discovery']['selected_for_phase_d_count']}` selected for phase D",
        f"- Synthesis: `{record['synthesis']['selected_knowledge_count']}` selected, `{record['synthesis']['consensus_count']}` consensus, `{record['synthesis']['excluded_knowledge_count']}` excluded, `{record['synthesis']['open_question_count']}` open questions",
        f"- Delivery complete: `{record['delivery']['required_files_complete']}`",
        f"- Missing artifacts: `{', '.join(record['missing_artifacts']) if record['missing_artifacts'] else 'none'}`",
        f"- Stage status: `need={record['stage_status']['need_profile']}`, `discovery={record['stage_status']['discovery']}`, `community={record['stage_status']['community']}`, `synthesis={record['stage_status']['synthesis']}`, `delivery={record['stage_status']['delivery']}`, `validation={record['stage_status']['validation']}`",
    ]
    if record["notes"]:
        lines.append("- Notes:")
        for note in record["notes"]:
            lines.append(f"  - {note}")
    return lines


def write_jsonl(path: Path, run_records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in run_records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
