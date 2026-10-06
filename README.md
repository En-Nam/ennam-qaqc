# ennam-qaqc — QA Test-Case Plugin for Claude Code

Writes **import-ready Gherkin `.feature` test-case files** from whatever you give
it — a short brief, a Detail Requirement, any reference file — following your
project's template, its context file, and the QC-TCs authoring method
(decomposition → 19-dimension coverage → traceability → gap review).

It **only writes test cases**. It never runs tests, writes automation or app
code, or launches/inspects an app, device or browser.

## Commands

| Command | What it does | Example |
|---|---|---|
| `/ennam-qaqc:init` | Point the plugin at your project context file, or scan the repo and draft one (shown for approval first) | `/ennam-qaqc:init .claude/skills/PROJECT.md` |
| `/ennam-qaqc:write-tc` | Write (or update / preview) one `.feature` file from any material | `/ennam-qaqc:write-tc @docs/DR-003-005-01-search-form.md` |
| `/ennam-qaqc:review-tc` | Review an existing `.feature`: validator, import rules, coverage vs. source, checklist; offers fixes | `/ennam-qaqc:review-tc "test-cases/Explore & Discovery/search-form.feature"` |

The `qc-tcs` skill also loads on its own when you ask for test cases in plain words.

## How it adapts to each project

Everything project-specific lives in a **context file** — usually `PROJECT.md`,
but any file with the same kind of content works, and none is required. It holds
the tag vocabulary, paths, case-id format, source of truth, import rules and
known traps. Blank template: `templates/PROJECT.md`.

The plugin finds it in this order: a path you give → `.claude/qaqc.json` → known
spots → it asks you (point to a file / draft one / continue on defaults). Full
procedure and defaults: `docs/CONTEXT_RESOLUTION.md`.

`.claude/qaqc.json` is written by `init` and holds **paths only**:

```json
{ "projectContext": ".claude/skills/PROJECT.md", "template": "test-cases/TEMPLATE.feature", "testCasesRoot": "test-cases/" }
```

**Template:** the one `qaqc.json` names → the one the context file names →
`<root>/TEMPLATE.feature` → the plugin default (`templates/TEMPLATE.feature`).

## When it stops to ask

Only at these points: no context file found · nothing to write from · target
file or case id can't be derived · the target file already exists (update / new /
preview) · the material mentions a design but has no link (you can skip).
Everything else is decided in writing: unclear behaviour becomes
`[ASSUMPTION]` / `OQ-xx` and is listed in the report.

## Validator

`scripts/validate_feature.py` runs automatically after every write to a
`.feature` file and checks Gherkin validity plus the universal QC-TCs rules
(Given/When/Then in every scenario, full-line comments, tag lines hold only tags,
every `Examples` column used, …). Project-specific import rules (title length,
`Background:` allowed, tags on `Feature:`) are checked by the agent from your
context file.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py path/to/file.feature
```

## Installation

The repository is private to the `En-Nam` organisation: you need read access,
and git on your machine must be able to clone it (SSH key or HTTPS credentials).

```
/plugin marketplace add En-Nam/ennam-qaqc
/plugin install ennam-qaqc@ennam-qaqc
```

Enable it for everyone working in a project — commit this to the project's
`.claude/settings.json`; teammates get it on their next session:

```json
{
  "extraKnownMarketplaces": {
    "ennam-qaqc": { "source": { "source": "github", "repo": "En-Nam/ennam-qaqc" } }
  },
  "enabledPlugins": { "ennam-qaqc@ennam-qaqc": true }
}
```

Update to a newer version: `/plugin marketplace update ennam-qaqc`.

Then, once per project: `/ennam-qaqc:init`.

Local development — point a test project at your checkout instead:

```json
{
  "extraKnownMarketplaces": {
    "ennam-qaqc": { "source": { "source": "directory", "path": "/path/to/ennam-qaqc" } }
  },
  "enabledPlugins": { "ennam-qaqc@ennam-qaqc": true }
}
```

## Requirements

- Claude Code with plugin support
- Python 3.7+ (validator and hook)

## Development

```bash
python3 -m unittest discover -s tests -v
```
