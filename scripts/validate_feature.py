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
