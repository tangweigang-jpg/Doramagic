"""预提取 API 模型 — api.read 端点的请求/响应契约。"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field

from doramagic_contracts.domain_graph import (
    DomainBrick,
    AtomCluster,
    DeprecationEvent,
    SnapshotStats,
)
from doramagic_contracts.base import KnowledgeAtom, KnowledgeType, Confidence


# --- Domain Listing ---


class DomainListItem(BaseModel):
    """单个领域摘要 — GET /domains 返回列表的元素。"""

    domain_id: str
    display_name: str
    project_count: int = Field(ge=0)
    brick_count: int = Field(ge=0)
    snapshot_version: str
    last_updated: str


class DomainListResponse(BaseModel):
    """GET /domains 响应。"""

    domains: list[DomainListItem]
    total_count: int = Field(ge=0)


# --- Domain Bricks ---


class DomainBricksResponse(BaseModel):
    """GET /domains/{id}/bricks 响应。"""

    domain_id: str
    snapshot_version: str
    bricks: list[DomainBrick]
    total_count: int = Field(ge=0)


# --- Domain Truth ---


class DomainTruthResponse(BaseModel):
    """GET /domains/{id}/truth 响应。"""

    domain_id: str
    snapshot_version: str
    truth_md: str


# --- Atom Query ---


class AtomQueryParams(BaseModel):
    """GET /domains/{id}/atoms 查询参数。"""

    knowledge_type: Optional[KnowledgeType] = None
    confidence_min: Optional[Confidence] = None
    keyword: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AtomQueryResponse(BaseModel):
    """GET /domains/{id}/atoms 响应。"""

    domain_id: str
    snapshot_version: str
    atoms: list[KnowledgeAtom]
    total_count: int = Field(ge=0)
    has_more: bool = False


# --- Deprecations ---


class DeprecationListResponse(BaseModel):
    """GET /domains/{id}/deprecations 响应。"""

    domain_id: str
    deprecations: list[DeprecationEvent]
    total_count: int = Field(ge=0)


# --- Health Check ---


class HealthCheckResponse(BaseModel):
    """GET /domains/{id}/health/{project} 响应。"""

    domain_id: str
    project_id: str
    snapshot_version: str
    overall_status: Literal["healthy", "stale", "drifted", "unknown"]
    health_md: str
    brick_coverage: float = Field(ge=0, le=1)
    stale_brick_count: int = Field(ge=0, default=0)


# --- API Config ---


class ApiReadConfig(BaseModel):
    """api.read 服务配置。"""

    data_dir: str = "data/snapshots"
    host: str = "0.0.0.0"
    port: int = Field(default=8420, ge=1, le=65535)
    cors_origins: list[str] = ["*"]
