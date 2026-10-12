#!/usr/bin/env python3
"""
Name Files and Folders by Id
============================

Purpose: Put the identifiers into the test-case paths, so a search for an id
         finds the file and folders sort by epic:

           test-cases/EP-PA-005-Collections/DR-PA-005-003-01-create-collection.feature

         file   = '<case id>-<name>.feature'   (the case id from the '# Feature:' line)
         folder = 'EP-<code>-<epic>-<name>'    (from the case ids of the files inside it)

         Only the id prefix changes. The routing tags do not: the screen tag stays the
         file name without its id, the area tag the folder name without its id.

Usage:   python3 name_by_id.py [--config PATH] [--write] PATH [PATH ...]
         PATH is a .feature file or a folder (searched recursively). Without --write it
         is a dry run: the plan, nothing moved. Without --config, the nearest
         .claude/qaqc.json above the working directory.

Rules:   - needs caseIds in qaqc.json (and not caseIds.names = false); otherwise nothing is renamed
         - a file is renamed only when its case id is valid (matches caseIds.pattern); a header that
           still holds several ids ('US-003 / DR-PA-005-003-01 v1.1, EP-005') is named by the one
           valid id in it. No valid id, or two different ones, keeps the name
         - an existing id prefix is replaced, never doubled ('DR-001-001-01-x' -> 'DR-PA-001-001-01-x')
         - the epic is the pattern's (?P<epic>...) group, else the 2nd number group of
           'DR-<CODE>-<EPIC>-<US>-<NN>'; the code is the (?P<code>...) group
         - a folder is renamed only when every file in it with a valid case id names the same
           epic; the test-cases root itself is never renamed
         - a target that already exists is never overwritten
         - tracked paths move with 'git mv' (git diff -M HEAD shows a rename); untracked ones
           with a plain rename. Nothing is committed.
         - entries in .claude/qaqc-conform/ (state and reports) follow the rename

Exit:    0 ok (renamed, or nothing to do), 1 a rename was refused (conflict or collision),
         64 usage error

Python 3.7+, standard library only.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_feature as vf  # noqa: E402

# 'DR-PA-005-003-01-', 'DR-001-001-01-', 'EP-PA-005-', 'EP-005-', 'US-001-' at the start of a name
ID_PREFIX_RE = re.compile(r"^[A-Z]{2,}(?:-[A-Z][A-Z0-9]*)?(?:-\d+)+-(?=\S)")
ID_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+")
DEFAULT_SHAPE_RE = re.compile(r"^[A-Z]+-(?P<code>[A-Z][A-Z0-9]*)-(?P<epic>\d+)-\d+-\d+$")
CONFORM_DIR = Path(".claude") / "qaqc-conform"


def strip_id(name):
    """The name without a leading id prefix: 'DR-PA-005-003-01-create-collection' -> 'create-collection'."""
    return ID_PREFIX_RE.sub("", name, count=1)


def _matches(value, case_rules):
    pattern = case_rules.get("pattern")
    try:
        return bool(re.fullmatch(pattern, value) if isinstance(pattern, str) else DEFAULT_SHAPE_RE.match(value))
    except re.error:
        return False


def valid_case_id(case_id, case_rules):
    """The id to name by: the case id when it fully matches caseIds.pattern (or, without a pattern,
    the default shape) - or, in a header still holding several ids ('US-003 / DR-PA-005-003-01 v1.1'),
    the one id in it that does. None when there is no such id or more than one."""
    if not case_id or not isinstance(case_rules, dict):
        return None
    if _matches(case_id, case_rules):
        return case_id
    found = {token for token in ID_TOKEN_RE.findall(case_id) if _matches(token, case_rules)}
    return found.pop() if len(found) == 1 else None


def folder_id(case_id, case_rules):
    """'EP-<code>-<epic>' (or 'EP-<epic>' without a code) for a valid case id, else None."""
    pattern = (case_rules or {}).get("pattern")
    groups = {}
    if isinstance(pattern, str):
        try:
            match = re.fullmatch(pattern, case_id)
            groups = match.groupdict() if match else {}
        except re.error:
            groups = {}
    if not groups.get("epic"):
        shape = DEFAULT_SHAPE_RE.match(case_id)
        if not shape:
            return None
        groups = dict(shape.groupdict(), **{k: v for k, v in groups.items() if v})
    code = groups.get("code")
    return "EP-%s-%s" % (code, groups["epic"]) if code else "EP-%s" % groups["epic"]


def file_target(path, case_id):
    stem = strip_id(path.stem)
    return path.with_name("%s-%s%s" % (case_id, stem, path.suffix))


def folder_target(folder, fid):
    return folder.with_name("%s-%s" % (fid, strip_id(folder.name)))


def collect(paths):
    files = []
    for raw in paths:
        path = Path(raw)
        found = sorted(path.rglob("*.feature")) if path.is_dir() else [path]
        files.extend(p for p in found if p.suffix == ".feature" and p.name != "TEMPLATE.feature")
    seen, unique = set(), []
    for path in files:
        key = path.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _case_id(path):
    return vf.identifiers(path.read_text(encoding="utf-8"), {})["case_id"]


def plan(files, case_rules, root):
    """[(kind, old, new or None, note)] — kind 'file' or 'folder'; new None means kept."""
    steps, folders = [], {}
    root = root.resolve() if root else None
    for path in files:
        case_id = _case_id(path)
        valid = valid_case_id(case_id, case_rules)
        folders.setdefault(path.parent.resolve(), path.parent)
        if not valid:
            reason = "no case id" if not case_id or case_id.upper() in ("<TODO>", "TODO") else \
                "no single valid case id in %r" % case_id
            steps.append(("file", path, None, reason + " - name kept"))
            continue
        target = file_target(path, valid)
        if target.name == path.name:
            continue
        if target.exists():
            steps.append(("file", path, None, "%s already exists - not overwritten" % target.name))
        else:
            steps.append(("file", path, target, ""))
    for resolved, folder in sorted(folders.items()):
        if root is not None and resolved == root:
            continue
        # Every file in the folder decides its name, not only the files passed in.
        ids = [valid_case_id(_case_id(p), case_rules) for p in sorted(folder.glob("*.feature"))
               if p.name != "TEMPLATE.feature"]
        fids = sorted({folder_id(i, case_rules) for i in ids if i} - {None})
        if not fids:
            continue
        if len(fids) > 1:
            steps.append(("folder", folder, None, "its files name different epics (%s) - name kept" % ", ".join(fids)))
            continue
        target = folder_target(folder, fids[0])
        if target.name == folder.name:
            continue
        if target.exists():
            steps.append(("folder", folder, None, "%s already exists - not overwritten" % target.name))
        else:
            steps.append(("folder", folder, target, ""))
    return steps


def _git(args, cwd):
    try:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    except OSError:
        return None


def _tracked(path):
    out = _git(["ls-files", "--", path.name], path.parent)
    return bool(out and out.returncode == 0 and out.stdout.strip())


def move(old, new):
    if _tracked(old):
        out = _git(["mv", "--", old.name, str(new.resolve())], old.parent)
        if out and out.returncode == 0:
            return
    old.rename(new)


def _rel(path, repo_root):
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return None


def follow_state(repo_root, old_rel, new_rel):
    """Re-key .claude/qaqc-conform/state.json entries and move report files under the renamed path."""
    state_path = repo_root / CONFORM_DIR / "state.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        files = state.get("files", {})
        renamed = {}
        for key, entry in files.items():
            if key == old_rel or key.startswith(old_rel + "/"):
                key = new_rel + key[len(old_rel):]
            renamed[key] = entry
        state["files"] = renamed
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    reports = repo_root / CONFORM_DIR / "reports"
    for suffix in (".md", ""):
        source = reports / (old_rel + suffix)
        if source.exists():
            target = reports / (new_rel + suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)


def run(paths, out, write, config):
    config = Path(config) if config else vf.find_config(Path.cwd())
    data = {}
    if config is not None:
        try:
            data = json.loads(Path(config).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            out.write("FAIL: cannot read %s (%s)\n" % (config, type(exc).__name__))
            return 1
    case_rules = data.get("caseIds") if isinstance(data, dict) else None
    if not isinstance(case_rules, dict) or case_rules.get("names") is False:
        out.write("note: caseIds not set (or caseIds.names is false) - nothing renamed\n")
        return 0
    repo_root = Path(config).resolve().parent.parent
    root = repo_root / (data.get("testCasesRoot") or "test-cases")
    steps = plan(collect(paths), case_rules, root)
    refused = False
    # Files first, inside their current folder; then the folders (deepest first).
    folders = sorted((s for s in steps if s[0] == "folder"), key=lambda s: -len(s[1].resolve().parts))
    for kind, old, new, note in [s for s in steps if s[0] == "file"] + folders:
        if new is None:
            refused = refused or "already exists" in note or "different epics" in note
            out.write("keep    %s - %s\n" % (old, note))
            continue
        out.write("%s %s -> %s\n" % ("renamed" if write else "rename ", old, new.name))
        if write:
            old_rel, new_rel = _rel(old, repo_root), _rel(new, repo_root)
            move(old, new)
            if old_rel and new_rel:
                follow_state(repo_root, old_rel, new_rel)
    renames = sum(1 for s in steps if s[2] is not None)
    out.write("%d rename(s)%s\n" % (renames, "" if write else " planned (dry run - add --write to apply)"))
    return 1 if refused else 0


def main(argv=None, out=None):
    args = sys.argv[1:] if argv is None else list(argv)
    write, config = False, None
    while args and args[0].startswith("--"):
        flag = args.pop(0)
        if flag == "--write":
            write = True
        elif flag == "--config" and args:
            config = args.pop(0)
        else:
            args = []
            break
    if not args:
        sys.stderr.write("usage: name_by_id.py [--config PATH] [--write] PATH [PATH ...]\n")
        return 64
    return run(args, out or sys.stdout, write, config)


if __name__ == "__main__":
    sys.exit(main())
