# preextract-api.read — Design Decisions

Date: 2026-03-19
Module: `apps.preextract-api.read`
Racer: S1-Sonnet (collaborated with S3-Gemini base)
Round: 5, Track B

---

## D-001: Module-level singleton store with dynamic env-var resolution

**Decision**: Four module-level dicts (`_snapshots`, `_domain_data`, `_domain_truth`, `_domain_atoms`) hold all state. `load_snapshots()` clears and repopulates them by calling `_resolve_data_dir()` at invocation time.

**Rationale**: A module-level singleton allows the `TestClient(app)` pattern — tests import `app` once and call `load_snapshots()` directly to swap data directories without restarting the process. `_resolve_data_dir()` reads `DORAMAGIC_API_DATA_DIR` at call time (not at import time), so `monkeypatch.setenv()` + `load_snapshots()` in tests correctly picks up the new path.

**Trade-off**: Not thread-safe under concurrent `load_snapshots()` calls. Acceptable for a single-process dev/test server; production deployments restart on data changes.

---

## D-002: Atoms loaded from atoms.json; empty list when absent

**Decision**: `GET /domains/{id}/atoms` serves atoms from `atoms.json` in the snapshot directory. If the file is absent, `total_count=0` and `atoms=[]` are returned without error.

**Rationale**: `atoms.parquet` is optional per spec. The fixture data (`calorie-tracking`) has no atom file. Returning an empty list is the correct fallback — it accurately reflects that no atom data is present, and tests can verify this explicitly.

**Trade-off**: No atoms are served for the calorie-tracking fixture unless an `atoms.json` is added. The atoms endpoint is fully exercised via a temp-dir test that injects a synthetic `atoms.json`.

**Candidate extension**: Add parquet support (pyarrow) when `atoms_parquet_path` is non-null in the manifest.

---

## D-003: Single-file FastAPI app, flat module-level handlers

**Decision**: All 7 endpoints are implemented as top-level `@app.get` handlers in a single `app.py` file.

**Rationale**: The module is small (7 GET endpoints, all read-only). Router splitting adds indirection without proportional benefit. Flat layout maximises readability for a race submission.

---

## D-004: `/health` returns plain dict

**Decision**: `GET /health` returns `{"status": "ok"}` as a plain Python dict with no response model.

**Rationale**: Spec states the response verbatim. No typed model needed for a single-field liveness probe.

---

## D-005: Health endpoint returns `unknown` + empty `health_md` for unrecognised projects

**Decision**: If `project_id` is not found in any brick's `source_project_ids`, `overall_status="unknown"` and `health_md=""`.

**Rationale**: Spec explicitly defines: "health 端点 project 不存在 → `overall_status: 'unknown'` + 空 health_md". The domain is valid; only the project reference is unknown, so no 404 is raised.

---

## D-006: CORS allows all origins and methods

**Decision**: `CORSMiddleware` is configured with `allow_origins=["*"]` and `allow_methods=["*"]`.

**Rationale**: Spec mandates CORS is enabled. No restrictions specified for a local dev API. Operator can tighten if needed.

---

## D-007: `_PROJECT_ROOT` resolved from `__file__`, not CWD

**Decision**: `_PROJECT_ROOT = Path(__file__).resolve().parents[3]` locates the monorepo root regardless of where pytest is invoked from.

**Rationale**: Tests are run from the repo root (`pytest packages/...`) but the module file is 3 levels deep. `__file__`-relative resolution is stable across all invocation contexts. CWD-relative resolution would break when pytest is run from a subdirectory.
