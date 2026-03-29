"""领域图谱模型 — snapshot_builder 构建领域知识快照。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from doramagic_contracts.base import (
    Confidence,
    EvidenceRef,
    KnowledgeType,
    SignalKind,
)

# --- Domain Brick ---


class DomainBrick(BaseModel):
    """领域积木 — 经过多项目验证的知识单元，可注入 Stage 0/1 加速提取。"""

    brick_id: str
    domain_id: str
    knowledge_type: KnowledgeType
    statement: str
    confidence: Confidence
    signal: SignalKind
    source_project_ids: list[str]
    support_count: int = Field(ge=1)
    evidence_refs: list[EvidenceRef] = []
    tags: list[str] = []


# --- Atom Cluster ---


class AtomCluster(BaseModel):
    """原子簇 — 语义相近的知识原子聚类，附带共识声明。"""

    cluster_id: str
    theme: str
    consensus_statement: str
    atom_ids: list[str]
    signal: SignalKind
    support_count: int = Field(ge=1)


# --- Deprecation ---


class DeprecationEvent(BaseModel):
    """废弃事件 — 某个 brick 不再有效时的记录。"""

    event_id: str
    domain_id: str
    brick_id: str
    reason: str
    deprecated_at: str
    replacement_brick_id: str | None = None


# --- Snapshot Stats ---


class SnapshotStats(BaseModel):
    """快照统计摘要。"""

    project_count: int = Field(ge=0)
    atom_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    brick_count: int = Field(ge=0)
    deprecation_count: int = Field(ge=0, default=0)
    coverage_ratio: float = Field(ge=0, le=1)


# --- Snapshot Builder I/O ---


class SnapshotConfig(BaseModel):
    """snapshot_builder 配置。"""

    output_dir: str | None = None
    include_parquet: bool = True
    include_sqlite: bool = True
    min_support_for_brick: int = Field(default=2, ge=1)
    cluster_similarity_threshold: float = Field(default=0.75, ge=0, le=1)


class SnapshotBuilderInput(BaseModel):
    """snapshot_builder 输入。"""

    schema_version: str = "dm.snapshot-builder-input.v1"
    domain_id: str
    domain_display_name: str = ""
    fingerprints: list  # list[ProjectFingerprint] — 避免循环导入，运行时验证
    compare_output: dict  # CompareOutput 字典
    synthesis_report: dict  # SynthesisReportData 字典
    community_knowledge: dict = {}  # CommunityKnowledge 字典
    config: SnapshotConfig = SnapshotConfig()


class DomainSnapshot(BaseModel):
    """领域快照 — snapshot_builder 的核心输出数据。"""

    schema_version: str = "dm.domain-snapshot.v1"
    domain_id: str
    domain_display_name: str
    snapshot_version: str
    bricks: list[DomainBrick]
    atom_clusters: list[AtomCluster]
    deprecation_events: list[DeprecationEvent] = []
    stats: SnapshotStats


class SnapshotBuilderOutput(BaseModel):
    """snapshot_builder 输出 — 文件路径清单 + 快照数据。"""

    schema_version: str = "dm.snapshot-builder-output.v1"
    domain_id: str
    snapshot_version: str
    domain_bricks_path: str
    domain_truth_path: str
    atoms_parquet_path: str | None = None
    domain_map_sqlite_path: str | None = None
    snapshot_manifest_path: str
    stats: SnapshotStats
