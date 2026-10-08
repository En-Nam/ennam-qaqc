---
description: Upgrade existing .feature files (e.g. a teammate's, legacy formats) to the plugin's format and rules, in place — mechanical import fixes first, then a full content upgrade per file
argument-hint: [file or folder ...] [--format-only]
allowed-tools: Agent, SendMessage, Read, Glob, Grep, AskUserQuestion, Bash(python3:*), Bash(git rev-parse:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Conform existing test cases

**Request:** $ARGUMENTS

Brings existing `.feature` files up to the plugin's format and rules **in place**,
so every one imports and follows the same conventions as newly written files.
Plugin rules apply to every file, legacy ones included.

## Rules

1. **Git is the undo.** Never edit a file with uncommitted changes; never commit,
   stash or reset anything yourself.
2. **Nothing changes meaning silently.** Phase A only makes changes its safety
   check proves harmless; every Phase B change is listed per scenario.
3. **One confirmation, then run.** Ask once which files to upgrade; after that,
   only the agent's `NEEDS_INPUT` questions pause the run.

## Step 1 — Resolve context (gate)

Follow `${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` §2–§4. Conformance is
defined by the project's rules, so `.claude/qaqc.json` must hold `importRules`
and `tagRules`. If either is missing, stop:

> The project's rules are not machine-readable yet. Run `/ennam-qaqc:init` →
> "refresh rules", then run `/ennam-qaqc:conform` again.

## Step 2 — Collect the files

The paths in the request (files or folders), else every `*.feature` under the
test-cases root. Never include `TEMPLATE.feature`.

## Step 3 — Git gate

`git rev-parse --show-toplevel` must succeed, and
`git status --porcelain -- <files>` must be empty. Otherwise stop and list the
files:

> These files have uncommitted changes (or are not in a git repo). Conform edits
> in place and relies on git to undo, so commit or stash them first:
> <files>

## Step 4 — Inventory and confirm

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py <files>` and show
one table: file · scenarios · FAIL · WARN · legacy `Scenario -` titles. Then ask
once (AskUserQuestion):

> Upgrade these <n> files in place? Each file gets the mechanical import fixes,
> then <a full content upgrade by the agent | nothing else (--format-only)>.

Options: all / choose files / cancel.

## Step 5 — Phase A: mechanical conversion

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/conform_feature.py --write <files>`.
A file it reports as `SKIPPED - safety check failed` is left untouched and
excluded from Phase B; report it. Re-run the validator and keep the counts.

`--format-only` → skip to Step 7.

## Step 6 — Phase B: full upgrade, one agent per file

For each file (up to 3 in parallel):

- **Case id** from its `# Feature:` line; **source spec** found by that id
  (`**/*<id>*`, `grep -rl "detail_id: <id>"`) or through the spec source the
  context file names. None found → `Material: the file itself (no source spec found)`.
- Dispatch `subagent_type: "ennam-qaqc:tc-agent"` with the same prompt as
  `/ennam-qaqc:write-tc` Step 6, using:
  - `Mode: upgrade`
  - `Target file: <path>`
  - `Prior file: git HEAD:<path> (the version before this upgrade)`
  - `Design: <the file's own Figma line, or none mentioned>` — do not ask
  - `## Material`: the source spec (if found), then the target file.
- `NEEDS_INPUT` → ask the user, then continue that agent with `SendMessage`.

## Step 7 — Report

Run the validator on every file again, then `git diff --stat -- <files>`.

```
## Conform — <n> files
| File | Scenarios before → after | FAIL before → after | Triage | Status |
| <path> | 39 → 41 | 223 → 0 | 22 / 19 / 0 | import-ready / needs a decision / skipped |

Undo one file: git restore <path>      Review: git diff -- <path>
Nothing has been committed.
```

Then each agent's Final Report, verbatim, under a heading per file.
