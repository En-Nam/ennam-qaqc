import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("validate_case_ids", ROOT / "scripts" / "validate_case_ids.py")
vc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vc)


def feature(case_id, scenarios, next_id):
    lines = ["# Feature: Sample  (%s)" % case_id, "# Scenario IDs: next @TC-%02d" % next_id, "Feature: Sample"]
    for number, title in scenarios:
        lines += ["  @positive @logic @area @screen @TC-%02d" % number, "  Scenario: Positive - %s" % title,
                  "    Given a", "    When b", "    Then c"]
    return "\n".join(lines) + "\n"


class SuiteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        for args in (["init", "-q"], ["config", "user.email", "t@e"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True)
        (self.repo / ".claude").mkdir()
        self.config = {"testCasesRoot": "test-cases/", "caseIds": {"pattern": r"^DR-[A-Z]{2}-\d{3}-\d{3}-\d{2}$"},
                       "tagRules": {"scenarioId": {"prefix": "@TC-", "digits": 2}}}
        self.save_config()
        (self.repo / "test-cases").mkdir()
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "One"), (2, "Two"), (3, "Three")], 4))
        self.commit()

    def save_config(self):
        (self.repo / ".claude" / "qaqc.json").write_text(json.dumps(self.config), encoding="utf-8")

    def write(self, name, text):
        (self.repo / "test-cases" / name).write_text(text, encoding="utf-8")

    def commit(self):
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=self.repo, check=True)

    def run_suite(self):
        out = io.StringIO()
        code = vc.main(["--config", str(self.repo / ".claude" / "qaqc.json")], out=out)
        return code, out.getvalue()

    def test_clean_suite_passes(self):
        self.write("b.feature", feature("DR-PA-001-001-02", [(1, "Other")], 2))
        self.assertEqual(self.run_suite()[0], 0)

    def test_s1_duplicate_case_id(self):
        self.write("b.feature", feature("DR-PA-001-001-01", [(1, "Other")], 2))
        code, out = self.run_suite()
        self.assertEqual(code, 1)
        self.assertIn("S1", out)

    def test_s2_case_id_without_dr(self):
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "DR-001-001-01-x.md").write_text("---\ndetail_id: DR-PA-001-001-09\n---\n", encoding="utf-8")
        self.config["caseIds"]["drSources"] = "docs/DR-*.md"
        self.save_config()
        code, out = self.run_suite()
        self.assertEqual(code, 1)
        self.assertIn("S2", out)

    def test_s3_next_went_down(self):
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "One"), (2, "Two"), (3, "Three")], 3))
        code, out = self.run_suite()
        self.assertIn("S3", out)

    def test_s4_reused_retired_id(self):
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "One"), (3, "Three")], 4))
        self.commit()
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "One"), (2, "Brand new"), (3, "Three")], 4))
        code, out = self.run_suite()
        self.assertEqual(code, 1)
        self.assertIn("S4", out)

    def test_s5_renumbered(self):
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "Two"), (2, "Three")], 4))
        code, out = self.run_suite()
        self.assertEqual(code, 1)
        self.assertIn("S5", out)

    def test_s6_retired_is_warn(self):
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "One"), (3, "Three")], 4))
        code, out = self.run_suite()
        self.assertEqual(code, 0)
        self.assertIn("S6", out)

    def test_s7_missing_case_id_is_warn(self):
        self.write("b.feature", feature("<TODO>", [(1, "Other")], 2))
        code, out = self.run_suite()
        self.assertEqual(code, 0)
        self.assertIn("S7", out)

    def test_duplicate_titles_unchanged_is_not_s5(self):
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "Login"), (2, "Login")], 3))
        self.commit()
        code, out = self.run_suite()
        self.assertEqual(code, 0)
        self.assertNotIn("S5", out)

    def test_malformed_config_is_reported_not_crashed(self):
        (self.repo / ".claude" / "qaqc.json").write_text("{not json", encoding="utf-8")
        code, out = self.run_suite()
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)

    def test_absolute_drsources_is_warn_and_skips_s2(self):
        self.config["caseIds"]["drSources"] = "/abs/DR-*.md"
        self.save_config()
        code, out = self.run_suite()
        self.assertEqual(code, 0)
        self.assertIn("drSources", out)
        self.assertNotIn("FAIL S2", out)

    def test_empty_drsources_is_warn_and_skips_s2(self):
        self.config["caseIds"]["drSources"] = ""
        self.save_config()
        code, out = self.run_suite()
        self.assertEqual(code, 0)
        self.assertIn("drSources", out)

    def test_without_case_ids_config_skips_s1_s2_s7(self):
        del self.config["caseIds"]
        self.save_config()
        self.write("b.feature", feature("DR-PA-001-001-01", [(1, "Other")], 2))
        self.write("c.feature", feature("<TODO>", [(1, "Third")], 2))
        code, out = self.run_suite()
        self.assertEqual(code, 0)
        self.assertNotIn("S1", out)
        self.assertNotIn("S7", out)
        self.assertIn("caseIds not set", out)

    def test_no_config_anywhere_is_a_note(self):
        with tempfile.TemporaryDirectory() as other:
            out = io.StringIO()
            cwd = os.getcwd()
            os.chdir(other)
            try:
                code = vc.main([], out=out)
            finally:
                os.chdir(cwd)
        self.assertEqual(code, 0)
        self.assertIn("nothing to check", out.getvalue())

    def test_explicit_missing_config_still_fails(self):
        out = io.StringIO()
        code = vc.main(["--config", str(self.repo / "nope.json")], out=out)
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out.getvalue())

    def test_history_works_when_claude_is_in_a_subfolder(self):
        sub = self.repo / "qa"
        (sub / ".claude").mkdir(parents=True)
        (sub / "test-cases").mkdir()
        (sub / ".claude" / "qaqc.json").write_text(json.dumps(self.config), encoding="utf-8")
        target = sub / "test-cases" / "z.feature"
        target.write_text(feature("DR-PA-001-001-01", [(1, "One"), (2, "Two"), (3, "Three")], 4), encoding="utf-8")
        self.commit()
        target.write_text(feature("DR-PA-001-001-01", [(1, "Two"), (2, "Three")], 4), encoding="utf-8")
        out = io.StringIO()
        code = vc.main(["--config", str(sub / ".claude" / "qaqc.json")], out=out)
        self.assertEqual(code, 1)
        self.assertIn("S5", out.getvalue())

    def test_history_decodes_utf8(self):
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "Đăng nhập"), (2, "Two"), (3, "Three")], 4))
        self.commit()
        self.write("a.feature", feature("DR-PA-001-001-01", [(1, "Two"), (2, "Đăng nhập"), (3, "Three")], 4))
        code, out = self.run_suite()
        self.assertEqual(code, 1)
        self.assertIn("S5", out)


if __name__ == "__main__":
    unittest.main()
