"""Mock cross-project compare module for Round 2 race development."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from doramagic_contracts.base import EvidenceRef, KnowledgeAtom, ProjectFingerprint
from doramagic_contracts.cross_project import (
    CompareInput,
    CompareMetrics,
    CompareOutput,
    CompareSignal,
)
from doramagic_contracts.envelope import (
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
)

MODULE_NAME = "cross-project.compare"
COMPARISON_FILENAME = "comparison_result.json"
VALID_SIGNALS = {
    "ALIGNED",
    "STALE",
    "MISSING",
    "ORIGINAL",
    "DRIFTED",
    "DIVERGENT",
    "CONTESTED",
}
TOKEN_SYNONYMS = {
    "parses": "parse",
    "parsed": "parse",
    "parsing": "parse",
    "parseas": "parse",
    "parsesinto": "parse",
    "normalized": "normalize",
    "normalizes": "normalize",
    "normalised": "normalize",
    "contract": "schema",
    "structured": "schema",
    "jsonschema": "schema",
    "parsedas": "parse",
    "inputs": "input",
    "foods": "food",
}


@dataclass(frozen=True)
class AtomRecord:
    project_id: str
    project_name: str
    atom: KnowledgeAtom
    normalized_statement: str
    lexical_tokens: tuple[str, ...]
    semantic_tokens: tuple[str, ...]
    subject_key: str
    predicate_key: str
    object_key: str
    community_signature: tuple[str, str, str, str]


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _canonical_tokens(value: str) -> tuple[str, ...]:
    tokens = []
    for raw_token in _normalize_text(value).split():
        token = TOKEN_SYNONYMS.get(raw_token, raw_token)
        if token:
            tokens.append(token)
    return tuple(tokens)


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    intersection = len(left_set & right_set)
    union = len(left_set | right_set)
    if union == 0:
        return 0.0
    return intersection / union


def _slot_score(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    if overlap >= 0.8:
        return 0.9
    if overlap >= 0.5:
        return 0.75
    if overlap > 0:
        return 0.62
    return 0.0


def _canonical_statement(atom: KnowledgeAtom) -> str:
    parts = [
        atom.knowledge_type,
        atom.subject,
        atom.predicate,
        atom.object,
        atom.scope,
        atom.normative_force,
    ]
    return " ".join(_canonical_tokens(" ".join(parts)))


def _build_record(fingerprint: ProjectFingerprint, atom: KnowledgeAtom) -> AtomRecord:
    community = fingerprint.community_signals
    return AtomRecord(
        project_id=fingerprint.project.repo_id,
        project_name=fingerprint.project.full_name,
        atom=atom,
        normalized_statement=_canonical_statement(atom),
        lexical_tokens=_canonical_tokens(f"{atom.subject} {atom.predicate} {atom.object}"),
        semantic_tokens=_canonical_tokens(
            f"{atom.knowledge_type} {atom.subject} {atom.predicate} {atom.object}"
        ),
        subject_key=" ".join(_canonical_tokens(atom.subject)),
        predicate_key=" ".join(_canonical_tokens(atom.predicate)),
        object_key=" ".join(_canonical_tokens(atom.object)),
        community_signature=(
            community.issue_activity or "unknown",
            community.pr_merge_velocity or "unknown",
            community.changelog_frequency or "unknown",
            community.sentiment or "unknown",
        ),
    )


def _lexical_score(left: AtomRecord, right: AtomRecord) -> float:
    if left.normalized_statement == right.normalized_statement:
        return 1.0
    return _jaccard(left.lexical_tokens, right.lexical_tokens)


def _semantic_score(left: AtomRecord, right: AtomRecord) -> float:
    return _jaccard(left.semantic_tokens, right.semantic_tokens)


def _structured_score(left: AtomRecord, right: AtomRecord) -> float:
    slots = [
        _slot_score(left.subject_key, right.subject_key),
        _slot_score(left.predicate_key, right.predicate_key),
        _slot_score(left.object_key, right.object_key),
        1.0 if left.atom.knowledge_type == right.atom.knowledge_type else 0.0,
        1.0 if left.atom.scope == right.atom.scope else 0.0,
    ]
    return sum(slots) / len(slots)


def _match_score(left: AtomRecord, right: AtomRecord) -> float:
    lexical = _lexical_score(left, right)
    semantic = _semantic_score(left, right)
    structured = _structured_score(left, right)
    if lexical >= 0.92:
        return round(lexical, 4)
    return round(max(semantic, structured, (semantic + structured) / 2), 4)


def _collect_records(fingerprints: Sequence[ProjectFingerprint]) -> list[AtomRecord]:
    records: list[AtomRecord] = []
    for fingerprint in fingerprints:
        for atom in fingerprint.knowledge_atoms:
            records.append(_build_record(fingerprint, atom))
    records.sort(key=lambda item: (item.project_id, item.atom.atom_id))
    return records


def _pairwise_matches(
    records: Sequence[AtomRecord],
    partial_threshold: float,
) -> dict[tuple[int, int], float]:
    matches: dict[tuple[int, int], float] = {}
    for left_index in range(len(records)):
        for right_index in range(left_index + 1, len(records)):
            left = records[left_index]
            right = records[right_index]
            if left.project_id == right.project_id:
                continue
            score = _match_score(left, right)
            if score >= partial_threshold:
                matches[(left_index, right_index)] = score
    return matches


def _components(
    records: Sequence[AtomRecord], matches: dict[tuple[int, int], float]
) -> list[list[int]]:
    union_find = _UnionFind(len(records))
    for (left_index, right_index), _score in matches.items():
        union_find.union(left_index, right_index)

    grouped: dict[int, list[int]] = {}
    for index in range(len(records)):
        root = union_find.find(index)
        grouped.setdefault(root, []).append(index)

    return [
        sorted(indexes, key=lambda item: (records[item].project_id, records[item].atom.atom_id))
        for indexes in grouped.values()
    ]


def _signal_id(signal: str, project_ids: Sequence[str], normalized_statement: str) -> str:
    stable_payload = "{0}|{1}|{2}".format(
        signal,
        ",".join(project_ids),
        normalized_statement,
    )
    digest = hashlib.sha1(stable_payload.encode("utf-8")).hexdigest()[:12].upper()
    return f"SIG-{digest}"


def _community_independence(records: Sequence[AtomRecord]) -> float:
    if not records:
        return 0.0
    project_diversity = len({record.project_id for record in records}) / len(records)
    community_diversity = len({record.community_signature for record in records}) / len(records)
    return round(min(1.0, (0.7 * project_diversity) + (0.3 * community_diversity)), 2)


def _cluster_score(
    component: Sequence[int],
    records: Sequence[AtomRecord],
    matches: dict[tuple[int, int], float],
) -> float:
    scores = []
    for left_pos in range(len(component)):
        for right_pos in range(left_pos + 1, len(component)):
            key = tuple(sorted((component[left_pos], component[right_pos])))
            if key in matches:
                scores.append(matches[key])
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def _representative_record(component: Sequence[int], records: Sequence[AtomRecord]) -> AtomRecord:
    representative = min(
        (records[index] for index in component),
        key=lambda item: (item.normalized_statement, item.project_id, item.atom.atom_id),
    )
    return representative


def _second_pass_original(
    component: Sequence[int],
    component_score: float,
    records: Sequence[AtomRecord],
    matches: dict[tuple[int, int], float],
    partial_threshold: float,
) -> tuple[bool, str]:
    if len(component) != 1:
        return False, "second pass skipped: clustered with another project"

    index = component[0]
    best_alternative = 0.0
    for (left_index, right_index), score in matches.items():
        if index in (left_index, right_index):
            best_alternative = max(best_alternative, score)

    if component_score >= partial_threshold:
        best_alternative = max(best_alternative, component_score)

    if best_alternative < partial_threshold:
        return True, "second-pass retrieval found no comparable atom above partial threshold"
    return False, f"second-pass retrieval found alternative score {best_alternative:.2f}"


def _component_signal(
    component: Sequence[int],
    records: Sequence[AtomRecord],
    matches: dict[tuple[int, int], float],
    input_data: CompareInput,
) -> CompareSignal | None:
    project_ids = sorted({records[index].project_id for index in component})
    support_count = len(project_ids)
    support_independence = _community_independence([records[index] for index in component])
    match_score = _cluster_score(component, records, matches)
    representative = _representative_record(component, records)
    normalized_statement = representative.normalized_statement
    project_count = len(input_data.fingerprints)
    coverage = support_count / project_count
    evidence_refs: list[EvidenceRef] = []
    for index in component:
        evidence_refs.extend(records[index].atom.evidence_refs[:1])

    signal = None
    notes = None
    if (
        support_count >= input_data.config.missing_min_support
        and support_count < project_count
        and coverage >= input_data.config.missing_min_coverage
        and support_independence >= input_data.config.missing_min_independence
    ):
        signal = "MISSING"
        notes = f"coverage={coverage:.2f}; independence={support_independence:.2f}"
    elif support_count >= 2 and match_score >= input_data.config.semantic_threshold:
        signal = "ALIGNED"
        if match_score >= input_data.config.exact_aligned_threshold:
            notes = "exact alignment via lexical/structured match"
        else:
            notes = "semantic wording variation resolved by structured matching"
    elif support_count >= 2 and match_score >= input_data.config.partial_threshold:
        signal = "DRIFTED"
        notes = "partial overlap across projects"
    else:
        confirmed_original, second_pass_note = _second_pass_original(
            component,
            match_score,
            records,
            matches,
            input_data.config.partial_threshold,
        )
        if confirmed_original:
            signal = "ORIGINAL"
            match_score = min(match_score, input_data.config.partial_threshold - 0.01)
            notes = second_pass_note

    if signal is None:
        return None
    if signal not in VALID_SIGNALS:
        raise ValueError(f"Unexpected signal emitted: {signal}")

    return CompareSignal(
        signal_id=_signal_id(signal, project_ids, normalized_statement),
        signal=signal,
        subject_project_ids=project_ids,
        normalized_statement=normalized_statement,
        support_count=support_count,
        support_independence=support_independence,
        match_score=match_score,
        evidence_refs=evidence_refs,
        notes=notes,
    )


def _comparison_output_path(domain_id: str) -> Path:
    base_dir = os.environ.get("DORAMAGIC_COMPARE_OUTPUT_DIR")
    if base_dir:
        root = Path(base_dir).expanduser().resolve()
    else:
        root = Path(tempfile.gettempdir()) / "doramagic_compare"
    return root / domain_id / COMPARISON_FILENAME


def _write_comparison_result(output: CompareOutput) -> None:
    target_path = _comparison_output_path(output.domain_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(output.model_dump(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _blocked_envelope(error_code: str) -> ModuleResultEnvelope[CompareOutput]:
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="blocked",
        error_code=error_code,
        data=None,
        metrics=RunMetrics(
            wall_time_ms=0,
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )


def run_compare(input_data: CompareInput) -> ModuleResultEnvelope[CompareOutput]:
    """Run deterministic mock comparison across project fingerprints."""

    started_at = time.perf_counter()
    if len(input_data.fingerprints) < 2:
        return _blocked_envelope(ErrorCodes.INPUT_INVALID)

    for fingerprint in input_data.fingerprints:
        if fingerprint.schema_version != "dm.project-fingerprint.v1":
            return _blocked_envelope(ErrorCodes.SCHEMA_MISMATCH)

    records = _collect_records(input_data.fingerprints)
    matches = _pairwise_matches(records, input_data.config.partial_threshold)
    components = _components(records, matches)

    signals = []
    for component in components:
        signal = _component_signal(component, records, matches, input_data)
        if signal is not None:
            signals.append(signal)

    signals.sort(
        key=lambda item: (
            item.signal,
            ",".join(item.subject_project_ids),
            item.normalized_statement,
            item.signal_id,
        )
    )

    output = CompareOutput(
        domain_id=input_data.domain_id,
        compared_projects=[fingerprint.project.repo_id for fingerprint in input_data.fingerprints],
        signals=signals,
        metrics=CompareMetrics(
            project_count=len(input_data.fingerprints),
            atom_count=len(records),
            aligned_count=sum(1 for signal in signals if signal.signal == "ALIGNED"),
            missing_count=sum(1 for signal in signals if signal.signal == "MISSING"),
            original_count=sum(1 for signal in signals if signal.signal == "ORIGINAL"),
            drifted_count=sum(1 for signal in signals if signal.signal == "DRIFTED"),
        ),
    )
    _write_comparison_result(output)

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="ok",
        error_code=None,
        data=output,
        metrics=RunMetrics(
            wall_time_ms=max(elapsed_ms, 1),
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )
