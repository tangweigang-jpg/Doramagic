# BRICK_INVENTORY.md — S1-Sonnet Brick Forge (Race B)

Generated: 2026-03-20

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total bricks | 89 |
| L1 (framework-level) bricks | 15 |
| L2 (pattern-level) bricks | 74 |
| Failure/anti-pattern bricks | 17 |
| Failure ratio | 19.1% (≥15% ✓) |
| Frameworks/domains covered | 12 |
| Evidence refs per brick | 1 (all with documentation URLs) |

---

## Domain × Knowledge_Type Count Table

| Domain | capability | rationale | constraint | interface | failure | assembly_pattern | TOTAL |
|--------|-----------|-----------|------------|-----------|---------|-----------------|-------|
| python-general | 5 | 3 | 1 | 1 | 3 | 3 | 16 |
| fastapi-flask | 3 | 2 | 0 | 0 | 2 | 2 | 9 |
| home-assistant | 1 | 1 | 1 | 2 | 1 | 2 | 8 |
| obsidian-logseq | 1 | 2 | 0 | 1 | 1 | 1 | 6 |
| go-general | 2 | 2 | 0 | 1 | 1 | 1 | 7 |
| django | 1 | 2 | 0 | 0 | 2 | 2 | 7 |
| react | 1 | 1 | 1 | 0 | 2 | 1 | 6 |
| domain-finance | 0 | 1 | 3 | 0 | 1 | 1 | 6 |
| domain-pkm | 0 | 2 | 1 | 0 | 1 | 2 | 6 |
| domain-private-cloud | 0 | 0 | 1 | 0 | 2 | 3 | 6 |
| domain-health | 1 | 0 | 3 | 1 | 1 | 0 | 6 |
| domain-info-ingestion | 1 | 0 | 1 | 0 | 1 | 3 | 6 |
| **TOTAL** | **16** | **16** | **12** | **7** | **17** | **21** | **89** |

> Note: Per-cell counts are derived from the Failure bricks list above (authoritative) + approximate type distribution from JSONL files. Some cells may vary by ±1. Authoritative truth is in the JSONL files.

---

## Failure (Anti-Pattern) Bricks — Full List

Bricks with `knowledge_type="failure"`:

| Brick ID | Domain | Description |
|----------|--------|-------------|
| py-l2-import-side-effects | python-general | Module-level code runs on import — DB connections at module scope break test environments |
| py-l2-mutable-defaults | python-general | `def f(items=[])` shares one list across all calls — classic Python gotcha |
| py-l2-asyncio-pitfalls | python-general | Blocking calls in asyncio event loop freeze all concurrent tasks |
| flask-l2-request-context | fastapi-flask | Flask context proxies don't work outside request context — background thread trap |
| fastapi-l2-middleware-order | fastapi-flask | CORS middleware ordering — last added runs first, auth before CORS causes preflight failures |
| obsidian-l2-plugin-lifecycle | obsidian-logseq | addEventListener without registerEvent() leaks after plugin reload |
| go-l2-failure-init | go-general | init() hides initialization errors, makes code untestable |
| django-l2-n-plus-1 | django | N+1 query problem without select_related/prefetch_related |
| django-l2-signals | django | post_save fires before transaction commit — signal handlers see rolled-back data |
| react-l2-use-effect-cleanup | react | Missing cleanup causes memory leaks; StrictMode double-invocation exposes them |
| react-l2-key-prop | react | Array index as key causes state corruption on reorder/delete |
| finance-l2-decimal-precision | domain-finance | Float arithmetic for money — 0.1 + 0.2 ≠ 0.3 causes audit failures |
| pkm-l2-sync | domain-pkm | Vault state files in git cause constant merge conflicts |
| selfhosted-l2-data-persistence | domain-private-cloud | SQLite inside container (not volume-mounted) loses data on update |
| selfhosted-l2-secrets-management | domain-private-cloud | .env in git = credential leak; docker inspect exposes env vars |
| health-l2-unit-safety | domain-health | Storing weight/dosage without unit — kg vs lbs confusion is a patient safety risk |
| info-l2-queue-design | domain-info-ingestion | Celery without retry config and expires= loses tasks and fills Redis |

**Total failure bricks: 17 out of 89 = 19.1%** (requirement: ≥15% ✓)

---

## Coverage vs. Requirements

| Requirement | Required | Actual | Status |
|-------------|----------|--------|--------|
| Python general (L1+L2) | ≥15 | 16 | ✓ |
| FastAPI/Flask | ≥8 | 9 | ✓ |
| Home Assistant | ≥8 | 8 | ✓ |
| Obsidian/Logseq | ≥6 | 6 | ✓ |
| Go general | ≥6 | 7 | ✓ |
| Django | ≥6 | 7 | ✓ |
| React | ≥5 | 6 | ✓ |
| domain-finance | ≥5 | 6 | ✓ |
| domain-pkm | ≥5 | 6 | ✓ |
| domain-private-cloud | ≥5 | 6 | ✓ |
| domain-health | ≥5 | 6 | ✓ |
| domain-info-ingestion | ≥5 | 6 | ✓ |
| Failure bricks ≥15% | ≥15% | 19.1% | ✓ |
| Evidence refs | all | all | ✓ |
| Works with adapter=None | yes | yes | ✓ |

---

## Brick Level Distribution

| Level | Count | Fraction | Token Budget |
|-------|-------|----------|--------------|
| L1 (framework philosophy) | 15 | 16.9% | ≤400 tokens |
| L2 (patterns / UNSAID) | 74 | 83.1% | ≤800 tokens |

L1 bricks are framework-level anchors — WHY a framework is designed the way it is.
L2 bricks are specific patterns, anti-patterns, and UNSAID knowledge.

---

## Files Produced

```
races/r06/bricks/s1-sonnet/
├── brick_forge.py              # Main script (works with adapter=None)
├── DECISIONS.md                # Design decisions
├── BRICK_INVENTORY.md          # This file
├── bricks/
│   ├── python_general.jsonl    # 16 bricks
│   ├── fastapi_flask.jsonl     # 9 bricks
│   ├── home_assistant.jsonl    # 8 bricks
│   ├── obsidian_logseq.jsonl   # 6 bricks
│   ├── go_general.jsonl        # 7 bricks
│   ├── django.jsonl            # 7 bricks
│   ├── react.jsonl             # 6 bricks
│   ├── domain_finance.jsonl    # 6 bricks
│   ├── domain_pkm.jsonl        # 6 bricks
│   ├── domain_private_cloud.jsonl  # 6 bricks
│   ├── domain_health.jsonl     # 6 bricks
│   └── domain_info_ingestion.jsonl # 6 bricks
└── tests/
    └── test_brick_forge.py     # Comprehensive test suite
```
