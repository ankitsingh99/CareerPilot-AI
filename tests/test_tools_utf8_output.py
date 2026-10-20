"""The Python tools must write UTF-8 whatever the host's default encoding is.

On Windows a piped stdout (which is how Claude Code runs every tool) defaults
to the ANSI code page, cp1252 on most Western installs. A tool that prints a
posting title, company, CV line or file name outside that code page then dies
with UnicodeEncodeError before the workflow sees any output: `/rank` could not
list a single Cyrillic, CJK, Devanagari, Polish or Turkish posting.

Each case runs the real CLI in a child process with a legacy stdout forced via
PYTHONIOENCODING, so the Linux CI job reproduces what Windows users hit. The
child must exit cleanly and its bytes must decode as UTF-8.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    import openpyxl
except ImportError:
    openpyxl = None

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"

# One name per script family that cp1252 cannot encode.
CYRILLIC = "Яндекс"
CJK = "腾讯"
POLISH = "Żabka Łódź"


def run_legacy_stdout(argv, cwd=None):
    """Run a tool the way a Western-locale Windows host pipes it."""
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
    return subprocess.run([sys.executable, *map(str, argv)], cwd=cwd, env=env, capture_output=True)


class ToolsWriteUtf8(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)

    def assert_clean_utf8(self, proc, expect_code, *needles, stream="stdout"):
        err = proc.stderr.decode("utf-8", "replace")
        self.assertNotIn("UnicodeEncodeError", err)
        self.assertEqual(proc.returncode, expect_code, err)
        text = getattr(proc, stream).decode("utf-8")
        for needle in needles:
            self.assertIn(needle, text)
        return text

    def write_state(self, seen):
        state = self.tmp / "seen_jobs.json"
        state.write_text(json.dumps({"version": 1, "seen": seen}, ensure_ascii=False), encoding="utf-8")
        return state

    @staticmethod
    def entry(company, title):
        return {
            "title": title, "company": company, "url": "https://example.com/jobs/123456",
            "portal": "example", "status": "new", "first_seen": "2026-09-20",
        }

    def test_rank_candidates_lists_non_latin_postings(self):
        state = self.write_state({"a": self.entry(CYRILLIC, "Инженер"), "b": self.entry(CJK, "工程师")})
        proc = run_legacy_stdout([TOOLS / "rank_state.py", "candidates", "--state", state, "--today", "2026-09-21"])
        out = json.loads(self.assert_clean_utf8(proc, 0, CYRILLIC, CJK))
        self.assertEqual(out["eligible"], 2)

    def test_rank_apply_prints_the_ranking_for_non_latin_postings(self):
        state = self.write_state({"a": self.entry(CJK, "工程师")})
        results = self.tmp / "results.json"
        results.write_text(json.dumps([{
            "key": "a", "status": "scored",
            "scores": {"technical": 80, "experience": 80, "behavioral": 80, "career": 80},
        }]), encoding="utf-8")
        proc = run_legacy_stdout([
            TOOLS / "rank_state.py", "apply", "--results", results, "--state", state, "--today", "2026-09-21",
        ])
        out = json.loads(self.assert_clean_utf8(proc, 0, CJK))
        self.assertEqual([row["key"] for row in out["ranked"]], ["a"])

    def test_job_key_audit_reports_non_latin_entries(self):
        state = self.write_state({f"{CYRILLIC}_Инженер": self.entry(CYRILLIC, "Инженер")})
        proc = run_legacy_stdout([TOOLS / "job_key.py", "--audit", state])
        self.assertNotIn(b"UnicodeEncodeError", proc.stderr)
        self.assertIn(CYRILLIC, proc.stdout.decode("utf-8"))




if __name__ == "__main__":
    unittest.main()
