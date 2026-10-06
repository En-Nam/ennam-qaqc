# Changelog

All notable changes to the `ennam-qaqc` plugin are documented here.

## [0.1.0] - 2026-10-06

### Added

- `/ennam-qaqc:init` — point at an existing project context file (any name, any
  path), or scan the repo and draft one; writes `.claude/qaqc.json` (paths only).
- `/ennam-qaqc:write-tc` — write, update or preview one `.feature` file from any
  material (brief, DR, reference file, URL), with explicit gates only.
- `/ennam-qaqc:review-tc` — validator + project rules + coverage + checklist
  review with optional fixes.
- `tc-agent` — authoring agent following the QC-TCs method.
- `qc-tcs` skill — the QC-TCs method, adapted to resolve the project context file
  instead of a fixed `PROJECT.md`.
- `scripts/validate_feature.py` + PostToolUse hook — Gherkin and universal-rule
  linter (checks G1–G14).
- Templates: default `TEMPLATE.feature` (QC-TCs), blank `PROJECT.md` with a new
  §13 for per-project import rules, `qaqc.example.json`.
