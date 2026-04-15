"""蓝图驱动约束采集管线——主编排。

流程：
1. 加载蓝图
2. 构建上下文
3. 对每个 stage × 5 kinds 提取约束
4. 遗漏检查
5. Edge 约束 + Global 约束 + Claim Boundary 专项
6. 构造 Constraint 对象 + 校验（跳过规范化步骤，直接用 raw scope）
7. 去重（合并 applies_to）
8. 入库
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from doramagic_constraint_schema.serializer import ConstraintStore
from doramagic_constraint_schema.types import (
    AppliesTo,
    Constraint,
    ConstraintConfidence,
    ConstraintCore,
    ConstraintKind,
    ConstraintScope,
    ConstraintVersion,
    EvidenceRef,
    EvidenceRefType,
    SourceType,
    TargetScope,
)
from doramagic_constraint_schema.validators import validate_constraint
from doramagic_shared_utils.llm_adapter import LLMAdapter

from .blueprint_loader import ParsedBlueprint, load_blueprint
from .context_builder import ExtractionContextBuilder
from .extract.extractor import ConstraintExtractor
from .extract.prompts import KIND_GUIDANCE
from .refine.dedup import dedup_constraints

logger = logging.getLogger(__name__)

ALL_KINDS = list(KIND_GUIDANCE.keys())

# LLM 输出中必须存在的字段（P1-4: 拒绝 malformed 而非用占位符）
REQUIRED_RAW_FIELDS = {"when", "modality", "action", "consequence_kind", "consequence_description"}


@dataclass
class ConstraintPipelineResult:
    """管线运行结果。"""

    blueprint_id: str
    total_extracted: int = 0
    after_validation: int = 0
    after_dedup: int = 0
    stored: int = 0
    errors: list[str] = field(default_factory=list)
    by_kind: dict[str, int] = field(default_factory=dict)
    by_scope: dict[str, int] = field(default_factory=dict)


def _validate_raw_fields(raw: dict[str, Any]) -> list[str]:
    """P1-4: 检查 LLM 原始输出是否包含所有必填字段。返回缺失字段列表。"""
    missing = []
    for f in REQUIRED_RAW_FIELDS:
        val = raw.get(f)
        if not val or (isinstance(val, str) and len(val.strip()) < 3):
            missing.append(f)
    return missing


def _raw_to_constraint(
    raw: dict[str, Any],
    constraint_id: str,
    blueprint: ParsedBlueprint,
    target_scope: TargetScope,
    stage_ids: list[str] | None = None,
    edge_ids: list[str] | None = None,
) -> Constraint | None:
    """将 LLM 原始输出转换为 Constraint 对象。

    P1-4: 不再为缺失字段填占位符——缺失字段在调用前已被 _validate_raw_fields 拒绝。
    """
    try:
        # 映射 source_type
        source_type_str = raw.get("source_type", "expert_reasoning")
        try:
            source_type = SourceType(source_type_str)
        except ValueError:
            source_type = SourceType.EXPERT_REASONING

        # 构建 evidence_refs
        evidence_refs: list[EvidenceRef] = []
        evidence_summary = raw.get("evidence_summary", "")
        if evidence_summary:
            ref_type = (
                EvidenceRefType.SOURCE_CODE
                if source_type == SourceType.CODE_ANALYSIS
                else EvidenceRefType.DOC
            )
            project = "unknown"
            projects = blueprint.source.get("projects")
            if projects and len(projects) > 0:
                project = projects[0]
            evidence_refs.append(
                EvidenceRef(
                    type=ref_type,
                    source=project,
                    locator=evidence_summary[:200],
                    summary=evidence_summary[:200],
                )
            )

        # 确定 constraint_kind
        kind_str = raw.get("constraint_kind", "domain_rule")
        try:
            constraint_kind = ConstraintKind(kind_str)
        except ValueError:
            constraint_kind = ConstraintKind.DOMAIN_RULE

        return Constraint(
            id=constraint_id,
            core=ConstraintCore(
                when=raw["when"],
                modality=raw["modality"],
                action=raw["action"],
                consequence={
                    "kind": raw["consequence_kind"],
                    "description": raw.get(
                        "consequence_description",
                        f"Violation of {kind_str} constraint",
                    ),
                },
            ),
            constraint_kind=constraint_kind,
            applies_to=AppliesTo(
                target_scope=target_scope,
                stage_ids=stage_ids or [],
                edge_ids=edge_ids or [],
                blueprint_ids=[blueprint.id],
            ),
            scope=ConstraintScope(
                level="domain",
                domains=[blueprint.domain],
            ),
            confidence=ConstraintConfidence(
                source_type=source_type,
                score=raw.get("confidence_score", 0.7),
                consensus=raw.get("consensus", "mixed"),
                evidence_refs=evidence_refs,
            ),
            machine_checkable=raw.get("machine_checkable", False),
            promote_to_acceptance=raw.get("promote_to_acceptance", False),
            severity=raw.get("severity", "medium"),
            freshness=raw.get("freshness", "semi_stable"),
            version=ConstraintVersion(
                status="draft",
                schema_version="2.2",
            ),
            tags=[blueprint.domain, constraint_kind.value],
            validation_threshold=raw.get("validation_threshold"),
            derived_from=raw.get("derived_from"),
            guard_pattern=raw.get("guard_pattern"),
        )
    except Exception as e:
        logger.warning("构造 Constraint 失败: %s — 原始数据: %s", e, raw)
        return None


def _postprocess_constraints(constraints: list[Constraint]) -> None:
    """SOP v2.2 Step 4: 后处理 P0-P5 规则，原地修改。"""
    consequence_kind_words = {
        "bug",
        "performance",
        "financial_loss",
        "data_corruption",
        "service_disruption",
        "operational_failure",
        "compliance",
        "safety",
        "false_claim",
    }

    for c in constraints:
        # P0a: expert_reasoning + score > 0.7 → 降为 0.7
        st = c.confidence.source_type
        is_expert = st == SourceType.EXPERT_REASONING or (
            isinstance(st, str) and st == "expert_reasoning"
        )
        if is_expert and c.confidence.score > 0.7:
            c.confidence.score = 0.7

        # P4: consequence_description 质量检查
        # Consequence 是 Pydantic BaseModel，用属性访问
        desc = c.core.consequence.description if hasattr(c.core.consequence, "description") else ""
        if len(desc) < 20 or desc.strip().lower() in consequence_kind_words:
            if c.tags is None:
                c.tags = []
            if "P4_NEEDS_FIX" not in c.tags:
                c.tags.append("P4_NEEDS_FIX")

    p0a_count = sum(
        1
        for c in constraints
        if (
            (
                c.confidence.source_type == SourceType.EXPERT_REASONING
                or (
                    isinstance(c.confidence.source_type, str)
                    and c.confidence.source_type == "expert_reasoning"
                )
            )
            and c.confidence.score == 0.7
        )
    )
    p4_count = sum(1 for c in constraints if c.tags and "P4_NEEDS_FIX" in c.tags)
    logger.info("后处理: P0a=%d, P4=%d 条需人工修复", p0a_count, p4_count)


async def run_constraint_pipeline(
    blueprint_path: Path,
    repo_path: Path,
    domain: str,
    adapter: LLMAdapter,
    *,
    constraints_path: Path | None = None,
    output_path: Path | None = None,
    dry_run: bool = False,
) -> ConstraintPipelineResult:
    """运行蓝图驱动约束采集管线。

    Args:
        blueprint_path: 蓝图 YAML 文件路径
        repo_path: 项目源码本地 clone 路径
        domain: 领域名（如 "finance"）
        adapter: LLM 适配器
        constraints_path: 约束存储根路径（如 knowledge/constraints），与 output_path 二选一
        output_path: 输出 JSONL 路径（CLI 便捷参数，覆盖 constraints_path）
        dry_run: 如果为 True，只提取不入库

    Returns:
        ConstraintPipelineResult 运行结果
    """
    # output_path 优先级高于 constraints_path
    if output_path is not None:
        constraints_path = output_path.parent
    result = ConstraintPipelineResult(blueprint_id="")

    # Step 1: 加载蓝图
    blueprint = load_blueprint(blueprint_path)
    result.blueprint_id = blueprint.id

    # P2-8: domain 一致性检查
    if blueprint.domain and blueprint.domain != domain:
        logger.warning(
            "CLI domain '%s' 与蓝图 domain '%s' 不一致，使用蓝图 domain",
            domain,
            blueprint.domain,
        )
        domain = blueprint.domain

    logger.info("=== 开始约束采集: %s (domain=%s) ===", blueprint.id, domain)

    # Step 2: 构建上下文
    ctx_builder = ExtractionContextBuilder(blueprint, repo_path)
    extractor = ConstraintExtractor(adapter)

    # P1-2 修复：每条 raw dict 直接绑定 scope 元数据，不依赖后置 key 匹配
    @dataclass
    class RawWithScope:
        raw: dict[str, Any]
        target_scope: TargetScope
        stage_ids: list[str]
        edge_ids: list[str]

    all_items: list[RawWithScope] = []

    # 并发控制：限制同时进行的 LLM 调用数
    MAX_CONCURRENT = 5
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    # ── 辅助函数：带信号量的阶段提取 ──
    async def _extract_stage(stage_obj: Any) -> list[RawWithScope]:
        """单个阶段的提取（5 kinds 串行 + 遗漏检查）。阶段间并行。"""
        items: list[RawWithScope] = []
        async with sem:
            stage_ctx = ctx_builder.build_stage_context(stage_obj.id)
            stage_extracted: list[dict[str, Any]] = []
            for kind in ALL_KINDS:
                logger.info("提取: stage=%s, kind=%s", stage_obj.id, kind)
                raw_constraints = await extractor.extract_stage_constraints(
                    stage_ctx,
                    kind,
                    already_extracted=stage_extracted,
                )
                for rc in raw_constraints:
                    items.append(RawWithScope(rc, TargetScope.STAGE, [stage_obj.id], []))
                    stage_extracted.append(rc)
            # Step 4: 遗漏检查
            omissions = await extractor.run_omission_check(stage_extracted, stage_ctx)
            for rc in omissions:
                items.append(RawWithScope(rc, TargetScope.STAGE, [stage_obj.id], []))
        return items

    async def _extract_edge(edge_obj: Any) -> list[RawWithScope]:
        """单条 edge 的提取。"""
        async with sem:
            logger.info("提取: edge=%s", edge_obj.id)
            edge_ctx = ctx_builder.build_edge_context(edge_obj.id)
            raw_constraints = await extractor.extract_edge_constraints(edge_ctx)
            return [RawWithScope(rc, TargetScope.EDGE, [], [edge_obj.id]) for rc in raw_constraints]

    # Step 3: 跨阶段并行提取（阶段内 5 kinds 串行保留 already_extracted 去重）
    logger.info(
        "Step 3: 并行提取 %d 个阶段（max_concurrent=%d）", len(blueprint.stages), MAX_CONCURRENT
    )
    stage_results = await asyncio.gather(*[_extract_stage(s) for s in blueprint.stages])
    for stage_items in stage_results:
        all_items.extend(stage_items)

    # Step 5: Edge 约束并行提取
    if blueprint.edges:
        logger.info("Step 5: 并行提取 %d 条 edge", len(blueprint.edges))
        edge_results = await asyncio.gather(*[_extract_edge(e) for e in blueprint.edges])
        for edge_items in edge_results:
            all_items.extend(edge_items)

    # Step 6: Global + Claim Boundary 并行
    global_ctx = ctx_builder.build_global_context()

    async def _extract_global() -> list[RawWithScope]:
        async with sem:
            logger.info("提取: global constraints")
            rcs = await extractor.extract_global_constraints(global_ctx)
            return [RawWithScope(rc, TargetScope.GLOBAL, [], []) for rc in rcs]

    async def _extract_claims() -> list[RawWithScope]:
        async with sem:
            logger.info("提取: claim boundaries")
            rcs = await extractor.extract_claim_boundaries(global_ctx)
            return [RawWithScope(rc, TargetScope.GLOBAL, [], []) for rc in rcs]

    global_items, claim_items = await asyncio.gather(_extract_global(), _extract_claims())
    all_items.extend(global_items)
    all_items.extend(claim_items)

    # Step 2.4: 蓝图驱动的业务约束派生（从 business_decisions 派生）
    business_decisions: list[dict] = blueprint.raw.get("business_decisions", [])
    if business_decisions:
        logger.info("Step 2.4: 从 %d 条 business_decisions 派生约束", len(business_decisions))
        derived_constraints = await extractor.extract_derived_constraints(
            blueprint_path=blueprint_path,
            business_decisions=business_decisions,
        )
        for rc in derived_constraints:
            all_items.append(RawWithScope(rc, TargetScope.GLOBAL, [], []))
        logger.info("Step 2.4: 派生了 %d 条约束", len(derived_constraints))
    else:
        logger.info("Step 2.4: 蓝图无 business_decisions 字段，跳过派生步骤")

    # Step 2.5: 审计发现转化（将未被 Step 2.4 覆盖的审计发现转化为约束）
    # audit_checklist_summary can be a dict (summary) or list (items) depending on blueprint version
    raw_audit = blueprint.raw.get("audit_checklist_summary", {})
    if isinstance(raw_audit, dict):
        # Summary dict — extract items list if present, otherwise check fail count
        audit_items = raw_audit.get("items", [])
        if not audit_items and raw_audit.get("fail", 0) > 0:
            audit_items = [raw_audit]  # treat the whole summary as one item
    elif isinstance(raw_audit, list):
        audit_items = raw_audit
    else:
        audit_items = []
    audit_findings_to_convert = [
        item for item in audit_items if isinstance(item, dict) and item.get("fail", 0) > 0
    ]
    if audit_findings_to_convert:
        logger.info("Step 2.5: 转化 %d 条审计发现", len(audit_findings_to_convert))
        audit_constraints = await extractor.convert_audit_findings(
            blueprint_path=blueprint_path,
            audit_findings=audit_findings_to_convert,
        )
        for rc in audit_constraints:
            all_items.append(RawWithScope(rc, TargetScope.GLOBAL, [], []))
        logger.info("Step 2.5: 转化了 %d 条约束", len(audit_constraints))
    else:
        logger.info("Step 2.5: 无待转化的审计发现，跳过")

    result.total_extracted = len(all_items)
    logger.info("总共提取 %d 条候选约束", result.total_extracted)

    # Step 7: 构造 Constraint 对象 + 校验（P1-2: scope 直接从 RawWithScope 取）
    if constraints_path is None:
        constraints_path = Path("knowledge/constraints")
    store = ConstraintStore(constraints_path)
    next_id = store.get_next_id(domain)
    valid_constraints: list[Constraint] = []

    for item in all_items:
        # P1-4: 拒绝缺失必填字段的 raw
        missing = _validate_raw_fields(item.raw)
        if missing:
            result.errors.append(f"LLM 输出缺失字段 {missing}: {item.raw.get('when', '?')}")
            continue

        constraint_id = f"{domain}-C-{next_id:03d}"
        constraint = _raw_to_constraint(
            item.raw,
            constraint_id,
            blueprint,
            item.target_scope,
            item.stage_ids,
            item.edge_ids,
        )
        if constraint is None:
            result.errors.append(f"构造失败: {item.raw.get('when', '?')}")
            continue

        vr = validate_constraint(
            constraint,
            valid_stage_ids=blueprint.stage_ids,
            valid_edge_ids=blueprint.edge_ids,
        )
        if not vr.valid:
            result.errors.extend(vr.errors)
            logger.warning("校验失败 %s: %s", constraint_id, vr.errors)
            continue

        valid_constraints.append(constraint)
        next_id += 1

    result.after_validation = len(valid_constraints)

    # Step 8: 去重（P1-1: 合并 applies_to 而非丢弃）
    dedup_result = dedup_constraints(valid_constraints)
    result.after_dedup = len(dedup_result.unique)

    # Step 8.5: 后处理 P0-P5（SOP v2.2 Step 4）
    _postprocess_constraints(dedup_result.unique)

    # Step 9: 入库（P2-9: dry_run 时跳过）
    if dry_run:
        logger.info("dry_run 模式：跳过入库，共 %d 条约束", result.after_dedup)
        result.stored = 0
    else:
        stored_count = 0
        for c in dedup_result.unique:
            if store.store(c):
                stored_count += 1
                kind_val = (
                    c.constraint_kind
                    if isinstance(c.constraint_kind, str)
                    else c.constraint_kind.value
                )
                result.by_kind[kind_val] = result.by_kind.get(kind_val, 0) + 1
                scope_val = (
                    c.applies_to.target_scope
                    if isinstance(c.applies_to.target_scope, str)
                    else c.applies_to.target_scope.value
                )
                result.by_scope[scope_val] = result.by_scope.get(scope_val, 0) + 1
        result.stored = stored_count

    logger.info(
        "=== 管线完成: %s — 提取 %d → 校验 %d → 去重 %d → 入库 %d ===",
        blueprint.id,
        result.total_extracted,
        result.after_validation,
        result.after_dedup,
        result.stored,
    )

    return result
