# Context Resolution

One procedure, used by every ennam-qaqc command, the `tc-agent` and the
`qc-tcs` skill. It finds three things:

| Thing | What it is |
|---|---|
| **Context file** | The project's adapter: vocabulary, paths, format, import rules, traps. Usually `PROJECT.md`, but any file with that kind of content works. **Optional.** |
| **Template** | The `.feature` skeleton every generated file follows. |
| **Test-cases root** | The folder test cases are written under. |

## 1. Pointer file — `.claude/qaqc.json`

Written only by `/ennam-qaqc:init`. Three paths (relative to the repo root)
plus one machine-readable copy of the importer's rules. Any key may be absent
or `null`.

```json
{
  "projectContext": ".claude/skills/PROJECT.md",
  "template": "test-cases/TEMPLATE.feature",
  "testCasesRoot": "test-cases/",
  "importRules": {
    "featureTags": false,
    "featureDescription": false,
    "background": false,
    "rule": false,
    "maxTitleLength": 200,
    "maxTagLength": 100
  }
}
```

**`importRules`** is what `validate_feature.py` enforces (codes P1–P6) after
every write. Its source of truth stays the context file's §13 (or the
template's `IMPORT RULES` block): `init` copies the rules here, and re-running
`init` refreshes them. A key that is absent is not checked.

| Key | Meaning when set |
|---|---|
| `featureTags` | `false` → no tags on the `Feature:` line |
| `featureDescription` | `false` → no description text under `Feature:` (use `#` comments) |
| `background` | `false` → no `Background:` block |
| `rule` | `false` → no `Rule:` block |
| `maxTitleLength` | longest allowed scenario title, in characters |
| `maxTagLength` | longest allowed tag, in characters including `@` |

Rules the validator cannot express stay in the context file; the agent checks
those.

## 2. Context file — first hit wins

1. **Given by the user** in this request — a path, an `@file`, `--context`, or
   "use X as the project context".
2. **`.claude/qaqc.json` → `projectContext`**, if that file exists. If it points
   at a missing file, say so and continue down the list.
3. **Known spots** — collect every hit:
   - `.claude/skills/PROJECT.md`, `.claude/qaqc/PROJECT.md`, `PROJECT.md`
   - any other `**/PROJECT.md` outside `node_modules/`, `.git/`, `vendor/`
   - `CLAUDE.md` or `AGENTS.md` with a QA / test-case section
     (`grep -il "profile: qa\|test case" CLAUDE.md AGENTS.md`)
   - `<test-cases root>/README.md`

   One hit → use it and say which. Several → ask which (list them).
4. **Nothing found → ask the user**, and wait:
   ```
   I couldn't find a project context file (PROJECT.md or similar) for test cases.
   1. It's at <path> — or use another reference file
   2. Scan this repo and draft one (/ennam-qaqc:init)
   3. Continue without one — plugin defaults
   ```
   Never choose for the user.

A context file need not have every section. Missing sections fall back to §5;
the report lists which defaults were used.

## 3. Template — first hit wins

1. `.claude/qaqc.json` → `template`
2. A skeleton the context file names (e.g. PROJECT.md §3 "Skeleton: …")
3. `<test-cases root>/TEMPLATE.feature`
4. `${CLAUDE_PLUGIN_ROOT}/templates/TEMPLATE.feature` (plugin default)

## 4. Test-cases root — first hit wins

1. `.claude/qaqc.json` → `testCasesRoot`
2. The path pattern the context file gives (PROJECT.md §3)
3. `test-cases/`, if it exists
4. The folder holding the most `*.feature` files (outside `node_modules/`)
5. Ask the user

## 5. Defaults — when the context file is absent or silent

| Topic | Default |
|---|---|
| Tag vocabulary and order | The resolved template's Tag legend and "Tag order" line |
| Area tag | kebab-case of the area folder (`Explore & Discovery/` → `@explore-discovery`) |
| Screen tag | the file name without `.feature` |
| File path | `<root>/<Area>/<kebab-case-feature-name>.feature` |
| Scenario naming | `Scenario: Positive - …` / `Scenario: Negative - …` |
| Shared setup (`Background:`) | not used — every scenario stands alone |
| Priority | none — do not introduce one |
| Source of truth | app-truth (SKILL.md §1 A), as the template's SPEC-DIFFS line states |
| Authoring rule | documents only — never launch or inspect the product; add a COPY SOURCE note; SPEC-DIFFS "None recorded" |
| Import rules | the resolved template's `IMPORT RULES` comment block (machine-checked only once `init` has written `importRules`) |
| Error-handling scope | from the platform: mobile → no HTTP-status scenarios; web with route interception → in scope. State it as an `[ASSUMPTION]`. |
| Exit paths | mobile: system Back, on-screen back, ✕, each CTA · web: browser Back/Forward, in-page back, ✕, each CTA, direct URL / refresh |
| Queued work | listed in the report only |
| Run limits | scenarios that use up a rate-limited real resource (SMS, email, payment) or lock shared state are not counted as automatable now; mark them `[LIMIT]` (see the agent) |

## 6. Closest sibling

Before writing, read one existing `.feature` under the root (never
`TEMPLATE.feature`) to match house style: prefer the same area folder, then the
largest file. None exists → the template alone sets the style.

A sibling shows **style**, never **rules**: where it breaks the import rules
(tags on `Feature:`, a legacy `Scenario -` title, a description under
`Feature:`), the import rules win and the new file does not copy the break.

## 7. Prior file and owners

- **Prior file** — any existing `.feature` for the same case id (grep
  `(<case id>)` on `# Feature:` lines) or at the target path. Even when a *new*
  file is being written, it is a source: its SPEC-DIFFS, LIVE VERIFICATION
  notes and copy bugs record what was **observed in the product**.
- **Owners** — other `.feature` files that cite the same DR/spec ids, the same
  screens or the same feature names (`grep -rl`). What they own is asserted
  here only at the boundary, naming the owning file.
