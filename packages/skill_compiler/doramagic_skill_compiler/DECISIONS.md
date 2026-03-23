# skill-compiler.openclaw Decisions

## Deterministic mock compiler

This Round 3 implementation is intentionally deterministic and does not call an LLM.
It compiles `selected_knowledge` into a stable OpenClaw bundle so downstream validation can test file structure and platform fit before a real prompt-driven compiler exists.

## Conflict handling is conservative

The contracts do not carry an explicit conflict-resolution object.
To satisfy the spec safely, any explicit synthesis conflict or any `SynthesisDecision` with `decision == "option"` is treated as unresolved and blocks the build with `E_UNRESOLVED_CONFLICT`.

## Platform adaptations are explicit

Three transformations are always recorded in `skill_build_manifest.json`:

- allowed tools are normalized to `exec/read/write`
- `cron` is omitted from frontmatter
- storage paths are rewritten to the `~/clawd/` prefix from `PlatformRules`

## Provenance and limitations stay source-driven

`PROVENANCE.md` is generated only from `selected_knowledge`.
`LIMITATIONS.md` is generated from `excluded_knowledge` and `conflicts`.
This keeps the output traceable to the synthesis report and avoids silently inventing product constraints.
