---
description: Review an existing .feature test-case file — validator, project import rules, coverage against its source, and the QC-TCs checklist — then offer fixes
argument-hint: <path.feature> [--source <spec file or id>] [--prior <earlier version>]
allowed-tools: Read, Edit, Glob, Grep, AskUserQuestion, Bash(python3:*), Bash(git log:*)
---

# Review test cases

**Request:** $ARGUMENTS

## Step 1 — Resolve context

`${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` §2–§3, same gate as
`/ennam-qaqc:write-tc`. Read `${CLAUDE_PLUGIN_ROOT}/skills/qc-tcs/SKILL.md`, the
context file, the template and the target file. If `--source` is given — or the
header's `Source:` names a file you can find — read it too. Read earlier
versions of the target as well: every `--prior` file,
`git log -p --follow -- <file>`, and the project's knowledge store
(CONTEXT_RESOLUTION.md §7).

## Step 2 — Checks

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py "<file>"` — each
   FAIL is Critical (P1–P10 are the project's import and tag rules from
   `.claude/qaqc.json`); each WARN a Warning, except **G16** (a step not
   observable in the product), which is Critical. P11 means the template's
   `IMPORT RULES` comment was not copied verbatim.
2. Project rules (context §3, §6, §13 — or template IMPORT RULES + defaults):
   whatever the validator did not check (no `importRules` / `tagRules` in
   `qaqc.json`); the context file's settled edge cases (§6) applied; triage block
   counts vs. tags (count with grep) and a reconciliation line wherever a
   build-level blocker or run limit (§9) applies.
3. Triage against CONTEXT_RESOLUTION.md §8 (Critical when wrong):
   - a blocker names its exact step, and moves only scenarios whose `When`/`Then`
     need that step;
   - a scenario a tester can run alone today is MANUAL, not BLOCKED; every
     BLOCKED has a `# [BACKEND]` line naming **who** outside QA must make **what**
     change — reaching the state through the app, by waiting or by repeating an
     action is MANUAL;
   - no scenario mixes parts that triage differently.
4. Template shape: every template header block present, in order; the
   `IMPORT RULES` comment verbatim; a one-line coverage summary that matches the
   COVERAGE block.
5. Judgment (Critical unless noted):
   - **Not observable** — a scenario whose `When`/`Then` needs server-side
     inspection, logs or source code, or that has no expected result ("determine
     whether…", "record the outcome").
   - **Document typo asserted** — a literal string copied from a typo in the spec
     (missing word, malformed example) rather than observed in the product.
   - **Duplicate partition** (Warning) — two scenarios, or an Outline row and a
     standalone, testing the same input class for the same outcome.
   - **Owned elsewhere** (Warning) — behaviour asserted beyond the boundary when
     another `.feature` in the suite has a scenario asserting it
     (CONTEXT_RESOLUTION.md §7).
   - **Handed off without evidence** (Critical) — behaviour marked out of scope
     as "owned by <file>" where that file has no scenario asserting it; it is
     now covered nowhere.
   - **Lost prior knowledge** (Critical) — a SPEC-DIFF, observed copy bug or
     scenario present in an earlier version (working copy, git history, or a
     file passed with `--source`/`--prior`) that is neither kept nor retired
     with a reason.
   - **Run limits** (Warning) — `[LIMIT]` applied inconsistently: a scenario
     that hits a cap or triggers a lockout counted as automatable, or a scenario
     that merely uses one unit marked `[LIMIT]` while others that use one too are
     automatable (CONTEXT_RESOLUTION.md §8).
   - **Disputed string quoted** (Critical) — a literal that an `OQ-xx` says is
     unresolved appears in quotes in a step (or as a literal display value).
   - **More than one case id** (Warning) — the `# Feature:` line carries one id
     in the context file's format; older ids belong in `Source:`.
   - **Message template filled in by hand** (Critical) — a literal string built
     from a source template (`X attempts remaining`) where the source's own
     examples disagree (`1 attempt` vs `1 attempts`); it should be an open
     question asserting only the agreed part.
   - **Routing tags changed** (Critical) — area or screen tags that differ from
     the last **committed** version of the file without a reason, or a "screen" tag that
     names a topic (`@session-persistence`, `@accessibility`). Routing tags are
     the suite's lookup keys.
6. With a source: every inventory item in the source — ACs, Rules, Alts, input
   fields, interaction elements and their enabled/visible conditions, display
   states, UX and accessibility items, rate limits — appears in the COVERAGE
   block (mapped to scenario titles, or `NOT UI-OBSERVABLE` with a reason) and in
   at least one scenario's traceability comment; spot-check up to 20 quoted strings in
   steps — each must appear verbatim in the source or be marked as observed in
   the product.
7. SKILL.md §10 gap review and §11 checklist.

## Step 3 — Report

```
## Review — <file>
Verdict: <Import-ready | Fix before import | Needs coverage work>

### Critical (blocks import or misleads triage)
- <file:line> <issue> → <fix>

### Warnings
- …

### Coverage (when a source was read)
Covered <n> · Partially <n> · Missing <n> · Needs clarification <n>
<rows that are not Covered>

### Checklist (SKILL.md §11)
<failed items, or "all pass">
```

## Step 4 — Offer fixes

Ask: fix all critical / fix everything / pick items / none. Edit only what was
approved, then re-run the validator (Step 2.1) and report the new counts. Review never adds
scenarios — coverage gaps go to `/ennam-qaqc:write-tc` in update mode.
