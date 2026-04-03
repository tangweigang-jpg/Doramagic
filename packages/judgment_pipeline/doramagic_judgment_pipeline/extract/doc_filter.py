"""文档过滤器 — 为仓库文档内容做相关性过滤。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from ..source_adapters.base import RawExperienceRecord


class DocFilterTrack(StrEnum):
    BLACKLIST_EXCLUDED = "blacklist_excluded"
    WHITELIST_PASSED = "whitelist_passed"
    SIGNAL_PASSED = "signal_passed"
    SIGNAL_REJECTED = "signal_rejected"


@dataclass
class DocFilterResult:
    record: RawExperienceRecord
    track: DocFilterTrack
    score: float
    reason: str

    @property
    def passed(self) -> bool:
        return self.track in (DocFilterTrack.WHITELIST_PASSED, DocFilterTrack.SIGNAL_PASSED)


# 黑名单：这些段落标题几乎不含领域知识或资源边界信息
HEADING_BLACKLIST = re.compile(
    r"(?i)^(contribut|license|changelog|release\s+note|acknowledgment|sponsor|"
    r"code\s+of\s+conduct|citation|badge|build\s+status|ci[/ ]cd|"
    r"table\s+of\s+contents|development\s+setup|how\s+to\s+contribute|"
    r"pull\s+request|commit\s+convention|git\s+workflow)"
)

# 白名单：这些段落标题高概率含有知识层或资源层信息
HEADING_WHITELIST = re.compile(
    r"(?i)(limitation|caveat|known\s+issue|breaking\s+change|deprecat|"
    r"constraint|warning|important|requirement|architecture|design|"
    r"how\s+it\s+works|concept|overview|api\s+reference|usage|"
    r"configuration|faq|troubleshoot|migration|upgrade|"
    r"performance|benchmark|comparison|vs\s+|alternative)"
)


def filter_doc_records(records: list[RawExperienceRecord]) -> list[DocFilterResult]:
    """过滤文档记录。返回每条记录的过滤结果。"""
    results: list[DocFilterResult] = []

    for record in records:
        title_lower = record.title.lower()
        signals = record.signals

        # Step 1: 黑名单硬排除
        if HEADING_BLACKLIST.search(title_lower):
            results.append(
                DocFilterResult(
                    record=record,
                    track=DocFilterTrack.BLACKLIST_EXCLUDED,
                    score=0,
                    reason=f"标题命中黑名单: {record.title}",
                )
            )
            continue

        # Step 2: 白名单快速通过
        if HEADING_WHITELIST.search(title_lower):
            results.append(
                DocFilterResult(
                    record=record,
                    track=DocFilterTrack.WHITELIST_PASSED,
                    score=10.0,
                    reason=f"标题命中白名单: {record.title}",
                )
            )
            continue

        # Step 3: 信号打分
        score = _compute_doc_score(signals)
        threshold = _get_doc_threshold(record)

        if score >= threshold:
            results.append(
                DocFilterResult(
                    record=record,
                    track=DocFilterTrack.SIGNAL_PASSED,
                    score=score,
                    reason=f"文档信号得分 {score:.1f} >= 阈值 {threshold}",
                )
            )
        else:
            results.append(
                DocFilterResult(
                    record=record,
                    track=DocFilterTrack.SIGNAL_REJECTED,
                    score=score,
                    reason=f"文档信号得分 {score:.1f} < 阈值 {threshold}",
                )
            )

    return results


def _compute_doc_score(signals: dict) -> float:
    """文档信号打分。"""
    score = 0.0

    body_length = signals.get("body_length", 0)
    if body_length >= 200:
        score += 1.0
    if body_length >= 500:
        score += 0.5

    if signals.get("has_code_blocks"):
        score += 1.5

    if signals.get("has_warnings"):
        score += 2.5

    if signals.get("has_api_boundaries"):
        score += 2.5

    if signals.get("has_domain_rules"):
        score += 2.0

    return score


def _get_doc_threshold(record: RawExperienceRecord) -> float:
    """根据文档类型调整阈值。"""
    source_type = record.signals.get("source_type", "")

    if source_type == "github_readme":
        return 2.0
    if source_type == "github_changelog":
        return 3.0
    if source_type == "github_deps":
        return 0.0
    if source_type == "github_doc":
        return 2.5
    if source_type == "github_code":
        return 0.0

    return 3.0
