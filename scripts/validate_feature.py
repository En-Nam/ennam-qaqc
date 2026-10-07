#!/usr/bin/env python3
"""
Feature File Validator
======================

Purpose: Lint a Gherkin .feature test-case file against
         1. the rules every ennam-qaqc project shares: Gherkin validity plus the
            QC-TCs universal rules (SKILL.md §4.2) — codes G*;
         2. the project's importer rules, when `.claude/qaqc.json` holds an
            `importRules` object (written by /ennam-qaqc:init from the context
            file's §13) — codes P*.

Usage:   python3 validate_feature.py [--config PATH] FILE [FILE ...]
         python3 validate_feature.py --hook     # PostToolUse payload on stdin

         Without --config, the nearest `.claude/qaqc.json` above each file is used.

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
  G15 WARN two scenarios with the same title
  G16 WARN a When/Then step a tester cannot observe in the product (server-side
           inspection, delivery logs, database records, source code)

Import rules (only when importRules sets them):
  P1  FAIL tags on the `Feature:` line          (featureTags: false)
  P2  FAIL description text under `Feature:`     (featureDescription: false)
  P3  FAIL a `Background:` block                 (background: false)
  P4  FAIL a `Rule:` block                       (rule: false)
  P5  FAIL a scenario title over the limit       (maxTitleLength: N)
  P6  FAIL a tag over the limit, incl. the "@"   (maxTagLength: N)

Python 3.7+, standard library only.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

KEYWORD_RE = re.compile(r"^(Feature|Background|Rule|Scenario Outline|Scenario|Examples):(.*)$")
MISSING_COLON_RE = re.compile(r"^(Feature|Background|Rule|Scenario Outline|Scenario|Examples)\s*(-|–|$)")
STEP_RE = re.compile(r"^(Given|When|Then|And|But|\*)\s+(\S.*)$")
TAG_RE = re.compile(r"^@[^\s@#]+$")
PLACEHOLDER_RE = re.compile(r"<([^<>]+)>")
UNOBSERVABLE_RE = re.compile(
    r"server[- ]side|\bdelivery logs?\b|\b(database|db) (record|row|table)s?\b|\bsource code\b"
    r"|\binspect\w*\b[^.]*\b(logs?|records?|database|backend|generator)\b",
    re.IGNORECASE,
)
TAG_TARGETS = ("Feature", "Rule", "Scenario", "Scenario Outline", "Examples")
DOCSTRING_FENCES = ('"""', "`" * 3)  # built, not typed: a literal fence breaks markdown that embeds this file
CONFIG_RELATIVE = Path(".claude") / "qaqc.json"


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


@dataclass
class Facts:
    """Structure the import-rule checks need, collected while parsing."""
    feature_tag_line: Optional[int] = None
    description_line: Optional[int] = None
    background_lines: List[int] = field(default_factory=list)
    rule_lines: List[int] = field(default_factory=list)
    tags: List[Tuple[int, str]] = field(default_factory=list)


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


def validate(text, rules=None):
    """Lint `text`. `rules` is the importRules dict from .claude/qaqc.json, or None."""
    findings = []

    def add(code, severity, line, message):
        findings.append(Finding(code, severity, line, message))

    facts = Facts()
    feature_lines = []
    scenarios = []
    current = None          # Scenario being filled
    block = None            # None | feature | background | scenario | examples | orphan
    feature_header = False  # directly under the Feature: line, before any other keyword
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
            tokens = line.split()
            bad = [token for token in tokens if not TAG_RE.match(token)]
            if bad:
                add("G4", "FAIL", no, "tag line holds non-tag text %r; a tag line may contain only @tags" % " ".join(bad))
            facts.tags.extend((no, token) for token in tokens if TAG_RE.match(token))
            pending_tag = no
            continue

        keyword = KEYWORD_RE.match(line)
        if keyword:
            kw, rest = keyword.group(1), keyword.group(2).strip()
            if pending_tag is not None and kw not in TAG_TARGETS:
                add("G5", "FAIL", pending_tag,
                    "tags must precede Feature:, Rule:, Scenario:, Scenario Outline: or Examples:, not %s:" % kw)
            if kw == "Feature" and pending_tag is not None:
                facts.feature_tag_line = pending_tag
            pending_tag = None
            block_has_body = False
            feature_header = kw == "Feature"
            if kw == "Feature":
                feature_lines.append(no)
                block, current = "feature", None
            elif kw == "Rule":
                facts.rule_lines.append(no)
                block, current = "feature", None
            elif kw == "Background":
                facts.background_lines.append(no)
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
        elif feature_header and facts.description_line is None:
            facts.description_line = no
        # Otherwise: description text directly under a keyword line. Valid Gherkin;
        # whether the project allows it under Feature: is import rule P2.

    if pending_tag is not None:
        add("G5", "FAIL", pending_tag, "tag line at end of file has no Scenario:")
    if len(feature_lines) != 1:
        where = feature_lines[1] if len(feature_lines) > 1 else 1
        add("G1", "FAIL", where, "found %d Feature: lines; a file holds exactly one" % len(feature_lines))

    seen_titles = {}
    for scenario in scenarios:
        _check_scenario(scenario, add)
        if scenario.title in seen_titles:
            add("G15", "WARN", scenario.line,
                "same title as the scenario on line %d; one title should name one behaviour" % seen_titles[scenario.title])
        else:
            seen_titles[scenario.title] = scenario.line

    if rules:
        _check_import_rules(rules, facts, scenarios, add)

    findings.sort(key=lambda f: (f.line, f.code))
    return findings


def _check_scenario(sc, add):
    keywords = {kw for _, kw, _ in sc.steps} | sc.inherited
    missing = [kw for kw in ("Given", "When", "Then") if kw not in keywords]
    if missing:
        add("G6", "FAIL", sc.line,
            "scenario %r has no %s step (And/But do not count)" % (_short(sc.title), "/".join(missing)))

    phase = None
    for no, kw, text in sc.steps:
        if kw in ("Given", "When", "Then"):
            phase = kw
        if phase in ("When", "Then") and UNOBSERVABLE_RE.search(text):
            add("G16", "WARN", no,
                "%r is not observable in the product; record the rule as not UI-observable instead of a scenario"
                % _short(text))

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


def _limit(rules, key):
    value = rules.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _check_import_rules(rules, facts, scenarios, add):
    if rules.get("featureTags") is False and facts.feature_tag_line:
        add("P1", "FAIL", facts.feature_tag_line,
            "tags on the Feature: line are not allowed (importRules.featureTags=false); put them on every scenario")
    if rules.get("featureDescription") is False and facts.description_line:
        add("P2", "FAIL", facts.description_line,
            "description text under Feature: is not allowed (importRules.featureDescription=false); write it as # comments")
    if rules.get("background") is False:
        for line in facts.background_lines:
            add("P3", "FAIL", line,
                "Background: is not allowed (importRules.background=false); repeat the Given in every scenario")
    if rules.get("rule") is False:
        for line in facts.rule_lines:
            add("P4", "FAIL", line, "Rule: is not allowed (importRules.rule=false)")
    max_title = _limit(rules, "maxTitleLength")
    if max_title is not None:
        for sc in scenarios:
            if len(sc.title) > max_title:
                add("P5", "FAIL", sc.line,
                    "title is %d characters; the importer allows %d (importRules.maxTitleLength)" % (len(sc.title), max_title))
    max_tag = _limit(rules, "maxTagLength")
    if max_tag is not None:
        for line, tag in facts.tags:
            if len(tag) > max_tag:
                add("P6", "FAIL", line,
                    "tag %r is %d characters; the importer allows %d (importRules.maxTagLength)"
                    % (_short(tag), len(tag), max_tag))


def find_config(path):
    """Nearest .claude/qaqc.json at or above `path`, or None."""
    start = Path(path).resolve()
    for folder in [start] + list(start.parents):
        candidate = folder / CONFIG_RELATIVE
        if candidate.is_file():
            return candidate
    return None


def load_import_rules(config_path):
    """(rules or None, note or None). A config without importRules is not an error."""
    if config_path is None:
        return None, None
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, "could not read %s (%s); import rules not checked" % (config_path, exc.__class__.__name__)
    rules = data.get("importRules") if isinstance(data, dict) else None
    if rules is None:
        return None, None
    if not isinstance(rules, dict):
        return None, "%s: importRules is not an object; import rules not checked" % config_path
    return rules, None


def rules_for(path, config=None):
    """Import rules for one file: an explicit config, else the nearest .claude/qaqc.json."""
    config_path = config if config is not None else find_config(Path(path).parent)
    rules, note = load_import_rules(config_path)
    return rules, (config_path if rules else None), note


def validate_file(path, rules=None):
    return validate(Path(path).read_text(encoding="utf-8"), rules)


def run_cli(paths, out, config=None):
    failed = False
    for path in paths:
        rules, rules_source, note = rules_for(path, config)
        if note:
            out.write("note: %s\n" % note)
        if rules_source:
            out.write("import rules: %s\n" % rules_source)
        findings = validate_file(path, rules)
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
    rules, _, _ = rules_for(path)
    fails = [f for f in validate_file(path, rules) if f.severity == "FAIL"]
    if not fails:
        return 0
    err.write("validate_feature.py: %s has %d FAIL finding(s); fix them before continuing.\n" % (path, len(fails)))
    for finding in fails:
        err.write(finding.format(path) + "\n")
    return 2


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if args == ["--hook"]:
        return run_hook(sys.stdin, sys.stderr)
    config = None
    if args[:1] == ["--config"]:
        if len(args) < 2:
            args = []
        else:
            config, args = Path(args[1]), args[2:]
    if not args or args[0].startswith("-"):
        sys.stderr.write("usage: validate_feature.py [--config PATH] FILE [FILE ...] | --hook\n")
        return 64
    return run_cli(args, sys.stdout, config)


if __name__ == "__main__":
    sys.exit(main())
