"""Build deterministic domain snapshots from fingerprints and compare signals."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "contracts"))

from doramagic_contracts.base import EvidenceRef, KnowledgeAtom, ProjectFingerprint  # noqa: E402
from doramagic_contracts.cross_project import (  # noqa: E402
    CommunityKnowledge,
    CompareOutput,
    CompareSignal,
    SynthesisDecision,
    SynthesisReportData,
)
from doramagic_contracts.domain_graph import (  # noqa: E402
    AtomCluster,
    DomainBrick,
    DomainSnapshot,
    SnapshotBuilderInput,
    SnapshotBuilderOutput,
    SnapshotStats,
)
from doramagic_contracts.envelope import (  # noqa: E402
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)

MODULE_NAME = "domain-graph.snapshot_builder"
SNAPSHOT_FILENAME = "DOMAIN_BRICKS.json"
TRUTH_FILENAME = "DOMAIN_TRUTH.md"
MANIFEST_FILENAME = "snapshot_manifest.json"
ATOMS_JSON_FILENAME = "atoms.json"
ATOMS_PARQUET_FILENAME = "atoms.parquet"
SQLITE_FILENAME = "domain_map.sqlite"
DEFAULT_OUTPUT_DIR = "data/snapshots"

_SIGNAL_PRIORITY = {
    "ALIGNED": 0,
    "MISSING": 1,
    "ORIGINAL": 2,
    "STALE": 3,
    "DRIFTED": 4,
    "DIVERGENT": 5,
    "CONTESTED": 6,
}
_TOKEN_SYNONYMS = {
    "accepts": "accept",
    "accepting": "accept",
    "accepted": "accept",
    "using": "use",
    "uses": "use",
    "used": "use",
    "recognition": "recognize",
    "recognizes": "recognize",
    "recognized": "recognize",
    "vision": "photo",
    "photos": "photo",
    "image": "photo",
    "images": "photo",
    "logging": "log",
    "logs": "log",
    "logged": "log",
    "persisted": "persist",
    "persists": "persist",
    "persistence": "persist",
    "stored": "store",
    "storage": "store",
    "stores": "store",
    "local": "local",
    "locally": "local",
}
_TAG_STOPWORDS = {
    "a",
    "all",
    "and",
    "are",
    "as",
    "based",
    "both",
    "for",
    "from",
    "in",
    "is",
    "of",
    "or",
    "per",
    "projects",
    "the",
    "to",
    "user",
    "via",
    "with",
}


def _model_validate(model_class, payload):
    if isinstance(payload, model_class):
        return payload
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(payload)
    return model_class(**payload)


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _metrics(wall_time_ms: int) -> RunMetrics:
    return RunMetrics(
        wall_time_ms=max(wall_time_ms, 0),
        llm_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
        retries=0,
    )


def _blocked_envelope(error_code: str, wall_time_ms: int = 0) -> ModuleResultEnvelope[SnapshotBuilderOutput]:
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="blocked",
        error_code=error_code,
        warnings=[],
        data=None,
        metrics=_metrics(wall_time_ms),
    )


def _error_envelope(
    wall_time_ms: int,
    message: str,
) -> ModuleResultEnvelope[SnapshotBuilderOutput]:
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="error",
        error_code=None,
        warnings=[WarningItem(code="UNEXPECTED_ERROR", message=message)],
        data=None,
        metrics=_metrics(wall_time_ms),
    )


def _normalize_text(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", lowered)


def _tokenize(value: str) -> Tuple[str, ...]:
    tokens = []
    for raw_token in _normalize_text(value).split():
        tokens.append(_TOKEN_SYNONYMS.get(raw_token, raw_token))
    return tuple(tokens)


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


def _atom_statement(atom: KnowledgeAtom) -> str:
    return "{0} {1} {2}".format(atom.subject, atom.predicate, atom.object).strip()


def _atom_signal_score(atom: KnowledgeAtom, signal: CompareSignal) -> float:
    statement_tokens = _tokenize(_atom_statement(atom))
    signal_tokens = _tokenize(signal.normalized_statement)
    score = _jaccard(statement_tokens, signal_tokens)
    if atom.knowledge_type == _infer_knowledge_type(signal.normalized_statement):
        score += 0.1
    if atom.scope and atom.scope.lower() in signal.normalized_statement.lower():
        score += 0.05
    return round(min(score, 1.0), 4)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_output_dir(input_data: SnapshotBuilderInput) -> Path:
    repo_root = _repo_root()
    if input_data.config.output_dir:
        output_dir = Path(input_data.config.output_dir).expanduser()
        if not output_dir.is_absolute():
            output_dir = repo_root / output_dir
        return output_dir.resolve()

    base_dir = os.environ.get("DORAMAGIC_SNAPSHOT_OUTPUT_DIR")
    if base_dir:
        root = Path(base_dir).expanduser()
        if not root.is_absolute():
            root = repo_root / root
        return (root / input_data.domain_id).resolve()

    return (repo_root / DEFAULT_OUTPUT_DIR / input_data.domain_id).resolve()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _all_synthesis_decisions(report: SynthesisReportData) -> List[SynthesisDecision]:
    decisions = []
    decisions.extend(report.selected_knowledge)
    decisions.extend(report.consensus)
    decisions.extend(report.unique_knowledge)
    decisions.extend(report.excluded_knowledge)
    return decisions


def _decision_lookup(report: SynthesisReportData) -> Dict[str, SynthesisDecision]:
    mapping = {}
    for decision in _all_synthesis_decisions(report):
        for source_ref in decision.source_refs:
            mapping.setdefault(source_ref, decision)
    return mapping


def _signal_sort_key(signal: CompareSignal, decision_lookup: Dict[str, SynthesisDecision]) -> Tuple:
    statement = _statement_for_signal(signal, decision_lookup)
    return (
        _SIGNAL_PRIORITY.get(signal.signal, 99),
        -signal.support_count,
        -signal.match_score,
        statement.lower(),
        signal.signal_id,
    )


def _statement_for_signal(signal: CompareSignal, decision_lookup: Dict[str, SynthesisDecision]) -> str:
    decision = decision_lookup.get(signal.signal_id)
    if decision is not None and decision.statement.strip():
        return decision.statement.strip()
    return signal.normalized_statement.strip()


def _infer_knowledge_type(statement: str) -> str:
    lowered = statement.lower()
    if any(token in lowered for token in ("accept", "input", "interface", "api", "chat")):
        return "interface"
    if any(token in lowered for token in ("persist", "store", "storage", "backend", "directory", "json")):
        return "constraint"
    if any(token in lowered for token in ("because", "improve", "accuracy", "rationale", "why")):
        return "rationale"
    if any(token in lowered for token in ("bootstrap", "bundled", "assemble", "pattern")):
        return "assembly_pattern"
    if any(token in lowered for token in ("fail", "error", "bug", "pitfall")):
        return "failure"
    return "capability"


def _knowledge_type_for_signal(selected_atoms: Sequence[KnowledgeAtom], statement: str) -> str:
    if not selected_atoms:
        return _infer_knowledge_type(statement)

    counts = Counter(atom.knowledge_type for atom in selected_atoms)
    best_count = max(counts.values())
    candidates = sorted(kind for kind, count in counts.items() if count == best_count)
    if len(candidates) == 1:
        return candidates[0]

    scored_atoms = sorted(
        selected_atoms,
        key=lambda atom: (
            -counts[atom.knowledge_type],
            atom.atom_id,
        ),
    )
    return scored_atoms[0].knowledge_type


def _confidence_for_signal(signal: CompareSignal, selected_atoms: Sequence[KnowledgeAtom]) -> str:
    atom_confidences = Counter(atom.confidence for atom in selected_atoms)
    if signal.signal == "ALIGNED" and signal.support_count >= 3:
        return "high"
    if signal.signal == "ALIGNED" and signal.support_count >= 2 and signal.match_score >= 0.8:
        return "high"
    if atom_confidences:
        if atom_confidences.get("high", 0) >= atom_confidences.get("medium", 0):
            return "high"
        if atom_confidences.get("medium", 0) > 0:
            return "medium"
    return "medium"


def _dedupe_evidence_refs(refs: Iterable[EvidenceRef]) -> List[EvidenceRef]:
    deduped = []
    seen = set()
    for ref in refs:
        key = (
            ref.kind,
            ref.path,
            ref.start_line,
            ref.end_line,
            ref.snippet,
            ref.artifact_name,
            ref.source_url,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _tags_from_statement(statement: str, knowledge_type: str) -> List[str]:
    tags = [knowledge_type]
    for token in _tokenize(statement):
        if token in _TAG_STOPWORDS or len(token) < 4:
            continue
        if token not in tags:
            tags.append(token)
        if len(tags) >= 5:
            break
    return tags


def _theme_for_signal(statement: str, knowledge_type: str) -> str:
    lowered = statement.lower()
    if "photo" in lowered or "image" in lowered:
        return "Photo And Text Input"
    if any(token in lowered for token in ("persist", "store", "storage", "json", "directory")):
        return "Storage Pattern"
    if any(token in lowered for token in ("prompt", "accuracy", "quality")):
        return "Quality Improvement"
    if any(token in lowered for token in ("ai", "gpt", "food", "calorie")):
        return "AI Calorie Recognition"
    return "{0} Pattern".format(knowledge_type.replace("_", " ").title())


def _select_atoms_for_signal(
    signal: CompareSignal,
    atoms_by_project: Dict[str, List[KnowledgeAtom]],
) -> List[KnowledgeAtom]:
    selected = []
    for project_id in sorted(set(signal.subject_project_ids)):
        candidates = atoms_by_project.get(project_id, [])
        if not candidates:
            continue
        ranked = sorted(
            candidates,
            key=lambda atom: (
                -_atom_signal_score(atom, signal),
                atom.knowledge_type,
                atom.atom_id,
            ),
        )
        selected.append(ranked[0])
    return selected


def _build_clusters(
    input_data: SnapshotBuilderInput,
    compare_output: CompareOutput,
    decision_lookup: Dict[str, SynthesisDecision],
    atoms_by_project: Dict[str, List[KnowledgeAtom]],
) -> Tuple[List[AtomCluster], Dict[str, List[KnowledgeAtom]]]:
    clusters = []
    selected_atoms_by_signal = {}
    ordered_signals = sorted(compare_output.signals, key=lambda signal: _signal_sort_key(signal, decision_lookup))
    for index, signal in enumerate(ordered_signals, start=1):
        selected_atoms = _select_atoms_for_signal(signal, atoms_by_project)
        selected_atoms_by_signal[signal.signal_id] = selected_atoms
        if not selected_atoms:
            continue
        statement = _statement_for_signal(signal, decision_lookup)
        knowledge_type = _knowledge_type_for_signal(selected_atoms, statement)
        clusters.append(
            AtomCluster(
                cluster_id="CL-{0}-{1:03d}".format(input_data.domain_id, index),
                theme=_theme_for_signal(statement, knowledge_type),
                consensus_statement=statement,
                atom_ids=[atom.atom_id for atom in selected_atoms],
                signal=signal.signal,
                support_count=len({atom.atom_id for atom in selected_atoms}),
            )
        )
    return clusters, selected_atoms_by_signal


def _eligible_brick_signals(
    compare_output: CompareOutput,
    min_support: int,
) -> List[CompareSignal]:
    eligible = []
    for signal in compare_output.signals:
        if signal.signal != "ALIGNED":
            continue
        if signal.support_count < min_support:
            continue
        eligible.append(signal)
    return eligible


def _build_bricks(
    input_data: SnapshotBuilderInput,
    eligible_signals: Sequence[CompareSignal],
    decision_lookup: Dict[str, SynthesisDecision],
    selected_atoms_by_signal: Dict[str, List[KnowledgeAtom]],
) -> List[DomainBrick]:
    ordered_signals = sorted(eligible_signals, key=lambda signal: _signal_sort_key(signal, decision_lookup))
    bricks = []
    for index, signal in enumerate(ordered_signals, start=1):
        statement = _statement_for_signal(signal, decision_lookup)
        selected_atoms = selected_atoms_by_signal.get(signal.signal_id, [])
        evidence_refs = []
        evidence_refs.extend(signal.evidence_refs)
        for atom in selected_atoms:
            evidence_refs.extend(atom.evidence_refs[:2])
        bricks.append(
            DomainBrick(
                brick_id="B-{0}-{1:03d}".format(input_data.domain_id, index),
                domain_id=input_data.domain_id,
                knowledge_type=_knowledge_type_for_signal(selected_atoms, statement),
                statement=statement,
                confidence=_confidence_for_signal(signal, selected_atoms),
                signal=signal.signal,
                source_project_ids=sorted(set(signal.subject_project_ids)),
                support_count=signal.support_count,
                evidence_refs=_dedupe_evidence_refs(evidence_refs),
                tags=_tags_from_statement(statement, _knowledge_type_for_signal(selected_atoms, statement)),
            )
        )
    return bricks


def _coverage_ratio(atom_count: int, clusters: Sequence[AtomCluster]) -> float:
    if atom_count <= 0:
        return 0.0
    covered_atoms = set()
    for cluster in clusters:
        covered_atoms.update(cluster.atom_ids)
    return round(min(1.0, len(covered_atoms) / atom_count), 2)


def _build_stats(
    fingerprints: Sequence[ProjectFingerprint],
    atoms: Sequence[KnowledgeAtom],
    clusters: Sequence[AtomCluster],
    bricks: Sequence[DomainBrick],
) -> SnapshotStats:
    return SnapshotStats(
        project_count=len(fingerprints),
        atom_count=len(atoms),
        cluster_count=len(clusters),
        brick_count=len(bricks),
        deprecation_count=0,
        coverage_ratio=_coverage_ratio(len(atoms), clusters),
    )


def _unique_insights(
    compare_output: CompareOutput,
    report: SynthesisReportData,
    decision_lookup: Dict[str, SynthesisDecision],
) -> List[str]:
    lines = []
    seen = set()
    original_signal_ids = {signal.signal_id for signal in compare_output.signals if signal.signal == "ORIGINAL"}
    for decision in report.unique_knowledge + report.selected_knowledge:
        if not set(decision.source_refs) & original_signal_ids:
            continue
        if decision.statement in seen:
            continue
        seen.add(decision.statement)
        source_hint = ", ".join(decision.source_refs[:1]) if decision.source_refs else "unique source"
        lines.append(
            "- **{0}**: {1} ({2})".format(
                decision.statement,
                decision.rationale or "Single-project insight worth keeping in view.",
                source_hint,
            )
        )
    for signal in compare_output.signals:
        if signal.signal != "ORIGINAL":
            continue
        statement = _statement_for_signal(signal, decision_lookup)
        if statement in seen:
            continue
        seen.add(statement)
        lines.append(
            "- **{0}**: unique to {1}.".format(
                statement,
                ", ".join(sorted(signal.subject_project_ids)),
            )
        )
    return lines


def _disputed_lines(compare_output: CompareOutput, decision_lookup: Dict[str, SynthesisDecision]) -> List[str]:
    lines = []
    for signal in sorted(compare_output.signals, key=lambda item: _signal_sort_key(item, decision_lookup)):
        if signal.signal not in ("DIVERGENT", "CONTESTED", "DRIFTED"):
            continue
        statement = _statement_for_signal(signal, decision_lookup)
        suffix = signal.notes or "Cross-project disagreement requires manual resolution."
        lines.append(
            "- **{0}** ({1}): {2}".format(
                statement,
                signal.signal,
                suffix,
            )
        )
    return lines


def _community_lines(community_knowledge: CommunityKnowledge) -> List[str]:
    lines = []
    for item in community_knowledge.skills + community_knowledge.tutorials + community_knowledge.use_cases:
        reusable = "; ".join(item.reusable_knowledge[:2]) if item.reusable_knowledge else "no reusable notes"
        lines.append(
            "- **{0}**: {1}".format(item.name, reusable)
        )
    return lines


def _brick_lines(bricks: Sequence[DomainBrick], project_count: int) -> List[str]:
    if not bricks:
        return [
            "No knowledge signal met the current `min_support_for_brick` threshold.",
        ]
    lines = []
    for brick in bricks:
        lines.append(
            "- **{0}** ({1}/{2} projects): {3}".format(
                brick.statement,
                brick.support_count,
                project_count,
                " / ".join(brick.tags[:3]) if brick.tags else brick.knowledge_type,
            )
        )
    return lines


def _cluster_lines(clusters: Sequence[AtomCluster]) -> List[str]:
    if not clusters:
        return ["No atom clusters were built from the current compare output."]
    lines = []
    for cluster in clusters:
        lines.append(
            "- **{0}** ({1} atoms, {2}): {3}".format(
                cluster.theme,
                len(cluster.atom_ids),
                cluster.signal,
                cluster.consensus_statement,
            )
        )
    return lines


def _render_truth_markdown(
    input_data: SnapshotBuilderInput,
    snapshot_version: str,
    bricks: Sequence[DomainBrick],
    clusters: Sequence[AtomCluster],
    compare_output: CompareOutput,
    report: SynthesisReportData,
    community_knowledge: CommunityKnowledge,
    decision_lookup: Dict[str, SynthesisDecision],
) -> str:
    display_name = input_data.domain_display_name or input_data.domain_id
    project_count = len(compare_output.compared_projects)
    unique_lines = _unique_insights(compare_output, report, decision_lookup)
    disputed_lines = _disputed_lines(compare_output, decision_lookup)
    community_lines = _community_lines(community_knowledge)
    open_questions = report.open_questions or ["No open questions recorded."]

    sections = [
        "# Domain Truth: {0}".format(display_name),
        "",
        "> Snapshot version: {0}".format(snapshot_version),
        "> Projects analyzed: {0}".format(project_count),
        "",
        "## Consensus Bricks",
    ]
    sections.extend(_brick_lines(bricks, project_count))
    sections.extend(
        [
            "",
            "## Atom Clusters",
        ]
    )
    sections.extend(_cluster_lines(clusters))
    sections.extend(
        [
            "",
            "## Unique Insights",
        ]
    )
    sections.extend(unique_lines or ["- No unique insights were preserved in this snapshot."])
    sections.extend(
        [
            "",
            "## Contested Or Divergent Areas",
        ]
    )
    sections.extend(disputed_lines or ["- No contested or divergent signals were recorded."])
    sections.extend(
        [
            "",
            "## Community Reuse Notes",
        ]
    )
    sections.extend(community_lines or ["- No community knowledge was attached to this snapshot."])
    sections.extend(
        [
            "",
            "## Open Questions",
        ]
    )
    sections.extend("- {0}".format(item) for item in open_questions)
    sections.append("")
    return "\n".join(sections)


def _atom_rows(
    fingerprints: Sequence[ProjectFingerprint],
    clusters: Sequence[AtomCluster],
) -> List[dict]:
    project_by_atom_id = {}
    atom_by_id = {}
    for fingerprint in fingerprints:
        for atom in fingerprint.knowledge_atoms:
            project_by_atom_id[atom.atom_id] = fingerprint.project.repo_id
            atom_by_id[atom.atom_id] = atom

    cluster_membership = {}
    for cluster in clusters:
        for atom_id in cluster.atom_ids:
            cluster_membership.setdefault(atom_id, []).append(cluster.cluster_id)

    rows = []
    for atom_id in sorted(atom_by_id):
        atom = atom_by_id[atom_id]
        rows.append(
            {
                "atom_id": atom.atom_id,
                "project_id": project_by_atom_id.get(atom.atom_id),
                "knowledge_type": atom.knowledge_type,
                "subject": atom.subject,
                "predicate": atom.predicate,
                "object": atom.object,
                "scope": atom.scope,
                "normative_force": atom.normative_force,
                "confidence": atom.confidence,
                "statement": _atom_statement(atom),
                "cluster_ids": cluster_membership.get(atom.atom_id, []),
            }
        )
    return rows


def _write_atoms_json(output_dir: Path, atoms: Sequence[KnowledgeAtom]) -> None:
    payload = [_model_dump(atom) for atom in atoms]
    _write_json(output_dir / ATOMS_JSON_FILENAME, payload)


def _write_atoms_parquet(output_dir: Path, rows: Sequence[dict]) -> Optional[str]:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None

    target = output_dir / ATOMS_PARQUET_FILENAME
    dataframe = pd.DataFrame(list(rows))
    try:
        dataframe.to_parquet(target, index=False)
    except Exception:
        return None
    return target.name


def _write_sqlite(
    output_dir: Path,
    atom_rows: Sequence[dict],
    clusters: Sequence[AtomCluster],
    bricks: Sequence[DomainBrick],
) -> Optional[str]:
    target = output_dir / SQLITE_FILENAME
    connection = sqlite3.connect(str(target))
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS atoms (
                atom_id TEXT PRIMARY KEY,
                project_id TEXT,
                knowledge_type TEXT,
                subject TEXT,
                predicate TEXT,
                object TEXT,
                scope TEXT,
                normative_force TEXT,
                confidence TEXT,
                statement TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clusters (
                cluster_id TEXT PRIMARY KEY,
                theme TEXT,
                consensus_statement TEXT,
                signal TEXT,
                support_count INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cluster_atoms (
                cluster_id TEXT,
                atom_id TEXT,
                PRIMARY KEY (cluster_id, atom_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bricks (
                brick_id TEXT PRIMARY KEY,
                domain_id TEXT,
                knowledge_type TEXT,
                statement TEXT,
                confidence TEXT,
                signal TEXT,
                support_count INTEGER
            )
            """
        )
        cursor.execute("DELETE FROM atoms")
        cursor.execute("DELETE FROM clusters")
        cursor.execute("DELETE FROM cluster_atoms")
        cursor.execute("DELETE FROM bricks")
        cursor.executemany(
            """
            INSERT INTO atoms (
                atom_id, project_id, knowledge_type, subject, predicate, object,
                scope, normative_force, confidence, statement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["atom_id"],
                    row["project_id"],
                    row["knowledge_type"],
                    row["subject"],
                    row["predicate"],
                    row["object"],
                    row["scope"],
                    row["normative_force"],
                    row["confidence"],
                    row["statement"],
                )
                for row in atom_rows
            ],
        )
        cursor.executemany(
            """
            INSERT INTO clusters (
                cluster_id, theme, consensus_statement, signal, support_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    cluster.cluster_id,
                    cluster.theme,
                    cluster.consensus_statement,
                    cluster.signal,
                    cluster.support_count,
                )
                for cluster in clusters
            ],
        )
        cursor.executemany(
            "INSERT INTO cluster_atoms (cluster_id, atom_id) VALUES (?, ?)",
            [
                (cluster.cluster_id, atom_id)
                for cluster in clusters
                for atom_id in cluster.atom_ids
            ],
        )
        cursor.executemany(
            """
            INSERT INTO bricks (
                brick_id, domain_id, knowledge_type, statement, confidence, signal, support_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    brick.brick_id,
                    brick.domain_id,
                    brick.knowledge_type,
                    brick.statement,
                    brick.confidence,
                    brick.signal,
                    brick.support_count,
                )
                for brick in bricks
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return target.name


def _snapshot_output(
    input_data: SnapshotBuilderInput,
    snapshot_version: str,
    stats: SnapshotStats,
    atoms_parquet_path: Optional[str],
    sqlite_path: Optional[str],
) -> SnapshotBuilderOutput:
    return SnapshotBuilderOutput(
        domain_id=input_data.domain_id,
        snapshot_version=snapshot_version,
        domain_bricks_path=SNAPSHOT_FILENAME,
        domain_truth_path=TRUTH_FILENAME,
        atoms_parquet_path=atoms_parquet_path,
        domain_map_sqlite_path=sqlite_path,
        snapshot_manifest_path=MANIFEST_FILENAME,
        stats=stats,
    )


def _validate_inputs(
    input_data: SnapshotBuilderInput,
) -> Tuple[Optional[List[ProjectFingerprint]], Optional[CompareOutput], Optional[SynthesisReportData], Optional[CommunityKnowledge]]:
    if not input_data.fingerprints:
        return None, None, None, None

    fingerprints = [_model_validate(ProjectFingerprint, item) for item in input_data.fingerprints]
    compare_output = _model_validate(CompareOutput, input_data.compare_output)
    synthesis_report = _model_validate(SynthesisReportData, input_data.synthesis_report)
    community_knowledge = _model_validate(CommunityKnowledge, input_data.community_knowledge or {})
    return fingerprints, compare_output, synthesis_report, community_knowledge


def run_snapshot_builder(input: SnapshotBuilderInput) -> ModuleResultEnvelope[SnapshotBuilderOutput]:
    """Build a domain snapshot and write fixed output artifacts."""

    started_at = time.perf_counter()
    try:
        if not input.fingerprints:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            return _blocked_envelope(ErrorCodes.INPUT_INVALID, elapsed_ms)

        try:
            fingerprints, compare_output, synthesis_report, community_knowledge = _validate_inputs(input)
        except Exception:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            return _blocked_envelope(ErrorCodes.SCHEMA_MISMATCH, elapsed_ms)

        if fingerprints is None or compare_output is None or synthesis_report is None or community_knowledge is None:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            return _blocked_envelope(ErrorCodes.INPUT_INVALID, elapsed_ms)

        atoms = []
        atoms_by_project = {}
        for fingerprint in sorted(fingerprints, key=lambda item: item.project.repo_id):
            ordered_atoms = sorted(fingerprint.knowledge_atoms, key=lambda atom: atom.atom_id)
            atoms.extend(ordered_atoms)
            atoms_by_project[fingerprint.project.repo_id] = ordered_atoms

        decision_lookup = _decision_lookup(synthesis_report)
        clusters, selected_atoms_by_signal = _build_clusters(
            input,
            compare_output,
            decision_lookup,
            atoms_by_project,
        )
        bricks = _build_bricks(
            input,
            _eligible_brick_signals(compare_output, input.config.min_support_for_brick),
            decision_lookup,
            selected_atoms_by_signal,
        )
        stats = _build_stats(fingerprints, atoms, clusters, bricks)
        snapshot_version = _now_utc()
        display_name = input.domain_display_name or input.domain_id
        snapshot = DomainSnapshot(
            domain_id=input.domain_id,
            domain_display_name=display_name,
            snapshot_version=snapshot_version,
            bricks=bricks,
            atom_clusters=clusters,
            deprecation_events=[],
            stats=stats,
        )
        truth_md = _render_truth_markdown(
            input,
            snapshot_version,
            bricks,
            clusters,
            compare_output,
            synthesis_report,
            community_knowledge,
            decision_lookup,
        )

        output_dir = _resolve_output_dir(input)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / SNAPSHOT_FILENAME, _model_dump(snapshot))
        _write_text(output_dir / TRUTH_FILENAME, truth_md)
        _write_atoms_json(output_dir, atoms)

        atom_rows = _atom_rows(fingerprints, clusters)
        atoms_parquet_path = None
        if input.config.include_parquet:
            atoms_parquet_path = _write_atoms_parquet(output_dir, atom_rows)

        sqlite_path = None
        if input.config.include_sqlite:
            sqlite_path = _write_sqlite(output_dir, atom_rows, clusters, bricks)

        output = _snapshot_output(
            input,
            snapshot_version,
            stats,
            atoms_parquet_path,
            sqlite_path,
        )
        _write_json(output_dir / MANIFEST_FILENAME, _model_dump(output))

        warnings = []
        status = "ok"
        if not bricks:
            status = "degraded"
            warnings.append(
                WarningItem(
                    code="NO_BRICKS",
                    message="No ALIGNED signal met min_support_for_brick={0}.".format(
                        input.config.min_support_for_brick
                    ),
                )
            )

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return ModuleResultEnvelope(
            module_name=MODULE_NAME,
            status=status,
            error_code=None,
            warnings=warnings,
            data=output,
            metrics=_metrics(elapsed_ms),
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return _error_envelope(elapsed_ms, str(exc))
