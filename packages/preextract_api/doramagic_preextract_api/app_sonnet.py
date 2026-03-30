"""FastAPI read-only API for pre-extracted domain knowledge snapshots.

Endpoints:
  GET /domains                          -> DomainListResponse
  GET /domains/{domain_id}/bricks       -> DomainBricksResponse
  GET /domains/{domain_id}/truth        -> DomainTruthResponse
  GET /domains/{domain_id}/atoms        -> AtomQueryResponse (filterable, paginated)
  GET /domains/{domain_id}/deprecations -> DeprecationListResponse
  GET /domains/{domain_id}/health/{project_id} -> HealthCheckResponse
  GET /health                           -> {"status": "ok"}

Public API:
  app          — FastAPI application instance
  load_snapshots() — (re-)load all snapshots from DORAMAGIC_API_DATA_DIR
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# FastAPI imports
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Contract imports
# ---------------------------------------------------------------------------
from doramagic_contracts.api import (
    AtomQueryResponse,
    DeprecationListResponse,
    DomainBricksResponse,
    DomainListItem,
    DomainListResponse,
    DomainTruthResponse,
    HealthCheckResponse,
)
from doramagic_contracts.base import KnowledgeAtom
from doramagic_contracts.domain_graph import (
    DeprecationEvent,
    DomainSnapshot,
)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_DATA_DIR = "data/snapshots"


def _get_data_dir() -> Path:
    """Resolve data directory from env var, falling back to default.

    Relative paths are resolved relative to the repo root.
    """
    raw = os.environ.get("DORAMAGIC_API_DATA_DIR", _DEFAULT_DATA_DIR)
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    return p


def _get_port() -> int:
    return int(os.environ.get("DORAMAGIC_API_PORT", "8420"))


# ---------------------------------------------------------------------------
# In-memory snapshot store (module-level singleton)
# ---------------------------------------------------------------------------


class _SnapshotStore:
    """Holds all loaded domain snapshots, indexed by domain_id."""

    def __init__(self) -> None:
        # domain_id -> DomainSnapshot (or None if corrupt)
        self._snapshots: dict[str, DomainSnapshot | None] = {}
        # domain_id -> raw truth markdown
        self._truths: dict[str, str] = {}
        # domain_id -> list of KnowledgeAtom (from atoms.json)
        self._atoms: dict[str, list[KnowledgeAtom]] = {}

    def clear(self) -> None:
        self._snapshots.clear()
        self._truths.clear()
        self._atoms.clear()

    def load(self, data_dir: Path) -> None:
        """Scan data_dir, load all valid domain subdirectories."""
        self.clear()
        if not data_dir.exists():
            return  # no data yet — API starts with empty /domains

        for subdir in sorted(data_dir.iterdir()):
            if not subdir.is_dir():
                continue
            manifest_path = subdir / "snapshot_manifest.json"
            bricks_path = subdir / "DOMAIN_BRICKS.json"
            truth_path = subdir / "DOMAIN_TRUTH.md"
            atoms_path = subdir / "atoms.json"  # optional JSON file

            if not manifest_path.exists():
                continue  # not a valid snapshot directory

            domain_id = subdir.name
            try:
                bricks_data = (
                    json.loads(bricks_path.read_text(encoding="utf-8"))
                    if bricks_path.exists()
                    else {}
                )
                snapshot = DomainSnapshot(**bricks_data)
                truth_md = truth_path.read_text(encoding="utf-8") if truth_path.exists() else ""
                # Load atoms.json if present
                atoms: list[KnowledgeAtom] = []
                if atoms_path.exists():
                    raw_atoms = json.loads(atoms_path.read_text(encoding="utf-8"))
                    atoms = [KnowledgeAtom(**a) for a in raw_atoms]

                self._snapshots[domain_id] = snapshot
                self._truths[domain_id] = truth_md
                self._atoms[domain_id] = atoms
            except Exception:
                # Mark domain as corrupt — callers get 500, not 404
                self._snapshots[domain_id] = None
                self._truths[domain_id] = ""
                self._atoms[domain_id] = []

    def domain_ids(self) -> list[str]:
        return list(self._snapshots.keys())

    def get_snapshot(self, domain_id: str) -> DomainSnapshot:
        """Return snapshot or raise HTTPException (404 / 500)."""
        if domain_id not in self._snapshots:
            raise HTTPException(status_code=404, detail=f"Domain not found: {domain_id}")
        snap = self._snapshots[domain_id]
        if snap is None:
            raise HTTPException(
                status_code=500, detail=f"Snapshot corrupted for domain: {domain_id}"
            )
        return snap

    def get_truth(self, domain_id: str) -> str:
        self.get_snapshot(domain_id)  # validates existence + corruption
        return self._truths.get(domain_id, "")

    def get_atoms(self, domain_id: str) -> list[KnowledgeAtom]:
        self.get_snapshot(domain_id)  # validates existence + corruption
        return self._atoms.get(domain_id, [])


_store = _SnapshotStore()


# ---------------------------------------------------------------------------
# Public load_snapshots() — called by tests and startup handler
# ---------------------------------------------------------------------------


def load_snapshots(data_dir: Path | None = None) -> None:
    """(Re-)load all snapshots from disk.

    Args:
        data_dir: Override directory.  If None, reads DORAMAGIC_API_DATA_DIR
                  environment variable (resolved relative to repo root).
    """
    if data_dir is None:
        data_dir = _get_data_dir()
    _store.load(data_dir)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

_cors_origins: list[str] = ["*"]

app = FastAPI(
    title="Doramagic Pre-Extract API",
    description="Read-only API for pre-extracted domain knowledge snapshots.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    load_snapshots()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def service_health() -> dict:
    return {"status": "ok"}


@app.get("/domains", response_model=DomainListResponse)
async def list_domains() -> DomainListResponse:
    """List all pre-extracted domains."""
    items: list[DomainListItem] = []
    for domain_id in _store.domain_ids():
        try:
            snap = _store.get_snapshot(domain_id)
        except HTTPException:
            continue  # skip corrupted domains silently
        items.append(
            DomainListItem(
                domain_id=domain_id,
                display_name=snap.domain_display_name,
                project_count=snap.stats.project_count,
                brick_count=snap.stats.brick_count,
                snapshot_version=snap.snapshot_version,
                last_updated=snap.snapshot_version,
            )
        )
    return DomainListResponse(domains=items, total_count=len(items))


@app.get("/domains/{domain_id}/bricks", response_model=DomainBricksResponse)
async def get_bricks(domain_id: str) -> DomainBricksResponse:
    """Return all domain bricks for the given domain."""
    snap = _store.get_snapshot(domain_id)
    return DomainBricksResponse(
        domain_id=domain_id,
        snapshot_version=snap.snapshot_version,
        bricks=snap.bricks,
        total_count=len(snap.bricks),
    )


@app.get("/domains/{domain_id}/truth", response_model=DomainTruthResponse)
async def get_truth(domain_id: str) -> DomainTruthResponse:
    """Return the domain truth markdown for the given domain."""
    snap = _store.get_snapshot(domain_id)
    truth_md = _store.get_truth(domain_id)
    return DomainTruthResponse(
        domain_id=domain_id,
        snapshot_version=snap.snapshot_version,
        truth_md=truth_md,
    )


@app.get("/domains/{domain_id}/atoms", response_model=AtomQueryResponse)
async def query_atoms(
    domain_id: str,
    knowledge_type: str | None = Query(default=None),
    confidence_min: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AtomQueryResponse:
    """Query knowledge atoms with optional filters and pagination.

    Atoms are loaded from atoms.json if present in the snapshot directory.
    If atoms.json is absent, returns an empty list (total_count=0).

    Filters:
      knowledge_type: exact match
                      (capability|rationale|constraint|interface|failure|assembly_pattern)
      confidence_min: minimum confidence level (high > medium > low)
      keyword:        case-insensitive substring search across subject/predicate/object
      limit/offset:   standard pagination
    """
    snap = _store.get_snapshot(domain_id)

    # Confidence ordering for confidence_min filter
    _conf_rank: dict[str, int] = {"low": 0, "medium": 1, "high": 2}

    all_atoms = list(_store.get_atoms(domain_id))

    # Apply filters
    if knowledge_type is not None:
        all_atoms = [a for a in all_atoms if a.knowledge_type == knowledge_type]

    if confidence_min is not None:
        min_rank = _conf_rank.get(confidence_min, 0)
        all_atoms = [a for a in all_atoms if _conf_rank.get(a.confidence, 0) >= min_rank]

    if keyword is not None:
        kw = keyword.lower()
        all_atoms = [
            a
            for a in all_atoms
            if kw in a.subject.lower() or kw in a.predicate.lower() or kw in a.object.lower()
        ]

    total_count = len(all_atoms)
    page = all_atoms[offset : offset + limit]
    has_more = (offset + limit) < total_count

    return AtomQueryResponse(
        domain_id=domain_id,
        snapshot_version=snap.snapshot_version,
        atoms=page,
        total_count=total_count,
        has_more=has_more,
    )


@app.get("/domains/{domain_id}/deprecations", response_model=DeprecationListResponse)
async def get_deprecations(domain_id: str) -> DeprecationListResponse:
    """Return all deprecation events for the given domain."""
    snap = _store.get_snapshot(domain_id)
    events: list[DeprecationEvent] = snap.deprecation_events or []
    return DeprecationListResponse(
        domain_id=domain_id,
        deprecations=events,
        total_count=len(events),
    )


@app.get(
    "/domains/{domain_id}/health/{project_id}",
    response_model=HealthCheckResponse,
)
async def get_health(domain_id: str, project_id: str) -> HealthCheckResponse:
    """Return health check for a specific project against the domain snapshot.

    Returns overall_status='unknown' when project_id is not referenced by any brick.
    """
    snap = _store.get_snapshot(domain_id)

    # Bricks that mention this project
    covered_bricks = [b for b in snap.bricks if project_id in b.source_project_ids]

    total_bricks = len(snap.bricks)
    coverage = len(covered_bricks) / total_bricks if total_bricks > 0 else 0.0

    stale_signals = {"STALE", "DRIFTED"}
    stale_count = sum(1 for b in covered_bricks if b.signal in stale_signals)

    if not covered_bricks:
        overall_status: str = "unknown"
        health_md = ""
    elif stale_count > 0:
        overall_status = "stale"
        health_md = f"# Health Report: {project_id}\n\n{stale_count} stale brick(s) detected."
    else:
        overall_status = "healthy"
        health_md = (
            f"# Health Report: {project_id}\n\n"
            f"All {len(covered_bricks)} covered brick(s) are current."
        )

    return HealthCheckResponse(
        domain_id=domain_id,
        project_id=project_id,
        snapshot_version=snap.snapshot_version,
        overall_status=overall_status,
        health_md=health_md,
        brick_coverage=coverage,
        stale_brick_count=stale_count,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "doramagic_preextract_api.app:app",
        host="0.0.0.0",
        port=_get_port(),
        reload=False,
    )
