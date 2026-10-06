# ennam-qaqc Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin that writes import-ready Gherkin `.feature` test-case files from any material (brief, DR, reference file), following each project's template and context file and the QC-TCs authoring method.

**Architecture:** Same shape as `ennam-ba`: slash commands orchestrate (resolve context, run the gates, ask the user), one agent does the authoring, and a Python script enforces what prose cannot. One shared procedure (`docs/CONTEXT_RESOLUTION.md`) finds the project context file, the template and the test-cases root; everything project-specific comes from there. The QC-TCs `SKILL.md` ships as the plugin skill, adapted only where it hardcodes C4K.

**Tech Stack:** Claude Code plugin (markdown commands/agents/skills, `hooks.json`), Python 3.9 standard library (`unittest`, no third-party packages).

**Spec:** `docs/superpowers/specs/2026-10-06-ennam-qaqc-design.md`

**Source material (read-only, never modified):** `/Users/kai/Downloads/QC-TCs/` — `.claude/skills/SKILL.md`, `.claude/skills/PROJECT.md`, `test-cases/TEMPLATE.feature`, `test-cases/README.md`, `CLAUDE.md`, `test-cases/Explore & Discovery/search-form.feature`, `DR-003-005-01-search-form.md`.

## Global Constraints

- Plugin root: `/Users/kai/Develop/ennam-qaqc`. Plugin name `ennam-qaqc`, version `0.1.0`, author `Kai`.
- Python: must run on **Python 3.9.6** (installed). Standard library only. No `match`, no `X | Y` type unions.
- Every path inside a command/agent/skill that points into the plugin uses `${CLAUDE_PLUGIN_ROOT}`.
- The plugin never runs tests, never writes automation or app code, never launches or inspects an app/device/emulator/browser.
- Output `.feature` files follow the **resolved template** (default: QC-TCs `TEMPLATE.feature`, copied verbatim) and the project's import rules.
- **Import rules are per project** (context file §13, else the template's `IMPORT RULES` block). The validator checks only Gherkin validity + SKILL.md universal rules.
- The context file is **optional** and never required by name or path. `.claude/qaqc.json` holds **paths only** and is written only by `/ennam-qaqc:init`.
- **No example project files ship** in the plugin (no C4K `search-form.feature`, no C4K `PROJECT.md`).
- Gates (the only pauses): no context found · material missing · target/case id not derivable · target file exists · design mentioned but no link.
- Commit messages end with the trailer line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## File Structure

```
ennam-qaqc/
├── .claude-plugin/
│   ├── plugin.json                 # manifest (components auto-discovered)
│   └── marketplace.json            # local/git marketplace entry
├── .gitignore
├── README.md                       # usage, install, how context works
├── CHANGELOG.md
├── agents/tc-agent.md              # authoring agent
├── commands/
│   ├── init.md                     # /ennam-qaqc:init
│   ├── write-tc.md                 # /ennam-qaqc:write-tc
│   └── review-tc.md                # /ennam-qaqc:review-tc
├── docs/
│   ├── CONTEXT_RESOLUTION.md       # shared lookup procedure + defaults
│   └── superpowers/{specs,plans}/  # this plan + the spec
├── hooks/hooks.json                # PostToolUse → validator
├── scripts/validate_feature.py     # Gherkin + universal-rule linter
├── skills/qc-tcs/SKILL.md          # QC-TCs method, minimally adapted
├── templates/
│   ├── TEMPLATE.feature            # plugin default skeleton (verbatim QC-TCs)
│   ├── PROJECT.md                  # blank context-file template (13 sections)
│   └── qaqc.example.json           # pointer-file example
└── tests/test_validate_feature.py
```

---

### Task 1: Plugin scaffold

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.gitignore`

**Interfaces:**
- Produces: plugin name `ennam-qaqc` → command names `/ennam-qaqc:<file>`, agent `subagent_type: "ennam-qaqc:tc-agent"`, skill `ennam-qaqc:qc-tcs`. Components are **auto-discovered** from `commands/`, `agents/`, `skills/`, `hooks/hooks.json` — the manifest deliberately does not list them (listing `hooks/hooks.json` explicitly can trigger a "duplicate hooks file" load error).

- [ ] **Step 1: Initialise git**

Run: `cd /Users/kai/Develop/ennam-qaqc && git init -b main`
Expected: `Initialized empty Git repository`

- [ ] **Step 2: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "ennam-qaqc",
  "version": "0.1.0",
  "description": "QA test-case authoring — writes import-ready Gherkin .feature files from any material, following each project's template, context file and the QC-TCs method",
  "author": {
    "name": "Kai"
  },
  "keywords": ["qa", "qc", "test-cases", "gherkin", "feature", "bdd"]
}
```

- [ ] **Step 3: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "ennam-qaqc",
  "owner": {
    "name": "Kai"
  },
  "plugins": [
    {
      "name": "ennam-qaqc",
      "source": "./",
      "description": "QA test-case authoring — Gherkin .feature files from any material"
    }
  ]
}
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.pyc
.DS_Store
.claude/sessions/
```

- [ ] **Step 5: Verify JSON**

Run: `python3 -m json.tool .claude-plugin/plugin.json >/dev/null && python3 -m json.tool .claude-plugin/marketplace.json >/dev/null && echo OK`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add .claude-plugin .gitignore docs/superpowers
git commit -m "chore: scaffold ennam-qaqc plugin" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Validator core — `validate(text)`

**Files:**
- Create: `scripts/validate_feature.py`
- Test: `tests/test_validate_feature.py`

**Interfaces:**
- Produces: `validate(text: str) -> List[Finding]`; `Finding(code: str, severity: "FAIL"|"WARN", line: int, message: str)` with `Finding.format(path) -> "path:line: SEVERITY CODE message"`; `validate_file(path) -> List[Finding]`. Codes G1–G14 as listed in the module docstring.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validate_feature.py`:

```python
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("validate_feature", ROOT / "scripts" / "validate_feature.py")
vf = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vf)

VALID = """\
# =============================================================================
# Feature: Sample  (US-001)
# =============================================================================
Feature: Sample
  # As a user

  # AC-01 - happy path.
  @positive @logic @area @screen
  Scenario: Positive - Save the form
    Given User is on the form
    When User taps Save
    Then The confirmation "Saved" is displayed

  @negative @logic @area @screen
  Scenario Outline: Negative - Reject <input>
    Given User is on the form
    When User enters <input>
    Then The error "<message>" is displayed

    Examples:
      | input | message  |
      | ""    | Required |
"""


def codes(text):
    return [f.code for f in vf.validate(text)]


def fail_codes(text):
    return [f.code for f in vf.validate(text) if f.severity == "FAIL"]


class ValidFileTest(unittest.TestCase):
    def test_valid_file_has_no_findings(self):
        self.assertEqual(codes(VALID), [])

    def test_doc_string_content_is_ignored(self):
        text = VALID.replace(
            '    Then The confirmation "Saved" is displayed\n',
            '    Then The confirmation is displayed\n'
            '      """\n      free text @notatag\n      Scenario - not a keyword\n      """\n',
        )
        self.assertEqual(codes(text), [])

    def test_description_under_feature_is_allowed(self):
        # Valid Gherkin. Whether a project forbids it is a project rule, not ours.
        text = VALID.replace("  # As a user\n", "  As a user I want things\n")
        self.assertEqual(codes(text), [])

    def test_hash_inside_step_text_is_allowed(self):
        text = VALID.replace('"Saved" is displayed', '"Saved" is displayed in Berry #5A60EC')
        self.assertEqual(codes(text), [])


class FileLevelTest(unittest.TestCase):
    def test_g1_two_features(self):
        self.assertIn("G1", fail_codes(VALID + "\nFeature: Second\n"))

    def test_g1_no_feature(self):
        self.assertIn("G1", fail_codes(VALID.replace("Feature: Sample\n", "")))

    def test_g2_text_before_feature(self):
        self.assertIn("G2", fail_codes("Some intro text\n" + VALID))

    def test_g3_scenario_with_dash(self):
        text = VALID.replace("Scenario: Positive - Save the form", "Scenario - Positive - Save the form")
        self.assertIn("G3", fail_codes(text))

    def test_g3_bare_examples(self):
        self.assertIn("G3", fail_codes(VALID.replace("    Examples:\n", "    Examples\n")))

    def test_g4_trailing_comment_on_tag_line(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @area @screen # AC-01")
        self.assertIn("G4", fail_codes(text))

    def test_g4_bracket_marker_on_tag_line(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic [BACKEND] @area @screen")
        self.assertIn("G4", fail_codes(text))

    def test_g5_tag_line_at_end_of_file(self):
        self.assertIn("G5", fail_codes(VALID + "\n  @dangling\n"))

    def test_g5_tag_before_background(self):
        text = VALID.replace("  # As a user\n", "  @setup\n  Background:\n    Given User is signed in\n")
        self.assertIn("G5", fail_codes(text))

    def test_g13_step_outside_scenario(self):
        self.assertIn("G13", fail_codes(VALID.replace("  # As a user\n", "  Given a stray step\n")))

    def test_g14_text_after_steps(self):
        text = VALID.replace(
            '    Then The confirmation "Saved" is displayed\n',
            '    Then The confirmation "Saved" is displayed\n    the user is happy\n',
        )
        self.assertIn("G14", fail_codes(text))


class ScenarioLevelTest(unittest.TestCase):
    def test_g6_missing_when_and_does_not_count(self):
        text = VALID.replace("    When User taps Save\n", "    And User taps Save\n")
        found = [f for f in vf.validate(text) if f.code == "G6"]
        self.assertEqual(len(found), 1)
        self.assertIn("When", found[0].message)

    def test_g6_background_given_counts(self):
        text = VALID.replace("  # As a user\n", "  Background:\n    Given User is signed in\n")
        text = text.replace("    Given User is on the form\n", "", 1)
        self.assertNotIn("G6", fail_codes(text))

    def test_g7_outline_without_examples(self):
        self.assertIn("G7", fail_codes(VALID.split("    Examples:")[0]))

    def test_g7_examples_header_only(self):
        self.assertIn("G7", fail_codes(VALID.replace('      | ""    | Required |\n', "")))

    def test_g7_examples_in_plain_scenario(self):
        text = VALID.replace(
            '    Then The confirmation "Saved" is displayed\n',
            '    Then The confirmation "Saved" is displayed\n\n    Examples:\n      | a |\n      | 1 |\n',
        )
        self.assertIn("G7", fail_codes(text))

    def test_g8_row_cell_count_mismatch(self):
        text = VALID.replace('      | ""    | Required |\n', '      | ""    | Required | extra |\n')
        self.assertIn("G8", fail_codes(text))

    def test_g8_empty_column_name(self):
        text = VALID.replace("      | input | message  |\n", "      | input | message  | |\n")
        text = text.replace('      | ""    | Required |\n', '      | ""    | Required | x |\n')
        self.assertIn("G8", fail_codes(text))

    def test_g9_column_used_only_in_title(self):
        text = VALID.replace('    Then The error "<message>" is displayed\n', "    Then The error is displayed\n")
        text = text.replace("Reject <input>", "Reject <input> with <message>")
        found = [f for f in vf.validate(text) if f.code == "G9"]
        self.assertEqual(len(found), 1)
        self.assertIn("<message>", found[0].message)

    def test_g10_placeholder_without_column(self):
        text = VALID.replace(
            "    Given User is on the form\n    When User enters <input>",
            "    Given User is on the <screen>\n    When User enters <input>",
        )
        self.assertIn("G10", fail_codes(text))

    def test_g11_placeholder_in_plain_scenario_is_warn(self):
        text = VALID.replace("    When User taps Save\n", "    When User taps <button>\n")
        self.assertEqual([(f.code, f.severity) for f in vf.validate(text)], [("G11", "WARN")])

    def test_g12_hash_in_title_is_warn(self):
        text = VALID.replace("Scenario: Positive - Save the form", "Scenario: Positive - Save the form # AC-01")
        self.assertEqual([(f.code, f.severity) for f in vf.validate(text)], [("G12", "WARN")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kai/Develop/ennam-qaqc && python3 -m unittest discover -s tests -v`
Expected: ERROR — `FileNotFoundError` / `No such file or directory: .../scripts/validate_feature.py`

- [ ] **Step 3: Write `scripts/validate_feature.py`**

```python
#!/usr/bin/env python3
"""
Feature File Validator
======================

Purpose: Lint a Gherkin .feature test-case file against the rules every
         ennam-qaqc project shares: Gherkin validity plus the QC-TCs universal
         rules (SKILL.md §4.2). Project-specific import rules (title length,
         Background allowed, tags on Feature:, ...) live in the project context
         file and are checked by the agent, not here.

Usage:   python3 validate_feature.py FILE [FILE ...]
         python3 validate_feature.py --hook     # PostToolUse payload on stdin

Exit:    CLI  -> 0 no FAIL, 1 at least one FAIL, 64 usage error
         hook -> 0 nothing to report, 2 FAIL findings (stderr is fed back to Claude)

Checks:
  G1  FAIL exactly one `Feature:` line
  G2  FAIL free text before `Feature:` (only #, blank and tag lines may precede it)
  G3  FAIL a keyword without its colon (`Scenario - Positive - ...`, bare `Examples`)
  G4  FAIL a tag line holding anything but @tags (incl. a trailing # comment)
  G5  FAIL a tag line not followed by Feature:/Rule:/Scenario:/Scenario Outline:/Examples:
  G6  FAIL a scenario without a Given, a When and a Then (And/But do not count)
  G7  FAIL Examples: missing, outside an Outline, or without a data row
  G8  FAIL an Examples row whose cell count differs from the header, or an empty column name
  G9  FAIL an Examples column never used as <column> in a step (the title does not count)
  G10 FAIL an Outline step <placeholder> with no matching Examples column
  G11 WARN a <placeholder> in a plain Scenario step (Gherkin reads it literally)
  G12 WARN a scenario title containing " #" (a trailing comment becomes title text)
  G13 FAIL a step outside a scenario or background
  G14 FAIL free text after a step or table row (not a step, table, tag or comment)

Python 3.7+, standard library only.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Tuple

KEYWORD_RE = re.compile(r"^(Feature|Background|Rule|Scenario Outline|Scenario|Examples):(.*)$")
MISSING_COLON_RE = re.compile(r"^(Feature|Background|Rule|Scenario Outline|Scenario|Examples)\s*(-|–|$)")
STEP_RE = re.compile(r"^(Given|When|Then|And|But|\*)\s+(\S.*)$")
TAG_RE = re.compile(r"^@[^\s@#]+$")
PLACEHOLDER_RE = re.compile(r"<([^<>]+)>")
TAG_TARGETS = ("Feature", "Rule", "Scenario", "Scenario Outline", "Examples")
DOCSTRING_FENCES = ('"""', "`" * 3)  # built, not typed: a literal fence breaks markdown that embeds this file


@dataclass
class Finding:
    code: str
    severity: str  # "FAIL" or "WARN"
    line: int
    message: str

    def format(self, path):
        return "%s:%d: %s %s %s" % (path, self.line, self.severity, self.code, self.message)


@dataclass
class ExamplesBlock:
    line: int
    rows: List[Tuple[int, List[str]]] = field(default_factory=list)


@dataclass
class Scenario:
    line: int
    title: str
    outline: bool
    inherited: Set[str] = field(default_factory=set)
    steps: List[Tuple[int, str, str]] = field(default_factory=list)
    examples: List[ExamplesBlock] = field(default_factory=list)


def split_row(text):
    """'| a | b |' -> ['a', 'b']. Gherkin trims cells; an escaped pipe stays inside its cell."""
    inner = text.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", inner)]


def _short(title):
    return title if len(title) <= 60 else title[:57] + "..."


def validate(text):
    findings = []

    def add(code, severity, line, message):
        findings.append(Finding(code, severity, line, message))

    feature_lines = []
    scenarios = []
    current = None          # Scenario being filled
    block = None            # None | feature | background | scenario | examples | orphan
    background_keywords = set()
    block_has_body = False  # a step or table row seen since the last keyword line
    pending_tag = None      # line of a tag line still waiting for its target
    docstring = None        # opening fence while inside a doc string

    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()

        if docstring:
            if line.startswith(docstring):
                docstring = None
            continue
        if line.startswith(DOCSTRING_FENCES):
            docstring = line[:3]
            continue
        if not line or line.startswith("#"):
            continue

        if line.startswith("@"):
            bad = [token for token in line.split() if not TAG_RE.match(token)]
            if bad:
                add("G4", "FAIL", no, "tag line holds non-tag text %r; a tag line may contain only @tags" % " ".join(bad))
            pending_tag = no
            continue

        keyword = KEYWORD_RE.match(line)
        if keyword:
            kw, rest = keyword.group(1), keyword.group(2).strip()
            if pending_tag is not None and kw not in TAG_TARGETS:
                add("G5", "FAIL", pending_tag,
                    "tags must precede Feature:, Rule:, Scenario:, Scenario Outline: or Examples:, not %s:" % kw)
            pending_tag = None
            block_has_body = False
            if kw == "Feature":
                feature_lines.append(no)
                block, current = "feature", None
            elif kw == "Rule":
                block, current = "feature", None
            elif kw == "Background":
                block, current = "background", None
            elif kw in ("Scenario", "Scenario Outline"):
                current = Scenario(no, rest, kw == "Scenario Outline", set(background_keywords))
                scenarios.append(current)
                block = "scenario"
                if " #" in rest:
                    add("G12", "WARN", no, "title contains ' #'; a trailing comment becomes part of the title")
            else:  # Examples
                if current is None or not current.outline or block not in ("scenario", "examples"):
                    add("G7", "FAIL", no, "Examples: outside a Scenario Outline")
                    block = "orphan"
                else:
                    current.examples.append(ExamplesBlock(no))
                    block = "examples"
            continue

        if MISSING_COLON_RE.match(line):
            add("G3", "FAIL", no, "keyword without a colon: %r is not read as a keyword" % line[:60])
            pending_tag = None
            continue

        if pending_tag is not None:
            add("G5", "FAIL", pending_tag, "tag line is followed by %r instead of a Scenario:" % line[:60])
            pending_tag = None

        step = STEP_RE.match(line)
        if step:
            if block == "scenario":
                current.steps.append((no, step.group(1), step.group(2)))
            elif block == "background":
                background_keywords.add(step.group(1))
            else:
                add("G13", "FAIL", no, "step outside a Scenario or Background: %r" % line[:60])
            block_has_body = True
            continue

        if line.startswith("|"):
            if block == "examples":
                current.examples[-1].rows.append((no, split_row(line)))
            block_has_body = True
            continue

        if block is None:
            add("G2", "FAIL", no, "text before Feature:; only # comments, blank lines and tags may precede it")
        elif block_has_body:
            add("G14", "FAIL", no, "unexpected text %r; not a step, table row, tag or comment" % line[:60])
        # Otherwise: description text directly under a keyword line. Valid Gherkin;
        # whether the project allows it is a project rule, checked by the agent.

    if pending_tag is not None:
        add("G5", "FAIL", pending_tag, "tag line at end of file has no Scenario:")
    if len(feature_lines) != 1:
        where = feature_lines[1] if len(feature_lines) > 1 else 1
        add("G1", "FAIL", where, "found %d Feature: lines; a file holds exactly one" % len(feature_lines))

    for scenario in scenarios:
        _check_scenario(scenario, add)

    findings.sort(key=lambda f: (f.line, f.code))
    return findings


def _check_scenario(sc, add):
    keywords = {kw for _, kw, _ in sc.steps} | sc.inherited
    missing = [kw for kw in ("Given", "When", "Then") if kw not in keywords]
    if missing:
        add("G6", "FAIL", sc.line,
            "scenario %r has no %s step (And/But do not count)" % (_short(sc.title), "/".join(missing)))

    used = set()
    for _, _, text in sc.steps:
        used.update(name.strip() for name in PLACEHOLDER_RE.findall(text))

    if not sc.outline:
        for name in sorted(used):
            add("G11", "WARN", sc.line,
                "<%s> in a plain Scenario is read literally; use concrete data or a Scenario Outline" % name)
        return

    if not sc.examples:
        add("G7", "FAIL", sc.line, "Scenario Outline %r has no Examples: table" % _short(sc.title))
        return

    columns = set()
    for ex in sc.examples:
        if len(ex.rows) < 2:
            add("G7", "FAIL", ex.line, "Examples: needs a header row and at least one data row")
            if not ex.rows:
                continue
        header_line, header = ex.rows[0]
        if any(not name for name in header):
            add("G8", "FAIL", header_line, "Examples header has an empty column name")
        for row_line, cells in ex.rows[1:]:
            if len(cells) != len(header):
                add("G8", "FAIL", row_line, "row has %d cells; the header has %d" % (len(cells), len(header)))
        for name in header:
            if name and name not in used:
                add("G9", "FAIL", header_line, "column <%s> is never used in a step (the title does not count)" % name)
        columns.update(name for name in header if name)

    for name in sorted(used - columns):
        add("G10", "FAIL", sc.line, "step uses <%s> but no Examples column has that name" % name)


def validate_file(path):
    return validate(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests `ok`, final line `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_feature.py tests/test_validate_feature.py
git commit -m "feat: add Gherkin feature-file validator core" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Validator CLI, hook mode and `hooks.json`

**Files:**
- Modify: `scripts/validate_feature.py` (append after `validate_file`)
- Modify: `tests/test_validate_feature.py` (append a test class before the `if __name__` block)
- Create: `hooks/hooks.json`

**Interfaces:**
- Consumes: `validate_file(path)`, `Finding.format(path)` from Task 2.
- Produces: `run_cli(paths: List[str], out) -> int`, `run_hook(stdin, err) -> int`, `main(argv=None) -> int`. CLI command used by every later task: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py <file>`; per-file summary line `"<path>: <n> FAIL, <m> WARN"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_validate_feature.py` (above `if __name__ == "__main__":`), and add `import io`, `import json`, `import tempfile` to the imports at the top:

```python
class CliAndHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        path = Path(self.tmp.name) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def hook(self, payload):
        err = io.StringIO()
        code = vf.run_hook(io.StringIO(json.dumps(payload)), err)
        return code, err.getvalue()

    def test_cli_exit_codes_and_summary(self):
        good = self.write("good.feature", VALID)
        bad = self.write("bad.feature", VALID + "\nFeature: Second\n")
        out = io.StringIO()
        self.assertEqual(vf.run_cli([good], out), 0)
        self.assertIn("good.feature: 0 FAIL, 0 WARN", out.getvalue())
        self.assertEqual(vf.run_cli([good, bad], io.StringIO()), 1)

    def test_cli_usage(self):
        self.assertEqual(vf.main([]), 64)

    def test_hook_ignores_non_feature_files(self):
        path = self.write("notes.md", "Feature: x\nFeature: y\n")
        self.assertEqual(self.hook({"tool_input": {"file_path": path}}), (0, ""))

    def test_hook_ignores_template(self):
        path = self.write("TEMPLATE.feature", "no feature line\n")
        self.assertEqual(self.hook({"tool_input": {"file_path": path}}), (0, ""))

    def test_hook_reports_fail_with_exit_2(self):
        path = self.write("bad.feature", VALID + "\nFeature: Second\n")
        code, err = self.hook({"tool_name": "Write", "tool_input": {"file_path": path}})
        self.assertEqual(code, 2)
        self.assertIn("G1", err)

    def test_hook_passes_valid_file(self):
        path = self.write("good.feature", VALID)
        self.assertEqual(self.hook({"tool_input": {"file_path": path}}), (0, ""))

    def test_hook_ignores_bad_payload(self):
        err = io.StringIO()
        self.assertEqual(vf.run_hook(io.StringIO("not json"), err), 0)
        self.assertEqual(vf.run_hook(io.StringIO("[]"), err), 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -v`
Expected: the 7 new tests ERROR with `AttributeError: module 'validate_feature' has no attribute 'run_cli'` (or `run_hook` / `main`); Task 2 tests still pass.

- [ ] **Step 3: Append CLI + hook to `scripts/validate_feature.py`**

```python
def run_cli(paths, out):
    failed = False
    for path in paths:
        findings = validate_file(path)
        for finding in findings:
            out.write(finding.format(path) + "\n")
        fails = sum(1 for f in findings if f.severity == "FAIL")
        out.write("%s: %d FAIL, %d WARN\n" % (path, fails, len(findings) - fails))
        failed = failed or fails > 0
    return 1 if failed else 0


def run_hook(stdin, err):
    """PostToolUse: lint the .feature file just written. Exit 2 feeds stderr back to Claude."""
    try:
        payload = json.load(stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".feature") or Path(path).name == "TEMPLATE.feature" or not Path(path).is_file():
        return 0
    fails = [f for f in validate_file(path) if f.severity == "FAIL"]
    if not fails:
        return 0
    err.write("validate_feature.py: %s has %d FAIL finding(s); fix them before continuing.\n" % (path, len(fails)))
    for finding in fails:
        err.write(finding.format(path) + "\n")
    return 2


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args == ["--hook"]:
        return run_hook(sys.stdin, sys.stderr)
    if not args or args[0].startswith("-"):
        sys.stderr.write("usage: validate_feature.py FILE [FILE ...] | --hook\n")
        return 64
    return run_cli(args, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests `ok`, `OK`.

- [ ] **Step 5: Regression check against the real imported file**

Run: `python3 scripts/validate_feature.py "/Users/kai/Downloads/QC-TCs/test-cases/Explore & Discovery/search-form.feature"`
Expected: last line `...search-form.feature: 0 FAIL, <n> WARN`. That file imports cleanly into the C4K tool, so **any FAIL is a validator bug**: copy the offending lines into a new unit test in `tests/test_validate_feature.py`, watch it fail, fix `validate_feature.py`, re-run Steps 4–5. List any WARNs in the commit message body.

- [ ] **Step 6: Write `hooks/hooks.json`**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py\" --hook"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 7: Verify the hook end to end**

Run:
```bash
python3 -m json.tool hooks/hooks.json >/dev/null && echo JSON-OK
printf 'Feature: A\nFeature: B\n' > /tmp/qaqc-hook-check.feature
echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/qaqc-hook-check.feature"}}' | python3 scripts/validate_feature.py --hook; echo "exit=$?"
rm /tmp/qaqc-hook-check.feature
```
Expected: `JSON-OK`, a stderr line containing `G1`, then `exit=2`.

- [ ] **Step 8: Commit**

```bash
git add scripts/validate_feature.py tests/test_validate_feature.py hooks/hooks.json
git commit -m "feat: add validator CLI, PostToolUse hook mode and hooks.json" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The `qc-tcs` skill

**Files:**
- Create: `skills/qc-tcs/SKILL.md` (copy of QC-TCs `SKILL.md` + five edits)

**Interfaces:**
- Consumes: `docs/CONTEXT_RESOLUTION.md`, `templates/PROJECT.md`, `scripts/validate_feature.py` (names only — created in Tasks 3 and 5).
- Produces: skill `ennam-qaqc:qc-tcs`; section numbers §1–§13 unchanged (commands and agent cite them).

- [ ] **Step 1: Copy the source verbatim**

Run: `mkdir -p skills/qc-tcs && cp /Users/kai/Downloads/QC-TCs/.claude/skills/SKILL.md skills/qc-tcs/SKILL.md`

- [ ] **Step 2: Edit 1 — frontmatter**

Replace lines 2–3:
```
name: QC-TCs
description: Portable reference for authoring test cases - requirement decomposition, a 19-dimension coverage model, traceability, gap review and a pre-commit checklist. Project-agnostic - works for any app (mobile or web) and any automation framework (Maestro, Playwright, Cypress, Appium). Reads its project-specific vocabulary from PROJECT.md. Use when writing or reviewing a test case, deciding what scenarios a screen needs, or judging whether a scenario is automatable.
```
with:
```
name: qc-tcs
description: Portable reference for authoring test cases - requirement decomposition, a 19-dimension coverage model, traceability, gap review and a pre-commit checklist. Project-agnostic - works for any app (mobile or web) and any automation framework (Maestro, Playwright, Cypress, Appium). Reads its project-specific vocabulary from the project context file (PROJECT.md or equivalent, found via the ennam-qaqc context-resolution procedure). Use when writing or reviewing a test case or .feature file, deciding what scenarios a screen needs, or judging whether a scenario is automatable.
```

- [ ] **Step 3: Edit 2 — "How to use" block**

Replace the block that starts `> **This file is project-agnostic and is meant to be copied between projects` and ends `should say so and point at it; recurring facts belong there, not hardcoded here.` (source lines 12–28) with:

```
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
```

- [ ] **Step 4: Edit 3 — §4.2 import grammar sentence**

Replace:
```
into a tool, that tool's import grammar is a hard constraint** (this project:
CLAUDE.md "Import compatibility"). It beats every convenience below and any
older sibling file. Universal rules:
```
with:
```
into a tool, that tool's import grammar is a hard constraint** (`PROJECT.md`
§13, or — without one — the template's `IMPORT RULES` block). It beats every
convenience below and any older sibling file. Universal rules:
```

- [ ] **Step 5: Edit 4 — §11 first-but-one checklist item**

Replace:
```
- [ ] File meets the project's import rules (this project: CLAUDE.md "Import
      compatibility" — no tags or description under `Feature:`, Given + When +
      Then in every scenario, full-line comments only, every `Examples` column
      used in a step, titles ≤ 200 characters)
```
with:
```
- [ ] File meets the project's import rules (`PROJECT.md` §13, or the
      template's `IMPORT RULES` block) and `validate_feature.py` reports 0 FAIL
```

- [ ] **Step 6: Edit 5 — §13 Related**

Replace:
```
- **`PROJECT.md`** — this project's vocabulary, paths, format and traps. Read first.
- The project's run/report workflow and automation-authoring guidance, as named
  in `PROJECT.md`.
```
with:
```
- **`PROJECT.md`** (the context file) — this project's vocabulary, paths,
  format, import rules and traps. Read first.
- `${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` — how the context file,
  template and test-cases root are found, and the defaults.
- `${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py` — Gherkin + universal-rule
  linter (runs automatically after every write to a `.feature`).
- The project's run/report workflow and automation-authoring guidance, as named
  in `PROJECT.md`.
```

- [ ] **Step 7: Verify no C4K hardcoding remains and the method is intact**

Run:
```bash
grep -n 'CLAUDE.md "Import\|this project:\|Copy this whole skill' skills/qc-tcs/SKILL.md; echo "leftovers=$?"
grep -c '^## ' skills/qc-tcs/SKILL.md
diff <(grep '^## ' /Users/kai/Downloads/QC-TCs/.claude/skills/SKILL.md) <(grep '^## ' skills/qc-tcs/SKILL.md)
```
Expected: `leftovers=1` (grep found nothing); heading count `15`; the diff shows only `How to use this skill in a new project` → `How this skill is used`.

- [ ] **Step 8: Commit**

```bash
git add skills/qc-tcs/SKILL.md
git commit -m "feat: add qc-tcs skill adapted from QC-TCs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Templates and the context-resolution procedure

**Files:**
- Create: `templates/TEMPLATE.feature`, `templates/PROJECT.md`, `templates/qaqc.example.json`, `docs/CONTEXT_RESOLUTION.md`

**Interfaces:**
- Produces: `.claude/qaqc.json` schema `{projectContext, template, testCasesRoot}` (strings or null, repo-relative); CONTEXT_RESOLUTION.md section numbers §1 pointer file, §2 context file, §3 template, §4 test-cases root, §5 defaults, §6 closest sibling — cited by Tasks 6–9. PROJECT.md section numbers §1–§13 (same as QC-TCs §1–§12, plus §13 import rules).

- [ ] **Step 1: Copy the default template verbatim**

Run: `mkdir -p templates && cp /Users/kai/Downloads/QC-TCs/test-cases/TEMPLATE.feature templates/TEMPLATE.feature && cmp templates/TEMPLATE.feature /Users/kai/Downloads/QC-TCs/test-cases/TEMPLATE.feature && echo IDENTICAL`
Expected: `IDENTICAL`

- [ ] **Step 2: Write `templates/qaqc.example.json`**

```json
{
  "projectContext": ".claude/skills/PROJECT.md",
  "template": "test-cases/TEMPLATE.feature",
  "testCasesRoot": "test-cases/"
}
```

- [ ] **Step 3: Write `templates/PROJECT.md`**

````markdown
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

---

## Provenance
Filled by `/ennam-qaqc:init` when it drafts this file: one row per rule.

| Section | Rule | Source (file:line, "user answer", or "plugin default") |
|---|---|---|
````

- [ ] **Step 4: Write `docs/CONTEXT_RESOLUTION.md`**

````markdown
# Context Resolution

One procedure, used by every ennam-qaqc command, the `tc-agent` and the
`qc-tcs` skill. It finds three things:

| Thing | What it is |
|---|---|
| **Context file** | The project's adapter: vocabulary, paths, format, import rules, traps. Usually `PROJECT.md`, but any file with that kind of content works. **Optional.** |
| **Template** | The `.feature` skeleton every generated file follows. |
| **Test-cases root** | The folder test cases are written under. |

## 1. Pointer file — `.claude/qaqc.json`

Written only by `/ennam-qaqc:init`. Paths only, relative to the repo root —
never rules. Any key may be absent or `null`.

```json
{
  "projectContext": ".claude/skills/PROJECT.md",
  "template": "test-cases/TEMPLATE.feature",
  "testCasesRoot": "test-cases/"
}
```

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
| Import rules | the resolved template's `IMPORT RULES` comment block |
| Error-handling scope | from the platform: mobile → no HTTP-status scenarios; web with route interception → in scope. State it as an `[ASSUMPTION]`. |
| Exit paths | mobile: system Back, on-screen back, ✕, each CTA · web: browser Back/Forward, in-page back, ✕, each CTA, direct URL / refresh |
| Queued work | listed in the report only |

## 6. Closest sibling

Before writing, read one existing `.feature` under the root (never
`TEMPLATE.feature`) to match house style: prefer the same area folder, then the
largest file. None exists → the template alone sets the style.
````

- [ ] **Step 5: Verify**

Run:
```bash
python3 -m json.tool templates/qaqc.example.json >/dev/null && echo JSON-OK
grep -c '^## [0-9]*\. ' templates/PROJECT.md
grep -c '^## [0-9]\. ' docs/CONTEXT_RESOLUTION.md
python3 scripts/validate_feature.py templates/TEMPLATE.feature | grep FAIL
```
Expected: `JSON-OK`; `13`; `6`; exactly two FAIL lines, both `G10` (`<expected outcome>`, `<starting state>`) — skeleton placeholders, expected (the hook skips `TEMPLATE.feature`).

- [ ] **Step 6: Commit**

```bash
git add templates docs/CONTEXT_RESOLUTION.md
git commit -m "feat: add default template, blank PROJECT.md and context-resolution procedure" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `/ennam-qaqc:init`

**Files:**
- Create: `commands/init.md`

**Interfaces:**
- Consumes: CONTEXT_RESOLUTION.md §1–§4, `templates/PROJECT.md`.
- Produces: `.claude/qaqc.json`; optionally a drafted context file (default `.claude/qaqc/PROJECT.md`).

- [ ] **Step 1: Write `commands/init.md`**

````markdown
---
description: Point ennam-qaqc at this project's test-case context file, or scan the repo and draft one
argument-hint: [path-to-context-file]
allowed-tools: Read, Write, Glob, Grep, AskUserQuestion, Bash(ls:*)
---

# Init — project context for test cases

**Argument:** $1 (optional — path to an existing context file)

Sets up `.claude/qaqc.json` so later commands find the project's context file,
template and test-cases root without asking. Read
`${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` first — it defines the pointer
file, the lookup order and the defaults.

## Rules

1. **Never force a name or location.** Any file with the right kind of content is
   a valid context file, complete or not.
2. **Never write a drafted context file without explicit approval.**
3. **Never invent a rule.** Every drafted rule has a source: a repo file + line, a
   user answer, or "plugin default".
4. **`.claude/qaqc.json` holds paths only.**

## Step 1 — Existing pointer

If `.claude/qaqc.json` exists, show it and ask: keep / point elsewhere / re-scan.
Keep → report (Step 7) and stop.

## Step 2 — Ask for an existing file

If `$1` was given, use it. Otherwise collect candidates with
CONTEXT_RESOLUTION.md §2 step 3, then ask (AskUserQuestion):

> Do you already have a project context file for test cases — a PROJECT.md, or
> another file with the same kind of content (tags, paths, format, import rules)?

Options: each candidate found · "Another file — I'll give the path" ·
"No — scan the repo and draft one".

**A file is chosen:** confirm it exists and read it. Note which of the 13
sections of `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md` it covers; the rest use
defaults (not an error). Go to Step 6.

## Step 3 — Scan the repo

Read whatever exists, in parallel:

| Look at | To learn |
|---|---|
| `**/*.feature` (skip `node_modules/`, `.git/`, `TEMPLATE.feature`) — up to 10, the largest per folder | root and areas (folders) · area tag per folder (the tag shared by every scenario in that folder) · screen-tag convention · title prefixes · case-id format on `# Feature:` lines · header blocks in order · `Background:` / `Scenario Outline` use · priority tags · comment style |
| `**/TEMPLATE.feature` | template path |
| `README*`, `CLAUDE.md`, `AGENTS.md`, `<root>/README.md`, `docs/**/*test*` | conventions, source of truth, import tool and its rules, authoring rules |
| `flows/**/*.yaml`, `playwright.config.*`, `cypress.config.*`, `wdio.conf.*`, `.detoxrc*` | automation framework |
| `environments/*`, `.env.example`, `app.json`, `package.json` | platform (`react-native`/`expo` → mobile; `next`/`vite`/`react-dom` → web), app/site ids, environments |
| `docs/**/DR-*.md`, `docs/PLATFORMS/` | where specs live, case-id style |

## Step 4 — Ask what the scan could not settle

Ask only questions whose answers change the output and that the scan did not
answer with a source (AskUserQuestion, at most 4 per call):

1. Platform under test — mobile / web / both
2. Automation framework — Maestro / Playwright / Cypress / Appium / none
3. Case-id format — e.g. `US-001`, `DR-PA-003-005-01`, none
4. Areas / folders
5. Source of truth — app-truth / spec-truth
6. Import tool and its constraints — or "files are not imported"

## Step 5 — Draft, show, approve

Build the draft from `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md`. Fill each
section from the scan and the answers. A section nothing supports keeps its
guidance text plus "Not set — plugin default applies". Fill the Provenance table:
one row per rule with its source.

Show the full draft, then ask:

> Write this to `.claude/qaqc/PROJECT.md`? approve / different path / change something first / cancel

Write only on approval. Cancel → write nothing (not `qaqc.json` either) and stop.

## Step 6 — Write the pointer

Resolve the template (CONTEXT_RESOLUTION.md §3) and the root (§4), then write
`.claude/qaqc.json`:

```json
{
  "projectContext": "<context file path>",
  "template": "<template path, or null for the plugin default>",
  "testCasesRoot": "<root>"
}
```

## Step 7 — Report

```
ennam-qaqc initialised
  Context file : <path> (<existing | drafted>) — sections <n>/13, defaults for: <§x, §y | none>
  Template     : <path> (<why>)
  Test cases   : <root>
  Pointer      : .claude/qaqc.json
Next: /ennam-qaqc:write-tc <what to write test cases for>
```
````

- [ ] **Step 2: Verify frontmatter and references**

Run:
```bash
head -5 commands/init.md
grep -o 'CONTEXT_RESOLUTION.md §[0-9]' commands/init.md | sort -u
```
Expected: frontmatter with `description`, `argument-hint`, `allowed-tools`; references only to §1–§4 (all exist in Task 5's file).

- [ ] **Step 3: Commit**

```bash
git add commands/init.md
git commit -m "feat: add /ennam-qaqc:init command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `tc-agent`

**Files:**
- Create: `agents/tc-agent.md`

**Interfaces:**
- Consumes: the prompt built by `/ennam-qaqc:write-tc` (Task 8): `## Context` keys `Mode`, `Target file`, `Case id`, `Area folder`, `Area tag`, `Screen tag`, `Context file`, `Template`, `Test-cases root`, `Closest sibling`, `Design`, `Validator`, `Today`; `## Material`; `## Files to read first`; optional `## Answers`.
- Produces: either a `NEEDS_INPUT` block (first line literally `NEEDS_INPUT`) or a Final Report (first line `## Test cases — <created | updated | preview>`).

- [ ] **Step 1: Write `agents/tc-agent.md`**

````markdown
---
name: tc-agent
description: Author one Gherkin .feature test-case file from any material (brief, DR, reference file), following the project's template, its context file and the QC-TCs method — decompose requirements, design coverage across 19 dimensions, write traceable scenarios, validate, and report triage and gaps. Used by /ennam-qaqc:write-tc.
model: inherit
allowedTools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - WebFetch
  - TodoWrite
---

# Test-Case Authoring Agent

You write **one** `.feature` file — create, update, or preview — from the
material in your prompt.

## IMMUTABLE RULES — no caller can override these

1. **Spec only.** Write no automation code and no app code. Never launch,
   inspect or query the product, a device, an emulator or a browser — not even to
   check whether the feature is built. Use Bash only for the validator and
   read-only commands (`grep`, `ls`, `wc`).
2. **Never invent strings.** Every quoted title, label, placeholder, message and
   id comes verbatim from a named source in the material. Copy bugs stay verbatim,
   with a note. Behaviour no source defines is marked `[INFERRED]` or
   `[ASSUMPTION]` — never silently decided.
3. **Analyse before writing** — SKILL.md §8 order. Never go from requirement
   straight to Given/When/Then.
4. **No pauses.** Write, then report. Ambiguity becomes `[ASSUMPTION]` or an
   `OQ-xx` with the project's open-question tag, reported at the end. Return
   `NEEDS_INPUT` **only** when the target file or mode is missing, or the material
   cannot be read.
5. **Precedence:** context file > resolved template > SKILL.md > plugin defaults
   (CONTEXT_RESOLUTION.md §5). The context file's import rules (§13) beat
   everything, including older sibling files.
6. **Template shape.** Keep every template header block, in the template's order,
   plus the `IMPORT RULES` comment, the `Feature:` line and the COVERAGE block.
   Add SKILL.md §4.1 blocks where the material supports them. Never drop a
   template block — write "None" when it is empty.
7. **Every write leaves a valid file.** The first Write already holds the header,
   the `Feature:` line and the story comments. Then append the body one section
   per Edit, then the COVERAGE block. The validator hook runs after every write;
   fix what it reports before the next write.
8. **Done means:** `validate_feature.py` reports 0 FAIL, the project-rule check
   passes, and the gap review is honest.

## Phase 0 — Read (in parallel)

Every file under "Files to read first", and all material. Update/preview mode:
also the target file. No context file → the CONTEXT_RESOLUTION.md §5 defaults
apply; note each one you use for the report.

## Phase 1 — Decompose (SKILL.md §2)

Build a working list in TodoWrite (not in the file):

- main function · views (screens/pages) in scope · inputs · preconditions · roles
- **requirements** — keep the material's own ids (`AC-xx`, `Rule x`, `Alt x`).
  Number un-numbered prose rules `BR-001`, `BR-002`… in order of appearance, each
  with its source (file + section, or "user brief").
- state transitions (allowed and prohibited) · system responses
- every quoted string with its source
- ambiguities → `OQ-xx` with interpretations A/B and an owner if named;
  assumptions needed to keep writing → `[ASSUMPTION]`
- explicit out-of-scope items and the spec that owns each

## Phase 2 — Design coverage (SKILL.md §3)

Walk all 19 dimensions **per view**: applies (which scenarios) or not applicable
(why). Risk sets depth — payment, auth, data loss, permissions and submission get
boundary and negative depth. Plan numbered sections:
`# N. <STAGE OR VIEW>  (<AC/Rule range>)`. Use `Scenario Outline` only for one
behaviour across an equivalence partition.

## Phase 3 — Header + Feature line (one Write)

Template block order. Fill:

- `# Feature: <name>  (<case id>)`
- `# Source:` — spec/DR: `"<title>" v<n> (<author>, <DD Mon YYYY>)`; brief:
  `"User brief" (<requester if known>, <DD Mon YYYY>)`; several sources → one line
  each.
- Design line(s) from the `Design` fact (`<TODO>` when skipped).
- `COPY SOURCE` note when authoring is documents-only (the default): every quoted
  string is sourced from <sources + versions>, not verified against the product;
  build status not checked; a live verification pass must confirm the copy.
- `WHAT THIS FILE COVERS` (in scope / out of scope with owners) when there is more
  than one view or any out-of-scope boundary.
- Tag legend — only tags this file uses, each with its project meaning.
- `SPEC-DIFFS` — app-truth, nothing driven: "None recorded. This file has not yet
  been driven against the app." Spec-truth: omit (SKILL.md §5).
- `OPEN QUESTIONS` when any.
- `PRECONDITIONS` — environment, app/site id, auth, entry point, seeding, state
  reset, data mutation, markers.
- `TEST DATA` — role → value → notes (source of each value); fixtures named.
- Triage block (name per context file §6, else the template's) — ✅ now /
  `[BACKEND]` / ❌ not auto, plus "Automation for this file does not exist yet."
  when true.
- The template's `IMPORT RULES` comment (reworded only to match context §13).
- `Feature: <name>`, then "As a / I want / So that" as `#` comments (unless
  context §13 allows a description).

## Phase 4 — Body, one section per Edit

Each scenario (SKILL.md §4.2–§4.3, §6.1; context §3, §6):

1. Traceability comment on its own line: `# AC-07 / Rule 4 - <why>`. Markers on
   their own comment lines: `# [BACKEND] <what is needed>`, `# OQ-xx …`.
2. Tag line in slot order: direction, check type, gates, platform, area, screen.
3. `Scenario: Positive - …` / `Scenario: Negative - …` naming behaviour and
   outcome; the prefix agrees with the direction tag.
4. At least one `Given`, one `When`, one `Then`; one behaviour; user-perceivable
   assertions; persistence asserted by reopening, not by a success message.

## Phase 5 — COVERAGE block

Every requirement id → section(s), gates noted. Then `NOT APPLICABLE`
(dimension — why), `OUT OF SCOPE` (owner), `NOT COVERED (open questions)`. No
requirement may be missing.

## Phase 6 — Validate

1. Run `<Validator> "<target file>"`. Fix every FAIL and re-run until 0 FAIL. Fix
   WARNs unless deliberate (say why in the report).
2. Project-rule check (context §3, §6, §13 — or template IMPORT RULES + defaults):
   every import rule (title length, tag length, Feature-line tags, Background,
   description…); every tag in the vocabulary; tag order; exactly one direction and
   one check type per scenario; prefix ↔ direction; area + screen on every
   scenario.
3. Triage counts with grep — BLOCKED = blocked/not-implemented tags; MANUAL =
   visual/a11y/manual tags; AUTOMATABLE = the rest. The triage block must agree.
4. SKILL.md §10 gap review and §11 checklist. Fix what fails.

## Modes

- **create** — new file at the target path.
- **update** — keep existing scenarios unless the new material changes them; edit
  changed ones in place; add new ones to the right section; update Source
  (version/date), traceability, COVERAGE and the triage block. Never delete a
  scenario without listing it in the report.
- **preview** — write nothing. Report the scenarios that would be added /
  changed / removed (title, tags, requirement), then stop.

## NEEDS_INPUT (Rule 4 cases only)

```
NEEDS_INPUT
Question: <one question>
Options: 1. … 2. …
Why: <what is missing and why it cannot be derived>
```

## Final Report — always this shape

```
## Test cases — <created | updated | preview>
File      : <path>
Case id   : <id>
Sources   : <each source + version/date>
Context   : <context file | none — defaults used: …>
Scenarios : <total> — <n> automatable / <n> manual / <n> blocked

### Method
Views: …
Dimensions applied: … | Not applicable: <dimension — why>, …

### Gap review
Critical rules covered: <x>/<y>
| Requirement | Status | Note |
(only Partially covered / Missing / Needs clarification rows — otherwise "All <n> requirements covered")

### Open questions & assumptions
- OQ-xx …
- [ASSUMPTION] …

### Checks
validate_feature.py: 0 FAIL, <n> WARN (<why kept>)
Project rules: <pass | fixed: …>
Queued work: <recorded where the context file says | listed here: …>
```
````

- [ ] **Step 2: Verify**

Run:
```bash
head -14 agents/tc-agent.md
grep -n 'SKILL.md §\|CONTEXT_RESOLUTION.md §' agents/tc-agent.md | grep -o '§[0-9.]*' | sort -u | tr '\n' ' '
```
Expected: frontmatter `name: tc-agent`, tool list without any device/emulator/browser tools; cited sections all exist (SKILL §1–§13 incl. §4.1–§4.3, §6.1; CONTEXT_RESOLUTION §5).

- [ ] **Step 3: Commit**

```bash
git add agents/tc-agent.md
git commit -m "feat: add tc-agent authoring agent" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `/ennam-qaqc:write-tc`

**Files:**
- Create: `commands/write-tc.md`

**Interfaces:**
- Consumes: CONTEXT_RESOLUTION.md §2–§4, §6; agent `ennam-qaqc:tc-agent` and its prompt contract (Task 7).
- Produces: the user-facing entry point `/ennam-qaqc:write-tc <material> [--context path] [--out path]`.

- [ ] **Step 1: Write `commands/write-tc.md`**

````markdown
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
- Design: <links | <TODO> (user skipped) | none mentioned>
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
6. <each material file>
```

## Step 7 — NEEDS_INPUT loop

If the agent's reply starts with `NEEDS_INPUT`, ask the user that question, then
continue the same agent with `SendMessage` (answer included). If SendMessage is
unavailable, dispatch again with the same prompt plus `## Answers`. Repeat until
a Final Report arrives.

## Step 8 — Relay

Copy the Final Report verbatim. Add one line before it only if something failed.
````

- [ ] **Step 2: Verify the contract matches the agent**

Run:
```bash
for k in "Mode" "Target file" "Case id" "Area folder" "Area tag" "Screen tag" "Context file" "Template" "Test-cases root" "Closest sibling" "Design" "Validator" "Today"; do grep -q -- "- $k:" commands/write-tc.md || echo "missing in command: $k"; grep -q "\`$k\`" agents/tc-agent.md || grep -q "$k" agents/tc-agent.md || echo "agent never mentions: $k"; done; echo CHECKED
```
Expected: only `CHECKED` (no `missing` lines).

- [ ] **Step 3: Commit**

```bash
git add commands/write-tc.md
git commit -m "feat: add /ennam-qaqc:write-tc orchestrator" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `/ennam-qaqc:review-tc`

**Files:**
- Create: `commands/review-tc.md`

**Interfaces:**
- Consumes: CONTEXT_RESOLUTION.md §2–§3; the validator CLI; SKILL.md §10–§11.
- Produces: `/ennam-qaqc:review-tc <path.feature> [--source <spec>]`.

- [ ] **Step 1: Write `commands/review-tc.md`**

````markdown
---
description: Review an existing .feature test-case file — validator, project import rules, coverage against its source, and the QC-TCs checklist — then offer fixes
argument-hint: <path.feature> [--source <spec file or id>]
allowed-tools: Read, Edit, Glob, Grep, AskUserQuestion, Bash(python3:*)
---

# Review test cases

**Request:** $ARGUMENTS

## Step 1 — Resolve context

`${CLAUDE_PLUGIN_ROOT}/docs/CONTEXT_RESOLUTION.md` §2–§3, same gate as
`/ennam-qaqc:write-tc`. Read `${CLAUDE_PLUGIN_ROOT}/skills/qc-tcs/SKILL.md`, the
context file, the template and the target file. If `--source` is given — or the
header's `Source:` names a file you can find — read it too.

## Step 2 — Checks

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_feature.py "<file>"` — each
   FAIL is Critical, each WARN a Warning.
2. Project rules (context §3, §6, §13 — or template IMPORT RULES + defaults):
   import rules; tag vocabulary, order and slots; title prefix ↔ direction; area +
   screen tag on every scenario; triage block counts vs. tags (count with grep).
3. Template shape: every template header block present, in order.
4. With a source: every requirement in the source appears in the COVERAGE block
   and in at least one scenario's traceability comment; spot-check up to 20 quoted
   strings in steps — each must appear verbatim in the source.
5. SKILL.md §10 gap review and §11 checklist.

## Step 3 — Report

```
## Review — <file>
Verdict: <Import-ready | Fix before import | Needs coverage work>

### Critical (blocks import or misleads triage)
- <file:line> <issue> → <fix>

### Warnings
- …

### Coverage (when a source was read)
Covered <n> · Partially <n> · Missing <n> · Needs clarification <n>
<rows that are not Covered>

### Checklist (SKILL.md §11)
<failed items, or "all pass">
```

## Step 4 — Offer fixes

Ask: fix all critical / fix everything / pick items / none. Edit only what was
approved, then re-run Step 2.1 and report the new counts. Review never adds
scenarios — coverage gaps go to `/ennam-qaqc:write-tc` in update mode.
````

- [ ] **Step 2: Verify**

Run: `head -5 commands/review-tc.md && grep -c 'validate_feature.py' commands/review-tc.md`
Expected: valid frontmatter; count `1`.

- [ ] **Step 3: Commit**

```bash
git add commands/review-tc.md
git commit -m "feat: add /ennam-qaqc:review-tc command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: README and CHANGELOG

**Files:**
- Create: `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Write `README.md`**

````markdown
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

```
/plugin marketplace add En-Nam/ennam-qaqc
/plugin install ennam-qaqc@ennam-qaqc
```

Local development — in the project's `.claude/settings.json`:

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
````

- [ ] **Step 2: Write `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to the `ennam-qaqc` plugin are documented here.

## [0.1.0] - 2026-10-06

### Added

- `/ennam-qaqc:init` — point at an existing project context file (any name, any
  path), or scan the repo and draft one; writes `.claude/qaqc.json` (paths only).
- `/ennam-qaqc:write-tc` — write, update or preview one `.feature` file from any
  material (brief, DR, reference file, URL), with explicit gates only.
- `/ennam-qaqc:review-tc` — validator + project rules + coverage + checklist
  review with optional fixes.
- `tc-agent` — authoring agent following the QC-TCs method.
- `qc-tcs` skill — the QC-TCs method, adapted to resolve the project context file
  instead of a fixed `PROJECT.md`.
- `scripts/validate_feature.py` + PostToolUse hook — Gherkin and universal-rule
  linter (checks G1–G14).
- Templates: default `TEMPLATE.feature` (QC-TCs), blank `PROJECT.md` with a new
  §13 for per-project import rules, `qaqc.example.json`.
```

- [ ] **Step 3: Verify**

Run: `grep -o '/ennam-qaqc:[a-z-]*' README.md | sort -u && ls commands`
Expected: the three command names match the three files `init.md`, `review-tc.md`, `write-tc.md`.

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: add README and CHANGELOG for 0.1.0" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Acceptance run (manual, in a real session)

Runs the installed plugin against the real QC-TCs material. Nothing here is
committed to the plugin; findings become fixes in the task that owns the file.

**Files:**
- Create (outside the plugin): `/Users/kai/Develop/qaqc-acceptance/` (copy of QC-TCs), `/Users/kai/Develop/qaqc-empty/`

- [ ] **Step 1: Prepare the C4K-style project**

```bash
cp -R /Users/kai/Downloads/QC-TCs /Users/kai/Develop/qaqc-acceptance
cd /Users/kai/Develop/qaqc-acceptance
mkdir -p reference && mv "test-cases/Explore & Discovery/search-form.feature" reference/
cat > .claude/settings.json <<'EOF'
{
  "extraKnownMarketplaces": {
    "ennam-qaqc": { "source": { "source": "directory", "path": "/Users/kai/Develop/ennam-qaqc" } }
  },
  "enabledPlugins": { "ennam-qaqc@ennam-qaqc": true }
}
EOF
```

- [ ] **Step 2: A1 — init with an existing file**

New Claude Code session in `/Users/kai/Develop/qaqc-acceptance`; run `/ennam-qaqc:init`.
Pass when: it offers `.claude/skills/PROJECT.md` as a candidate; writes `.claude/qaqc.json` with `projectContext` = that path, `template` = `test-cases/TEMPLATE.feature`, `testCasesRoot` = `test-cases/`; writes no other file.

- [ ] **Step 3: A2 — write from the DR**

Run `/ennam-qaqc:write-tc @DR-003-005-01-search-form.md`.
Pass when: no question except gates that genuinely apply; file created at `test-cases/Explore & Discovery/search-form.feature`; case id `DR-PA-003-005-01`; and:

```bash
F="test-cases/Explore & Discovery/search-form.feature"
python3 /Users/kai/Develop/ennam-qaqc/scripts/validate_feature.py "$F" | tail -1
for n in $(seq -w 1 27); do grep -q "AC-$n" "$F" || echo "missing AC-$n"; done
grep -hoE '@[a-z0-9-]+' "$F" | sort -u
grep -n '^# [A-Z][A-Z -]*$\|^# [A-Z][A-Z ]*(' "$F" | head -20
```
Expected: `0 FAIL`; no `missing AC-` lines; tags only from PROJECT.md §6.1/§6.2 (`@explore`, `@search-form`, …); header blocks in template order. Compare scenario count and coverage block with `reference/search-form.feature` and note big gaps.

- [ ] **Step 4: A3 — existing-file gate**

Run `/ennam-qaqc:write-tc @DR-003-005-01-search-form.md` again.
Pass when: it asks update / new / preview before dispatching; choosing preview writes nothing.

- [ ] **Step 5: A4 — no context, free-text brief**

```bash
mkdir -p /Users/kai/Develop/qaqc-empty/.claude && cp /Users/kai/Develop/qaqc-acceptance/.claude/settings.json /Users/kai/Develop/qaqc-empty/.claude/
```
New session in `/Users/kai/Develop/qaqc-empty`; run `/ennam-qaqc:write-tc Login screen: email and password fields, both required; "Sign in" button enabled only when both are filled; wrong password shows "Incorrect email or password".`
Pass when: it asks the 3-option context question; choosing 3 (defaults) leads to case-id/area questions, then a file under `test-cases/` with the plugin template's blocks; requirements numbered `BR-001…`; quoted strings only those in the brief; validator `0 FAIL`.

- [ ] **Step 6: A5 — init drafts from a scan**

In `qaqc-empty` run `/ennam-qaqc:init`, choose "scan and draft".
Pass when: it asks only unanswered questions, shows a full draft with a Provenance table, and writes nothing until approved.

- [ ] **Step 7: A6 — review**

In `qaqc-acceptance` run `/ennam-qaqc:review-tc reference/search-form.feature --source DR-003-005-01-search-form.md`.
Pass when: verdict `Import-ready`; no Critical items from the validator.

- [ ] **Step 8: Record the result**

Write the outcome of A1–A6 (pass/fail + notes) into `docs/superpowers/plans/2026-10-06-ennam-qaqc-plugin.md` under a new `## Acceptance results` heading, then:

```bash
cd /Users/kai/Develop/ennam-qaqc
git add docs/superpowers/plans/2026-10-06-ennam-qaqc-plugin.md
git commit -m "docs: record 0.1.0 acceptance results" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
