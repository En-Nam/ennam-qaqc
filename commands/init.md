---
description: Point ennam-qaqc at this project's test-case context file, or scan the repo and draft one
argument-hint: [path-to-context-file]
allowed-tools: Read, Write, Glob, Grep, AskUserQuestion, Bash(ls:*)
---

# Init — project context for test cases

**Argument:** $1 (optional — path to an existing context file)

Sets up `.claude/qaqc.json` so later commands find the project's context file,
template and test-cases root without asking. Read
`${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` first — it defines the pointer
file, the lookup order and the defaults.

## Rules

1. **Never force a name or location.** Any file with the right kind of content is
   a valid context file, complete or not.
2. **Never write a drafted context file without explicit approval.**
3. **Never invent a rule.** Every drafted rule has a source: a repo file + line, a
   user answer, or "plugin default".
4. **`.claude/qaqc.json` holds paths only.**

## Step 1 — Existing pointer

If `.claude/qaqc.json` exists, show it and ask: keep / point elsewhere / re-scan.
Keep → report (Step 7) and stop.

## Step 2 — Ask for an existing file

If `$1` was given, use it. Otherwise collect candidates with
CONTEXT_RESOLUTION.md §2 step 3, then ask (AskUserQuestion):

> Do you already have a project context file for test cases — a PROJECT.md, or
> another file with the same kind of content (tags, paths, format, import rules)?

Options: each candidate found · "Another file — I'll give the path" ·
"No — scan the repo and draft one".

**A file is chosen:** confirm it exists and read it. Note which of the 13
sections of `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md` it covers; the rest use
defaults (not an error). Go to Step 6.

## Step 3 — Scan the repo

Read whatever exists, in parallel:

| Look at | To learn |
|---|---|
| `**/*.feature` (skip `node_modules/`, `.git/`, `TEMPLATE.feature`) — up to 10, the largest per folder | root and areas (folders) · area tag per folder (the tag shared by every scenario in that folder) · screen-tag convention · title prefixes · case-id format on `# Feature:` lines · header blocks in order · `Background:` / `Scenario Outline` use · priority tags · comment style |
| `**/TEMPLATE.feature` | template path |
| `README*`, `CLAUDE.md`, `AGENTS.md`, `<root>/README.md`, `docs/**/*test*` | conventions, source of truth, import tool and its rules, authoring rules |
| `flows/**/*.yaml`, `playwright.config.*`, `cypress.config.*`, `wdio.conf.*`, `.detoxrc*` | automation framework |
| `environments/*`, `.env.example`, `app.json`, `package.json` | platform (`react-native`/`expo` → mobile; `next`/`vite`/`react-dom` → web), app/site ids, environments |
| `docs/**/DR-*.md`, `docs/PLATFORMS/` | where specs live, case-id style |

## Step 4 — Ask what the scan could not settle

Ask only questions whose answers change the output and that the scan did not
answer with a source (AskUserQuestion, at most 4 per call):

1. Platform under test — mobile / web / both
2. Automation framework — Maestro / Playwright / Cypress / Appium / none
3. Case-id format — e.g. `US-001`, `DR-PA-003-005-01`, none
4. Areas / folders
5. Source of truth — app-truth / spec-truth
6. Import tool and its constraints — or "files are not imported"

## Step 5 — Draft, show, approve

Build the draft from `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md`. Fill each
section from the scan and the answers. A section nothing supports keeps its
guidance text plus "Not set — plugin default applies". Fill the Provenance table:
one row per rule with its source.

Show the full draft, then ask:

> Write this to `.claude/qaqc/PROJECT.md`? approve / different path / change something first / cancel

Write only on approval. Cancel → write nothing (not `qaqc.json` either) and stop.

## Step 6 — Write the pointer

Resolve the template (CONTEXT_RESOLUTION.md §3) and the root (§4), then write
`.claude/qaqc.json`:

```json
{
  "projectContext": "<context file path>",
  "template": "<template path, or null for the plugin default>",
  "testCasesRoot": "<root>"
}
```

## Step 7 — Report

```
ennam-qaqc initialised
  Context file : <path> (<existing | drafted>) — sections <n>/13, defaults for: <§x, §y | none>
  Template     : <path> (<why>)
  Test cases   : <root>
  Pointer      : .claude/qaqc.json
Next: /ennam-qaqc:write-tc <what to write test cases for>
```
