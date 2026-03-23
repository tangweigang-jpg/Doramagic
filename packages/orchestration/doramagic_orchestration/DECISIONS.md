# orchestration.phase_runner Decisions

## Mock-first orchestration

Round 4 only needs the full A-H pipeline to run end to end with correct manifests and error handling.
Phase C, D, and G therefore use deterministic mock bridges around the real module contracts instead of depending on live repos or the still-in-progress validator implementation.

## Real modules where they already exist

The runner uses the implemented modules for:

- `cross-project.discovery`
- `extraction.stage1_scan`
- `extraction.stage15_agentic`
- `cross-project.compare`
- `cross-project.synthesis`
- `skill-compiler.openclaw`

This keeps the orchestration path realistic while still allowing the missing edges to be mocked.

## Conservative degrade policy

If one or more Phase C project extractions fail but at least two extracted projects remain, the run continues as `degraded`.
If fewer than two remain, the run is blocked because compare and synthesis would no longer have enough cross-project signal.

## Validator loop is externally controllable

The mock validator reads `DORAMAGIC_VALIDATOR_SEQUENCE`, which makes revise-loop behavior deterministic in tests.
This allows tests to assert that `G -> REVISE -> F -> G` happens without rerunning the whole pipeline from A.
