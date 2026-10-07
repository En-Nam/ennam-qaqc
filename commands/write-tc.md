---
description: Write a Gherkin .feature test-case file from any material — a brief, a DR, a reference file — following the project's template and the QC-TCs method
argument-hint: <what to cover — text, @file, DR id, URL> [--context path] [--out path]
allowed-tools: Agent, SendMessage, Read, Glob, Grep, AskUserQuestion, WebFetch, Bash(python3:*)
---

# Write test cases — orchestrator

**Request:** $ARGUMENTS

You resolve facts and run the gates; `tc-agent` does the authoring.

## Orchestrator rules

1. **Context only.** Give the agent facts (paths, ids, decisions, material) —
   never behaviour instructions or question lists.
2. **Gates are the only pauses** (Steps 1, 2, 3, 4, 5). Ask nothing else.
3. **Never answer a gate for the user.** Silence, or an answer from another
   session, is not an answer.
4. **Relay verbatim.** Copy the agent's Final Report unchanged.
5. **No product.** Never launch, inspect or check the app, a device or a
   browser — not even to see whether the feature is built.

## Step 1 — Resolve context (gate)

Follow `${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` §2–§4. `--context <path>`
counts as "given by the user". If §2 step 4 fires, ask and wait:
option 1 → use the path; option 2 → tell the user to run `/ennam-qaqc:init`, then
stop; option 3 → `Context file: none (plugin defaults)`.

Import rules: if `.claude/qaqc.json` has an `importRules` object →
`Import rules: machine-checked by the validator (<its keys>)`. Otherwise →
`Import rules: not machine-checked — check them yourself`, and remember to add
one line to the relay in Step 8: "Tip: run `/ennam-qaqc:init` → refresh import
rules, so the validator enforces them." (No question — this is not a gate.)

## Step 2 — Collect the material (gate)

- `@file` / paths → read them
- a DR or story id → find the file (`**/*<id>*`, or grep `detail_id: <id>`); if
  the context file names a spec source (an MCP server, a docs folder), use it
- URLs → WebFetch
- text in the request → that text is material

Nothing usable (empty request, unreadable file) → ask what to write test cases
for, and wait.

## Step 3 — Design reference (gate, optional)

Look for design links (figma.com, or the design source the context file names)
in the material. If the material mentions a design, screens, frames or Figma but
no link is found, ask once:

> The material mentions a design but I found no link. Paste the design link(s),
> or reply "skip" (the header gets `<TODO>`).

Skip → `Design: <TODO> (user skipped)`. Nothing mentioned → `Design: none mentioned`.

## Step 4 — Target file and case id (gate)

From the context file's placement rule (PROJECT.md §3) or the defaults
(CONTEXT_RESOLUTION.md §5): area folder, file name, case id, area tag, screen
tag. `--out` wins for the path. The case id comes from the material (DR
`detail_id`, story id, …) in the context file's format.

Anything you cannot derive from a named source → ask (AskUserQuestion, derived
candidates as options). A case id nobody can give → `<TODO>`.

## Step 5 — Existing file (gate)

If the target path exists, or another `.feature` under the root carries the same
case id on its `# Feature:` line (`grep -rl "(<id>)" <root>`), ask:

> `<path>` already covers this.
> 1. Update it in place
> 2. Create a new file (I'll propose a name)
> 3. Preview what would be added/changed, then decide

→ Mode `update` / `create` (new path) / `preview`. No existing file → `create`.

Whatever the choice, the existing file is the **Prior file**
(CONTEXT_RESOLUTION.md §7) — its observations from the product are carried
forward even into a new file. No existing file → `Prior file: none`.

## Step 6 — Dispatch

Pick the closest sibling (CONTEXT_RESOLUTION.md §6). Call `Agent` with
`subagent_type: "ennam-qaqc:tc-agent"` and exactly this prompt:

```
Write test cases.

## Context
- Mode: <create | update | preview>
- Target file: <path>
- Case id: <id | <TODO>>
- Area folder: <folder>
- Area tag: <tag | derive per context file>
- Screen tag: <tag | derive per context file>
- Context file: <path | none (plugin defaults)>
- Template: <path> (<why — CONTEXT_RESOLUTION.md §3 step n>)
- Test-cases root: <path>
- Closest sibling: <path | none>
- Prior file: <path | none>
- Design: <links | <TODO> (user skipped) | none mentioned>
- Import rules: <machine-checked by the validator (<keys>) | not machine-checked — check them yourself>
- Validator: python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py
- Today: <YYYY-MM-DD>

## Material
<one subsection per source: "### <label> — <path | URL | user message>",
then "Read from <path>" for files, or the full text for pasted/fetched content>

## Files to read first (in parallel)
1. ${CLAUDE_PLUGIN_ROOT}/skills/qc-tcs/SKILL.md
2. ${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md
3. <context file, if any>
4. <template>
5. <closest sibling, if any>
6. <prior file, if any>
7. <each material file>
```

## Step 7 — NEEDS_INPUT loop

If the agent's reply starts with `NEEDS_INPUT`, ask the user that question, then
continue the same agent with `SendMessage` (answer included). If SendMessage is
unavailable, dispatch again with the same prompt plus `## Answers`. Repeat until
a Final Report arrives.

## Step 8 — Relay

Copy the Final Report verbatim. Add one line before it only if something failed,
and the import-rules tip from Step 1 after it when it applies.
