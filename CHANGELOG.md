# Changelog

All notable changes to the `ennam-qaqc` plugin are documented here.

## [0.2.0] - 2026-10-07

Driven by a side-by-side review of plugin output against a hand-written file
for the same DR (phone sign-in). The plugin had broadened coverage but broke
some of its own rules and made weaker judgment calls.

### Added

- **Validator enforces project import rules** (P1–P6): tags or a description
  under `Feature:`, `Background:`, `Rule:`, title and tag length — read from a
  new `importRules` object in `.claude/qaqc.json`, or `--config PATH`. Rules
  were previously agent-checked only, and a generated file shipped with tags on
  the `Feature:` line.
- Validator warnings **G15** (duplicate scenario titles) and **G16** (a
  When/Then step not observable in the product: server-side inspection,
  delivery logs, database records, source code).
- `init` derives `importRules` from the context file's §13 (or the template's
  `IMPORT RULES` block), shows the source of each, writes them to the pointer,
  and proves they load. Older pointers can be refreshed in place.
- `PROJECT.md` template: settled edge cases (§6), build-level automation
  blockers and run limits (§9), and the `importRules` key mapping (§13).
- `qc-tcs` skill §14 — lessons from the review.

### Changed

- `tc-agent`:
  - **Observable or nothing** — server-side-only rules get no scenario;
    they are listed as `NOT UI-OBSERVABLE` in coverage. No question/experiment
    scenarios.
  - **Observed copy bug vs document typo** — only copy seen in the product is
    asserted verbatim; spec typos become open questions.
  - **Prior file** — SPEC-DIFFs and observed copy from an existing file for the
    same case id are carried forward, even into a new file.
  - **Owners scan** — behaviour another `.feature` owns is asserted only at the
    boundary.
  - **One partition, one place**; three or more data-only variants become an
    Outline.
  - **Honest triage** — build-level blockers apply to exactly the scenarios that
    hit them; rate-limited or state-locking scenarios are `[LIMIT]` and not
    counted as automatable now; the triage block reconciles its counts.
  - Settled edge cases from the context file are applied.
  - A sibling file shows style, never rules.
  - Coverage maps requirements to scenario titles, with a one-line summary in
    the header; header blocks kept concise; `IMPORT RULES` copied verbatim.
- `write-tc` passes `Prior file` and `Import rules` to the agent and suggests an
  import-rules refresh when the pointer has none.
- `review-tc` checks observability, document-typo assertions, duplicate
  partitions, ownership, run limits and the coverage summary.

## [0.1.2] - 2026-10-07

### Changed

- README: install steps for the Claude desktop app (settings-file based — the
  `/plugin` commands are terminal-only), update steps, and the repository is
  now public. No functional change.

## [0.1.1] - 2026-10-06

### Changed

- Internal build notes (`docs/superpowers/`) are no longer published with the
  plugin. No functional change.

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
