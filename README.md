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
| `/ennam-qaqc:write-tc` | Write (or update / preview) one `.feature` file from any material; `--prior <file>` adds an earlier version to learn from | `/ennam-qaqc:write-tc @docs/DR-003-005-01-search-form.md` |
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

`.claude/qaqc.json` is written by `init`: three paths, plus machine-readable
copies of the importer's rules (context file §13) and the tag vocabulary (§6)
for the validator:

```json
{
  "projectContext": ".claude/skills/PROJECT.md",
  "template": "test-cases/TEMPLATE.feature",
  "testCasesRoot": "test-cases/",
  "importRules": { "featureTags": false, "featureDescription": false, "background": false,
                   "rule": false, "maxTitleLength": 200, "maxTagLength": 100 },
  "tagRules": { "direction": ["@positive", "@negative"],
                "checkType": ["@logic", "@navigation", "@ui", "@a11y"],
                "gates": ["@not-implemented", "@blocked", "@manual", "@pending-oq"],
                "platform": ["@ios-only", "@android-only"],
                "area": ["@authentication", "@account", "@explore"],
                "titlePrefix": { "@positive": "Positive - ", "@negative": "Negative - " } }
}
```

Change rules in the context file, then re-run `/ennam-qaqc:init` → "refresh
rules". Upgrading from an older version? Run that once — older pointers lack
`importRules` (before 0.2.0), `tagRules` (before 0.3.0) or `tagRules.triage`
(before 0.4.0), and those rules are not machine-checked until you do.

**Earlier versions of a feature file** are read before anything is written — the
working copy (uncommitted edits included), its git history, any file you pass
with `--prior <file>`, and the project's knowledge store (e.g. the Serena
backlog). Findings recorded only in a teammate's local copy are invisible until
they are pushed and pulled here or passed with `--prior` — so **file every
SPEC-DIFF in the knowledge store** (the report lists the ones to file), and every
later run will find it. Area and screen tags are taken from the last
**committed** version, never from an unreviewed draft.

**Triage** follows one definition: AUTOMATABLE = the framework can drive and
assert the scenario's own result on today's build; MANUAL = a tester can run it
alone today; BLOCKED = someone outside QA must change something first
(`docs/CONTEXT_RESOLUTION.md` §8).

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
`.feature` file. It checks:

- **Gherkin validity and the universal QC-TCs rules** (G1–G14) —
  Given/When/Then in every scenario, full-line comments, tag lines hold only
  tags, every `Examples` column used, …
- **Your project's import rules** (P1–P6) from `.claude/qaqc.json` → tags or a
  description under `Feature:`, `Background:`, `Rule:`, title and tag length.
- **Your project's tag rules** (P7–P10) → one direction and one check-type tag,
  slot order, one area then one screen tag, title prefix matching the direction.
- **The template's `IMPORT RULES` comment** copied verbatim (P11).
- **The header's triage totals** — `# Triage: A automatable / M manual / B blocked (N scenarios)`
  must match the tags (P12; a missing line is a warning). Header comments only:
  the importer never reads them, so the importable Gherkin is unchanged.
- **Two warnings** — duplicate scenario titles (G15), and steps a tester cannot
  observe in the product, such as server-side inspection or delivery logs (G16).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py path/to/file.feature
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py --config other/qaqc.json path/to/file.feature
```

Rules a script cannot judge (observability, duplicate partitions, ownership,
triage, carried-forward findings) are checked by the agent and by
`/ennam-qaqc:review-tc`.

## Installation

The repository is public, so no GitHub credentials are needed to install or
update. After installing, run `/ennam-qaqc:init` once per project.

### Claude desktop app (Code tab)

The `/plugin` slash commands are terminal-only and do not work in the desktop
app. Register the marketplace in a settings file instead:

**For a whole project (recommended for teams)** — commit this to the project's
`.claude/settings.json`. Everyone who opens a session in that project gets the
plugin (they may be asked to trust it the first time):

```json
{
  "extraKnownMarketplaces": {
    "ennam-qaqc": { "source": { "source": "github", "repo": "En-Nam/ennam-qaqc" } }
  },
  "enabledPlugins": { "ennam-qaqc@ennam-qaqc": true }
}
```

**For yourself, in every project** — put the same JSON in
`~/.claude/settings.json`.

Start a new session afterwards. Check it loaded by typing `/ennam-qaqc` — you
should see `init`, `write-tc` and `review-tc`.

To turn the plugin on or off later: **+** next to the prompt → **Plugins** →
**Manage plugins**. (**Add plugin** there only lists marketplaces that are
already registered, so the settings file above comes first.)

### Claude Code in a terminal

```
/plugin marketplace add En-Nam/ennam-qaqc
/plugin install ennam-qaqc@ennam-qaqc
```

or, outside a session: `claude plugin marketplace add En-Nam/ennam-qaqc` then
`claude plugin install ennam-qaqc@ennam-qaqc`.

### Updating

From a terminal: `claude plugin update ennam-qaqc@ennam-qaqc`, or inside a
session `/plugin marketplace update ennam-qaqc`. In the desktop app, if no
update option appears under **Manage plugins**, uninstall the plugin there and
start a new session — the settings file reinstalls the latest version.

### Local development

Point a test project's `.claude/settings.json` at your checkout:

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
