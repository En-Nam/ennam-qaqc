# Changelog

All notable changes to the `ennam-qaqc` plugin are documented here.

## [0.8.0] - 2026-10-08

### Added — bulk conform

- **Resumable runs** — `scripts/conform_state.py` keeps
  `.claude/qaqc-conform/state.json`: each file's status (pending / formatted /
  upgraded / needs-answers / skipped / failed) and a SHA-256 of conform's last
  write. Its gate lets a file with uncommitted changes through only when conform
  made them and nothing changed since, so an interrupted run continues instead
  of blocking on its own edits.
- **Reports on disk** — the agent writes each file's full report to
  `.claude/qaqc-conform/reports/<path>.md` and returns one line; the chat shows
  a single summary table.
- **Two-step plan** — for more than 10 files the command recommends Phase A on
  everything, a commit, then Phase B folder by folder.
- **`--batch N`** — at most N files through Phase B per run.
- **Collected questions** — agents run with `Questions: collect`: they take the
  conservative choice, finish the file, and list the question; all questions
  are asked once at the end and answered files are revised.
- `--again` re-upgrades finished files.

## [0.7.0] - 2026-10-08

### Added

- **`/ennam-qaqc:conform`** — upgrade existing `.feature` files (a teammate's
  own format, legacy `Scenario -` files) to the plugin's format and rules, in
  place. Plugin rules now apply to legacy files too.
  - **Phase A — `scripts/conform_feature.py`**: mechanical, meaning-preserving
    changes C1–C9 (keyword colons, tag-line text to comments, Feature tags onto
    every scenario, Feature description to comments, Background inlined, tag
    order, title prefix, IMPORT RULES comment, triage line). Dry run by
    default; a safety check (same scenarios, titles, steps) gates every write.
    On two real legacy files: 223 → 47 and 203 → 44 FAIL, scenario counts
    unchanged; what remains needs judgment.
  - **Phase B — `tc-agent` upgrade mode**: header to the template, re-triage,
    tag vocabulary, open questions, coverage against the source spec (adding
    missing scenarios when the spec is available); every scenario change listed
    with the rule that required it.
  - Requires the files to be committed (git is the undo); never commits, stashes
    or resets. `--format-only` stops after Phase A.

## [0.6.0] - 2026-10-08

Driven by checking the 0.5.0 output against the DR and PROJECT.md: it passed
every mechanical check but had three wrong assertions and five mis-triaged
scenarios. **No change to the importable output**; `TEMPLATE.feature` untouched.

### Added

- **P13 — settled edge cases are machine-checked.** `tagRules.settledEdgeCases`
  lists rules of the form "a scenario mentioning X is never tagged Y"; `init`
  derives them from PROJECT.md §6. The 0.5.0 output tagged both airplane-mode
  scenarios `@manual` — the third run to miss "airplane mode is not a gate".

### Changed

- `tc-agent` final checks, mirrored in `review-tc`:
  - **No contradictory assertions** — 0.5.0 asserted both "the field stops at 9
    digits" and an inline error after typing 10. Unknown outcome = one OQ.
  - **Thresholds cross-checked** — 0.5.0 entered a third wrong code and
    expected "no attempts remain" instead of the 15-minute lockout.
  - **Behaviour needs a source** — 0.5.0 asserted the resend countdown (right,
    per a teammate's observation) with no SPEC-DIFF saying where it came from.
- The report lists every behaviour that differs from the DR with its SPEC-DIFF.

## [0.5.0] - 2026-10-07

Driven by the fourth review. The 0.4.0 output was the first to pass every C4K
check (0 FAIL / 0 WARN with import rules, tag rules, the triage line and the
IMPORT RULES comment). **No change to the importable output or the validator.**

### Changed

- **Knowledge store is a prior source.** The agent greps the store the context
  file names (C4K: `.serena/memories/`) for findings about the case id, DR,
  feature and screens, and the report lists each SPEC-DIFF still to be filed
  there. The resend finding was lost again because it lived only in a
  teammate's copy that no run was given.
- **BLOCKED names who and what.** Every `@blocked` needs a `# [BACKEND]` line
  naming the person or team outside QA and the change; anything a tester can
  reach alone (through the app, by waiting, by repeating) is MANUAL. The 0.4.0
  output marked three such scenarios BLOCKED.
- **Routing tags come from the last committed version**, not the working copy —
  which may be the plugin's own unreviewed draft. Tag conventions vary by
  project and feature; none is assumed. Findings are still read from every
  version.
- **Disputed strings are never quoted** — the final check greps the steps for
  every candidate literal an open question names.
- **One case id** on the `# Feature:` line; older ids move to `Source:`.
- `review-tc` checks all of the above and reads the knowledge store.

## [0.4.0] - 2026-10-07

Driven by the third review. 0.3.0's fixes held; this release closes the gaps the
review missed. **No change to the importable output**: `TEMPLATE.feature` is
untouched, and every new check reads header comments or tags only.

### Added

- **P12** — the triage block's first line,
  `# Triage: A automatable / M manual / B blocked (N scenarios)`, is checked
  against the tags using a new `tagRules.triage` mapping (first match wins:
  blocked, then manual). A disagreement fails; a missing line warns. The 0.3.0
  output stated 23 manual where the tags gave 24.
- `write-tc`'s existing-file question also asks for a newer copy outside the
  repo (e.g. a teammate's) and adds it as a `--prior` source.

### Changed

- **P11 is now a FAIL** — a paraphrased `IMPORT RULES` comment blocks the write
  (it had been rewritten in three runs).
- **Routing tags carry over** from the prior file; a screen tag must name a
  screen. 0.3.0 replaced the suite's `@phone-auth` with five new tags, two of
  them topics.
- **Message templates are documents** — when a template's examples disagree
  (`1 attempt` / `1 attempts`), the agent raises an open question and asserts
  only the agreed part.
- **`[LIMIT]` redefined** — hitting a cap or triggering a lockout, not using one
  unit; single-unit use is covered by a run budget in PRECONDITIONS.
- The report names the prior sources read and the routing tags kept or changed.
- `review-tc` flags hand-filled templates, changed routing tags and inconsistent
  `[LIMIT]`.

## [0.3.0] - 2026-10-07

Driven by the second review (0.2.0 output vs Nghĩa's file). 0.2.0's fixes held,
but findings from the app were lost, two scenarios vanished, tag order was
wrong in three places, and 28 scenarios a tester can run were marked
`@blocked`.

### Added

- **Validator enforces tag rules** (P7–P10) from a new `tagRules` object in
  `.claude/qaqc.json`: exactly one direction and one check-type tag, slot order,
  one area tag then one screen tag, title prefix matching the direction. The
  agent's own tag check had missed problems twice.
- **P11** (warning) — the template's `IMPORT RULES` comment must be copied
  verbatim; the template comes from `qaqc.json` or the plugin default.
- `init` derives `tagRules` from the context file's §6; "refresh rules" updates
  older pointers.
- `write-tc --prior <file>` (repeatable) — learn from an earlier version kept
  anywhere, e.g. a teammate's copy.
- **One triage definition** (CONTEXT_RESOLUTION.md §8): AUTOMATABLE / MANUAL /
  BLOCKED by each scenario's own result; a blocker names its exact step; a
  blocker a tester can work around makes a scenario MANUAL, not BLOCKED.

### Changed

- **Prior knowledge**: the working copy (uncommitted edits included) wins over
  `HEAD`; git history is searched for dropped SPEC-DIFFs; newer versions on other
  branches are reported. A prior assertion that disagrees with the document
  becomes an open question instead of a silent pick. The report accounts for
  every prior scenario (kept / merged / reworded / dropped + why).
- **Ownership needs evidence** — a named scenario in the owning file; screens in
  the spec's own scope stay otherwise.
- **Coverage inventory** includes fields, interaction elements and their
  enabled conditions, display states, UX and accessibility items.
- Scenarios whose parts would triage differently are split.
- The report lists the settled edge cases applied.
- `review-tc` checks triage, hand-offs without evidence, lost prior knowledge
  and the full inventory.
- `qc-tcs` skill §14 extended with the 0.3.0 lessons.

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
