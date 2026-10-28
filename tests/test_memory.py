"""Tests for agent_memory: real file round-trips, no mocks of the core."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_memory as mem

PY = sys.executable
SCRIPT = str(Path(__file__).resolve().parent.parent / "agent_memory.py")


def run_cli(*args, db):
    return subprocess.run([PY, SCRIPT, "--db", db, *args],
                          capture_output=True, text=True, timeout=30)


class TestCore(unittest.TestCase):
    def test_add_search_round_trip(self):
        entries = []
        mem.add_entry(entries, "fact", "Shop opens at 8 in Arak", "shop,hours")
        hits = mem.search_entries(entries, "arak shop")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], 1)

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            mem.add_entry([], "rumor", "x", "")

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            mem.add_entry([], "fact", "   ", "")

    def test_supersede_hides_old_from_search_and_digest(self):
        entries = []
        mem.add_entry(entries, "fact", "Old console price source", "prices")
        mem.supersede_entry(entries, 1, "Vigyato daily price carousel")
        self.assertEqual(mem.search_entries(entries, "old console"), [])
        hits = mem.search_entries(entries, "vigyato")
        self.assertEqual(len(hits), 1)
        out = mem.digest(entries)
        self.assertIn("Vigyato", out)
        self.assertNotIn("Old console", out)

    def test_supersede_missing_or_twice_rejected(self):
        entries = []
        mem.add_entry(entries, "fact", "x", "")
        with self.assertRaises(ValueError):
            mem.supersede_entry(entries, 99, "y")
        mem.supersede_entry(entries, 1, "y")
        with self.assertRaises(ValueError):
            mem.supersede_entry(entries, 1, "z")

    def test_digest_groups_and_empty(self):
        entries = []
        mem.add_entry(entries, "lesson", "Never publish silent video", "video")
        mem.add_entry(entries, "decision", "Video-only feed", "instagram")
        out = mem.digest(entries)
        self.assertIn("## lessons", out)
        self.assertIn("## decisions", out)
        self.assertIn("Never publish silent video", out)
        self.assertIn("(memory is empty)", mem.digest([]))

    def test_prune_drops_only_superseded(self):
        entries = []
        mem.add_entry(entries, "fact", "old", "")
        mem.add_entry(entries, "fact", "kept", "")
        mem.supersede_entry(entries, 1, "new")
        kept, dropped = mem.prune_superseded(entries)
        self.assertEqual(dropped, 1)
        self.assertEqual([e["id"] for e in kept], [2, 3])

    def test_corrupt_db_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as fh:
            fh.write("{not json")
            path = fh.name
        with self.assertRaises(ValueError):
            mem.load_db(path)


class TestCLI(unittest.TestCase):
    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "memory.json")
            r = run_cli("add", "--kind", "fact", "--text", "Shop in Arak",
                        "--tags", "shop", db=db)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = run_cli("search", "arak", db=db)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Shop in Arak", r.stdout)
            r = run_cli("supersede", "1", "--by", "Shop on Rudaki street",
                        db=db)
            self.assertEqual(r.returncode, 0, r.stderr)
            # the old wording is gone from live search; the new one is found
            r = run_cli("search", "rudaki", db=db)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Rudaki", r.stdout)
            self.assertNotIn("Shop in Arak", r.stdout)
            r = run_cli("search", "arak", db=db)
            self.assertEqual(r.returncode, 1)
            r = run_cli("digest", db=db)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Rudaki", r.stdout)
            r = run_cli("search", "no-such-thing", db=db)
            self.assertEqual(r.returncode, 1)
            # the db file is plain readable JSON
            data = json.loads(Path(db).read_text(encoding="utf-8"))
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["superseded_by"], 2)


if __name__ == "__main__":
    unittest.main()
