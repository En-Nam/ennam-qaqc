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
plus machine-readable copies of the importer's rules and the tag rules. Any key
may be absent or `null`.

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
  },
  "tagRules": {
    "direction": ["@positive", "@negative"],
    "checkType": ["@logic", "@navigation", "@ui", "@a11y"],
    "gates": ["@not-implemented", "@blocked", "@manual", "@pending-oq"],
    "platform": ["@ios-only", "@android-only"],
    "area": ["@authentication", "@account", "@explore"],
    "titlePrefix": { "@positive": "Positive - ", "@negative": "Negative - " },
    "triage": {
      "blocked": ["@blocked", "@not-implemented"],
      "manual": ["@ui", "@a11y", "@manual"]
    }
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

**`tagRules`** is the context file's §6 vocabulary, enforced as codes P7–P10:
exactly one `direction` and one `checkType` tag, at most one `platform` tag,
tags in slot order (direction → check type → gates → platform → area →
screen), exactly one `area` tag followed by one screen tag (any other tag), and
the title prefix that `titlePrefix` maps the direction tag to. A slot list that
is absent is not checked.

**`tagRules.triage`** maps gate tags to MANUAL and BLOCKED (first match wins:
blocked, then manual, else automatable). With it, the validator checks the
header's triage line against the tags (P12):

```
#   Triage: 20 automatable / 24 manual / 1 blocked (45 scenarios)
```

The line is a header comment — the importer never reads it.

**The template's `IMPORT RULES` comment** is checked too (P11, a failure):
whenever a `qaqc.json` is found, the comment block starting `# IMPORT RULES` in
the resolved template must appear verbatim before `Feature:`.

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
| Triage definition | §8 — always, unless the context file defines its own |

## 6. Closest sibling

Before writing, read one existing `.feature` under the root (never
`TEMPLATE.feature`) to match house style: prefer the same area folder, then the
largest file. None exists → the template alone sets the style.

A sibling shows **style**, never **rules**: where it breaks the import rules
(tags on `Feature:`, a legacy `Scenario -` title, a description under
`Feature:`), the import rules win and the new file does not copy the break.

## 7. Prior file and owners

**Prior file** — every earlier version of this feature's test cases. Even when a
*new* file is written, it is a source: its SPEC-DIFFS, LIVE VERIFICATION notes
and copy bugs record what was **observed in the product**. Collect, in order:

1. Files the user names with `--prior <file>` (any path — e.g. a teammate's copy).
2. The existing `.feature` for the same case id (grep `(<case id>)` on
   `# Feature:` lines) or at the target path — **as it is on disk now**,
   uncommitted edits included. Read it before anything is written; never prefer
   `git show HEAD:` over the working copy.
3. Its git history: `git log -p --follow -- <path>` — SPEC-DIFF and observation
   lines that a later commit dropped are still evidence.
4. Other local branches: `git log --all --oneline -- <path>`. A commit on another
   branch that is newer than the working copy is **reported**, not merged
   (e.g. "origin/nghia has a newer version — pull it, or pass it with
   --prior").

Findings only reach the plugin if they are in one of these. A teammate's
uncommitted copy on another machine is invisible: commit and push it, pull it
here, or pass it with `--prior`.

**Routing tags carry over.** The prior file's area and screen tags are the
suite's lookup keys (flows, `/qa-run`, filters). Keep them unless the context
file says otherwise; a change is reported, never silent. A screen tag names a
screen or view — never a topic or check type (`@session-persistence`,
`@accessibility` are not screens).

**Owners** — other `.feature` files that cite the same DR/spec ids, the same
screens or the same feature names (`grep -rl`). Behaviour is handed to an owner
only with **evidence**: a named scenario in that file that asserts it. A screen
inside this spec's own scope stays here unless such a scenario exists.

## 8. Triage definition

One definition for every project (a context file may refine it, never contradict
it). Classify each scenario by **its own expected result**, not the whole flow:

| Triage | The scenario… | Typical project gate |
|---|---|---|
| **AUTOMATABLE** | can be driven and asserted by the automation framework on today's build, repeatably, by itself | none |
| **MANUAL** | can be run today by a tester alone — a real SMS read off a handset, OS UI, real elapsed time, judging visuals, a run limit (`[LIMIT]`) | `@manual` (or the check type `@ui` / `@a11y`) |
| **BLOCKED** | cannot be run by anyone in QA until **someone else** changes something — backend data or config, a build hook, an unbuilt screen | `@blocked` / `@not-implemented` |

- **Name the blocked step exactly.** A build-level blocker ("no DEV OTP hint")
  stops one step ("entering a valid code"). It moves only scenarios whose
  `When`/`Then` needs that step — not every scenario after it.
- **A blocker a tester can work around by hand makes a scenario MANUAL, not
  BLOCKED.**
- **One scenario, one triage.** If parts of a `Then` would triage differently
  (a screen change plus an SMS arriving on a handset), split the scenario.
- **`[LIMIT]` means exhausting or locking, not using.** A scenario is `[LIMIT]`
  (MANUAL) when running it **hits a cap or triggers a lockout** — the sixth send
  in an hour, the third wrong code, the eleventh failed validation. A scenario
  that merely **uses one unit** (one SMS send, one wrong attempt) stays
  automatable; PRECONDITIONS states the **run budget** instead, e.g. "one OTP
  send per run; reuse the active code across the OTP-screen scenarios; at most
  5 runs per hour per number".
