---
description: Point ennam-qaqc at this project's test-case context file, or scan the repo and draft one
argument-hint: [path-to-context-file]
allowed-tools: Read, Write, Glob, Grep, AskUserQuestion, Bash(ls:*), Bash(python3:*)
---

# Init — project context for test cases

**Argument:** $1 (optional — path to an existing context file)

Sets up `.claude/qaqc.json` so later commands find the project's context file,
template and test-cases root without asking, and so the validator can enforce
the project's import rules and tag rules after every write. Read
`${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` first — it defines the pointer
file, the lookup order and the defaults.

## Rules

1. **Never force a name or location.** Any file with the right kind of content is
   a valid context file, complete or not.
2. **Never write a drafted context file without explicit approval.**
3. **Never invent a rule.** Every drafted rule has a source: a repo file + line, a
   user answer, or "plugin default".
4. **`.claude/qaqc.json` holds three paths, `importRules` and `tagRules` —
   nothing else.** Both rule objects are copies; the context file stays the
   source of truth.
5. **Never guess a rule.** A rule the sources do not state is left out (left
   out = not checked), never filled with a default.

## Step 1 — Existing pointer

If `.claude/qaqc.json` exists, show it and ask: keep / refresh rules /
point elsewhere / re-scan.
- Keep → report (Step 8) and stop.
- Refresh rules → read the context file it points at, go to Step 6.
- A pointer **without `importRules` or `tagRules`** (written by an older
  version): say which rules are not machine-checked yet and recommend
  "refresh rules".

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

## Step 6 — Derive the import rules and tag rules

Read the import rules from, first hit wins: the context file's §13 (or any
section naming the importer's constraints — e.g. an "Import compatibility"
section in a CLAUDE.md the context file points to) → the resolved template's
`IMPORT RULES` comment block. Map each stated rule to a key
(CONTEXT_RESOLUTION.md §1):

| Stated rule | Key |
|---|---|
| no tags on `Feature:` | `"featureTags": false` |
| no description under `Feature:` | `"featureDescription": false` |
| no `Background:` | `"background": false` |
| no `Rule:` | `"rule": false` |
| title ≤ N characters | `"maxTitleLength": N` |
| tag ≤ N characters | `"maxTagLength": N` |

The opposite statement ("tags on `Feature:` are allowed") maps to `true`.
Unstated → leave the key out. "Files are not imported" → `"importRules": {}`.
**Tag rules** come from the context file's §6 tag vocabulary (else the
template's Tag legend): the tags per slot → `direction`, `checkType`, `gates`,
`platform`; the area tag per folder → `area`; the scenario naming convention →
`titlePrefix` (e.g. `{"@positive": "Positive - ", "@negative": "Negative - "}`);
the triage mapping (which gates mean BLOCKED, which mean MANUAL — PROJECT.md
§6.4 or the template's convertibility block) → `triage`
(e.g. `{"blocked": ["@blocked", "@not-implemented"], "manual": ["@ui", "@a11y", "@manual"]}`).
Settled edge cases (PROJECT.md §6) that read as "a scenario mentioning X is
never tagged Y" → `settledEdgeCases`: `{"when": "<regex for X>", "notTags":
[<Y tags>], "why": "<section + the rule>"}`. Keep the regex to the words the
rule uses (e.g. `airplane mode|no internet connection|offline`). A settled call
that does not fit that shape stays prose for the agent. Leave out a slot the
sources do not list. Never add a tag that appears only in
an existing `.feature` file — files show usage, not the vocabulary.

Show the result with the source line of each rule, e.g.
`featureTags: false  ← CLAUDE.md "Import compatibility" rule 3`,
`checkType: @logic @navigation @ui @a11y  ← PROJECT.md §6.1`. A rule the user
corrects is corrected in the **context file** first, then here.

## Step 7 — Write the pointer

Resolve the template (CONTEXT_RESOLUTION.md §3) and the root (§4), then write
`.claude/qaqc.json` (keep any other keys an existing pointer already has):

```json
{
  "projectContext": "<context file path>",
  "template": "<template path, or null for the plugin default>",
  "testCasesRoot": "<root>",
  "importRules": { "<key>": "<value from Step 6>" },
  "tagRules": { "<slot>": ["<tags from Step 6>"] }
}
```

Then prove the rules load:
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py <any existing .feature under the root>`
— the output must start with `import rules: .claude/qaqc.json (importRules,
tagRules, IMPORT RULES comment)`. Existing files that now FAIL are reported (not
fixed) in Step 8.

## Step 8 — Report

```
ennam-qaqc initialised
  Context file : <path> (<existing | drafted>) — sections <n>/13, defaults for: <§x, §y | none>
  Template     : <path> (<why>)
  Test cases   : <root>
  Import rules : <n> machine-checked (<keys>) — from <source> | none stated
  Tag rules    : <slots> — from <source> | none stated
  Existing files failing them: <n> (<file: codes>, …) | none
  Pointer      : .claude/qaqc.json
Next: /ennam-qaqc:write-tc <what to write test cases for>
```
