import importlib.util
import io
import json
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


if __name__ == "__main__":
    unittest.main()
