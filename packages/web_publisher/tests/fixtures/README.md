# Test Fixtures

This directory holds static test fixture files.

## Planned fixtures

- `bp-009/` — Real Crystal IR + seed.md + constraints for bp-009 (A股MACD回测)
  - `crystal_ir.json` — compiled Crystal IR
  - `PRODUCTION.seed.md` — seed file
  - `constraints.jsonl` — constraint entries
  - `qa_manifest.yaml` — creator proof entries
  - `expected_package.json` — expected assembled Package for regression testing

## How to add fixtures

1. Run the extraction pipeline for a blueprint to get the Crystal IR
2. Place the files here under `{blueprint_id}/`
3. Add a corresponding test in `test_pipeline.py` using `pytest.fixture` to load them

## Note

Fixtures are NOT checked into git if they contain real blueprint data.
Add to `.gitignore` if needed, or anonymize the data first.
