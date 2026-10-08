import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("conform_state", ROOT / "scripts" / "conform_state.py")
cs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cs)


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.feature").write_text("Feature: A\n", encoding="utf-8")
        (self.repo / "b.feature").write_text("Feature: B\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")

    def call(self, *argv):
        out = io.StringIO()
        code = cs.main(list(argv), out=out, root=self.repo)
        return code, out.getvalue()

    def edit(self, name, text):
        (self.repo / name).write_text(text, encoding="utf-8")

    def state(self):
        return json.loads((self.repo / cs.STATE_PATH).read_text(encoding="utf-8"))

    def test_add_is_idempotent_and_keeps_status(self):
        self.call("add", "a.feature", "b.feature")
        self.call("mark", "a.feature", "upgraded")
        self.call("add", "a.feature")
        self.assertEqual(self.state()["files"]["a.feature"]["status"], "upgraded")
        self.assertEqual(self.state()["files"]["b.feature"]["status"], "pending")

    def test_gate_clean_files_pass(self):
        code, out = self.call("gate", "a.feature", "b.feature")
        self.assertEqual(code, 0)
        self.assertIn("a.feature: clean", out)

    def test_gate_blocks_someone_elses_edit(self):
        self.edit("a.feature", "Feature: A edited by hand\n")
        code, out = self.call("gate", "a.feature")
        self.assertEqual(code, 1)
        self.assertIn("a.feature: BLOCKED", out)

    def test_gate_lets_conforms_own_edit_resume(self):
        self.call("add", "a.feature")
        self.edit("a.feature", "Feature: A conformed\n")
        self.call("mark", "a.feature", "formatted")
        code, out = self.call("gate", "a.feature")
        self.assertEqual(code, 0)
        self.assertIn("a.feature: resumable", out)

    def test_gate_blocks_edit_made_after_conform(self):
        self.call("add", "a.feature")
        self.edit("a.feature", "Feature: A conformed\n")
        self.call("mark", "a.feature", "formatted")
        self.edit("a.feature", "Feature: A conformed then hand-edited\n")
        code, out = self.call("gate", "a.feature")
        self.assertEqual(code, 1)
        self.assertIn("changed since conform", out)

    def test_next_filters_by_status_and_limit(self):
        self.call("add", "a.feature", "b.feature")
        self.call("mark", "a.feature", "formatted")
        self.call("mark", "b.feature", "formatted")
        code, out = self.call("next", "--status", "formatted", "--limit", "1")
        self.assertEqual(out.split(), ["a.feature"])

    def test_bad_status_is_rejected(self):
        code, _ = self.call("mark", "a.feature", "finished")
        self.assertEqual(code, 64)

    def test_mark_records_note(self):
        self.call("add", "a.feature")
        self.call("mark", "a.feature", "failed", "--note", "safety check failed")
        self.assertEqual(self.state()["files"]["a.feature"]["note"], "safety check failed")

    def test_reset_returns_files_to_pending(self):
        self.call("add", "a.feature")
        self.call("mark", "a.feature", "upgraded")
        self.call("reset", "a.feature")
        self.assertEqual(self.state()["files"]["a.feature"]["status"], "pending")

    def test_summary_counts(self):
        self.call("add", "a.feature", "b.feature")
        self.call("mark", "a.feature", "needs-answers")
        _, out = self.call("summary")
        self.assertIn("pending 1", out)
        self.assertIn("needs-answers 1", out)

    def test_usage(self):
        self.assertEqual(self.call()[0], 64)


if __name__ == "__main__":
    unittest.main()
