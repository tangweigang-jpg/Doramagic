"""判断采集流水线。线性编排：Fetch → Filter → Classify → Extract → Dedup → Store。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import Judgment
from doramagic_shared_utils.llm_adapter import LLMAdapter

from .extract.classifier import classify_record
from .extract.extractor import extract_judgments
from .extract.filter import FilterTrack, filter_records
from .refine.dedup import dedup_judgments
from .source_adapters.github import GitHubAdapter
from .store.linker import auto_link

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    fetched: int = 0
    filtered_in: int = 0
    filtered_out: int = 0
    classified: int = 0
    extracted: int = 0
    after_dedup: int = 0
    stored: int = 0
    relations_created: int = 0
    errors: list[str] = field(default_factory=list)


async def run_pipeline(
    github_token: str,
    target: dict,
    domain: str,
    judgments_path: str | Path,
    adapter: LLMAdapter,
) -> PipelineResult:
    """
    运行完整采集流水线。

    target 示例:
    {"owner": "freqtrade", "repo": "freqtrade", "state": "closed",
     "labels": "bug", "min_comments": 3, "since": "2024-01-01", "max_pages": 5}
    """
    result = PipelineResult()

    # 1. Fetch
    logger.info("开始拉取 %s/%s ...", target.get("owner"), target.get("repo"))
    github = GitHubAdapter(token=github_token)
    records = await github.fetch(target)
    result.fetched = len(records)
    logger.info("拉取完成: %d 条记录", result.fetched)

    # 2. Filter
    filter_results = filter_records(records)
    passed = [fr for fr in filter_results if fr.track != FilterTrack.REJECTED]
    result.filtered_in = len(passed)
    result.filtered_out = len(filter_results) - len(passed)
    logger.info("过滤完成: 通过 %d / 丢弃 %d", result.filtered_in, result.filtered_out)

    # 3. Classify
    classified_records: list[tuple] = []
    for fr in passed:
        try:
            category, reason = await classify_record(fr.record, adapter)
            if category != "low_value":
                classified_records.append((fr.record, category))
                logger.debug("分类: %s -> %s (%s)", fr.record.source_id, category, reason)
        except Exception as e:
            logger.warning("分类失败: %s (%s)", fr.record.source_id, e)
            result.errors.append(f"classify:{fr.record.source_id}:{e}")
    result.classified = len(classified_records)
    logger.info("分类完成: %d 条有效", result.classified)

    # 4. Extract
    all_judgments: list[Judgment] = []
    id_counter = 1
    for record, category in classified_records:
        try:
            judgments = await extract_judgments(
                record,
                category,
                adapter,
                domain,
                id_counter=id_counter,
            )
            all_judgments.extend(judgments)
            id_counter += len(judgments)
        except Exception as e:
            logger.warning("提取失败: %s (%s)", record.source_id, e)
            result.errors.append(f"extract:{record.source_id}:{e}")
    result.extracted = len(all_judgments)
    logger.info("提取完成: %d 颗判断", result.extracted)

    # 5. Dedup
    dedup_result = dedup_judgments(all_judgments)
    result.after_dedup = len(dedup_result.unique)
    logger.info(
        "去重完成: %d 颗唯一 / %d 颗重复",
        result.after_dedup,
        len(dedup_result.duplicates),
    )

    # 6. Store + Auto-link
    store = JudgmentStore(judgments_path)
    relations_count = 0
    for j in dedup_result.unique:
        try:
            relations = await auto_link(j, store, adapter)
            if relations:
                j.relations = relations
                relations_count += len(relations)
        except Exception as e:
            logger.warning("关系建立失败: %s (%s)", j.id, e)
        store.store(j)

    result.stored = len(dedup_result.unique)
    result.relations_created = relations_count
    logger.info("入库完成: %d 颗判断 / %d 条关系", result.stored, result.relations_created)

    return result
