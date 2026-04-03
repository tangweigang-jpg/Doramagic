"""三轨预过滤器。确定性，不用 LLM。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..source_adapters.base import RawExperienceRecord


class FilterTrack(StrEnum):
    TRACK_1_CODE_EVIDENCE = "track_1"
    TRACK_2_DESIGN_BOUNDARY = "track_2"
    TRACK_3_SIGNAL_SCORE = "track_3"
    REJECTED = "rejected"


@dataclass
class FilterResult:
    record: RawExperienceRecord
    track: FilterTrack
    score: float  # 轨道三的得分，轨道一/二为 0
    reason: str


def filter_records(records: list[RawExperienceRecord]) -> list[FilterResult]:
    """对所有记录执行三轨过滤，返回通过的记录及其轨道归属。"""
    results: list[FilterResult] = []

    for record in records:
        signals = record.signals

        # 轨道一：代码共证（需同时有技术失败信号，避免收录 typo/doc fix）
        if signals.get("has_code_fix"):
            labels = {label.lower() for label in signals.get("labels", [])}
            has_failure_signal = (
                labels & {"bug", "regression", "incident", "data-issue"}
                or signals.get("has_repro_steps")
                or signals.get("has_logs_or_evidence")
                or signals.get("body_length", 0) >= 80
            )
            if has_failure_signal:
                results.append(
                    FilterResult(
                        record=record,
                        track=FilterTrack.TRACK_1_CODE_EVIDENCE,
                        score=0,
                        reason="Issue 已关闭且关联 merged PR + 有技术失败信号",
                    )
                )
                continue

        # 轨道二：边界妥协
        if signals.get("is_design_boundary"):
            results.append(
                FilterResult(
                    record=record,
                    track=FilterTrack.TRACK_2_DESIGN_BOUNDARY,
                    score=0,
                    reason=f"设计边界标签 + body_length={signals.get('body_length', 0)}",
                )
            )
            continue

        # 轨道三：信号打分
        score = _compute_signal_score(signals)
        threshold = _get_threshold(record, signals)

        if score >= threshold:
            results.append(
                FilterResult(
                    record=record,
                    track=FilterTrack.TRACK_3_SIGNAL_SCORE,
                    score=score,
                    reason=f"信号得分 {score:.1f} >= 阈值 {threshold}",
                )
            )
        else:
            results.append(
                FilterResult(
                    record=record,
                    track=FilterTrack.REJECTED,
                    score=score,
                    reason=f"信号得分 {score:.1f} < 阈值 {threshold}",
                )
            )

    return results


def _compute_signal_score(signals: dict) -> float:
    """轨道三的加权打分。"""
    score = 0.0

    if signals.get("has_repro_steps"):
        score += 2.5
    if signals.get("expert_reply"):
        score += 2.0
    if signals.get("has_logs_or_evidence"):
        score += 1.5

    labels = {label.lower() for label in signals.get("labels", [])}
    if labels & {"bug", "regression", "incident", "data-issue"}:
        score += 1.5

    if signals.get("is_design_boundary"):
        score += 2.0

    if signals.get("closed_by_maintainer"):
        score += 1.0

    approval = signals.get("approval_score", 0)
    if approval >= 3:
        score += 1.0

    reply_count = signals.get("reply_count", 0)
    if reply_count >= 3:
        score += 0.5

    body_length = signals.get("body_length", 0)
    if body_length >= 120:
        score += 0.5

    # 减分
    if labels & {"feature", "enhancement", "feature-request"} and not signals.get(
        "has_logs_or_evidence"
    ):
        score -= 1.5
    if labels & {"question"} and not signals.get("has_repro_steps"):
        score -= 1.5

    return score


def _get_threshold(record: RawExperienceRecord, signals: dict) -> float:
    """根据类型动态调整阈值。"""
    labels = {label.lower() for label in signals.get("labels", [])}
    if labels & {"bug", "regression", "incident"}:
        return 3.0
    if record.pre_category == "bug":
        return 3.0
    if record.pre_category in ("workaround", "anti_pattern"):
        return 3.0
    if labels & {"discussion"}:
        return 3.5
    return 4.5
