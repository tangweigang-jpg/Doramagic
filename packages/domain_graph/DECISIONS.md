# DECISIONS.md — domain-graph.snapshot_builder

## Key Decisions

1. Domain bricks are promoted only from `ALIGNED` compare signals that meet `min_support_for_brick`.
2. `DIVERGENT` and `CONTESTED` signals are preserved in `DOMAIN_TRUTH.md` but never promoted to bricks.
3. Atom clusters are built deterministically by selecting the best-matching atom per supporting project for each compare signal.
4. `DOMAIN_BRICKS.json` stores the full `DomainSnapshot`, not only the brick list, so API consumers can reuse clusters and stats from one file.
5. Runtime output always includes `atoms.json` for API compatibility; Parquet is best-effort and only written when the environment supports it.
6. SQLite output is generated with the stdlib `sqlite3` module so the graph remains queryable without extra dependencies.

## Known Gaps

1. Signal-to-atom matching is lexical and heuristic, not embedding-based, so noisy fixtures can still map slightly imperfectly.
2. `atoms.parquet` depends on optional pandas/parquet support and may remain `null` in the manifest.
3. Theme/tag generation is deterministic but intentionally lightweight; it favors stable output over richer summarization.

## Test Coverage

1. Normal flow on the Sim2 calorie-tracking fixture.
2. Empty fingerprints returning `blocked + E_INPUT_INVALID`.
3. High `min_support_for_brick` returning `degraded` with zero bricks.
4. Non-empty `DOMAIN_TRUTH.md` containing the domain name and a brick statement.
