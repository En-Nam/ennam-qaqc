---
description: Upgrade existing .feature files (e.g. a teammate's, legacy formats) to the plugin's format and rules, in place — in bulk, resumable — mechanical import fixes first, then a full content upgrade per file
argument-hint: [file or folder ...] [--format-only] [--batch N] [--again]
allowed-tools: Agent, SendMessage, Read, Glob, Grep, AskUserQuestion, Bash(python3:*), Bash(git rev-parse:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Conform existing test cases

**Request:** $ARGUMENTS

Brings existing `.feature` files up to the plugin's format and rules **in place**,
so every one imports and follows the same conventions as newly written files.
Plugin rules apply to every file, legacy ones included. Built for whole suites:
the run is resumable, reports go to disk, and questions are collected for the end.

`S` below means `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/conform_state.py`; the run
state lives in `.claude/qaqc-conform/` (state + one report per file).

## Rules

1. **Git is the undo.** Never edit a file the state gate blocks; never commit,
   stash or reset anything yourself.
2. **Nothing changes meaning silently.** Phase A only makes changes its safety
   check proves harmless; every Phase B change is listed per scenario.
3. **Record every step.** After every write to a file, `S mark` it — the gate
   relies on the recorded hash to resume safely.
4. **Ask once at the start, once at the end.** Agents never stop the run for a
   question; they collect them (Step 7).

## Step 1 — Resolve context (gate)

Follow `${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` §2–§4. `.claude/qaqc.json`
must hold `importRules` and `tagRules`. If either is missing, stop:

> The project's rules are not machine-readable yet. Run `/ennam-qaqc:init` →
> "refresh rules", then run `/ennam-qaqc:conform` again.

## Step 2 — Collect the files and register them

The paths in the request (files or folders), else every `*.feature` under the
test-cases root. Never `TEMPLATE.feature`. Then `S add <files>` — files already
registered keep their status, so a re-run continues where the last one stopped.
`--again` → `S reset <files>` first (re-upgrade finished files).

## Step 3 — Git gate

`git rev-parse --show-toplevel` must succeed. Then `S gate <files>`:
- `clean` / `resumable` → go on (resumable = conform's own uncommitted edits);
- `BLOCKED` → stop and list those files with the gate's reason. Offer to continue
  with the other files only.

## Step 4 — Inventory, plan and confirm

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py <files>` and
`S summary`. Show one table: file · status · scenarios · FAIL · legacy
`Scenario -` titles. Files already `upgraded` are skipped (say so).

Plan the run:
- **Two-step for big suites.** More than 10 files still needing Phase B and no
  `--format-only` / `--batch` given → recommend: Phase A on everything now, the
  user commits, then Phase B folder by folder.
- **`--batch N`** → Phase B handles at most N files this run; the rest stay
  `formatted` for the next run.

Ask once (AskUserQuestion): run as planned / Phase A only for all files now /
choose files / cancel.

## Step 5 — Phase A: mechanical conversion

For the files whose status is `pending` (or every chosen file — Phase A is
idempotent): `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/conform_feature.py --write <files>`.
Then for each file:
- `written` or `already conformant` → `S mark <file> formatted`
- `SKIPPED - safety check failed` → `S mark <file> skipped --note "<reason>"`; it
  is left untouched and gets no Phase B.

`--format-only` → go to Step 8.

## Step 6 — Phase B: full upgrade, one agent per file

Take the files with `S next --status formatted [--limit N]`. For each (up to 3 in
parallel):

- **Case id** from its `# Feature:` line; **source spec** found by that id
  (`**/*<id>*`, `grep -rl "detail_id: <id>"`) or through the spec source the
  context file names. None found → `Material: the file itself (no source spec found)`.
- Dispatch `subagent_type: "ennam-qaqc:tc-agent"` with the same prompt as
  `/ennam-qaqc:write-tc` Step 6, using:
  - `Mode: upgrade`
  - `Target file: <path>`
  - `Prior file: git HEAD:<path> (the version before this run)`
  - `Design: <the file's own Figma line, or none mentioned>` — never ask
  - `Report file: .claude/qaqc-conform/reports/<path>.md`
  - `Questions: collect`
  - `## Material`: the source spec (if found), then the target file.
- When the agent returns: questions listed → `S mark <file> needs-answers`;
  otherwise `S mark <file> upgraded`. It failed or ran out of turns →
  `S mark <file> failed --note "<why>"` and carry on with the next file.

## Step 7 — Collected questions

Read the `### Questions for the user` section of every report written this run.
If there are any, show them **all at once**, grouped by file and numbered
(`Q1 search-form.feature — …`), each with the choice the agent made meanwhile.
The user answers in one reply (unanswered = keep the agent's choice). For each
file with answers, dispatch the agent again (`Mode: upgrade`, same context,
plus `## Answers`), then `S mark <file> upgraded`.

## Step 8 — Report

Run the validator on the run's files, `S summary`, and `git diff --stat -- <files>`.
Show only the summary — the full per-file reports stay on disk:

```
## Conform — <n> files this run
| File | Status | Scenarios before → after | FAIL before → after | Triage | Report |
| <path> | upgraded | 39 → 41 | 223 → 0 | 22 / 19 / 0 | .claude/qaqc-conform/reports/<path>.md |

Still to do: <n> formatted (run /ennam-qaqc:conform again to continue) · <n> skipped · <n> failed
Review: git diff -- <path>     Undo one file: git restore <path>     Nothing has been committed.
```

After the user commits, the gate sees those files as `clean` and their status
stays `upgraded`, so later runs skip them. `.claude/qaqc-conform/` can be
committed as an audit trail or added to `.gitignore`.
