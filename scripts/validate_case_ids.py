#!/usr/bin/env python3
"""
Case & Scenario ID Validator (suite-wide)
=========================================

Purpose: The identifier checks one file cannot make on its own — the ennam-ba
         rule that an identifier is unique, comes from a registry and is never
         reused, applied across the whole test-case suite and its git history.
         Per-file checks (shape, registry code, one id per scenario) are
         validate_feature.py P14-P16.

Usage:   python3 validate_case_ids.py [--config PATH] [--root DIR] [--no-history]
         Without --config, the nearest .claude/qaqc.json above the working directory.
         Without --root, qaqc.json testCasesRoot.

Checks:
  S1 FAIL two .feature files share a case id
  S2 FAIL a case id matches no DR detail_id        (only when caseIds.drSources is set)
     WARN caseIds.drSources is empty or absolute; the S2 check is skipped
  S3 FAIL a file's 'next' scenario id went down since HEAD
  S4 FAIL a scenario id new since HEAD is below HEAD's 'next' - a retired id reused
  S5 FAIL a scenario whose title occurs once at HEAD and once now has a different id - renumbered
     (titles duplicated on either side are skipped; G15 warns about duplicate titles)
  S6 WARN scenario ids retired since HEAD (scenario removed) - listed; never reuse them
  S7 WARN a file without a case id
  S1, S2 and S7 need caseIds in qaqc.json; S3-S6 need tagRules.scenarioId. Without them the check
  is skipped with a note, so a project that has not refreshed its rules sees nothing new.

Exit:    0 no FAIL, 1 at least one FAIL, 64 usage error
         1 also when .claude/qaqc.json cannot be read or parsed as a JSON object

Python 3.7+, standard library only.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_feature as vf  # noqa: E402

DETAIL_ID_RE = re.compile(r"^detail_id:\s*['\"]?([^'\"#\s]+)", re.MULTILINE)


def dr_ids(repo_root, pattern):
    """Every frontmatter detail_id in the files matching `pattern` (a glob under the repo root)."""
    found = set()
    for path in repo_root.glob(pattern):
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.startswith("---"):
            match = DETAIL_ID_RE.search(text.split("\n---", 1)[0])
            if match:
                found.add(match.group(1))
    return found


def head_text(repo_root, rel):
    try:
        # "./" makes git resolve the path against cwd, so .claude/ need not sit at the git toplevel.
        out = subprocess.run(["git", "show", "HEAD:./%s" % rel], cwd=repo_root, capture_output=True,
                             encoding="utf-8", errors="replace")
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def history_findings(rel, now, before, spec):
    findings = []
    if before is None:
        return findings
    head_ids = {number: title for number, title in before["scenarios"] if number is not None}
    now_ids = {number: title for number, title in now["scenarios"] if number is not None}
    if not head_ids:
        return findings
    fmt = lambda number: vf.format_scenario_id(spec, number)  # noqa: E731
    head_next = before["next"] or max(head_ids) + 1
    if now["next"] is not None and before["next"] is not None and now["next"] < before["next"]:
        findings.append(("FAIL", "S3", "%s: 'next' went down from %s to %s; ids are never reused"
                         % (rel, fmt(before["next"]), fmt(now["next"]))))
    for number in sorted(set(now_ids) - set(head_ids)):
        if number < head_next:
            findings.append(("FAIL", "S4", "%s: %s is new since HEAD but below HEAD's next %s - a retired id is "
                             "being reused; use the next number" % (rel, fmt(number), fmt(head_next))))
    head_titles = Counter(title for _, title in before["scenarios"])
    now_titles = Counter(title for _, title in now["scenarios"])
    head_by_title = {title: number for number, title in head_ids.items()}
    for number, title in sorted(now_ids.items()):
        old = head_by_title.get(title)
        if head_titles[title] != 1 or now_titles[title] != 1:
            continue  # duplicate titles cannot be matched by title; G15 warns about them
        if old is not None and old != number:
            findings.append(("FAIL", "S5", "%s: %r was %s at HEAD and is now %s - scenario ids never change"
                             % (rel, title, fmt(old), fmt(number))))
    retired = sorted(set(head_ids) - set(now_ids))
    if retired:
        findings.append(("WARN", "S6", "%s: retired since HEAD: %s - never reuse them"
                         % (rel, ", ".join(fmt(number) for number in retired))))
    return findings


def run(args, out):
    config = Path(args.config) if args.config else vf.find_config(Path.cwd())
    if config is None:
        out.write("note: no .claude/qaqc.json found - nothing to check (run /ennam-qaqc:init)\n")
        return 0
    if not Path(config).is_file():
        out.write("FAIL: cannot read %s (FileNotFoundError)\n" % config)
        return 1
    try:
        data = json.loads(Path(config).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("top level is not a JSON object")
    except (OSError, ValueError) as exc:
        out.write("FAIL: cannot read %s (%s)\n" % (config, type(exc).__name__))
        return 1
    repo_root = Path(config).resolve().parent.parent
    root = Path(args.root) if args.root else repo_root / (data.get("testCasesRoot") or "test-cases")
    spec = (data.get("tagRules") or {}).get("scenarioId")
    case_rules = data.get("caseIds") if isinstance(data.get("caseIds"), dict) else None
    if case_rules is None:
        out.write("note: caseIds not set - case ids not checked\n")

    findings, by_case = [], defaultdict(list)
    known = None
    pattern = (case_rules or {}).get("drSources")
    if isinstance(pattern, str):
        if not pattern.strip() or pattern.startswith("/") or Path(pattern).is_absolute():
            findings.append(("WARN", "S2", "caseIds.drSources must be a glob relative to the repo root; "
                             "DR existence not checked"))
        else:
            known = dr_ids(repo_root, pattern)

    files = sorted(path for path in root.rglob("*.feature") if path.name != "TEMPLATE.feature")
    for path in files:
        try:
            rel = path.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            rel = str(path)
        now = vf.identifiers(path.read_text(encoding="utf-8"), spec or {})
        case_id = now["case_id"]
        if case_rules is None:
            pass
        elif not case_id or case_id.upper() in ("<TODO>", "TODO"):
            findings.append(("WARN", "S7", "%s: no case id" % rel))
        else:
            by_case[case_id].append(rel)
            if known is not None and case_id not in known:
                findings.append(("FAIL", "S2", "%s: case id %s matches no DR detail_id under %s"
                                 % (rel, case_id, case_rules["drSources"])))
        if isinstance(spec, dict) and not args.no_history:
            before = head_text(repo_root, rel)
            findings.extend(history_findings(rel, now, vf.identifiers(before, spec) if before is not None else None, spec))
    for case_id, paths in sorted(by_case.items()):
        if len(paths) > 1:
            findings.append(("FAIL", "S1", "case id %s is claimed by %d files: %s" % (case_id, len(paths), ", ".join(paths))))

    for severity, code, message in findings:
        out.write("%s %s %s\n" % (severity, code, message))
    fails = sum(1 for severity, _, _ in findings if severity == "FAIL")
    out.write("%d file(s), %d case id(s): %d FAIL, %d WARN\n"
              % (len(files), len(by_case), fails, len(findings) - fails))
    return 1 if fails else 0


def main(argv=None, out=None):
    parser = argparse.ArgumentParser(prog="validate_case_ids.py")
    parser.add_argument("--config")
    parser.add_argument("--root")
    parser.add_argument("--no-history", action="store_true")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 64
    return run(args, out or sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
