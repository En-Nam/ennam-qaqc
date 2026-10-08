#!/usr/bin/env python3
"""
Conform Run State
=================

Purpose: Make /ennam-qaqc:conform resumable across interruptions and sessions.
         Records each file's status and a SHA-256 of its content right after
         conform last wrote it, in `.claude/qaqc-conform/state.json` at the
         repo root.

Usage:   python3 conform_state.py add FILE ...                 # register (keeps existing status)
         python3 conform_state.py gate FILE ...                # may conform edit these in place?
         python3 conform_state.py mark FILE STATUS [--note T]  # record status + content hash
         python3 conform_state.py next [--status S ...] [--limit N]
         python3 conform_state.py summary
         python3 conform_state.py reset FILE ...               # back to pending (re-upgrade)

Statuses: pending · formatted · upgraded · needs-answers · skipped · failed

Gate:    clean      - no uncommitted changes
         resumable  - uncommitted changes that conform made: the content still
                      matches the hash recorded at its last `mark`
         BLOCKED    - uncommitted changes conform did not make, or the file
                      changed after conform's last write (exit 1)

Exit:    0 ok, 1 gate blocked a file, 64 usage error

Python 3.7+, standard library only.
"""

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

STATE_PATH = Path(".claude") / "qaqc-conform" / "state.json"
STATUSES = ("pending", "formatted", "upgraded", "needs-answers", "skipped", "failed")


def repo_root(start):
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                             capture_output=True, text=True, check=True)
        return Path(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(start)


def rel(root, path):
    absolute = (Path.cwd() / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        return absolute.relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def load(root):
    path = root / STATE_PATH
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"version": 1, "started": now(), "files": {}}


def save(root, state):
    path = root / STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def uncommitted(root, name):
    out = subprocess.run(["git", "status", "--porcelain", "--", name], cwd=root,
                         capture_output=True, text=True)
    return bool(out.stdout.strip())


def cmd_add(root, state, args, out):
    for name in args.files:
        state["files"].setdefault(rel(root, name), {"status": "pending", "updated": now()})
    save(root, state)
    out.write("registered %d file(s)\n" % len(args.files))
    return 0


def cmd_gate(root, state, args, out):
    blocked = False
    for name in args.files:
        key = rel(root, name)
        if not (root / key).is_file():
            out.write("%s: BLOCKED - file not found\n" % key)
            blocked = True
            continue
        if not uncommitted(root, key):
            out.write("%s: clean\n" % key)
            continue
        entry = state["files"].get(key)
        if entry and entry.get("sha256") == digest(root / key):
            out.write("%s: resumable - uncommitted changes are conform's own (%s)\n" % (key, entry["status"]))
        elif entry and entry.get("sha256"):
            out.write("%s: BLOCKED - changed since conform last wrote it; commit or restore it first\n" % key)
            blocked = True
        else:
            out.write("%s: BLOCKED - uncommitted changes not made by conform; commit or stash them first\n" % key)
            blocked = True
    return 1 if blocked else 0


def cmd_mark(root, state, args, out):
    key = rel(root, args.file)
    entry = state["files"].setdefault(key, {})
    entry.update({"status": args.status, "updated": now()})
    if (root / key).is_file():
        entry["sha256"] = digest(root / key)
    if args.note:
        entry["note"] = args.note
    save(root, state)
    out.write("%s: %s\n" % (key, args.status))
    return 0


def cmd_next(root, state, args, out):
    wanted = args.status or ["pending", "formatted"]
    names = [name for name, entry in state["files"].items() if entry.get("status") in wanted]
    for name in names[:args.limit] if args.limit else names:
        out.write(name + "\n")
    return 0


def cmd_summary(root, state, args, out):
    counts = {status: 0 for status in STATUSES}
    for entry in state["files"].values():
        counts[entry.get("status", "pending")] = counts.get(entry.get("status", "pending"), 0) + 1
    out.write(" · ".join("%s %d" % (status, counts[status]) for status in STATUSES) + "\n")
    for name, entry in state["files"].items():
        note = (" - " + entry["note"]) if entry.get("note") else ""
        out.write("  %-14s %s%s\n" % (entry.get("status", "pending"), name, note))
    return 0


def cmd_reset(root, state, args, out):
    for name in args.files:
        state["files"][rel(root, name)] = {"status": "pending", "updated": now()}
    save(root, state)
    out.write("reset %d file(s) to pending\n" % len(args.files))
    return 0


def parser():
    p = argparse.ArgumentParser(prog="conform_state.py")
    sub = p.add_subparsers(dest="command")
    for name in ("add", "gate", "reset"):
        sub.add_parser(name).add_argument("files", nargs="+")
    mark = sub.add_parser("mark")
    mark.add_argument("file")
    mark.add_argument("status", choices=STATUSES)
    mark.add_argument("--note")
    nxt = sub.add_parser("next")
    nxt.add_argument("--status", nargs="+", choices=STATUSES)
    nxt.add_argument("--limit", type=int)
    sub.add_parser("summary")
    return p


def main(argv=None, out=None, root=None):
    out = out or sys.stdout
    try:
        args = parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 64
    if not args.command:
        sys.stderr.write("usage: conform_state.py {add,gate,mark,next,summary,reset} ...\n")
        return 64
    root = Path(root) if root else repo_root(Path.cwd())
    handlers = {"add": cmd_add, "gate": cmd_gate, "mark": cmd_mark, "next": cmd_next,
                "summary": cmd_summary, "reset": cmd_reset}
    return handlers[args.command](root, load(root), args, out)


if __name__ == "__main__":
    sys.exit(main())
