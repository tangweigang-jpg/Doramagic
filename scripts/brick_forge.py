"""brick_forge.py — S1-Sonnet Race B implementation.

Produces L1 (framework-level) and L2 (pattern-level) knowledge bricks
for Doramagic's 6 pre-extraction domains.

L1 bricks: Framework philosophy anchors (≤400 tokens each)
L2 bricks: Specific patterns, anti-patterns, UNSAID knowledge (≤800 tokens each)

Design:
- Works with adapter=None (all bricks are hardcoded from expert knowledge)
- LLMAdapter is supported for future enrichment but not required
- Each brick conforms to the DomainBrick schema from doramagic_contracts
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Add the packages directory to path for imports
_ROOT = Path(__file__).parent.parent.parent.parent  # s1-sonnet/bricks/r06/races/worktree-root
sys.path.insert(0, str(_ROOT / "packages" / "contracts"))

from doramagic_contracts.domain_graph import DomainBrick
from doramagic_contracts.base import EvidenceRef


# ---------------------------------------------------------------------------
# Type aliases (mirrors doramagic_contracts.base)
# ---------------------------------------------------------------------------

KnowledgeType = str  # "capability" | "rationale" | "constraint" | "interface" | "failure" | "assembly_pattern"
Confidence = str     # "high" | "medium" | "low"
SignalKind = str     # "ALIGNED" | "STALE" | "MISSING" | "ORIGINAL" | "DRIFTED" | "DIVERGENT" | "CONTESTED"


# ---------------------------------------------------------------------------
# Helper to build EvidenceRef quickly
# ---------------------------------------------------------------------------

def doc_ref(url: str, snippet: Optional[str] = None) -> EvidenceRef:
    return EvidenceRef(
        kind="community_ref",
        path=url,
        source_url=url,
        snippet=snippet,
    )


def code_ref(path: str, snippet: Optional[str] = None) -> EvidenceRef:
    return EvidenceRef(
        kind="artifact_ref",
        path=path,
        artifact_name=path.split("/")[-1],
        snippet=snippet,
    )


# ---------------------------------------------------------------------------
# Helper to build DomainBrick quickly
# ---------------------------------------------------------------------------

def brick(
    brick_id: str,
    domain_id: str,
    knowledge_type: KnowledgeType,
    statement: str,
    confidence: Confidence,
    signal: SignalKind,
    evidence_refs: list[EvidenceRef],
    tags: list[str],
    support_count: int = 5,
    source_project_ids: Optional[list[str]] = None,
) -> DomainBrick:
    return DomainBrick(
        brick_id=brick_id,
        domain_id=domain_id,
        knowledge_type=knowledge_type,
        statement=statement,
        confidence=confidence,
        signal=signal,
        source_project_ids=source_project_ids or ["hardcoded-expert-knowledge"],
        support_count=support_count,
        evidence_refs=evidence_refs,
        tags=tags,
    )


# ===========================================================================
# PYTHON GENERAL — covers all 6 domains (≥15 bricks)
# ===========================================================================

PYTHON_BRICKS: list[DomainBrick] = [
    # L1 — Core language philosophy
    brick(
        "py-l1-gil",
        "python-general",
        "constraint",
        "Python's Global Interpreter Lock (GIL) prevents true parallel CPU execution in a single process. "
        "CPU-bound tasks must use multiprocessing or separate processes; threading only helps I/O-bound work. "
        "This is NOT a bug to work around per-project — it's a language design constant. "
        "Extraction signal: projects that do CPU-heavy work (ML inference, image processing) use ProcessPoolExecutor, "
        "Ray, or spawn subprocesses; threading is reserved for network/disk I/O.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/glossary.html#term-global-interpreter-lock")],
        ["python", "concurrency", "gil", "l1"],
    ),
    brick(
        "py-l1-duck-typing",
        "python-general",
        "rationale",
        "Python uses structural/duck typing: 'if it walks like a duck and quacks like a duck, it is a duck.' "
        "Type annotations (PEP 484+) are hints, not enforcement. At runtime, any object with the right interface works. "
        "This means projects may implement protocol-based polymorphism WITHOUT inheritance. "
        "Extraction signal: look for Protocol classes, ABCs (abc.ABC), and __dunder__ method implementations as "
        "the REAL interface contracts, not class hierarchies.",
        "high",
        "ALIGNED",
        [doc_ref("https://peps.python.org/pep-0484/")],
        ["python", "types", "duck-typing", "l1"],
    ),
    brick(
        "py-l1-context-managers",
        "python-general",
        "capability",
        "Python context managers (with statement, __enter__/__exit__ or @contextmanager) handle "
        "resource acquisition and release deterministically. This is Python's primary RAII pattern. "
        "Files, DB connections, locks, HTTP sessions, and temporary state should use context managers. "
        "Extraction signal: repeated try/finally without context managers is a code smell indicating "
        "a missed opportunity for resource safety.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/reference/datamodel.html#context-managers")],
        ["python", "resource-management", "context-managers", "l1"],
    ),
    brick(
        "py-l1-generators",
        "python-general",
        "capability",
        "Python generators (yield) produce values lazily, enabling processing of datasets larger than memory. "
        "Generator expressions (x for x in ...) are memory-efficient alternatives to list comprehensions. "
        "asyncio is built on generators/coroutines under the hood. "
        "Extraction signal: projects processing large files, streams, or infinite sequences use generators; "
        "list() wrapping a generator call is a warning that the developer may not understand the tradeoff.",
        "high",
        "ALIGNED",
        [doc_ref("https://peps.python.org/pep-0342/")],
        ["python", "generators", "memory", "l1"],
    ),
    brick(
        "py-l1-dataclasses",
        "python-general",
        "capability",
        "Python dataclasses (@dataclass, Python 3.7+) auto-generate __init__, __repr__, __eq__ from field annotations. "
        "Pydantic extends this for validation and serialization. attrs is an alternative with more features. "
        "NamedTuple provides immutable dataclasses. In 2024+, most projects prefer Pydantic v2 over raw dataclasses "
        "for any data that crosses a trust boundary (API, user input, config files). "
        "Extraction signal: mixing raw dicts and dataclasses inconsistently signals architectural drift.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/library/dataclasses.html")],
        ["python", "dataclasses", "pydantic", "l1"],
    ),
    # L2 — Patterns and UNSAID
    brick(
        "py-l2-import-side-effects",
        "python-general",
        "failure",
        "Python module import executes top-level code immediately. Code at module scope runs on import, "
        "not on call. This means: (1) expensive initialization at module level slows startup for all importers; "
        "(2) database connections opened at module level fail in test environments without DB; "
        "(3) circular imports cause AttributeError at runtime, not at definition time. "
        "Common anti-pattern: putting 'db = create_engine(DATABASE_URL)' at module level in models.py.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/reference/import.html")],
        ["python", "imports", "anti-pattern", "failure", "l2"],
    ),
    brick(
        "py-l2-mutable-defaults",
        "python-general",
        "failure",
        "Python evaluates default argument values ONCE at function definition time, not on each call. "
        "def f(items=[]) creates ONE list shared across all calls — a notorious bug source. "
        "Correct pattern: def f(items=None): items = items or []. "
        "Extraction signal: any function with list, dict, or set as a default argument value is likely buggy. "
        "This also applies to class-level mutable attributes shared across instances.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python-guide.org/writing/gotchas/#mutable-default-arguments")],
        ["python", "defaults", "anti-pattern", "failure", "l2"],
    ),
    brick(
        "py-l2-exception-hierarchy",
        "python-general",
        "rationale",
        "Python exceptions are classes; catching a base class catches all subclasses. "
        "except Exception catches almost everything (not SystemExit/KeyboardInterrupt). "
        "except BaseException catches everything including KeyboardInterrupt. "
        "UNSAID: 'except Exception: pass' silently swallows errors including programming bugs. "
        "Best practice: catch the most specific exception possible, or re-raise with context (raise X from Y). "
        "Projects that do broad exception catching often hide real bugs behind 'graceful' degradation.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/library/exceptions.html")],
        ["python", "exceptions", "l2"],
    ),
    brick(
        "py-l2-asyncio-pitfalls",
        "python-general",
        "failure",
        "asyncio's single-threaded event loop means ANY blocking call (time.sleep, requests.get, file I/O without aiofiles) "
        "freezes ALL concurrent tasks. This is the #1 asyncio bug: mixing sync and async code. "
        "Blocking DB drivers (psycopg2, sqlite3) block the event loop; async alternatives needed (asyncpg, aiosqlite). "
        "run_in_executor() delegates blocking work to a thread pool. "
        "Extraction signal: 'import requests' in an asyncio project is a red flag unless guarded by run_in_executor.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/library/asyncio-eventloop.html")],
        ["python", "asyncio", "anti-pattern", "failure", "l2"],
    ),
    brick(
        "py-l2-pathlib",
        "python-general",
        "capability",
        "pathlib.Path (Python 3.4+) is the modern way to handle file paths. "
        "os.path.join and string concatenation for paths are obsolete patterns. "
        "Path objects are immutable, support / operator for joining, and have methods like .read_text(), .write_text(), "
        ".glob(), .rglob(), .stat(). "
        "Extraction signal: projects using os.path extensively are either old or maintained by developers "
        "not current with Python best practices. Mixing pathlib and os.path is a code smell.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/library/pathlib.html")],
        ["python", "pathlib", "l2"],
    ),
    brick(
        "py-l2-typing-patterns",
        "python-general",
        "interface",
        "Modern Python typing patterns (3.10+): use X | Y instead of Union[X, Y], use X | None instead of Optional[X]. "
        "list[int] instead of List[int] (no import needed). TypeAlias, TypeVar, ParamSpec for generic code. "
        "Protocol for structural subtyping (the Pythonic way to define interfaces without ABC). "
        "TypedDict for typed dict shapes. Literal for constrained string/int types. "
        "Extraction signal: from __future__ import annotations enables postponed evaluation for forward references.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/library/typing.html")],
        ["python", "typing", "interface", "l2"],
    ),
    brick(
        "py-l2-virtual-envs",
        "python-general",
        "assembly_pattern",
        "Python dependency isolation: venv (stdlib), virtualenv, conda, or uv (modern, fast). "
        "requirements.txt pins exact versions for reproducibility; pyproject.toml (PEP 517/518) is the modern standard. "
        "pip-tools compiles requirements.txt from pyproject.toml. "
        "UNSAID: projects without a lock file (requirements.txt or poetry.lock) will have non-reproducible builds. "
        "Extraction signal: the absence of ANY dependency lockfile is a deployment reliability risk.",
        "high",
        "ALIGNED",
        [doc_ref("https://peps.python.org/pep-0517/")],
        ["python", "packaging", "dependencies", "l2"],
    ),
    brick(
        "py-l2-decorators",
        "python-general",
        "capability",
        "Python decorators are functions that wrap other functions, applied at definition time. "
        "@functools.wraps preserves the wrapped function's metadata (critical for introspection, docs, tests). "
        "Class-based decorators with __call__ enable stateful decorators. "
        "Stacked decorators apply bottom-up (innermost first). "
        "UNSAID: decorators that don't use @wraps break Sphinx autodoc and pytest parametrize. "
        "Framework decorators (@app.route, @login_required) are typically syntactic sugar over registration in a registry.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/library/functools.html#functools.wraps")],
        ["python", "decorators", "l2"],
    ),
    brick(
        "py-l2-logging-config",
        "python-general",
        "assembly_pattern",
        "Python's logging module uses a hierarchy: root logger → named loggers (e.g., 'myapp.db'). "
        "basicConfig() configures the root logger globally — calling it in library code pollutes all users' logging. "
        "Libraries should use logging.getLogger(__name__) and add NullHandler() only. "
        "Applications configure logging via dictConfig() or fileConfig(). "
        "UNSAID: print() for debug output in library code is an anti-pattern that cannot be filtered or redirected. "
        "Extraction signal: libraries that call logging.basicConfig() are poorly structured.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/howto/logging.html")],
        ["python", "logging", "l2"],
    ),
    brick(
        "py-l2-descriptor-protocol",
        "python-general",
        "rationale",
        "Python's descriptor protocol (__get__, __set__, __delete__) underlies properties, classmethods, staticmethods, "
        "and ORMs like Django/SQLAlchemy. When you access obj.field, Python checks the class for a descriptor first. "
        "This is how Django model fields work: CharField() is a descriptor that intercepts attribute access. "
        "UNSAID: subclassing a model with a field of the same name shadows the parent's descriptor — "
        "a source of silent data bugs in ORM-based projects. "
        "Extraction signal: understanding descriptors is essential for any project using an ORM or property-heavy design.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/howto/descriptor.html")],
        ["python", "descriptors", "orm", "l2"],
    ),
    brick(
        "py-l2-slots",
        "python-general",
        "capability",
        "__slots__ in a class prevents dynamic attribute creation and reduces memory by replacing __dict__ with a "
        "fixed-size array. A class with 1M instances saves ~50-200MB by using __slots__. "
        "Inheritance complicates slots: subclassing a non-slots class negates the benefit. "
        "UNSAID: dataclasses support slots=True (Python 3.10+). Pydantic v2 models already use __slots__ internally. "
        "Extraction signal: __slots__ in a non-trivial project signals memory-conscious optimization, "
        "likely a high-volume data processing path.",
        "medium",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/reference/datamodel.html#slots")],
        ["python", "memory", "slots", "l2"],
    ),
]


# ===========================================================================
# FASTAPI / FLASK — finance, health, info-ingestion (≥8 bricks)
# ===========================================================================

FASTAPI_FLASK_BRICKS: list[DomainBrick] = [
    # L1 — Framework philosophy
    brick(
        "fastapi-l1-core",
        "fastapi-flask",
        "rationale",
        "FastAPI is built on Starlette (ASGI) + Pydantic (validation) + Python type hints. "
        "Its entire design philosophy is: use standard Python type annotations to drive automatic validation, "
        "serialization, and OpenAPI documentation. There is no 'magic' — each route's parameter types "
        "determine whether it comes from path, query, body, header, or cookie. "
        "Key mental model: FastAPI is a thin layer; most complexity lives in Pydantic models and dependency injection. "
        "Extraction signal: unusual route parameters or complex business logic NOT in Pydantic models indicates "
        "a team that hasn't fully internalized FastAPI's design.",
        "high",
        "ALIGNED",
        [doc_ref("https://fastapi.tiangolo.com/tutorial/")],
        ["fastapi", "l1", "asgi"],
    ),
    brick(
        "flask-l1-core",
        "fastapi-flask",
        "rationale",
        "Flask is a WSGI micro-framework: no ORM, no auth, no form validation built in. "
        "Its philosophy is 'batteries not included' — compose your own stack. "
        "Flask uses a global application context (app_ctx) and request context (req_ctx) via thread-locals. "
        "This is radically different from FastAPI's dependency injection. "
        "UNSAID: Flask's g object and current_app proxy work because of werkzeug's LocalStack. "
        "Extraction signal: Flask projects with heavy SQLAlchemy integration typically use flask_sqlalchemy "
        "for session management within request contexts, not raw SQLAlchemy sessions.",
        "high",
        "ALIGNED",
        [doc_ref("https://flask.palletsprojects.com/en/latest/design/")],
        ["flask", "l1", "wsgi"],
    ),
    # L2 — Patterns
    brick(
        "fastapi-l2-dependency-injection",
        "fastapi-flask",
        "capability",
        "FastAPI's Depends() system is its most powerful feature. Dependencies can be: "
        "functions, classes with __call__, sub-dependencies (nested Depends). "
        "FastAPI caches dependency results per request by default (use_cache=True). "
        "Common patterns: auth token validation, DB session injection, rate limiting, pagination. "
        "UNSAID: Depends() can yield (generator) to run teardown code after the response — "
        "this is the correct way to close DB sessions. Using a plain function that returns a session "
        "without yield leaks connections.",
        "high",
        "ALIGNED",
        [doc_ref("https://fastapi.tiangolo.com/tutorial/dependencies/")],
        ["fastapi", "dependency-injection", "l2"],
    ),
    brick(
        "fastapi-l2-pydantic-validation",
        "fastapi-flask",
        "capability",
        "FastAPI uses Pydantic v2 (Rust-accelerated) for request/response validation. "
        "Request bodies must be Pydantic BaseModel subclasses. Response models use response_model= parameter. "
        "Field() provides validators, defaults, aliases, examples. "
        "UNSAID: Pydantic v2 is NOT backward compatible with v1 — model.dict() became model.model_dump(), "
        "parse_obj() became model.model_validate(). Many older tutorials show v1 API. "
        "Extraction signal: projects mixing .dict() and .model_dump() are mid-migration between Pydantic versions.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.pydantic.dev/latest/migration/")],
        ["fastapi", "pydantic", "validation", "l2"],
    ),
    brick(
        "fastapi-l2-background-tasks",
        "fastapi-flask",
        "capability",
        "FastAPI's BackgroundTasks runs functions AFTER the response is sent, in the same process. "
        "These are NOT task queues — they're simple post-response hooks. "
        "BackgroundTasks are suitable for: email sending, cache invalidation, audit logging. "
        "NOT suitable for: long-running jobs, retryable tasks, jobs that need persistence. "
        "For real async task processing, projects use Celery, ARQ, or Dramatiq. "
        "Extraction signal: BackgroundTasks used for DB writes or external API calls that must not fail "
        "is an architectural risk — if the server crashes, the task is lost.",
        "high",
        "ALIGNED",
        [doc_ref("https://fastapi.tiangolo.com/tutorial/background-tasks/")],
        ["fastapi", "background-tasks", "l2"],
    ),
    brick(
        "flask-l2-blueprints",
        "fastapi-flask",
        "assembly_pattern",
        "Flask Blueprints organize routes into modular components, registered on the app with a URL prefix. "
        "Blueprint-specific template folders, static files, and error handlers are possible. "
        "Common pattern: api/v1/ Blueprint, auth/ Blueprint, admin/ Blueprint. "
        "UNSAID: Blueprints don't isolate state — db.session is still global, app config is still shared. "
        "Large Flask apps often use the Application Factory pattern (create_app()) to enable testing with different configs "
        "and prevent circular imports between extensions.",
        "high",
        "ALIGNED",
        [doc_ref("https://flask.palletsprojects.com/en/latest/blueprints/")],
        ["flask", "blueprints", "architecture", "l2"],
    ),
    brick(
        "fastapi-l2-lifespan",
        "fastapi-flask",
        "assembly_pattern",
        "FastAPI's lifespan context manager (Python 3.9+ recommended) handles startup and shutdown events. "
        "Replaces the deprecated @app.on_event('startup'). "
        "Use lifespan for: creating connection pools, loading ML models, initializing caches. "
        "UNSAID: code in lifespan runs in the main thread before workers start — avoid heavy blocking I/O. "
        "In production with Gunicorn+Uvicorn workers, lifespan runs once per worker, NOT once per deployment. "
        "Extraction signal: projects that create DB connection pools in lifespan are doing it correctly.",
        "high",
        "ALIGNED",
        [doc_ref("https://fastapi.tiangolo.com/advanced/events/")],
        ["fastapi", "lifespan", "startup", "l2"],
    ),
    brick(
        "flask-l2-request-context",
        "fastapi-flask",
        "failure",
        "Flask's request, g, session, and current_app are context-local proxies, not real objects. "
        "They only work within an active request context or application context. "
        "Accessing them outside a request (e.g., in background threads, startup code, CLI commands) raises RuntimeError. "
        "Anti-pattern: passing request.form or session data to background threads — the context is torn down "
        "before the thread reads the data. "
        "Correct pattern: extract the data from the context before spawning the thread.",
        "high",
        "ALIGNED",
        [doc_ref("https://flask.palletsprojects.com/en/latest/reqcontext/")],
        ["flask", "context", "failure", "anti-pattern", "l2"],
    ),
    brick(
        "fastapi-l2-middleware-order",
        "fastapi-flask",
        "failure",
        "FastAPI middleware wraps the entire request/response cycle. "
        "Middleware is applied in REVERSE order of addition — last added runs first for requests, first for responses. "
        "UNSAID: adding CORSMiddleware AFTER other middleware that might return early (like auth) can cause "
        "CORS failures on preflight OPTIONS requests, because the auth middleware blocks before CORS headers are added. "
        "CORS middleware must typically be the OUTERMOST (first added) middleware. "
        "Extraction signal: CORS issues in production but not development often trace to middleware ordering.",
        "high",
        "ALIGNED",
        [doc_ref("https://fastapi.tiangolo.com/tutorial/cors/")],
        ["fastapi", "middleware", "cors", "failure", "l2"],
    ),
]


# ===========================================================================
# HOME ASSISTANT — smart home domain (≥8 bricks)
# ===========================================================================

HOME_ASSISTANT_BRICKS: list[DomainBrick] = [
    # L1 — Platform philosophy
    brick(
        "ha-l1-core",
        "home-assistant",
        "rationale",
        "Home Assistant (HA) is a Python-based home automation platform with an event-driven architecture. "
        "Core concepts: entities (represent devices/sensors), domains (groups of entities like light, switch, sensor), "
        "integrations (code that provides entities), services (callable actions), and the event bus. "
        "Everything communicates via events; no direct function calls between integrations. "
        "The state machine stores current entity states; state changes fire events. "
        "Extraction signal: HA integrations that directly call other integrations' functions (not via services) "
        "are coupling incorrectly and will break on refactors.",
        "high",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/architecture_components")],
        ["home-assistant", "architecture", "l1"],
    ),
    brick(
        "ha-l1-config-flow",
        "home-assistant",
        "capability",
        "Home Assistant config flows provide UI-driven setup for integrations (replacing YAML-only config). "
        "A config flow is a series of steps, each returning a form schema or an entry. "
        "ConfigEntry stores the integration's configuration persistently. "
        "Options flows allow reconfiguration after setup. "
        "UNSAID: integrations still supporting ONLY YAML configuration are considered legacy — the HA team "
        "actively deprecates YAML-only integrations. "
        "Extraction signal: a custom integration without a config_flow.py is either old or not intended for sharing.",
        "high",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/config_entries_config_flow_handler")],
        ["home-assistant", "config-flow", "l1"],
    ),
    # L2 — Patterns
    brick(
        "ha-l2-entity-platform",
        "home-assistant",
        "assembly_pattern",
        "HA entities are registered via async_setup_entry() which receives ConfigEntry. "
        "async_add_entities() registers entities with the platform. "
        "Entities must implement async_update() for polling or call async_write_ha_state() for push updates. "
        "The update coordinator pattern (DataUpdateCoordinator) is the preferred way to share polling logic "
        "across multiple entities from the same device, avoiding redundant API calls. "
        "Extraction signal: integrations without DataUpdateCoordinator that poll multiple sensors independently "
        "make redundant API calls — a performance anti-pattern.",
        "high",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/integration_fetching_data")],
        ["home-assistant", "entities", "coordinator", "l2"],
    ),
    brick(
        "ha-l2-async-required",
        "home-assistant",
        "constraint",
        "Home Assistant's event loop is single-threaded. ALL integration code must be async unless explicitly "
        "delegated to a thread via hass.async_add_executor_job(). "
        "Blocking calls (requests.get, time.sleep, synchronous DB) in async context freeze the entire HA instance. "
        "The HA core team lints for this — blocking calls in async context are a review blocker. "
        "Extraction signal: integrations using the requests library directly (not aiohttp) without executor delegation "
        "will block the event loop and cause HA to become unresponsive.",
        "high",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/asyncio_working_with_async")],
        ["home-assistant", "async", "blocking", "failure", "l2"],
    ),
    brick(
        "ha-l2-device-registry",
        "home-assistant",
        "interface",
        "HA's device registry groups related entities under a single logical device. "
        "DeviceInfo (or DeviceEntry) links entities: same identifiers = same device. "
        "A device can have multiple entities across different platforms (sensor, switch, light). "
        "UNSAID: each entity's unique_id must be globally unique AND stable across restarts. "
        "Using a device's IP address as unique_id breaks when the IP changes. "
        "Best practice: use the device's serial number, MAC address, or a hash of stable properties.",
        "high",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/device_registry_index")],
        ["home-assistant", "device-registry", "unique-id", "l2"],
    ),
    brick(
        "ha-l2-services",
        "home-assistant",
        "interface",
        "HA services are the external API for triggering actions (like REST endpoints in a web API). "
        "Services are registered with async_register() and called via hass.services.async_call(). "
        "Service schemas use voluptuous for validation. "
        "UNSAID: calling a service from within an integration (hass.services.async_call) is the correct decoupling "
        "pattern, but it's async and non-blocking — the caller doesn't wait for completion by default. "
        "Use await with a synchronous wrapper only when result confirmation is needed.",
        "high",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/dev_101_services")],
        ["home-assistant", "services", "l2"],
    ),
    brick(
        "ha-l2-storage",
        "home-assistant",
        "capability",
        "HA provides a Store class for persistent JSON storage: Store(hass, version, key). "
        "This is the correct way to persist integration state across restarts — not writing files directly. "
        "Store handles atomic writes, migration between versions, and proper paths. "
        "UNSAID: data stored in ConfigEntry.data vs ConfigEntry.options vs Store serve different purposes: "
        "data = setup credentials (rarely changes), options = user preferences (UI-editable), "
        "Store = runtime-generated state (counters, learned values, historical data).",
        "high",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/integration_fetching_data#storing-data")],
        ["home-assistant", "storage", "persistence", "l2"],
    ),
    brick(
        "ha-l2-testing",
        "home-assistant",
        "assembly_pattern",
        "HA custom integrations should use pytest-homeassistant-custom-component for testing. "
        "The hass fixture provides a real HA instance. MockConfigEntry sets up config entries in tests. "
        "UNSAID: testing HA integrations without these fixtures means mocking dozens of internal APIs — "
        "fragile and doesn't catch real HA behavior. "
        "Extraction signal: custom integrations with zero tests are deployment risks — HA versions update weekly "
        "and frequently break undocumented internal behaviors that tests would catch.",
        "medium",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/development_testing")],
        ["home-assistant", "testing", "l2"],
    ),
]


# ===========================================================================
# OBSIDIAN / LOGSEQ PLUGINS — PKM domain (≥6 bricks)
# ===========================================================================

OBSIDIAN_LOGSEQ_BRICKS: list[DomainBrick] = [
    # L1 — Platform philosophy
    brick(
        "obsidian-l1-core",
        "obsidian-logseq",
        "rationale",
        "Obsidian is a local-first, Markdown-based knowledge management app. Its plugin API wraps CodeMirror 6 "
        "(editor), Electron (desktop runtime), and a custom Vault abstraction (file system). "
        "Plugins run in a Node.js-like environment with filesystem access (desktop only). "
        "Core philosophy: Obsidian owns the Vault (folder of .md files), plugins are guests. "
        "UNSAID: mobile plugins have a restricted API — no Node.js built-ins, no native modules. "
        "Desktop plugins that use require('fs') directly will fail on mobile.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.obsidian.md/Plugins/Getting+started/Build+a+plugin")],
        ["obsidian", "plugin", "l1"],
    ),
    brick(
        "logseq-l1-core",
        "obsidian-logseq",
        "rationale",
        "Logseq is an outliner-based PKM tool with a graph database (Datascript) under the hood. "
        "Unlike Obsidian (tree of markdown files), Logseq's data model is a flat graph of blocks with parent/child relationships. "
        "Plugins use the logseq.Editor API and Datascript queries for data access. "
        "UNSAID: Logseq is transitioning to a new DB version (Logseq DB) that breaks backward compatibility "
        "with existing plugins. Plugins for classic Logseq may not work with DB version.",
        "medium",
        "ALIGNED",
        [doc_ref("https://plugins-doc.logseq.com/")],
        ["logseq", "plugin", "l1"],
    ),
    # L2 — Patterns
    brick(
        "obsidian-l2-plugin-lifecycle",
        "obsidian-logseq",
        "assembly_pattern",
        "Obsidian plugins extend Plugin class with onload() and onunload(). "
        "Resources registered in onload() MUST be released in onunload() to prevent memory leaks. "
        "this.registerEvent(), this.addCommand(), this.addRibbonIcon() auto-unregister on unload. "
        "UNSAID: raw addEventListener() calls on DOM elements or app.workspace.on() WITHOUT using this.registerEvent() "
        "will leak — the event handler persists after the plugin is disabled/reloaded. "
        "This is the most common source of ghost behavior after plugin updates.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.obsidian.md/Plugins/Getting+started/Anatomy+of+a+plugin")],
        ["obsidian", "lifecycle", "memory-leak", "failure", "l2"],
    ),
    brick(
        "obsidian-l2-vault-api",
        "obsidian-logseq",
        "interface",
        "Obsidian's Vault API (this.app.vault) is the ONLY correct way to read/write files. "
        "Direct Node.js fs operations bypass Obsidian's cache and event system — changes won't trigger "
        "vault.on('modify') events and the metadata cache won't update. "
        "Key methods: vault.read(), vault.create(), vault.modify(), vault.rename(), vault.delete(). "
        "For metadata (frontmatter, links), use MetadataCache: app.metadataCache.getFileCache(). "
        "Extraction signal: plugins using require('fs') for vault files are doing it wrong.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.obsidian.md/Reference/TypeScript+API/Vault")],
        ["obsidian", "vault-api", "l2"],
    ),
    brick(
        "obsidian-l2-settings",
        "obsidian-logseq",
        "assembly_pattern",
        "Obsidian plugin settings use loadData()/saveData() for persistence (stored in .obsidian/plugins/<id>/data.json). "
        "The PluginSettingTab class provides the settings UI panel. "
        "UNSAID: settings are stored as plain JSON — no schema migration built in. "
        "When plugin updates add new settings keys, old users' data.json won't have them. "
        "Best practice: use Object.assign({}, DEFAULT_SETTINGS, await this.loadData()) to merge defaults "
        "with saved settings, ensuring new keys get their defaults.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.obsidian.md/Plugins/User+interface/Settings")],
        ["obsidian", "settings", "migration", "l2"],
    ),
    brick(
        "obsidian-l2-editor-extension",
        "obsidian-logseq",
        "capability",
        "Obsidian's editor is CodeMirror 6. Custom decorations, syntax highlighting, and inline widgets "
        "use CodeMirror 6's extension system (ViewPlugin, StateField, Decoration). "
        "UNSAID: CodeMirror 6 is a reactive system — extensions react to state transactions. "
        "Performing DOM manipulation directly on editor elements (not via CM6 decorations) will "
        "be wiped on the next CM6 render cycle. "
        "Extraction signal: plugins that modify .cm-editor DOM directly are fragile; "
        "correct plugins use ViewPlugin with decorations.",
        "medium",
        "ALIGNED",
        [doc_ref("https://codemirror.net/docs/guide/")],
        ["obsidian", "codemirror", "editor", "l2"],
    ),
]


# ===========================================================================
# GO GENERAL — self-hosted, info-ingestion (≥6 bricks)
# ===========================================================================

GO_BRICKS: list[DomainBrick] = [
    # L1 — Language philosophy
    brick(
        "go-l1-core",
        "go-general",
        "rationale",
        "Go's design philosophy: simplicity, readability, explicit error handling, and built-in concurrency. "
        "Go has no generics-based DI framework by design — dependency injection is done manually via constructors. "
        "Interfaces are implicit (structural typing, like Python duck typing) — a type satisfies an interface "
        "just by implementing its methods, no 'implements' declaration needed. "
        "UNSAID: Go programs are typically structured around small interfaces (1-3 methods) per the 'Go proverb': "
        "'The bigger the interface, the weaker the abstraction.'",
        "high",
        "ALIGNED",
        [doc_ref("https://go.dev/doc/effective_go")],
        ["go", "philosophy", "l1"],
    ),
    # L2 — Patterns
    brick(
        "go-l2-error-handling",
        "go-general",
        "rationale",
        "Go returns errors as the last return value (err error). "
        "Errors are values — they're compared, wrapped, and inspected with errors.Is() and errors.As(). "
        "fmt.Errorf with %w verb wraps errors for unwrapping. "
        "UNSAID: panic() is for programming errors (nil dereference, out-of-bounds), NOT for business logic errors. "
        "Using panic for error propagation and recovering in a handler is a Go anti-pattern — "
        "it's slower and hides the error chain. "
        "Extraction signal: code that panics on expected error conditions (file not found, network timeout) "
        "is not idiomatic Go.",
        "high",
        "ALIGNED",
        [doc_ref("https://go.dev/blog/error-handling-and-go")],
        ["go", "error-handling", "l2"],
    ),
    brick(
        "go-l2-goroutines",
        "go-general",
        "capability",
        "Go goroutines are lightweight threads managed by the Go runtime (not OS threads). "
        "Channels are the preferred communication mechanism: 'Do not communicate by sharing memory; "
        "share memory by communicating.' "
        "sync.WaitGroup waits for goroutine completion. sync.Mutex/sync.RWMutex protect shared state. "
        "UNSAID: goroutine leaks are a major source of memory growth — a goroutine blocked on a channel "
        "that will never receive stays alive. Always ensure goroutines can terminate. "
        "context.Context is the standard way to signal cancellation to goroutines.",
        "high",
        "ALIGNED",
        [doc_ref("https://go.dev/doc/faq#goroutines")],
        ["go", "goroutines", "concurrency", "l2"],
    ),
    brick(
        "go-l2-interface-design",
        "go-general",
        "assembly_pattern",
        "Go interfaces are implicitly satisfied. Best practice: define interfaces at the point of USE, not at the "
        "point of IMPLEMENTATION. A package that returns a concrete type is more flexible than one that returns "
        "an interface — consumers can define whatever interface they need. "
        "UNSAID: the io.Reader/io.Writer pattern is Go's most powerful abstraction — accepting io.Reader instead of "
        "*os.File makes a function work with files, HTTP responses, in-memory buffers, and anything that reads. "
        "Extraction signal: functions accepting concrete types (especially *os.File) instead of interfaces "
        "are unnecessarily constrained.",
        "high",
        "ALIGNED",
        [doc_ref("https://go.dev/wiki/CodeReviewComments#interfaces")],
        ["go", "interfaces", "design", "l2"],
    ),
    brick(
        "go-l2-context",
        "go-general",
        "interface",
        "context.Context is Go's standard mechanism for: (1) request-scoped values, (2) cancellation signals, "
        "(3) deadlines/timeouts. Context is always the FIRST parameter of any function that does I/O or "
        "might be cancelled: func DoSomething(ctx context.Context, ...). "
        "UNSAID: storing a Context in a struct is an anti-pattern — contexts are per-request, not per-object. "
        "context.WithTimeout() wraps a context with a deadline; the defer cancel() is mandatory to release resources. "
        "Extraction signal: functions doing HTTP/DB/gRPC calls without a context parameter cannot be cancelled.",
        "high",
        "ALIGNED",
        [doc_ref("https://pkg.go.dev/context")],
        ["go", "context", "cancellation", "l2"],
    ),
    brick(
        "go-l2-struct-embedding",
        "go-general",
        "capability",
        "Go uses struct embedding (not inheritance) for code reuse. An embedded type's methods are promoted "
        "to the embedding struct. This is NOT inheritance — there's no polymorphism (an *Outer is not an *Inner). "
        "Common pattern: embedding sync.Mutex directly in a struct to make it lockable, "
        "or embedding http.Client to add custom methods. "
        "UNSAID: embedding an interface in a struct gives the struct zero-value implementations (panics when called). "
        "This pattern is used in testing to create partial mocks — implement only the methods you need.",
        "high",
        "ALIGNED",
        [doc_ref("https://go.dev/doc/effective_go#embedding")],
        ["go", "embedding", "composition", "l2"],
    ),
    brick(
        "go-l2-failure-init",
        "go-general",
        "failure",
        "Go's init() function runs automatically before main(), once per package. "
        "Multiple init() functions per package are allowed and run in order. "
        "UNSAID: init() is hard to test and hard to see (no explicit caller). "
        "Relying on init() for critical initialization (DB connections, config loading) is an anti-pattern — "
        "errors in init() typically cause panic and are harder to handle gracefully. "
        "Prefer explicit initialization via constructors called from main(). "
        "Extraction signal: complex business logic in init() is a code smell.",
        "medium",
        "ALIGNED",
        [doc_ref("https://go.dev/doc/effective_go#init")],
        ["go", "init", "failure", "anti-pattern", "l2"],
    ),
]


# ===========================================================================
# DJANGO — finance, health domains (≥6 bricks)
# ===========================================================================

DJANGO_BRICKS: list[DomainBrick] = [
    # L1 — Framework philosophy
    brick(
        "django-l1-mtv",
        "django",
        "rationale",
        "Django uses MTV (Model-Template-View), NOT MVC. The Django 'View' is the controller — it handles "
        "business logic and selects templates. The 'Template' is the presentation layer. "
        "Models are Django's ORM layer with built-in validation. "
        "Key philosophy: batteries included — ORM, auth, admin, forms, caching, sessions all built in. "
        "UNSAID: Django's 'fat models, thin views' pattern means business logic belongs in model methods, "
        "not in views. Views that directly manipulate model data without model methods are hard to test and reuse.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.djangoproject.com/en/stable/faq/general/#django-appears-to-be-a-mvc-framework-but-you-call-the-controller-the-view")],
        ["django", "mtv", "architecture", "l1"],
    ),
    brick(
        "django-l1-orm",
        "django",
        "rationale",
        "Django ORM uses an Active Record pattern — each model instance represents a DB row. "
        "QuerySets are lazy: they don't hit the DB until evaluated (iteration, slicing, len(), bool()). "
        "This means chaining .filter().exclude().order_by() doesn't query the DB. "
        "UNSAID: QuerySets are ALSO cached — calling list(qs) evaluates and caches; qs[0] re-evaluates. "
        "This leads to the classic N+1 problem: iterating over objects and accessing related objects "
        "in a loop fires one query per iteration. select_related() and prefetch_related() are the fix.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.djangoproject.com/en/stable/topics/db/queries/")],
        ["django", "orm", "queryset", "l1"],
    ),
    # L2 — Patterns
    brick(
        "django-l2-n-plus-1",
        "django",
        "failure",
        "The N+1 query problem: fetching 100 blog posts and then accessing post.author in a template "
        "fires 101 queries (1 for posts + 1 per post for author). "
        "Fix: Post.objects.select_related('author') for ForeignKey/OneToOne (SQL JOIN). "
        "Post.objects.prefetch_related('tags') for ManyToMany/reverse FK (separate query + Python join). "
        "Detection: django-debug-toolbar shows duplicate queries. django-silk profiles them. "
        "UNSAID: prefetch_related with a custom queryset uses Prefetch() object. "
        "Extraction signal: any view doing DB access inside a template loop is likely N+1.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related")],
        ["django", "n+1", "performance", "failure", "l2"],
    ),
    brick(
        "django-l2-signals",
        "django",
        "failure",
        "Django signals (pre_save, post_save, post_delete) are synchronous and fire in the same transaction. "
        "They're used for side effects: audit logging, cache invalidation, sending emails. "
        "UNSAID: signals are invisible coupling — no type checker can trace them. "
        "post_save signal calling external APIs will delay saves and fail if the API is down. "
        "post_save fires even within transactions that will be rolled back — the signal handler may see "
        "data that never ends up in the DB. "
        "Best practice: use on_commit() for side effects that must only happen if the transaction commits.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.djangoproject.com/en/stable/topics/signals/")],
        ["django", "signals", "transactions", "failure", "l2"],
    ),
    brick(
        "django-l2-migrations",
        "django",
        "assembly_pattern",
        "Django migrations track schema changes as Python code. makemigrations generates them; migrate applies them. "
        "Migrations must be committed to version control — they ARE the schema history. "
        "UNSAID: squashmigrations compresses migration history for large projects. "
        "Data migrations (RunPython) mix schema and data changes — dangerous in production if the migration "
        "times out or fails halfway. "
        "Zero-downtime migration pattern: (1) add nullable column, (2) deploy and backfill, (3) make non-nullable. "
        "Extraction signal: migrations with direct SQL (RunSQL) indicate the ORM couldn't express the change.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.djangoproject.com/en/stable/topics/migrations/")],
        ["django", "migrations", "schema", "l2"],
    ),
    brick(
        "django-l2-custom-managers",
        "django",
        "capability",
        "Django model managers (Manager) encapsulate QuerySet logic. "
        "Custom managers add domain-specific query methods: Article.published.all() instead of "
        "Article.objects.filter(status='published'). "
        "Using get_queryset() override restricts the default queryset globally. "
        "UNSAID: overriding get_queryset() in the default manager affects admin, related managers, and all queries "
        "— use a separate manager for restricted views. "
        "Extraction signal: repeated .filter(is_active=True) or similar boilerplate across views is a sign "
        "that a custom manager is needed.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.djangoproject.com/en/stable/topics/db/managers/")],
        ["django", "managers", "queryset", "l2"],
    ),
    brick(
        "django-l2-settings-split",
        "django",
        "assembly_pattern",
        "Django uses a single settings.py by convention, but production projects should split settings: "
        "base.py (common), local.py (development overrides), production.py (production config). "
        "The DJANGO_SETTINGS_MODULE environment variable selects which to use. "
        "SECRET_KEY, DATABASE_URL, and API keys must come from environment variables, never be hardcoded. "
        "UNSAID: django-environ or python-decouple are common libraries for reading env vars with type coercion. "
        "Extraction signal: SECRET_KEY hardcoded in settings.py is a security vulnerability and indicates "
        "the project is not production-ready.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.djangoproject.com/en/stable/topics/settings/")],
        ["django", "settings", "configuration", "l2"],
    ),
]


# ===========================================================================
# REACT — finance frontend, PKM frontend (≥5 bricks)
# ===========================================================================

REACT_BRICKS: list[DomainBrick] = [
    # L1 — Framework philosophy
    brick(
        "react-l1-core",
        "react",
        "rationale",
        "React's core model: UI = f(state). The UI is a pure function of state — given the same state, "
        "the same UI renders. This enables predictability and time-travel debugging. "
        "React's reconciliation diffing algorithm computes minimal DOM updates. "
        "UNSAID: React's abstraction leaks — key prop, memo, useCallback all exist to work AROUND "
        "React's diffing algorithm when it's too aggressive. Understanding WHY these exist requires "
        "understanding the reconciler, not just the API. "
        "The component tree is a declarative description; React is the runtime that executes it.",
        "high",
        "ALIGNED",
        [doc_ref("https://react.dev/learn/thinking-in-react")],
        ["react", "philosophy", "l1"],
    ),
    # L2 — Patterns
    brick(
        "react-l2-hooks-rules",
        "react",
        "constraint",
        "React Hooks have two hard rules enforced by eslint-plugin-react-hooks: "
        "(1) Only call Hooks at the top level — not inside loops, conditions, or nested functions. "
        "(2) Only call Hooks from React function components or custom Hooks. "
        "UNSAID: these rules exist because React identifies hooks by their CALL ORDER. "
        "Conditional hook calls change the order across renders, corrupting React's internal state. "
        "Extraction signal: any conditional rendering that wraps a hook call is a bug, not a feature.",
        "high",
        "ALIGNED",
        [doc_ref("https://react.dev/reference/rules/rules-of-hooks")],
        ["react", "hooks", "rules", "constraint", "l2"],
    ),
    brick(
        "react-l2-use-effect-cleanup",
        "react",
        "failure",
        "useEffect cleanup prevents memory leaks and stale closures. "
        "The cleanup function returned from useEffect runs: (1) before the next effect, (2) on unmount. "
        "Common leaks: setInterval without clearInterval, addEventListener without removeEventListener, "
        "fetch() without AbortController, subscriptions without unsubscribe. "
        "UNSAID: In React 18 StrictMode, effects run TWICE in development to expose missing cleanups. "
        "If your effect breaks when run twice, it's missing cleanup. "
        "Extraction signal: fetch calls in useEffect without AbortController cause 'Can't update state on unmounted component' warnings.",
        "high",
        "ALIGNED",
        [doc_ref("https://react.dev/learn/synchronizing-with-effects#how-to-handle-the-effect-firing-twice-in-development")],
        ["react", "useEffect", "cleanup", "failure", "l2"],
    ),
    brick(
        "react-l2-state-colocation",
        "react",
        "assembly_pattern",
        "State should live as close as possible to where it's used (state colocation). "
        "Lifting state up to the nearest common ancestor is correct when siblings need shared state. "
        "Lifting state to a global store for purely local UI state is over-engineering. "
        "UNSAID: the 'prop drilling' pain that drives premature global state is often solved by "
        "component composition (render props, children as function) or Context (for truly global UI state). "
        "Redux/Zustand is appropriate for: cross-cutting concerns, server state sync, undo/redo — "
        "NOT for local form state or modal visibility.",
        "high",
        "ALIGNED",
        [doc_ref("https://react.dev/learn/sharing-state-between-components")],
        ["react", "state", "colocation", "l2"],
    ),
    brick(
        "react-l2-key-prop",
        "react",
        "failure",
        "React's key prop identifies elements in lists for reconciliation. "
        "Using array index as key is a common anti-pattern: when items are reordered or deleted, "
        "React reuses the wrong component instances — causing state bugs (wrong input values) and "
        "animation glitches. "
        "Keys must be stable, unique among siblings, and consistent across renders. "
        "UNSAID: keys are NOT passed as props to the component (props.key is undefined). "
        "Changing a key forces React to unmount and remount the component — sometimes used intentionally "
        "to reset component state.",
        "high",
        "ALIGNED",
        [doc_ref("https://react.dev/learn/rendering-lists#keeping-list-items-in-order-with-key")],
        ["react", "key", "reconciliation", "failure", "l2"],
    ),
    brick(
        "react-l2-server-components",
        "react",
        "capability",
        "React Server Components (RSC, React 19+) run on the server and send HTML to the client — "
        "zero JavaScript bundle impact. Server Components can directly access databases, file systems, "
        "and secrets. Client Components ('use client') run in the browser and handle interactivity. "
        "UNSAID: Server Components cannot use hooks, event handlers, or browser APIs. "
        "The boundary between server and client is explicit at the 'use client' directive. "
        "Extraction signal: Next.js App Router projects use RSC by default; pages/ directory projects "
        "use the old Pages Router with no RSC support.",
        "high",
        "ALIGNED",
        [doc_ref("https://react.dev/reference/rsc/server-components")],
        ["react", "server-components", "rsc", "l2"],
    ),
]


# ===========================================================================
# DOMAIN-SPECIFIC L2 BRICKS (≥5 per domain, 6 domains)
# ===========================================================================

# --- Finance domain ---
FINANCE_DOMAIN_BRICKS: list[DomainBrick] = [
    brick(
        "finance-l2-decimal-precision",
        "domain-finance",
        "failure",
        "NEVER use float for financial calculations. IEEE 754 floats cannot represent most decimal fractions "
        "exactly: 0.1 + 0.2 == 0.30000000000000004. This causes balance discrepancies, rounding errors in "
        "reports, and audit failures. Use Python's decimal.Decimal with explicit precision, or store amounts "
        "as integers (cents/paise) in the database. "
        "UNSAID: Django's DecimalField maps to PostgreSQL NUMERIC, which is exact. FloatField maps to DOUBLE PRECISION — "
        "never use FloatField for money. "
        "Extraction signal: any financial field stored as float is a critical bug.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.python.org/3/library/decimal.html")],
        ["finance", "decimal", "money", "failure", "l2"],
    ),
    brick(
        "finance-l2-audit-trail",
        "domain-finance",
        "constraint",
        "Financial applications require immutable audit trails — every write operation must be recorded with "
        "who, what, when, and before/after state. "
        "Soft deletes (is_deleted=True) instead of DELETE statements preserve history. "
        "UNSAID: audit logging should be append-only and ideally in a separate table/service — "
        "mixing audit data with operational data creates schema coupling and performance issues. "
        "django-simple-history and django-auditlog are common Django solutions. "
        "Extraction signal: financial models without created_by, created_at, updated_by, updated_at fields "
        "are missing basic audit capability.",
        "high",
        "ALIGNED",
        [doc_ref("https://pypi.org/project/django-simple-history/")],
        ["finance", "audit", "compliance", "l2"],
    ),
    brick(
        "finance-l2-double-entry",
        "domain-finance",
        "rationale",
        "Double-entry bookkeeping: every financial transaction debits one account and credits another by equal amounts. "
        "Assets = Liabilities + Equity is always maintained. "
        "UNSAID: most fintech projects that don't implement proper double-entry eventually discover they need it "
        "when auditors or reconciliation requirements hit. "
        "Ledger entries should be immutable: never UPDATE a ledger row, always INSERT a correcting entry. "
        "Extraction signal: a finance project with just 'amount' and 'direction' columns and no account abstraction "
        "is not double-entry and will have reconciliation problems.",
        "high",
        "ALIGNED",
        [doc_ref("https://en.wikipedia.org/wiki/Double-entry_bookkeeping")],
        ["finance", "double-entry", "accounting", "l2"],
    ),
    brick(
        "finance-l2-idempotency",
        "domain-finance",
        "constraint",
        "Financial API endpoints must be idempotent: calling the same payment/transfer request twice must not "
        "double-charge. Idempotency keys (client-generated UUID per operation) are the standard pattern. "
        "The server stores idempotency_key → result and returns the cached result for duplicates. "
        "UNSAID: without idempotency, network retries cause duplicate charges — a critical production bug. "
        "Stripe, PayPal, and all major payment APIs require idempotency keys for all mutation operations. "
        "Extraction signal: payment endpoints without idempotency key handling are unsafe for production.",
        "high",
        "ALIGNED",
        [doc_ref("https://stripe.com/docs/api/idempotent_requests")],
        ["finance", "idempotency", "payments", "l2"],
    ),
    brick(
        "finance-l2-rate-limiting",
        "domain-finance",
        "constraint",
        "Financial APIs must implement rate limiting to prevent abuse, scraping, and brute-force attacks. "
        "Rate limits protect both the API provider and prevent users from accidentally triggering "
        "large numbers of transactions. "
        "UNSAID: financial data APIs (bank statements, transaction history) often have their own rate limits "
        "from providers (Plaid, Yodlee, Open Banking) — exceeding them results in 429 errors and possible "
        "account suspension. "
        "Extraction signal: projects fetching financial data without backoff/retry logic or rate-limit awareness "
        "will fail in production under load.",
        "medium",
        "ALIGNED",
        [doc_ref("https://www.rfc-editor.org/rfc/rfc6585#section-4")],
        ["finance", "rate-limiting", "security", "l2"],
    ),
    brick(
        "finance-l2-data-encryption",
        "domain-finance",
        "constraint",
        "Financial data (account numbers, SSNs, card numbers) must be encrypted at rest and in transit. "
        "PCI DSS requires card data encryption; GDPR/CCPA covers personal financial data. "
        "Field-level encryption (encrypting specific DB columns) vs full-disk encryption serve different threat models. "
        "UNSAID: storing full card numbers is a PCI DSS Level 1 burden — most projects should use tokenization "
        "(store a token from the payment processor, never the actual card number). "
        "Extraction signal: projects storing raw card numbers in their own DB are non-compliant with PCI DSS.",
        "high",
        "ALIGNED",
        [doc_ref("https://www.pcisecuritystandards.org/documents/PCI_DSS_v3-2-1.pdf")],
        ["finance", "security", "encryption", "compliance", "l2"],
    ),
]


# --- PKM (Personal Knowledge Management) domain ---
PKM_DOMAIN_BRICKS: list[DomainBrick] = [
    brick(
        "pkm-l2-linking",
        "domain-pkm",
        "rationale",
        "PKM systems are fundamentally about connections, not storage. The value of a knowledge base grows "
        "with the number of meaningful links, not the number of notes. "
        "Bidirectional links (backlinks) are crucial: knowing what links TO a note is as important as "
        "what it links FROM. "
        "UNSAID: most PKM tools store backlinks as a derived index (not first-class data) — this index "
        "can become stale. Tools that recompute backlinks on every load are slower but always correct. "
        "Extraction signal: a PKM plugin that doesn't update backlinks on file rename/delete creates orphaned references.",
        "high",
        "ALIGNED",
        [doc_ref("https://maggieappleton.com/bidirectionals")],
        ["pkm", "linking", "backlinks", "l2"],
    ),
    brick(
        "pkm-l2-graph-database",
        "domain-pkm",
        "rationale",
        "Logseq uses Datascript (an in-memory graph database with Datalog query language) to model "
        "notes as graphs. This enables powerful queries like 'all blocks tagged #project created this week'. "
        "UNSAID: Datascript queries use [:find ?b :where [?b :block/content ?c] [(re-pattern ...) ?c]] syntax — "
        "not SQL. The learning curve is steep for developers used to SQL. "
        "Extraction signal: Logseq plugins that try to query data by iterating all pages instead of using "
        "Datascript queries are inefficient and miss the platform's primary strength.",
        "medium",
        "ALIGNED",
        [doc_ref("https://docs.logseq.com/#/page/queries")],
        ["pkm", "logseq", "datascript", "l2"],
    ),
    brick(
        "pkm-l2-markdown-portability",
        "domain-pkm",
        "constraint",
        "PKM tools built on Markdown files have a portability contract: notes should be readable outside the tool. "
        "Tool-specific syntax (Obsidian's [[wikilinks]], Logseq's block references like ((block-id))) "
        "reduces portability. "
        "UNSAID: Obsidian's [[wikilinks]] is not standard Markdown — GitHub, VS Code, and most Markdown parsers "
        "render it as literal text. Projects exporting to other formats need wikilink-to-href conversion. "
        "Extraction signal: heavy use of proprietary syntax is a lock-in indicator.",
        "high",
        "ALIGNED",
        [doc_ref("https://spec.commonmark.org/")],
        ["pkm", "markdown", "portability", "l2"],
    ),
    brick(
        "pkm-l2-search-indexing",
        "domain-pkm",
        "capability",
        "PKM search is either lexical (full-text search, fast, exact matches) or semantic (embedding-based, "
        "finds conceptually similar notes even without matching words). "
        "Obsidian's built-in search is lexical. Semantic search plugins use local embedding models (Ollama) "
        "or cloud APIs. "
        "UNSAID: building a semantic search plugin requires keeping embeddings in sync with file changes — "
        "incremental re-embedding on file save is needed, not full reindex on every search. "
        "Extraction signal: a PKM plugin doing full reindex on every search query will be unusable on vaults >1000 notes.",
        "medium",
        "ALIGNED",
        [doc_ref("https://developers.home-assistant.io/docs/")],
        ["pkm", "search", "semantic", "indexing", "l2"],
    ),
    brick(
        "pkm-l2-template-system",
        "domain-pkm",
        "assembly_pattern",
        "Obsidian's Templater plugin (community) and built-in Templates provide note templates. "
        "Templater supports dynamic templates with JavaScript: <%* tp.date.now() %>, file creation, cursor positioning. "
        "UNSAID: the built-in Templates plugin is simple string substitution; Templater is Turing-complete "
        "and can run shell commands — a security concern for vaults shared with untrusted parties. "
        "Extraction signal: projects using Templater for complex workflows (daily notes, project setup) "
        "reveal the team's structured thinking and workflow discipline.",
        "medium",
        "ALIGNED",
        [doc_ref("https://silentvoid13.github.io/Templater/")],
        ["pkm", "obsidian", "templater", "l2"],
    ),
    brick(
        "pkm-l2-sync",
        "domain-pkm",
        "failure",
        "PKM vaults synced across devices (iCloud, Dropbox, git) face conflict resolution challenges. "
        "Markdown files can merge cleanly; binary files (.canvas, databases) cannot. "
        "UNSAID: Logseq's .edn database format and Obsidian's .obsidian/workspace.json are state files "
        "that frequently conflict in git. The correct git pattern: .gitignore workspace.json and other state files. "
        "Extraction signal: vaults committed without a .gitignore for tool-state files will have constant "
        "merge conflicts across devices.",
        "high",
        "ALIGNED",
        [doc_ref("https://help.obsidian.md/Getting+started/Sync+your+notes+across+devices")],
        ["pkm", "sync", "git", "conflict", "l2"],
    ),
]


# --- Private cloud / self-hosted domain ---
PRIVATE_CLOUD_BRICKS: list[DomainBrick] = [
    brick(
        "selfhosted-l2-container-networking",
        "domain-private-cloud",
        "assembly_pattern",
        "Docker Compose services on the same network communicate by service name (not localhost). "
        "If 'web' and 'db' are services, web connects to 'db:5432', not 'localhost:5432'. "
        "UNSAID: a common mistake is hardcoding 'localhost' in app configs inside containers — "
        "this refers to the container itself, not the host or sibling containers. "
        "Port mapping (ports:) makes services reachable from the HOST; internal communication uses the "
        "Docker internal DNS. "
        "Extraction signal: database URLs with 'localhost' inside a Docker Compose setup are misconfigured.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.docker.com/compose/networking/")],
        ["self-hosted", "docker", "networking", "l2"],
    ),
    brick(
        "selfhosted-l2-reverse-proxy",
        "domain-private-cloud",
        "assembly_pattern",
        "Self-hosted applications typically sit behind a reverse proxy (nginx, Traefik, Caddy) that handles "
        "TLS termination, routing, and load balancing. "
        "The app receives HTTP traffic (not HTTPS) from the proxy. "
        "UNSAID: X-Forwarded-For header carries the real client IP — apps must trust and read this header "
        "to log real IPs. Without proper trusted-proxy configuration, all requests appear to come from the proxy. "
        "Caddy auto-provisions Let's Encrypt certs; Traefik does the same with Let's Encrypt/ZeroSSL. "
        "Extraction signal: apps that hardcode port 443 or handle their own TLS inside Docker are fighting "
        "against the standard reverse-proxy model.",
        "high",
        "ALIGNED",
        [doc_ref("https://caddyserver.com/docs/quick-starts/reverse-proxy")],
        ["self-hosted", "reverse-proxy", "tls", "l2"],
    ),
    brick(
        "selfhosted-l2-data-persistence",
        "domain-private-cloud",
        "constraint",
        "Docker containers are ephemeral — all data written inside a container is lost on container restart "
        "unless mounted to a volume or bind mount. "
        "Named volumes (managed by Docker) vs bind mounts (mapped to host directory) serve different needs. "
        "UNSAID: SQLite databases INSIDE a container (not volume-mounted) will lose all data on container updates. "
        "This is the #1 data loss cause in self-hosted deployments. "
        "Extraction signal: any database file path in a Docker container not pointing to a volume mount "
        "will lose data on container replacement.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.docker.com/storage/volumes/")],
        ["self-hosted", "docker", "volumes", "data-loss", "failure", "l2"],
    ),
    brick(
        "selfhosted-l2-secrets-management",
        "domain-private-cloud",
        "failure",
        "Docker Compose .env files are readable by all containers in the compose project by default via ${VAR} substitution. "
        "Docker secrets (Swarm mode) provide encrypted secret storage. "
        "UNSAID: .env files committed to git repositories expose secrets — this is the most common credential leak. "
        ".env files should be in .gitignore; provide .env.example instead. "
        "Environment variables in Docker are visible in process listings and docker inspect — "
        "not suitable for high-sensitivity secrets (use Docker secrets or a vault like HashiCorp Vault). "
        "Extraction signal: hardcoded passwords in docker-compose.yml are critical security issues.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.docker.com/compose/environment-variables/")],
        ["self-hosted", "secrets", "security", "failure", "l2"],
    ),
    brick(
        "selfhosted-l2-healthchecks",
        "domain-private-cloud",
        "assembly_pattern",
        "Docker health checks (HEALTHCHECK instruction or healthcheck: in compose) enable depends_on: "
        "condition: service_healthy to ensure the DB is ready before the app starts. "
        "Without healthchecks, depends_on: only waits for the container to START, not to be READY. "
        "UNSAID: the classic race condition — app container starts before DB is accepting connections — "
        "causes 'connection refused' errors that are hard to debug. "
        "Standard fix: healthcheck + condition: service_healthy, or a wait-for-it.sh script. "
        "Extraction signal: projects with startup order issues that use sleep 10 as a workaround need proper healthchecks.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.docker.com/compose/compose-file/05-services/#depends_on")],
        ["self-hosted", "docker", "healthcheck", "l2"],
    ),
    brick(
        "selfhosted-l2-backup",
        "domain-private-cloud",
        "constraint",
        "Self-hosted data requires a backup strategy: volume snapshots, pg_dump for PostgreSQL, "
        "SQLite backup API for SQLite, restic/rclone for file backups. "
        "3-2-1 rule: 3 copies, 2 media, 1 offsite. "
        "UNSAID: backing up a PostgreSQL data directory while the DB is running can produce corrupt backups "
        "unless using pg_dump (logical backup) or pg_basebackup (physical, with WAL). "
        "Extraction signal: self-hosted projects without documented backup procedures are one disk failure "
        "away from data loss.",
        "medium",
        "ALIGNED",
        [doc_ref("https://www.postgresql.org/docs/current/backup.html")],
        ["self-hosted", "backup", "disaster-recovery", "l2"],
    ),
]


# --- Health data domain ---
HEALTH_DOMAIN_BRICKS: list[DomainBrick] = [
    brick(
        "health-l2-unit-safety",
        "domain-health",
        "failure",
        "Health data has catastrophic unit confusion risks: kg vs lbs (body weight), mg vs g vs mcg "
        "(medication dosage), mmHg vs kPa (blood pressure), mg/dL vs mmol/L (blood glucose). "
        "The 1999 Mars Climate Orbiter crash is the canonical example — health stakes are higher. "
        "Best practice: store values with their unit, or always store in SI units and convert on display. "
        "UNSAID: apps that store '70' without the unit are dangerous — is that kg or lbs? "
        "Extraction signal: health data fields without unit metadata in the schema are a patient safety risk.",
        "high",
        "ALIGNED",
        [doc_ref("https://www.fda.gov/drugs/drug-safety-and-availability/medication-errors-related-clioquinol")],
        ["health", "units", "safety", "failure", "l2"],
    ),
    brick(
        "health-l2-hipaa",
        "domain-health",
        "constraint",
        "HIPAA (US) and GDPR (EU) govern health data. Protected Health Information (PHI) includes: "
        "names, dates (except year), geographic data <state, phone numbers, SSN, diagnosis codes. "
        "De-identification requires removing ALL 18 HIPAA identifiers. "
        "UNSAID: storing 'anonymized' data with age, zip code, and diagnosis date can re-identify patients "
        "via quasi-identifier linkage — this is NOT de-identified under HIPAA. "
        "Business Associate Agreements (BAA) required for any vendor handling PHI. "
        "Extraction signal: health apps storing dates of birth + diagnosis codes + zip codes are processing PHI.",
        "high",
        "ALIGNED",
        [doc_ref("https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/index.html")],
        ["health", "hipaa", "gdpr", "compliance", "l2"],
    ),
    brick(
        "health-l2-time-series",
        "domain-health",
        "capability",
        "Health metrics (heart rate, blood glucose, sleep data, steps) are time-series data. "
        "TimescaleDB (PostgreSQL extension) and InfluxDB are designed for this. "
        "UNSAID: storing health time-series in a regular PostgreSQL table without proper indexing "
        "on the timestamp column will cause catastrophically slow queries as data grows. "
        "Regular RDBMS tables with a timestamp index can handle moderate health data; "
        "TimescaleDB's hypertable partitioning is needed at millions of data points. "
        "Extraction signal: health apps with a 'readings' table and no time-series-optimized storage "
        "will face performance cliffs as user data grows.",
        "medium",
        "ALIGNED",
        [doc_ref("https://docs.timescale.com/getting-started/latest/")],
        ["health", "time-series", "database", "l2"],
    ),
    brick(
        "health-l2-fhir",
        "domain-health",
        "interface",
        "FHIR (Fast Healthcare Interoperability Resources) is the modern standard for health data interchange. "
        "FHIR resources: Patient, Observation, Condition, Medication, Encounter. "
        "HL7 FHIR R4 is the current stable version; SMART on FHIR handles OAuth2 authorization for EHR access. "
        "UNSAID: most health apps do NOT need to implement FHIR internally — FHIR is an interoperability standard "
        "for exchanging data with EHRs. Apps that need to connect to hospital systems or Apple Health/Google Fit "
        "need FHIR parsing but not necessarily FHIR storage. "
        "Extraction signal: projects claiming FHIR compliance that store data in arbitrary schemas are misrepresenting FHIR.",
        "high",
        "ALIGNED",
        [doc_ref("https://hl7.org/fhir/R4/")],
        ["health", "fhir", "interoperability", "l2"],
    ),
    brick(
        "health-l2-consent",
        "domain-health",
        "constraint",
        "Health app users must explicitly consent to data collection, storage, and sharing. "
        "Consent must be informed (plain language), specific (per purpose), and revocable. "
        "UNSAID: pre-checked consent boxes are illegal under GDPR. Bundled consent (one checkbox for everything) "
        "is also invalid — each purpose needs separate consent. "
        "Data minimization principle: collect only what's necessary for the stated purpose. "
        "Extraction signal: health apps with a single 'I agree to Terms of Service' checkbox for all data "
        "collection are not GDPR-compliant.",
        "high",
        "ALIGNED",
        [doc_ref("https://gdpr.eu/consent/")],
        ["health", "consent", "gdpr", "compliance", "l2"],
    ),
    brick(
        "health-l2-wger-pattern",
        "domain-health",
        "assembly_pattern",
        "wger Workout Manager (open source health tracker) exemplifies Django-based health app patterns: "
        "REST API via Django REST Framework, per-user data isolation, exercise/routine/workout as core domain objects. "
        "Key pattern: all user data is scoped by User FK, permission checks in ViewSets ensure users only "
        "see their own data. "
        "UNSAID: a common security bug in health apps is trusting user-supplied IDs without checking ownership — "
        "e.g., PUT /api/workouts/42/ where 42 belongs to another user. "
        "Django's QuerySet filtering by user=request.user is the correct isolation pattern.",
        "high",
        "ALIGNED",
        [doc_ref("https://github.com/wger-project/wger")],
        ["health", "django", "user-isolation", "authorization", "l2"],
    ),
]


# --- Information ingestion domain ---
INFO_INGESTION_BRICKS: list[DomainBrick] = [
    brick(
        "info-l2-rss-atom",
        "domain-info-ingestion",
        "capability",
        "RSS 2.0 and Atom 1.0 are the standard feed formats for content syndication. "
        "feedparser (Python) handles both formats plus various extension modules (iTunes, Dublin Core, GeoRSS). "
        "UNSAID: many feeds are malformed XML — feedparser's lenient parsing handles most real-world feeds, "
        "but strict XML parsers will fail. "
        "Feed update frequency must be respected: polling too frequently gets IPs banned. "
        "If-Modified-Since and ETag HTTP headers enable conditional fetching — skip parsing if feed unchanged. "
        "Extraction signal: info ingestion projects that poll all feeds on the same schedule regardless "
        "of their update frequency waste resources and risk IP bans.",
        "high",
        "ALIGNED",
        [doc_ref("https://feedparser.readthedocs.io/en/latest/")],
        ["info-ingestion", "rss", "atom", "l2"],
    ),
    brick(
        "info-l2-web-scraping",
        "domain-info-ingestion",
        "assembly_pattern",
        "Web scraping stack: requests/httpx for HTTP, BeautifulSoup/lxml for HTML parsing, "
        "Playwright/Selenium for JavaScript-rendered pages. "
        "Scrapy is a full framework for structured scraping with pipelines, middlewares, and item processors. "
        "UNSAID: robots.txt is a legal and ethical constraint, not just a suggestion in many jurisdictions. "
        "User-Agent string should identify the bot, not impersonate a browser — unless intentionally bypassing "
        "detection, which may violate ToS. "
        "Rate limiting with exponential backoff and jitter prevents overloading target servers.",
        "high",
        "ALIGNED",
        [doc_ref("https://scrapy.org/doc/")],
        ["info-ingestion", "scraping", "l2"],
    ),
    brick(
        "info-l2-deduplication",
        "domain-info-ingestion",
        "assembly_pattern",
        "Content deduplication prevents redundant storage and processing of duplicate articles. "
        "URL normalization (remove UTM params, canonicalize scheme/path) is the first pass. "
        "Content fingerprinting (SimHash, MinHash) detects near-duplicate content with different URLs. "
        "UNSAID: the same article often appears at multiple URLs (AMP version, syndicated copies, mobile/desktop). "
        "A fingerprint-based dedup is more effective than URL dedup alone. "
        "Extraction signal: info ingestion projects without dedup will balloon storage and surface "
        "duplicate content to users.",
        "high",
        "ALIGNED",
        [doc_ref("https://ekzhu.com/datasketch/lsh.html")],
        ["info-ingestion", "deduplication", "l2"],
    ),
    brick(
        "info-l2-rate-limiting",
        "domain-info-ingestion",
        "constraint",
        "Info ingestion systems must respect rate limits of upstream sources: "
        "News APIs (NewsAPI, Guardian, NYT) have per-day request limits. "
        "RSS/Atom fetching should use conditional HTTP (ETag/If-Modified-Since) and back off on 429 responses. "
        "UNSAID: API rate limits are often enforced per key and per IP — running multiple workers with "
        "the same API key counts as one entity for rate limiting purposes. "
        "Using Redis-based rate limiting (redis-py-rate-limiter) centralizes limit state across workers. "
        "Extraction signal: multi-worker scrapers without centralized rate limiting will quickly exhaust API quotas.",
        "high",
        "ALIGNED",
        [doc_ref("https://developer.nytimes.com/faq#a11")],
        ["info-ingestion", "rate-limiting", "l2"],
    ),
    brick(
        "info-l2-content-extraction",
        "domain-info-ingestion",
        "capability",
        "Extracting the main article text from HTML (removing navigation, ads, sidebars) is a key challenge. "
        "trafilatura and newspaper3k are Python libraries for this. "
        "Mozilla's Readability algorithm (also available as a Python port) is used by Firefox Reader Mode. "
        "UNSAID: ML-based extractors (trafilatura uses heuristics + ML) outperform CSS-selector approaches "
        "for arbitrary websites. Hardcoded CSS selectors break when site templates change. "
        "For structured extraction (specific fields), use a combination of structured data (JSON-LD, OpenGraph) "
        "first, then fall back to heuristic extraction. "
        "Extraction signal: scrapers using brittle CSS selectors will require constant maintenance.",
        "medium",
        "ALIGNED",
        [doc_ref("https://trafilatura.readthedocs.io/")],
        ["info-ingestion", "content-extraction", "l2"],
    ),
    brick(
        "info-l2-queue-design",
        "domain-info-ingestion",
        "assembly_pattern",
        "Info ingestion pipelines need a work queue for: fetch jobs, processing jobs, and notification jobs. "
        "Celery + Redis/RabbitMQ is the classic Python task queue. ARQ (asyncio-based, simpler) is modern alternative. "
        "UNSAID: Celery's default settings have serious problems: "
        "(1) result backend stores ALL results forever unless expires= is set, filling Redis; "
        "(2) task_acks_late=False means failed tasks are lost if the worker crashes mid-execution; "
        "(3) no retry by default — transient failures cause permanent task loss. "
        "Extraction signal: Celery without max_retries and retry_on_exception configured loses tasks silently.",
        "high",
        "ALIGNED",
        [doc_ref("https://docs.celeryq.dev/en/stable/userguide/tasks.html#retrying")],
        ["info-ingestion", "celery", "queue", "failure", "l2"],
    ),
]


# ===========================================================================
# BRICK REGISTRY — all bricks organized by file
# ===========================================================================

BRICK_FILES: dict[str, list[DomainBrick]] = {
    "python_general": PYTHON_BRICKS,
    "fastapi_flask": FASTAPI_FLASK_BRICKS,
    "home_assistant": HOME_ASSISTANT_BRICKS,
    "obsidian_logseq": OBSIDIAN_LOGSEQ_BRICKS,
    "go_general": GO_BRICKS,
    "django": DJANGO_BRICKS,
    "react": REACT_BRICKS,
    "domain_finance": FINANCE_DOMAIN_BRICKS,
    "domain_pkm": PKM_DOMAIN_BRICKS,
    "domain_private_cloud": PRIVATE_CLOUD_BRICKS,
    "domain_health": HEALTH_DOMAIN_BRICKS,
    "domain_info_ingestion": INFO_INGESTION_BRICKS,
}


# ===========================================================================
# FORGE FUNCTION
# ===========================================================================

def forge_all_bricks(
    output_dir: Path,
    adapter=None,  # Optional LLMAdapter — not used in v1 (all hardcoded)
) -> dict[str, int]:
    """Write all bricks to JSONL files in output_dir/bricks/.

    Args:
        output_dir: Base output directory (races/r06/bricks/s1-sonnet/)
        adapter: Optional LLMAdapter instance (unused, bricks are hardcoded)

    Returns:
        Dict mapping filename -> brick count written
    """
    bricks_dir = output_dir / "bricks"
    bricks_dir.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}

    for filename, bricks in BRICK_FILES.items():
        out_path = bricks_dir / f"{filename}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for b in bricks:
                line = b.model_dump_json()
                f.write(line + "\n")
        counts[filename] = len(bricks)
        print(f"[brick_forge] Wrote {len(bricks)} bricks → {out_path.name}")

    return counts


def load_bricks_from_dir(bricks_dir: Path) -> list[DomainBrick]:
    """Load all bricks from JSONL files in a directory."""
    all_bricks: list[DomainBrick] = []
    for jsonl_file in sorted(bricks_dir.glob("*.jsonl")):
        with jsonl_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    all_bricks.append(DomainBrick.model_validate_json(line))
    return all_bricks


def print_stats(bricks: list[DomainBrick]) -> None:
    """Print summary statistics for a brick collection."""
    from collections import Counter

    total = len(bricks)
    failure_count = sum(1 for b in bricks if b.knowledge_type == "failure")
    failure_pct = failure_count / total * 100 if total > 0 else 0

    type_counts = Counter(b.knowledge_type for b in bricks)
    domain_counts = Counter(b.domain_id for b in bricks)

    print(f"\n=== BRICK STATS ===")
    print(f"Total bricks: {total}")
    print(f"Failure/anti-pattern bricks: {failure_count} ({failure_pct:.1f}%)")
    print(f"\nBy knowledge_type:")
    for kt, count in sorted(type_counts.items()):
        print(f"  {kt:25s}: {count}")
    print(f"\nBy domain_id:")
    for domain, count in sorted(domain_counts.items()):
        print(f"  {domain:35s}: {count}")


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Doramagic Brick Forge — S1-Sonnet Race B")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Output directory (default: same as this script)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics after writing",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    print(f"[brick_forge] Forging bricks → {output_dir}")

    counts = forge_all_bricks(output_dir)

    total = sum(counts.values())
    print(f"\n[brick_forge] Done! Total bricks: {total}")

    if args.stats:
        bricks_dir = output_dir / "bricks"
        bricks = load_bricks_from_dir(bricks_dir)
        print_stats(bricks)


if __name__ == "__main__":
    main()
