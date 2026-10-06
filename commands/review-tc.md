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
   FAIL is Critical, each WARN a Warning.
2. Project rules (context §3, §6, §13 — or template IMPORT RULES + defaults):
   import rules; tag vocabulary, order and slots; title prefix ↔ direction; area +
   screen tag on every scenario; triage block counts vs. tags (count with grep).
3. Template shape: every template header block present, in order.
4. With a source: every requirement in the source appears in the COVERAGE block
   and in at least one scenario's traceability comment; spot-check up to 20 quoted
   strings in steps — each must appear verbatim in the source.
5. SKILL.md §10 gap review and §11 checklist.

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
approved, then re-run Step 2.1 and report the new counts. Review never adds
scenarios — coverage gaps go to `/ennam-qaqc:write-tc` in update mode.
