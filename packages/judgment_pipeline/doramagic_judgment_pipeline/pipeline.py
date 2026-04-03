"""判断采集流水线。线性编排：Fetch → Filter → Classify → Extract → Dedup → Store。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from doramagic_judgment_schema.serializer import JudgmentStore
from doramagic_judgment_schema.types import Judgment
from doramagic_shared_utils.llm_adapter import LLMAdapter

from .extract.classifier import classify_record

# Sprint 4
from .extract.doc_extractor import extract_doc_judgments
from .extract.doc_filter import filter_doc_records
from .extract.extractor import extract_judgments
from .extract.filter import FilterTrack, filter_records
from .refine.dedup import dedup_judgments
from .source_adapters.base import RawExperienceRecord
from .source_adapters.code_search import CodeSearchAdapter
from .source_adapters.github import GitHubAdapter
from .source_adapters.repo_doc import RepoDocAdapter
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


# ── Sprint 4 追加 ──


@dataclass
class DocPipelineResult:
    """文档采集流水线结果统计。"""

    fetched: int = 0
    filtered_in: int = 0
    filtered_out: int = 0
    extracted: int = 0
    after_dedup: int = 0
    stored: int = 0
    errors: list[str] = field(default_factory=list)


async def run_doc_pipeline(
    github_token: str,
    target: dict,
    domain: str,
    judgments_path: str | Path,
    adapter: LLMAdapter,
    model: str = "sonnet",
) -> DocPipelineResult:
    """文档采集流水线：RepoDocAdapter → DocFilter → DocExtractor → Dedup → Store"""
    result = DocPipelineResult()

    records: list[RawExperienceRecord] = []

    # 1a. 文档采集
    doc_adapter = RepoDocAdapter(token=github_token)
    try:
        doc_records = await doc_adapter.fetch(target)
        records.extend(doc_records)
        logger.info("[Doc] 文档采集: %d 条", len(doc_records))
    except Exception as e:
        result.errors.append(f"文档拉取失败: {e}")

    # 1b. 代码采集
    code_target = {
        "owner": target["owner"],
        "repo": target["repo"],
        "language": target.get("language", "python"),
        "domain": target.get("domain"),
        "max_results_per_pattern": target.get("max_code_results", 10),
    }
    code_adapter = CodeSearchAdapter(token=github_token)
    try:
        code_records = await code_adapter.fetch(code_target)
        records.extend(code_records)
        logger.info("[Doc] 代码采集: %d 条", len(code_records))
    except Exception as e:
        result.errors.append(f"代码采集失败: {e}")

    result.fetched = len(records)
    logger.info("[Doc] 总采集: %d 条记录", result.fetched)

    if not records:
        return result

    # 2. Filter
    filter_results = filter_doc_records(records)
    passed = [fr.record for fr in filter_results if fr.passed]
    result.filtered_in = len(passed)
    result.filtered_out = result.fetched - result.filtered_in
    logger.info("[Doc] Filter: %d 通过 / %d 丢弃", result.filtered_in, result.filtered_out)

    if not passed:
        return result

    # 3. Extract
    all_judgments: list[Judgment] = []
    id_counter = _get_next_id_counter(judgments_path, domain)

    for record in passed:
        try:
            judgments = await extract_doc_judgments(
                record=record,
                adapter=adapter,
                domain=domain,
                model=model,
                id_counter=id_counter,
            )
            all_judgments.extend(judgments)
            id_counter += len(judgments)
        except Exception as e:
            logger.warning("[Doc] 提取失败: %s (record=%s)", e, record.source_id)
            result.errors.append(f"提取失败 {record.source_id}: {e}")

    result.extracted = len(all_judgments)
    logger.info("[Doc] Extracted %d 颗判断", result.extracted)

    if not all_judgments:
        return result

    # 4. Dedup
    dedup_result = dedup_judgments(all_judgments)
    result.after_dedup = len(dedup_result.unique)
    logger.info("[Doc] Dedup: %d → %d", result.extracted, result.after_dedup)

    # 5. Store
    store = JudgmentStore(judgments_path)
    stored_count = 0
    for j in dedup_result.unique:
        try:
            store.store(j)
            stored_count += 1
        except Exception as e:
            logger.warning("[Doc] 入库失败: %s (id=%s)", e, j.id)
            result.errors.append(f"入库失败 {j.id}: {e}")

    result.stored = stored_count
    logger.info("[Doc] Stored %d 颗判断", result.stored)

    return result


@dataclass
class FullPipelineResult:
    """三层完整采集结果。"""

    issue_result: PipelineResult | None = None
    doc_result: DocPipelineResult | None = None
    total_stored: int = 0
    layer_coverage: dict[str, int] = field(default_factory=dict)
    crystal_text: str = ""


async def run_full_pipeline(
    github_token: str,
    issue_target: dict,
    doc_target: dict,
    domain: str,
    task_description: str,
    judgments_path: str | Path,
    adapter: LLMAdapter,
    model: str = "sonnet",
    compile_crystal: bool = True,
    max_tokens: int | None = None,
) -> FullPipelineResult:
    """三层完整采集流水线。"""
    import asyncio

    result = FullPipelineResult()

    issue_task = asyncio.create_task(
        run_pipeline(
            github_token=github_token,
            target=issue_target,
            domain=domain,
            judgments_path=judgments_path,
            adapter=adapter,
        )
    )
    doc_task = asyncio.create_task(
        run_doc_pipeline(
            github_token=github_token,
            target=doc_target,
            domain=domain,
            judgments_path=judgments_path,
            adapter=adapter,
            model=model,
        )
    )

    result.issue_result, result.doc_result = await asyncio.gather(issue_task, doc_task)
    result.total_stored = (result.issue_result.stored if result.issue_result else 0) + (
        result.doc_result.stored if result.doc_result else 0
    )

    # 统计三层覆盖度
    store = JudgmentStore(judgments_path)
    all_domain = store.list_by_domain(domain)
    for j in all_domain:
        layer_name = j.layer.value if hasattr(j.layer, "value") else str(j.layer)
        result.layer_coverage[layer_name] = result.layer_coverage.get(layer_name, 0) + 1

    logger.info("[Full] 三层覆盖: %s", result.layer_coverage)

    # 编译晶体
    if compile_crystal:
        from doramagic_crystal_compiler.compiler import compile_crystal as do_compile
        from doramagic_crystal_compiler.retrieve import retrieve

        retrieval = retrieve(store=store, domain=domain)
        result.crystal_text = do_compile(
            retrieval=retrieval,
            domain=domain,
            task_description=task_description,
            max_tokens=max_tokens,
        )
        logger.info("[Full] 晶体编译完成，长度=%d 字符", len(result.crystal_text))

    return result


def _get_next_id_counter(judgments_path: str | Path, domain: str) -> int:
    """获取下一个可用的 ID 计数器。"""
    try:
        store = JudgmentStore(judgments_path)
        existing = store.list_by_domain(domain)
        if not existing:
            return 1
        max_num = 0
        for j in existing:
            parts = j.id.rsplit("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                max_num = max(max_num, int(parts[1]))
        return max_num + 1
    except Exception:
        return 1
