# PROJECT.md — test-case context for <project>

The project-specific half of the QC-TCs method used by the **ennam-qaqc**
plugin. The plugin's `qc-tcs` skill is the same for every project; this file is
what makes it fit *this* one. Keep the section headings and numbers — the skill
refers to them. A section you leave out falls back to the plugin defaults
(`docs/CONTEXT_RESOLUTION.md` §5 in the plugin).

---

## 1. Project identity
Project / product under test / platform (mobile, web, both) / repo type.

## 2. Automation framework
Which tool (Playwright, Cypress, Maestro, Appium, none/manual)? Where does
automation code live? Does authoring test cases write any of it? Which skill or
doc owns running them, and which wins on conflict?

## 3. Where test cases live, and in what format
Path pattern · areas/folders · skeleton file · where the case id goes and its
format · scenario naming convention · parameterised-scenario syntax · whether
shared setup blocks (`Background:`) are used · how a new file is placed and
named · how steps are written (Given / When / Then style, copy quoting,
seeding sentences, fixtures).

## 4. Source of truth
App-truth or spec-truth? (SKILL.md §1 A or B.) Where do specs live and how are
they fetched? Where does a divergence get recorded?

## 5. Authoring rule
May the author launch the product while writing? If not, say so explicitly and
say what to mark in the header instead (e.g. a COPY SOURCE note, SPEC-DIFFS
"None recorded").

## 6. Tag vocabulary
Map each SKILL.md Kind to this project's tag, per slot (direction, check type,
gates, platform, area, screen) and the tag order. Area tag per folder. State
whether a priority scheme exists — if none, say "none, do not introduce one".
Name the header triage block (`AUTOMATION CONVERTIBILITY`,
`MAESTRO CONVERTIBILITY`, …).

`/ennam-qaqc:init` copies the vocabulary into `.claude/qaqc.json` → `tagRules`
so the validator enforces it. Give it as lists the mapping is unambiguous from:

| Slot | `tagRules` key | Example |
|---|---|---|
| Direction (exactly 1) | `direction` | `@positive`, `@negative` |
| Check type (exactly 1) | `checkType` | `@logic`, `@navigation`, `@ui`, `@a11y` |
| Gates (0+) | `gates` | `@not-implemented`, `@blocked`, `@manual`, `@pending-oq` |
| Platform (0–1) | `platform` | `@ios-only`, `@android-only` |
| Area (exactly 1, then one screen tag) | `area` | one per folder |
| Title prefix per direction | `titlePrefix` | `@positive` → `Positive - ` |

**Triage** follows the plugin's definition (CONTEXT_RESOLUTION.md §8):
AUTOMATABLE = the framework can drive and assert the scenario's own result on
today's build; MANUAL = a tester can run it alone today; BLOCKED = someone
outside QA must change something first. Say which gate tag means MANUAL and
which means BLOCKED here; refine the definition, never contradict it.

**Settled edge cases** — tagging calls already decided for this project, one
line each (e.g. "Airplane mode is not a gate — the framework drives it";
"Data that already exists in dev is a TEST DATA fixture, not `@blocked`").
The agent applies these before its own judgment.

## 7. Error-handling scope
Can the interface surface HTTP errors? Can the framework intercept/stub routes?
If yes, status-code scenarios are in scope; if no, they are backend items.

## 8. Exit paths to assert separately
Mobile: system Back, in-app back, ✕, CTAs.
Web: browser Back/Forward, in-page back, ✕, CTAs, direct URL entry / refresh.
List any known divergence between them.

## 9. Environment & preconditions
Runnable environments · app/site identifier and how to confirm it · auth state
and whether sign-in can be automated · which scenarios mutate real data.

**Build-level automation blockers** — anything that stops automation for a
whole flow on the current build (e.g. "no DEV OTP hint: a valid OTP cannot be
read"). Name the **exact step** it blocks ("entering a valid code", not "the
OTP flow") and whether a tester can do that step by hand — then the affected
scenarios are MANUAL, not BLOCKED.

**Run limits** — rate limits, real messages (SMS, email, push), payments,
lockouts or quotas that a repeated automated run would use up. Say whether
dev resets them; if not, scenarios that hit them are not counted as
automatable now.

## 10. Where knowledge and queued work go
Memory system, ticket tracker, or backlog path. How to record missing
automation.

## 11. Project-specific traps
Past incidents worth warning the next author about. Keep each to 1–3 lines.

## 12. Reference files
Best worked example · good parameterised example · conventions doc · skeleton.

## 13. Import / format constraints
The test-case tool these files are imported into, and the grammar its importer
accepts. **These rules beat every other convention, including older files.**
Number each rule and say whether a violation refuses the whole file or rejects
one scenario. Answer at least:
- Tags allowed on the `Feature:` line? A description under `Feature:`?
- `Background:` / `Rule:` allowed?
- Must every scenario have Given + When + Then?
- Comment placement (full-line only?)
- Maximum scenario-title length; maximum tag length
- `Scenario Outline` / `Examples` constraints
- What the importer does not carry over (header comments, Feature name,
  priority, status…) — so what must be inside the steps
No importer → write "None — files are not imported".

`/ennam-qaqc:init` copies the rules a script can check into
`.claude/qaqc.json` → `importRules`, and `validate_feature.py` then enforces
them after every write. State them so the mapping is unambiguous:

| Rule | `importRules` key |
|---|---|
| Tags allowed on the `Feature:` line? | `featureTags` (true / false) |
| Description allowed under `Feature:`? | `featureDescription` (true / false) |
| `Background:` allowed? | `background` (true / false) |
| `Rule:` allowed? | `rule` (true / false) |
| Maximum scenario-title length | `maxTitleLength` (number) |
| Maximum tag length | `maxTagLength` (number) |

Edit the rules **here**, then re-run `/ennam-qaqc:init` to refresh the copy.

---

## Provenance
Filled by `/ennam-qaqc:init` when it drafts this file: one row per rule.

| Section | Rule | Source (file:line, "user answer", or "plugin default") |
|---|---|---|
