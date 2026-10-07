---
name: qc-tcs
description: Portable reference for authoring test cases - requirement decomposition, a 19-dimension coverage model, traceability, gap review and a pre-commit checklist. Project-agnostic - works for any app (mobile or web) and any automation framework (Maestro, Playwright, Cypress, Appium). Reads its project-specific vocabulary from the project context file (PROJECT.md or equivalent, found via the ennam-qaqc context-resolution procedure). Use when writing or reviewing a test case or .feature file, deciding what scenarios a screen needs, or judging whether a scenario is automatable.
---

# QC-TCs — writing test cases

The **authoring reference**: how to design and write test cases that cover a
feature, are traceable to requirements, and are honest about what can be
automated.

> **This file is project-agnostic and ships unchanged in the ennam-qaqc plugin.**
> It contains no tag names, no folder paths, no framework assumptions.
> Everything project-specific lives in the project's **context file**.

## How this skill is used

1. **`PROJECT.md` in this file means the project context file** — a
   `PROJECT.md`, or any file with the same kind of content, found by
   `${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` (user-given path →
   `.claude/qaqc.json` → known spots → ask the user). Its blank template is
   `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md`.
2. **Read it first, every time**, then follow the method below. Wherever this
   file says *"per PROJECT.md"*, that's the hook.
3. To write a file, prefer `/ennam-qaqc:write-tc`; to check one,
   `/ennam-qaqc:review-tc`. If this skill is invoked directly, run
   CONTEXT_RESOLUTION.md before anything else.

If no context file is found, **ask the user** — point to a file, draft one with
`/ennam-qaqc:init`, or continue on the plugin defaults
(CONTEXT_RESOLUTION.md §5). Never invent conventions the project does not use.
If the project keeps durable knowledge in a memory or ticketing system, the
context file should say so and point at it; recurring facts belong there, not
hardcoded here.

**Spec only.** Authoring a test case writes *no* automation code and *no* app
code, unless `PROJECT.md` explicitly says otherwise.

---

## 0. The golden rule

```
Requirement understanding → decomposition → business-rule extraction →
risk analysis → coverage design → test cases → traceability → gap review
```

**Not** `requirement → generate steps`.

The objective is not many test cases. It is **traceable, meaningful, risk-aware,
automation-ready cases with measurable coverage**. Optimise in this order:

> Correctness > Coverage > Traceability > Maintainability > Automation readiness > Number of TCs

When given a spec, screenshots, ACs, or an SME explanation: **analyse first, do
not immediately generate test steps.** Order: §1 source of truth → §2 decompose
→ §3 design coverage → §4 write → §5–§7 divergences, tags, traceability → §10
gap review → §11 checklist. §8 is that loop as a numbered procedure — if you
read one section, read §8.

---

## 1. Source-of-truth priority

**`PROJECT.md` declares the order.** Two common ones:

**A — App-truth (the built product ships ahead of its specs).** Assertions
describe what the app actually does; divergence from the spec is recorded as a
numbered SPEC-DIFF (§5) and a scenario matching one is a **PASS**, never a fail.
The test case documents reality; the bug tracker documents the complaint.

**B — Spec-truth (the specification is contractual).** Assertions describe what
the spec requires; divergence is a **defect** and the test is expected to fail
until the app complies.

Getting this backwards inverts every failure triage in the project, so it is the
first question `PROJECT.md` answers. Within either order, the fallback chain is:

| Priority | Source | Marker |
|---|---|---|
| 1 | Whichever of app / spec `PROJECT.md` names primary | (default) |
| 2 | The other of the two | cite `AC-xx` / `Rule-xx` |
| 3 | SME clarification — BA, PO, dev, QA lead | `Source: <name> Q&A <date>` |
| 4 | Inference — nothing above defines it | `[INFERRED]` + confirm with PO |

**Authoring vs verifying.** When *writing* test cases you normally work from
documents, not a running app — see §8 step 3 and §9. The priority above governs
how a *result* is judged, not whether you must boot the product to write.

An unresolved spec question is never an excuse to invent behaviour. Tag it (per
`PROJECT.md`), assert only what is settled, and name the open question.

---

## 2. Decompose before you write

Extract:

- **Main function** — what the feature exists to accomplish.
- **Inputs** — required/optional, type, allowed & invalid values, boundaries,
  empty/whitespace, max length, special characters, paste vs typing.
- **Preconditions** — auth state, role, feature flag, config, existing data,
  prior actions, environment.
- **Business rules** — each stated explicitly and independently testable.
- **State transitions** — `initial → action → processing → expected state`,
  including transitions that must be *prohibited*.
- **System responses** — UI, validation message, navigation, control state,
  loading/error/success states, persistence.

Converting an SME explanation: turn prose into a numbered rule first, *then*
write scenarios from the rule. "If the centre doesn't support tours, the CTA
falls back to Start Enquiry" becomes `BR-001` with two branches → two scenarios.

**Ambiguity is never silently resolved.** State the interpretations and ask:

```
Ambiguity: behaviour undefined when X occurs.
  A. ...   B. ...
Recommended clarification: should the system behave as A or B?
```

If you must assume to keep drafting, mark it `[ASSUMPTION]` inline.

---

## 3. Coverage model — what scenarios a view needs

Walk every dimension for **every view** (screen / page / route) in scope.
Anything skipped is skipped on purpose and said so in the header — never
silently.

The **Kind** column is the portable classification; map each Kind to your
project's tag names in `PROJECT.md`.

| # | Dimension | Kind | Typically automatable |
|---|---|---|---|
| 1 | **Happy path** — valid precondition + valid input + valid action | positive / logic | ✅ |
| 2 | **Visual/design conformance** — one per view, and one per separately designed state (each design frame: default, filled, empty, error…) | visual | ❌ manual |
| 3 | **Entry navigation** — how the user arrives | navigation | ✅ |
| 4 | **Exit navigation** — every documented way out (see below) | navigation | ✅ |
| 5 | **Required/optional fields** — empty, whitespace-only, valid | negative / logic | ✅ |
| 6 | **Format validation** — one scenario per rule | negative / logic | ✅ |
| 7 | **Boundary values** — see §3.1 | negative / logic | ✅ |
| 8 | **Gate/enablement** — when the primary action is enabled vs disabled | positive + negative | ✅ |
| 9 | **Pre-fill / default state**, incl. the untouched "not dirty" case | positive / logic | ✅ |
| 10 | **Empty state** — zero items | positive / logic | ✅ |
| 11 | **Transient states** — loading, submitting, disabled-while-sending | positive / logic | ✅ usually |
| 12 | **Destructive-action guard** — confirm dialog, cancel restores | negative / logic | ✅ |
| 13 | **State transitions** — valid ones, and prohibited ones | logic | ✅ |
| 14 | **Persistence** — survives reload, navigate-away-and-back, re-login | positive / logic | ✅ |
| 15 | **Role / permission** — authorised, unauthorised, unauthenticated | negative / logic | ✅ / ⛔ |
| 16 | **Error handling** — the errors this feature can actually surface | negative / logic | depends — §3.2 |
| 17 | **Accessibility** — labels, focus order, target size, contrast | a11y | ❌ manual |
| 18 | **Backend-only outcomes** — delivery, emails, third-party records | backend | ⛔ blocked |
| 19 | **Out-of-scope destinations** owned by another spec | blocked | ⛔ blocked |

### Platform note — dimension 4 (exit navigation)

Enumerate **every** exit the platform offers, and assert each **separately** —
they are different code paths and routinely diverge:

- **Mobile:** hardware/system Back, on-screen back control, close (✕), each CTA.
- **Web:** browser Back/Forward, in-page back control, close (✕), each CTA, and
  direct URL entry / refresh on a deep route.

Never generalise one exit from another. If `PROJECT.md` records a past bug here,
treat that exit as high-risk.

### Dimensions most often forgotten

- **#9 the not-dirty pre-fill case** — can the user submit without touching
  anything?
- **#4 each exit path separately** (above).
- **#14 persistence** — a value that "saved" but reverts on reopen. Assert the
  reopen/reload, not just the success message.

### 3.1 Boundary and partition discipline

Where a requirement states a limit, test `min-1, min, min+1` and
`max-1, max, max+1` — but only boundaries **reachable through the interface**.
If the field hard-stops at the cap, `max+1` is unenterable and that fact is
itself the assertion.

Group equivalent inputs and test one representative each. Do **not** write three
scenarios for "John", "Mike", "David" — same partition, one scenario. Maximum
meaningful coverage, minimum redundant scenarios.

### 3.2 Don't over-test — and what counts as over-testing depends on the platform

Never generate scenarios to inflate the count. Skip a dimension that genuinely
does not apply rather than manufacturing a case for it.

**Dimension 16 is where this bites, and the answer is platform-specific:**

- If the interface **cannot surface** a condition (a backend delivery, a
  provider-side record, an HTTP status the UI never renders), it is a **backend**
  item — assert the UI outcome, not the invisible state.
- If the interface **can surface** it — a web app rendering a 404/403/500 page,
  a framework that can intercept and stub a response (Playwright `route()`,
  Cypress `intercept()`) — then error scenarios are **legitimate and expected**.

`PROJECT.md` states which applies. Writing status-code scenarios for a UI that
cannot show them is over-testing; omitting them for a web app that can is a
coverage gap.

---

## 4. File anatomy

`PROJECT.md` gives the **location, file format, and naming**. Before writing,
**read the closest existing sibling** and match its layout and phrasing —
conformance to the project beats personal taste.

Two parts: a **header block** (metadata, in whatever comment syntax the format
uses) and the **body** (the scenarios).

### 4.1 Header block, field by field

| Field | Required | Notes |
|---|---|---|
| Feature name + **case id** | ✅ | Id format per `PROJECT.md`. |
| `Source` | ✅ | Spec title + version + author + date. Say `DRAFT` if it is. |
| Design reference | ✅ | Link/frame for visual scenarios, or `<TODO>`. |
| `Implementation` | ○ | Source files, if the repo has them. |
| `WHAT THIS FILE COVERS` | ○ | For multi-view flows: what is in scope **and what is not**, naming the file that owns it. |
| `Tag legend` | ✅ | Every tag used in the file. |
| `SPEC-DIFFS` | ✅ when any exist | Numbered. See §5. |
| `OPEN QUESTIONS` | ✅ when any exist | `OQ-xx`, what is undecided, who owns it. |
| `PRECONDITIONS` | ✅ | Environment, app/site identifier, auth state, entry point, state reset, data-mutation warnings. |
| `TEST DATA` | ✅ | Table: role → value → notes. Include known selectors/ids. |
| `AUTOMATION CONVERTIBILITY` | ✅ | Authoritative triage: automatable now / backend / not automatable / separate spec. |
| `FEATURE STATUS` | only if unbuilt | Tag accordingly; the file is then a forward-looking plan. |
| `LIVE VERIFICATION <date>` | ○ strongly encouraged | What was verified, where, on which build. This is what makes the file trustworthy later. |

### 4.2 Body

Structure per `PROJECT.md`'s format. **If the project imports its test cases
into a tool, that tool's import grammar is a hard constraint** (`PROJECT.md`
§13, or — without one — the template's `IMPORT RULES` block). It beats every
convenience below and any older sibling file. Universal rules:

- Group scenarios under numbered section banners per view/stage, citing the
  AC/Rule range they cover.
- **Name the behaviour and its outcome**, not the mechanic: *"Prevent submission
  when the required email is empty"* — not *"Test validation"*, *"Check form"*.
- Use a consistent positive/negative prefix, exactly as the project's existing
  files do.
- An `AC-xx / Rule-xx` comment on its own line directly above a scenario is how
  a reader knows a surprising assertion is deliberate rather than a mistake.
  Comments are always full-line. Never put a comment at the end of a step,
  title or tag line: an importer reads it as part of that line.
- Every scenario has at least one `Given`, one `When` and one `Then`. Visual and
  accessibility checks are included; give them an action such as "the screen
  finishes loading".
- **Parameterised scenarios** (Gherkin `Scenario Outline` + `Examples`, or the
  equivalent) for **one behaviour across an equivalence partition** — not as a
  way to merge unrelated behaviours. Every `Examples` column must be used as
  `<column>` in a step. Don't add documentation-only columns; put row notes in
  a comment. Gherkin trims table cells, so a value whose leading or trailing
  spaces matter must carry its quotes inside the cell.
- **Shared setup blocks** (Gherkin `Background`, framework `beforeEach`): use
  only if `PROJECT.md` says the project uses them. Where scenarios are run
  individually by tag, each must stand alone — repeat the setup instead.

### 4.3 One scenario = one behaviour

Each scenario proves exactly one thing. If the action block chains several
unrelated actions with different expected outcomes, split it. A failing
multi-behaviour scenario cannot tell you which behaviour broke.

Write business-readable steps. Assert what the user perceives — not DOM
structure, CSS selectors, or internal calls — unless the scenario is explicitly
an API/integration check.

---

## 5. SPEC-DIFFs — recording divergence

Used when `PROJECT.md` declares **app-truth** (§1 order A). Each entry states
three things:

```
2. CHARACTER CAPS ARE SOFT-VALIDATION, NOT TRUNCATION. AC-24 says the name field
   is "max 100", implying it stops accepting at the cap. The app instead ACCEPTS
   over-length input and BLOCKS submission with an inline error — "Keep this
   under 100 characters" + the action disabled. (Verified live 2026-09-18.)
```

1. **What the spec says** (with AC/Rule number)
2. **What the app actually does** (verbatim copy)
3. **Evidence** — verified live, when, or explicitly "not yet driven"

A SPEC-DIFF is **not** a bug report. If the behaviour is wrong, record the
SPEC-DIFF here **and** raise it wherever the project tracks defects. The test
case keeps describing what the app does, so the suite stays green against
reality.

Under **spec-truth** (order B) there is no SPEC-DIFF section — divergence is a
failing test plus a defect.

---

## 6. Tags and triage

**`PROJECT.md` owns the tag vocabulary.** Map these portable *Kinds* to it:

| Kind | Meaning | Automatable |
|---|---|---|
| positive / negative | expected vs error/edge path | depends on the rest |
| logic | business rule / behaviour | ✅ usually |
| navigation | view transition | ✅ usually |
| visual | design conformance (colour, font, spacing) | ❌ manual |
| a11y | accessibility | ❌ manual |
| manual | needs a human, a real device signal, or multi-account state | ❌ manual |
| open-question | unresolved spec question — assert only what is settled | ✅ partial |
| not-implemented | not built yet; fails until it is | ⛔ |
| blocked / backend | backend-controlled or owned by another spec | ⛔ |
| area / view | routing only | — |

**Tag honestly.** Tagging a manual check as automatable makes a future run either
fake a pass or report a false fail. If unsure whether your framework can assert
it, treat it as **not automatable** until proven otherwise.

Rule of thumb: if an assertion names a colour, pixel value, font, animation
quality, or says "matches the design" → visual, manual.

### 6.1 Choosing a scenario's tags

Think of the tags as **slots**, filled in a fixed order. `PROJECT.md` gives the
concrete tag for each slot, plus project-specific edge cases.

1. **Routing** — area and view. Exactly one each. If the format forbids
   file-level tags, repeat them on every scenario.
2. **Direction** — exactly one of positive / negative, agreeing with the title
   prefix. Negative = the user is stopped, something is hidden, excluded or not
   saved, input is rejected, or an error/empty state shows.
3. **Check type** — exactly one; the first match wins: visual (names a colour,
   font, px or the design) → a11y → navigation (the outcome is a different
   view) → logic.
4. **Gates** — zero or more. Ask in turn:
   not built? → not-implemented ·
   needs **someone else** to change backend data/config? → blocked, with a
   comment saying what is needed ·
   the tester can set it up **alone** but the framework cannot? → manual ·
   the result depends on an open question? → open-question.
5. **Platform** — only if the behaviour exists on one platform.

**Triage follows the tags, first match wins:** blocked/not-implemented →
BLOCKED; visual/a11y/manual → MANUAL; everything else → AUTOMATABLE. The file's
automation-convertibility block must agree with these counts.

Markers such as `[BACKEND]` or `[INFERRED]` are comment text, not tags. Keep
them off tag lines unless `PROJECT.md` says the format allows it.

**Priority:** use a priority scheme **only if `PROJECT.md` defines one**. Do not
introduce `P0`–`P3` into a project that has no such field. Risk reasoning still
belongs in the work regardless: put it in the section banner or a comment, and
let it drive *which §3 dimensions you cover most deeply* — payment, auth, data
loss, permissions and submission paths deserve boundary and negative depth that
a cosmetic toggle does not.

---

## 7. Traceability

Every scenario traces to something, on its own comment line above the scenario.
Never put it at the end of a step or title line (see §4.2):

```
# AC-17 / Rule 8 — callback number seeding.
# Source: BA Q&A 2026-09-16 (D3).        ← SME-derived
# Source: [INFERRED] — confirm with PO.
```

Then a **coverage matrix** at end of file mapping every `AC-xx` and `Rule-xx` to
the section covering it:

```
# AC-17 callback number autofill ......... §5 (autofill + editable)
# Rule 6 delivery over both channels ..... §4 (blocked — backend)
# OUT OF SCOPE (own spec, boundary only): the booking flow (§1)
```

Mandatory when the feature has multiple ACs or business rules. These are
**reference only — never used as tags**. Its job is proving no AC was dropped,
and naming the ones deliberately left out.

---

## 8. Authoring loop

1. **Read `PROJECT.md`**, then the closest existing sibling test case.
2. **Decompose** the spec per §2 — every AC, rule, input, state, role.
3. **Source the copy.** Follow `PROJECT.md`'s authoring rule. Unless it says
   otherwise, author **from the spec/documents** — do not launch the product,
   boot a device, or inspect a live build to decide whether a feature exists.
   Record in the header that the copy is document-sourced and awaits live
   verification. Driving the product belongs to the *run/verify* task, not this
   one.
4. **Design coverage** — walk §3 per view; note which dimensions don't apply.
5. **Write the header block** in the §4.1 order.
6. **Write the scenarios**; one behaviour each.
7. **Write the coverage matrix**; confirm no AC is unmapped.
8. **Run the §10 gap review, then the §11 checklist.**
9. If automation for these scenarios doesn't exist yet, record that where
   `PROJECT.md` says work is queued — do **not** write the automation code.
10. Report, in the reply (not in the file): path + one triage line —
    *N automatable / N manual / N blocked* — then the §10 gap review as
    *Covered / Partially covered / Missing / Needs clarification*, plus any open
    questions and `[ASSUMPTION]`s raised.

---

## 9. Never invent strings

Every quoted title, label, placeholder, error message and element id comes from
a **named source** — never from memory.

**While authoring** (no live product — §8 step 3), the source is the
**spec/design**, quoted verbatim. Mark it in the header as document-sourced and
not yet verified, so a later run knows to confirm it.

**While verifying or running**, the live product outranks the document (under
app-truth):

1. the **running app** — inspector / snapshot / screenshot
2. **source code** — component, schema and string/locale files
3. a **design export** — for visual scenarios only

Where the two disagree, resolve per §1 and record it per §5.

**Capture bugs verbatim.** If the screen reads `"Whats your mobile number?"`
without the apostrophe, the assertion says exactly that, with a note flagging it
as a copy bug. Silently "correcting" copy creates a permanent false failure.

---

## 10. Gap review — before you finalize

Ask, and answer honestly:

- **Requirements** — is every AC, business rule, condition and expected outcome
  covered, or explicitly listed as out of scope?
- **Inputs** — valid, invalid, empty, whitespace, min, max, over-max, pasted?
- **Users** — each relevant role, unauthenticated, insufficient permission?
- **System** — dependency unavailable, duplicate data, timeout? (only where the
  interface can actually surface it — §3.2)
- **States** — every state enumerated; prohibited transitions asserted as
  prohibited?
- **Regression** — what existing behaviour could this change break?

Classify each requirement as **Covered / Partially covered / Missing / Needs
clarification**, and report the last three. Do **not** claim full coverage unless
every applicable AC and rule maps to at least one scenario. A file that misses
one critical business rule is not high quality regardless of how many scenarios
it has — report critical-rule coverage separately from the total.

---

## 11. Pre-commit checklist

- [ ] `PROJECT.md` read; its vocabulary, paths and format followed
- [ ] File meets the project's import rules (`PROJECT.md` §13, or the
      template's `IMPORT RULES` block) and `validate_feature.py` reports 0 FAIL
- [ ] Case id present in the project's required place
- [ ] Sibling read; header order and phrasing match
- [ ] Every quoted string came from a named source, not memory
- [ ] Known copy bugs asserted verbatim with a note
- [ ] Every SPEC-DIFF numbered: spec-says / app-does / evidence
- [ ] Open questions recorded and tagged
- [ ] `[ASSUMPTION]` / `[INFERRED]` marked wherever behaviour was not verified
- [ ] Every view has a visual scenario, marked non-automatable
- [ ] An accessibility scenario exists, marked non-automatable
- [ ] **Every exit path asserted separately** (system Back, in-page back, ✕, CTAs)
- [ ] Not-dirty / untouched pre-fill case covered
- [ ] Persistence asserted by reopening/reloading, not by the success message
- [ ] Boundaries limited to those reachable through the interface
- [ ] No redundant scenarios within one equivalence partition
- [ ] One behaviour per scenario
- [ ] Shared setup blocks used only if `PROJECT.md` allows them
- [ ] No priority scheme unless `PROJECT.md` defines one
- [ ] Every scenario fills the §6.1 tag slots: one direction (agreeing with the
      title prefix), one check type, any gates that apply, area + view, in
      `PROJECT.md`'s order; every blocked gate has a comment saying what is needed
- [ ] `AUTOMATION CONVERTIBILITY` matches the actual tags — no manual check tagged automatable
- [ ] `PRECONDITIONS` names environment, app id, auth state, entry point, state reset
- [ ] Data-writing scenarios warn that they mutate real state
- [ ] Coverage matrix maps every AC/Rule, or names it out of scope
- [ ] No automation code and no app code written
- [ ] Missing automation recorded where the project queues work

---

## 12. Universal traps

Project-specific incidents belong in `PROJECT.md`. These recur everywhere:

- **A green run is not a pass.** A passing automated check can assert the wrong
  element — a non-clickable label stacked above the real control, a stale view
  that never navigated. Assert that the *destination* was reached, not merely
  that an action did not error.
- **Part-way failures mutate state.** Any scenario that creates, renames or
  deletes data must say so in PRECONDITIONS, and say how to reset.
- **Don't over-claim a finding's scope.** "Back navigation is broken" often means
  one specific exit path is broken. Assert only what you actually drove.
- **Fixtures block more than you expect.** Scenarios needing specific account or
  data state are blocked until that fixture exists. Name the fixture in TEST DATA
  so the blocker is actionable.
- **Unverified copy rots.** Strings taken from a spec and never confirmed against
  the product become false assertions. Mark them, and re-verify before trusting
  a red result.

---

## 13. Related

- **`PROJECT.md`** (the context file) — this project's vocabulary, paths,
  format, import rules and traps. Read first.
- `${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` — how the context file,
  template and test-cases root are found, and the defaults.
- `${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py` — Gherkin, universal-rule
  and project import-rule linter (runs automatically after every write to a
  `.feature`; import rules come from `.claude/qaqc.json` → `importRules`).
- The project's run/report workflow and automation-authoring guidance, as named
  in `PROJECT.md`.

---

## 14. Lessons from review (ennam-qaqc 0.2.0)

Findings from comparing plugin output with a hand-written file. They sharpen
§3.2, §6, §9 and §10; they do not replace them.

- **Observable or nothing.** A rule whose only evidence is server-side (storage
  format, generator quality, delivery logs, database rows) gets no scenario.
  Record it in the coverage matrix as `NOT UI-OBSERVABLE — <why>`. `@blocked` is
  for a visible outcome whose **setup** needs someone else.
- **No question-scenarios.** An open question lives in OPEN QUESTIONS. A
  scenario always states an expected result.
- **Observed copy bug ≠ document typo.** §9's "capture bugs verbatim" applies to
  copy **seen in the product**. A typo only in the spec is an open question;
  assert the settled part.
- **Carry observations forward.** An earlier file's SPEC-DIFFs and observed copy
  outrank the document under app-truth — even when a new file replaces it.
- **One partition, one place.** An input covered by an Outline row gets no
  standalone scenario for the same outcome. Three or more scenarios differing
  only in data are one Outline.
- **Boundary for what others own.** Search the suite for files citing the same
  spec ids or screens; assert their behaviour only at the hand-off.
- **Honest automation counts.** A build-level blocker applies to exactly the
  scenarios that pass through the blocked step. A scenario that uses up a
  rate-limited real resource or locks shared state is not "automatable now"
  (`[LIMIT]`). The triage block says which scenarios each reason moves.
- **A sibling shows style, not rules.** Never copy an import-rule break (tags on
  `Feature:`, legacy titles) from an existing file.
- **Findable coverage.** Map each requirement to scenario titles, and put a
  one-line coverage summary in the header.

### 0.3.0 additions

- **One triage definition** (CONTEXT_RESOLUTION.md §8). AUTOMATABLE = the
  framework can drive and assert this scenario's own result on today's build.
  MANUAL = a tester can run it alone today. BLOCKED = someone outside QA must
  change something first. A blocker names its exact step and moves only the
  scenarios that need that step; a blocker a tester can do by hand means MANUAL.
- **Prior knowledge lives in more than one place.** Read the working copy
  (uncommitted edits included), the file's git history, and any earlier version
  a teammate hands over. A prior assertion that disagrees with the document,
  with nothing to settle it, is an open question — not a silent pick.
- **Account for every prior scenario**: kept, merged, reworded or dropped, with
  the reason.
- **Hand off only with evidence** — a named scenario in the owning file. A
  screen inside this spec's scope stays here otherwise.
- **The coverage inventory is everything the spec enumerates**: fields,
  interaction elements and their enabled conditions, display states, UX and
  accessibility items, rate limits — not only ACs and Rules.
- **Tag rules are machine-checked** (`tagRules` in `.claude/qaqc.json`), like
  import rules. A sibling's tag order is not evidence of the vocabulary.

### 0.4.0 additions

- **Totals are counted, not written.** The triage block's first line is
  `# Triage: A automatable / M manual / B blocked (N scenarios)`, and the
  validator checks it against the tags.
- **`[LIMIT]` means hitting a cap or triggering a lockout**, not using one unit.
  State a run budget for single-unit use and apply the test to every scenario.
- **Message templates are documents too.** Where a template's examples disagree
  (singular vs plural), raise an open question and assert the agreed part.
- **Routing tags carry over** from the prior file; a screen tag names a screen.
- **The `IMPORT RULES` comment is copied, not paraphrased** — a reworded one now
  fails validation.

### 0.5.0 additions

- **File findings where every run can see them.** Read the project's knowledge
  store (the context file says where) for SPEC-DIFFs and observations about the
  feature, and list each finding that still needs filing there. A finding that
  lives only in one copy of a `.feature` is lost when that copy is replaced.
- **BLOCKED names who and what.** If a tester can reach the state alone —
  through the app, by waiting, by repeating an action — it is MANUAL.
- **Routing tags come from the last committed version**, never from an
  unreviewed draft; the right tags depend on the project and feature.
- **A disputed string is never quoted** anywhere in the steps.
- **One case id** on the `# Feature:` line; older ids go in `Source:`.

