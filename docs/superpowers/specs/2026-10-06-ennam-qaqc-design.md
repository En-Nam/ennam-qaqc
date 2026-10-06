# ennam-qaqc — Design

**Date:** 2026-10-06 · **Status:** agreed in discussion, ready to plan
**Built-pattern reference:** `ennam-ba` (commands orchestrate, agents do the work, scripts enforce what prose can't)
**Method reference:** QC-TCs (`SKILL.md`, `PROJECT.md`, `TEMPLATE.feature`, `test-cases/README.md`, CLAUDE.md "Profile: qa")

## 1. Purpose

A Claude Code plugin that writes **Gherkin `.feature` test-case files** from whatever material the
user gives — chat text, a DR, any reference file — following the project's template and the QC-TCs
authoring method. The files are later imported into a test-case system.

**Authoring only.** The plugin never runs tests, never writes automation or app code, and never
launches or inspects an app, device, emulator or browser.

## 2. Decisions

| # | Decision |
|---|---|
| D1 | Input can be anything: user text, DR files, any reference file, URLs the user gives. |
| D2 | **Dynamic per project.** Project specifics come from a *project context file* (PROJECT.md or any file with the same kind of content). It is **not required** by name or path. |
| D3 | Context resolution: user-given path → `.claude/qaqc.json` → search known spots → **ask the user**. The user may point at another reference, run init, or continue with plugin defaults. |
| D4 | `init` asks for an existing context file (any path). If there is none, it scans the repo and drafts one. It shows the draft with provenance and writes only after the user approves. |
| D5 | `init` writes `.claude/qaqc.json` — a pointer file only (paths, no rules). |
| D6 | Template resolution: `qaqc.json` template → template named by the context file → `<testCasesRoot>/TEMPLATE.feature` → plugin default (`templates/TEMPLATE.feature` = QC-TCs `TEMPLATE.feature`, verbatim). |
| D7 | Output must follow the resolved template's block order and the importer's grammar. The template is the minimum; richer SKILL §4.1 blocks (COPY SOURCE, WHAT THIS FILE COVERS, OPEN QUESTIONS, section banners, full coverage block) are added when the input supports them. |
| D8 | **Import rules are per project.** They live in the project context file (new §13 in the blank PROJECT.md template). Without a context file, the template's own `IMPORT RULES` comment block applies. |
| D9 | The validator script checks **only** Gherkin validity + SKILL.md universal rules. Project-specific rules (import limits, tag vocabulary, tag order, triage block) are checked by the agent from the context file. |
| D10 | Free text with no AC numbering is decomposed into numbered `BR-xx` rules (SKILL §2), cited in traceability comments and the coverage block. No new header block. |
| D11 | When the target file already exists, **ask**: update in place / create a new file / preview the additions. |
| D12 | Design (Figma) links are optional. If the input mentions a design but no link is found, ask once; the user may skip (`<TODO>`). |
| D13 | No example project files ship in the plugin. The agent learns house style from the project's own closest sibling `.feature` file. |
| D14 | Pauses are explicit gates only (no context found, target/case id unknown, file exists, design link missing). Everything else: state the method, then write without waiting; ambiguity → `[ASSUMPTION]` / `[INFERRED]` / `OQ-xx`. |
| D15 | Large files are written in chunks: header → body section by section → coverage block. |

## 3. Components

| Component | Responsibility |
|---|---|
| `skills/qc-tcs/SKILL.md` | The QC-TCs method, minimally adapted: "PROJECT.md" means the resolved context file; hardcoded C4K import references point to the context file / template. |
| `docs/CONTEXT_RESOLUTION.md` | One shared procedure: find context file, template, test-cases root; defaults when running without context. |
| `templates/TEMPLATE.feature` | Plugin default skeleton — QC-TCs `TEMPLATE.feature`, verbatim. |
| `templates/PROJECT.md` | Blank context-file template (12 QC-TCs questions + §13 import rules). |
| `templates/qaqc.example.json` | Pointer-file example. |
| `scripts/validate_feature.py` | Gherkin + universal-rule linter; CLI and PostToolUse hook mode. |
| `hooks/hooks.json` | Run the validator after Write/Edit/MultiEdit on `*.feature`. |
| `commands/init.md` | Locate or draft the context file; write `qaqc.json`. |
| `commands/write-tc.md` | Orchestrator: resolve context, collect input, run the gates, dispatch the agent, relay its report. |
| `agents/tc-agent.md` | Authoring agent: decompose → design coverage → write → validate → gap review → report. No user touchpoints; returns `NEEDS_INPUT` if blocked. |
| `commands/review-tc.md` | Review an existing `.feature`: validator + project rules + gap review + §11 checklist. |

## 4. Out of scope (v1)

Running tests, reporting results, escalation, automation authoring, a knowledge base, shipping
example projects, machine-readable project rules for the validator.
