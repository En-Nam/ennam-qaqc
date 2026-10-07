---
description: Review an existing .feature test-case file — validator, project import rules, coverage against its source, and the QC-TCs checklist — then offer fixes
argument-hint: <path.feature> [--source <spec file or id>]
allowed-tools: Read, Edit, Glob, Grep, AskUserQuestion, Bash(python3:*)
---

# Review test cases

**Request:** $ARGUMENTS

## Step 1 — Resolve context

`${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` §2–§3, same gate as
`/ennam-qaqc:write-tc`. Read `${CLAUDE_PLUGIN_ROOT}/skills/qc-tcs/SKILL.md`, the
context file, the template and the target file. If `--source` is given — or the
header's `Source:` names a file you can find — read it too.

## Step 2 — Checks

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py "<file>"` — each
   FAIL is Critical (P-codes are the project's import rules from
   `.claude/qaqc.json`); each WARN a Warning, except **G16** (a step not
   observable in the product), which is Critical.
2. Project rules (context §3, §6, §13 — or template IMPORT RULES + defaults):
   import rules the validator did not check; tag vocabulary, order and slots;
   title prefix ↔ direction; area + screen tag on every scenario; the context
   file's settled edge cases (§6) applied; triage block counts vs. tags (count
   with grep) and a reconciliation line wherever a build-level blocker or run
   limit (§9) applies.
3. Template shape: every template header block present, in order; the
   `IMPORT RULES` comment verbatim; a one-line coverage summary that matches the
   COVERAGE block.
4. Judgment (Critical unless noted):
   - **Not observable** — a scenario whose `When`/`Then` needs server-side
     inspection, logs or source code, or that has no expected result ("determine
     whether…", "record the outcome").
   - **Document typo asserted** — a literal string copied from a typo in the spec
     (missing word, malformed example) rather than observed in the product.
   - **Duplicate partition** (Warning) — two scenarios, or an Outline row and a
     standalone, testing the same input class for the same outcome.
   - **Owned elsewhere** (Warning) — behaviour asserted beyond the boundary when
     another `.feature` in the suite cites the same DR/screen
     (CONTEXT_RESOLUTION.md §7).
   - **Run limits** (Warning) — a scenario counted as automatable that uses up a
     rate-limited real resource or locks shared state, without `[LIMIT]`.
5. With a source: every requirement in the source appears in the COVERAGE block
   (mapped to scenario titles, or `NOT UI-OBSERVABLE` with a reason) and in at
   least one scenario's traceability comment; spot-check up to 20 quoted strings in
   steps — each must appear verbatim in the source or be marked as observed in
   the product.
6. SKILL.md §10 gap review and §11 checklist.

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
