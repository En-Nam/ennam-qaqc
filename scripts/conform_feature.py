#!/usr/bin/env python3
"""
Feature File Conformer
======================

Purpose: Bring an existing .feature file into the plugin's import format with
         changes that cannot alter what a scenario tests. Everything that needs
         judgment is left alone — validate_feature.py reports it afterwards and
         /ennam-qaqc:conform hands it to the agent.

Usage:   python3 conform_feature.py [--config PATH] [--write] FILE [FILE ...]
         Without --write it is a dry run: a unified diff per file, nothing saved.
         Without --config, the nearest `.claude/qaqc.json` above each file is used.

Exit:    0 every file conformed (or already was), 1 a file failed its safety
         check and was left untouched, 64 usage error

Changes (each only when the project's rules call for it):
  C1 `Scenario - …`, `Scenario Outline - …`, `Examples -`, bare `Examples` → keyword with a colon
  C2 non-tag text on a tag line (a trailing `# comment`, `[BACKEND]`) → its own comment line above
  C3 tags on the `Feature:` line → added to every scenario      (importRules.featureTags = false)
  C4 description text under `Feature:` → `#` comment lines       (importRules.featureDescription = false)
  C5 a feature-level `Background:` → its steps copied into every scenario, block removed
                                                                (importRules.background = false)
  C6 scenario tags reordered: direction, check type, gates, platform, area, screen   (tagRules)
  C7 a missing title prefix added from the direction tag        (tagRules.titlePrefix)
  C8 the template's IMPORT RULES comment inserted, or restored if reworded
  C9 the `# Triage:` line recounted, or inserted after the CONVERTIBILITY heading   (tagRules.triage)

Safety check before anything is saved: the same scenarios in the same order,
titles unchanged except for an added prefix, the same steps in the same order
(plus any copied Background steps). A file that fails is left untouched.

Python 3.7+, standard library only.
"""

import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_feature as vf  # noqa: E402

DASH_RE = re.compile(r"^(\s*)(Scenario Outline|Scenario|Examples|Background|Rule)\s*[-–]\s*(.*)$")
BARE_RE = re.compile(r"^(\s*)(Examples|Background)\s*$")
KEYWORD_RE = re.compile(r"^(\s*)(Feature|Background|Rule|Scenario Outline|Scenario|Examples):\s?(.*)$")
HEADING_RE = re.compile(r"^#.*CONVERTIBILITY", re.IGNORECASE)
TRIAGE_RE = re.compile(r"^(\s*#\s*)Triage:", re.IGNORECASE)
SLOTS = ("direction", "checkType", "gates", "platform")


@dataclass
class Result:
    text: str
    changes: Set[str] = field(default_factory=set)
    problem: Optional[str] = None


def _indent(line):
    return line[:len(line) - len(line.lstrip())]


def _code_lines(lines):
    """Yield (index, stripped) for lines outside doc strings that are not blank or comments."""
    fence = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith(vf.DOCSTRING_FENCES):
            fence = stripped[:3]
            continue
        if stripped and not stripped.startswith("#"):
            yield index, stripped


def fix_lines(lines, changes):
    """C1 + C2 — line-level fixes that make the file parseable at all."""
    out = list(lines)
    for index, stripped in reversed(list(_code_lines(lines))):
        line = lines[index]
        dash = DASH_RE.match(line)
        bare = BARE_RE.match(line)
        if dash:
            rest = dash.group(3).strip()
            out[index] = "%s%s:%s" % (dash.group(1), dash.group(2), " " + rest if rest else "")
            changes.add("C1")
        elif bare:
            out[index] = "%s%s:" % (bare.group(1), bare.group(2))
            changes.add("C1")
        elif stripped.startswith("@"):
            tokens = stripped.split()
            tags = [token for token in tokens if vf.TAG_RE.match(token)]
            others = [token for token in tokens if not vf.TAG_RE.match(token)]
            if others:
                comment = " ".join(others)
                if not comment.startswith("#"):
                    comment = "# " + comment
                indent = _indent(line)
                out[index:index + 1] = [indent + comment] + ([indent + " ".join(tags)] if tags else [])
                changes.add("C2")
    return out


def extract(lines):
    """[(title, [step text, ...])] for every Scenario / Scenario Outline, in order."""
    scenarios, current = [], None
    for index, stripped in _code_lines(lines):
        keyword = KEYWORD_RE.match(lines[index])
        if keyword:
            kind = keyword.group(2)
            if kind in ("Scenario", "Scenario Outline"):
                current = (keyword.group(3).strip(), [])
                scenarios.append(current)
            elif kind != "Examples":
                current = None
            continue
        step = vf.STEP_RE.match(stripped)
        if step and current is not None:
            current[1].append(step.group(2))
    return scenarios


def safety_problem(base_lines, new_lines, background_steps, prefixes):
    before, after = extract(base_lines), extract(new_lines)
    if len(before) != len(after):
        return "scenario count changed %d -> %d" % (len(before), len(after))
    for (title_before, steps_before), (title_after, steps_after) in zip(before, after):
        if title_after != title_before and not any(title_after == p + title_before for p in prefixes):
            return "title changed: %r -> %r" % (title_before, title_after)
        if steps_after != background_steps + steps_before:
            return "steps changed in scenario %r" % title_before
    return None


def _structure(lines):
    feature, feature_tags, background, rules, scenarios, pending = None, [], None, [], [], []
    for index, stripped in _code_lines(lines):
        if stripped.startswith("@"):
            pending.append(index)
            continue
        keyword = KEYWORD_RE.match(lines[index])
        if keyword:
            kind = keyword.group(2)
            if kind == "Feature":
                feature, feature_tags = index, pending
            elif kind == "Background" and background is None and not rules and not scenarios:
                background = index
            elif kind == "Rule":
                rules.append(index)
            elif kind in ("Scenario", "Scenario Outline"):
                scenarios.append((index, pending))
        pending = []
    return feature, feature_tags, background, rules, scenarios


def _order(tags, tag_rules):
    slots = [set(tag_rules.get(name) or []) for name in SLOTS]
    areas = set(tag_rules.get("area") or [])

    def rank(tag):
        for position, slot in enumerate(slots):
            if tag in slot:
                return (position, 0)
        return (len(slots), 0 if tag in areas else 1)
    return sorted(tags, key=rank)


def _tokens(lines, indices):
    return [token for index in indices for token in lines[index].split()]


def conform(text, project):
    newline = "\r\n" if "\r\n" in text else "\n"
    original = text.replace("\r\n", "\n").split("\n")
    changes = set()
    lines = fix_lines(original, changes)
    base = list(lines)

    import_rules = project.import_rules or {}
    tag_rules = project.tag_rules or {}
    feature, feature_tags, background, rules, scenarios = _structure(lines)
    replace, delete, insert_before = {}, set(), {}
    background_steps = []
    prefixes = list((tag_rules.get("titlePrefix") or {}).values()) if isinstance(tag_rules.get("titlePrefix"), dict) else []

    lifted = []
    if import_rules.get("featureTags") is False and feature_tags:
        lifted = _tokens(lines, feature_tags)
        delete.update(feature_tags)
        changes.add("C3")

    if import_rules.get("featureDescription") is False and feature is not None:
        for index in range(feature + 1, len(lines)):
            stripped = lines[index].strip()
            if stripped.startswith("@") or KEYWORD_RE.match(lines[index]):
                break
            if stripped and not stripped.startswith("#"):
                replace[index] = _indent(lines[index]) + "# " + stripped
                changes.add("C4")

    background_block = []
    if import_rules.get("background") is False and background is not None and not rules:
        end = len(lines)
        for index in range(background + 1, len(lines)):
            stripped = lines[index].strip()
            if stripped.startswith("@") or KEYWORD_RE.match(lines[index]):
                end = index
                break
        # The block ends at its last step / table row: comments after it belong
        # to the scenario that follows.
        code = [i for i, _ in _code_lines(lines) if background < i < end]
        background_block = list(range(background, (code[-1] if code else background) + 1))
        body = [lines[i] for i in background_block[1:]]
        steps = [line for line in body if vf.STEP_RE.match(line.strip())]
        if steps:
            background_steps = [vf.STEP_RE.match(line.strip()).group(2) for line in steps]
            base_indent = _indent(steps[0])
            delete.update(background_block)
            changes.add("C5")

    for index, tag_indices in scenarios:
        tags = _tokens(lines, tag_indices)
        merged = tags + [tag for tag in lifted if tag not in tags]
        if tag_rules and any(isinstance(tag_rules.get(name), list) for name in SLOTS):
            ordered = _order(merged, tag_rules)
            if ordered != merged:
                changes.add("C6")
            merged = ordered
        if merged != tags or len(tag_indices) > 1:
            new_line = _indent(lines[index]) + " ".join(merged)
            if tag_indices:
                replace[tag_indices[0]] = new_line
                delete.update(tag_indices[1:])
            else:
                insert_before.setdefault(index, []).append(new_line)

        if prefixes:
            keyword = KEYWORD_RE.match(lines[index])
            title = keyword.group(3).strip()
            direction = next((tag for tag in merged if tag in tag_rules["titlePrefix"]), None)
            if direction and not any(title.startswith(p) for p in prefixes):
                replace[index] = "%s%s: %s%s" % (keyword.group(1), keyword.group(2),
                                                 tag_rules["titlePrefix"][direction], title)
                changes.add("C7")

        if "C5" in changes:
            first_step = next((i for i, stripped in _code_lines(lines)
                               if i > index and vf.STEP_RE.match(stripped)), None)
            following = [i for i, _ in scenarios if i > index]
            if first_step is not None and (not following or first_step < following[0]):
                step_indent = _indent(lines[first_step])
                copied = [step_indent + line[len(base_indent):] if line.startswith(base_indent) else line
                          for line in body if line.strip()]
                insert_before.setdefault(first_step, []).extend(copied)

    lines = []
    for index, line in enumerate(base):
        lines.extend(insert_before.get(index, []))
        if index not in delete:
            lines.append(replace.get(index, line))

    lines = _import_comment(lines, project.import_comment, changes)
    if isinstance(tag_rules.get("triage"), dict):
        lines = _triage_line(lines, tag_rules["triage"], changes)

    problem = safety_problem(base, lines, background_steps, prefixes)
    if problem:
        return Result(text, set(), problem)
    if lines == original:
        return Result(text, set(), None)
    return Result(newline.join(lines), changes, None)


def _feature_index(lines):
    return next((i for i, _ in _code_lines(lines) if KEYWORD_RE.match(lines[i]) and
                 KEYWORD_RE.match(lines[i]).group(2) == "Feature"), None)


def _import_comment(lines, comment, changes):
    feature = _feature_index(lines)
    if not comment or feature is None:
        return lines
    start = next((i for i in range(feature) if lines[i].strip().startswith("# IMPORT RULES")), None)
    if start is not None:
        end = start
        while end < feature and lines[end].strip().startswith("#"):
            end += 1
        if [line.strip() for line in lines[start:end]] == comment:
            return lines
        changes.add("C8")
        return lines[:start] + list(comment) + lines[end:]
    anchor = feature
    while anchor > 0 and lines[anchor - 1].strip().startswith("@"):
        anchor -= 1
    block = list(comment)
    if anchor > 0 and lines[anchor - 1].strip():
        block = [""] + block
    changes.add("C8")
    return lines[:anchor] + block + lines[anchor:]


def _triage_line(lines, triage, changes):
    feature = _feature_index(lines)
    if feature is None:
        return lines
    scenarios = []
    _, _, _, _, found = _structure(lines)
    for index, tag_indices in found:
        scenarios.append(vf.Scenario(index, "", False, tags=[(0, tag) for tag in _tokens(lines, tag_indices)]))
    automatable, manual, blocked = vf.triage_counts(triage, scenarios)
    text = "Triage: %d automatable / %d manual / %d blocked (%d scenarios)" % (
        automatable, manual, blocked, len(scenarios))
    for index in range(feature):
        existing = TRIAGE_RE.match(lines[index])
        if existing:
            wanted = existing.group(1) + text
            if lines[index] != wanted:
                lines = lines[:index] + [wanted] + lines[index + 1:]
                changes.add("C9")
            return lines
    heading = next((i for i in range(feature) if HEADING_RE.match(lines[i].strip())), None)
    if heading is None:
        return lines
    changes.add("C9")
    return lines[:heading + 1] + ["#   " + text] + lines[heading + 1:]


def run(paths, out, write, config):
    status = 0
    for path in paths:
        project = vf.rules_for(path, config)
        for note in project.notes:
            out.write("note: %s\n" % note)
        text = Path(path).read_text(encoding="utf-8")
        result = conform(text, project)
        if result.problem:
            out.write("%s: SKIPPED - safety check failed (%s); file left untouched\n" % (path, result.problem))
            status = 1
            continue
        if not result.changes:
            out.write("%s: already conformant\n" % path)
            continue
        label = " ".join(sorted(result.changes))
        if write:
            Path(path).write_text(result.text, encoding="utf-8")
            out.write("%s: written (%s)\n" % (path, label))
        else:
            out.writelines(difflib.unified_diff(text.splitlines(True), result.text.splitlines(True),
                                                path, path + " (conformed)"))
            out.write("%s: would change (%s) - dry run, nothing written\n" % (path, label))
    return status


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    write, config = False, None
    while args and args[0].startswith("--"):
        flag = args.pop(0)
        if flag == "--write":
            write = True
        elif flag == "--config" and args:
            config = Path(args.pop(0))
        else:
            args = []
            break
    if not args:
        sys.stderr.write("usage: conform_feature.py [--config PATH] [--write] FILE [FILE ...]\n")
        return 64
    return run(args, sys.stdout, write, config)


if __name__ == "__main__":
    sys.exit(main())
