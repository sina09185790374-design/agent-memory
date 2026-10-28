#!/usr/bin/env python3
"""agent-memory: a tiny persistent memory file for local agents.

One JSON file, stdlib only, no network, no API keys, no shell.

The problem it solves: every agent session starts from zero and re-derives
the same facts, decisions and lessons. This keeps them in one plain file
that any later session can read, search and inject into its prompt.

Entries have a kind (fact / decision / lesson), free text, tags, and a
creation date. Nothing is ever silently overwritten: when a fact changes,
the old entry is *superseded* (kept, but hidden from search and digests)
and a new entry takes its place. Stale memory is the bug this tool exists
to prevent -- a superseded price, decision or instruction must never come
back as if it were current.

Storage format (memory.json): a JSON list of entries:
    {"id": 1, "kind": "fact", "text": "...", "tags": ["shop"],
     "created": "2026-10-27", "superseded_by": null}

Usage:
    python3 agent_memory.py add --kind fact --text "..." --tags shop,prices
    python3 agent_memory.py list [--kind fact] [--tag shop]
    python3 agent_memory.py search "console prices"
    python3 agent_memory.py supersede 3 --by "New price list source"
    python3 agent_memory.py digest [--days 7]
    python3 agent_memory.py prune --yes   # drops superseded entries only

Exit codes: 0 ok, 1 nothing found / refused, 2 bad input.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

KINDS = ("fact", "decision", "lesson")
DEFAULT_DB = "memory.json"


def load_db(path):
    """Return the entry list; a missing file is an empty memory."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"memory file {path} is not valid JSON: {exc}")
    if not isinstance(data, list):
        raise ValueError(f"memory file {path} must contain a JSON list")
    for entry in data:
        if not isinstance(entry, dict) or "id" not in entry or "text" not in entry:
            raise ValueError(f"memory file {path} has a malformed entry: {entry!r}")
    return data


def save_db(path, entries):
    Path(path).write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def next_id(entries):
    return max((e["id"] for e in entries), default=0) + 1


def parse_tags(raw):
    if not raw:
        return []
    tags = [t.strip().lower() for t in raw.split(",")]
    return [t for t in tags if t]


def add_entry(entries, kind, text, tags, created=None):
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    entry = {
        "id": next_id(entries),
        "kind": kind,
        "text": text.strip(),
        "tags": parse_tags(tags),
        "created": created or date.today().isoformat(),
        "superseded_by": None,
    }
    entries.append(entry)
    return entry


def live_entries(entries):
    """Entries that are still current (not superseded)."""
    return [e for e in entries if e.get("superseded_by") is None]


def search_entries(entries, query, include_superseded=False):
    """Keyword search over text + tags; most matching terms rank first."""
    words = [w.lower() for w in query.split() if w]
    if not words:
        raise ValueError("search query must not be empty")
    pool = entries if include_superseded else live_entries(entries)
    scored = []
    for entry in pool:
        haystack = (entry["text"] + " " + " ".join(entry.get("tags", []))).lower()
        hits = sum(1 for w in words if w in haystack)
        if hits:
            scored.append((hits, entry))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    return [entry for _, entry in scored]


def supersede_entry(entries, entry_id, replacement_text, kind=None):
    """Mark entry superseded and append its replacement; returns (old, new)."""
    old = next((e for e in entries if e["id"] == entry_id), None)
    if old is None:
        raise ValueError(f"no entry with id {entry_id}")
    if old.get("superseded_by") is not None:
        raise ValueError(f"entry {entry_id} is already superseded")
    new = add_entry(entries, kind or old["kind"], replacement_text,
                    ",".join(old.get("tags", [])))
    old["superseded_by"] = new["id"]
    return old, new


def digest(entries, days=None):
    """Markdown digest of live entries, grouped by kind.

    With days=N, only entries created within the last N days are included.
    Pass days=None for the full digest.
    """
    pool = live_entries(entries)
    if days is not None:
        if days < 0:
            raise ValueError("days must be >= 0")
        today = date.today()
        pool = [e for e in pool
                if (today - date.fromisoformat(e["created"])).days <= days]
    lines = ["# Agent memory digest", ""]
    for kind in KINDS:
        group = [e for e in pool if e["kind"] == kind]
        if not group:
            continue
        lines.append(f"## {kind}s")
        for entry in group:
            tags = f" [{', '.join(entry['tags'])}]" if entry.get("tags") else ""
            lines.append(f"- (#{entry['id']}, {entry['created']}) "
                         f"{entry['text']}{tags}")
        lines.append("")
    if len(lines) == 2:
        lines.append("(memory is empty)")
    return "\n".join(lines).rstrip() + "\n"


def prune_superseded(entries):
    """Drop superseded entries; returns (kept, dropped_count)."""
    kept = [e for e in entries if e.get("superseded_by") is None]
    return kept, len(entries) - len(kept)


def fmt(entry):
    tags = f" [{', '.join(entry['tags'])}]" if entry.get("tags") else ""
    sup = f" (superseded by #{entry['superseded_by']})" \
        if entry.get("superseded_by") is not None else ""
    return f"#{entry['id']} [{entry['kind']}] {entry['created']} " \
        f"{entry['text']}{tags}{sup}"


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db", default=DEFAULT_DB,
                        help="memory JSON file (default: memory.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="add one entry")
    p.add_argument("--kind", choices=KINDS, required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--tags", default="")

    p = sub.add_parser("list", help="list entries (live only by default)")
    p.add_argument("--kind", choices=KINDS)
    p.add_argument("--tag")
    p.add_argument("--include-superseded", action="store_true")

    p = sub.add_parser("search", help="search live entries")
    p.add_argument("query")
    p.add_argument("--include-superseded", action="store_true")

    p = sub.add_parser("supersede", help="replace an entry with a new one")
    p.add_argument("entry_id", type=int)
    p.add_argument("--by", required=True, help="replacement text")
    p.add_argument("--kind", choices=KINDS,
                   help="kind of the replacement (default: same as old)")

    p = sub.add_parser("digest", help="print a Markdown digest")
    p.add_argument("--days", type=int, default=None)

    p = sub.add_parser("prune", help="drop superseded entries")
    p.add_argument("--yes", action="store_true", required=True,
                   help="confirm destructive prune")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        entries = load_db(args.db)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        if args.command == "add":
            entry = add_entry(entries, args.kind, args.text, args.tags)
            save_db(args.db, entries)
            print(fmt(entry))
        elif args.command == "list":
            pool = entries if args.include_superseded else live_entries(entries)
            if args.kind:
                pool = [e for e in pool if e["kind"] == args.kind]
            if args.tag:
                pool = [e for e in pool if args.tag.lower() in e.get("tags", [])]
            if not pool:
                print("(no entries)")
                return 1
            for entry in pool:
                print(fmt(entry))
        elif args.command == "search":
            results = search_entries(entries, args.query,
                                     args.include_superseded)
            if not results:
                print("(no matches)")
                return 1
            for entry in results:
                print(fmt(entry))
        elif args.command == "supersede":
            old, new = supersede_entry(entries, args.entry_id, args.by, args.kind)
            save_db(args.db, entries)
            print(f"superseded: {fmt(old)}")
            print(f"replacement: {fmt(new)}")
        elif args.command == "digest":
            print(digest(entries, args.days), end="")
        elif args.command == "prune":
            kept, dropped = prune_superseded(entries)
            save_db(args.db, kept)
            print(f"pruned {dropped} superseded entr{'y' if dropped == 1 else 'ies'}")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
