import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
_SPEC = importlib.util.spec_from_file_location("name_by_id", ROOT / "scripts" / "name_by_id.py")
nb = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(nb)
_SPEC_VC = importlib.util.spec_from_file_location("validate_case_ids", ROOT / "scripts" / "validate_case_ids.py")
vc = importlib.util.module_from_spec(_SPEC_VC)
_SPEC_VC.loader.exec_module(vc)

RULES = {"pattern": r"^DR-(?P<code>PA|PP)-\d{3}-\d{3}-\d{2}$"}


def feature(case_id, scenarios=((1, "One"),), next_id=2):
    lines = ["# Feature: Sample  (%s)" % case_id, "# Scenario IDs: next @TC-%02d" % next_id, "Feature: Sample"]
    for number, title in scenarios:
        lines += ["  @positive @logic @area @screen @TC-%02d" % number, "  Scenario: Positive - %s" % title,
                  "    Given a", "    When b", "    Then c"]
    return "\n".join(lines) + "\n"


class HelpersTest(unittest.TestCase):
    def test_strip_id(self):
        self.assertEqual(nb.strip_id("DR-PA-005-003-01-create-collection"), "create-collection")
        self.assertEqual(nb.strip_id("DR-001-001-01-login-form"), "login-form")
        self.assertEqual(nb.strip_id("EP-PA-005-Collections"), "Collections")
        self.assertEqual(nb.strip_id("EP-005-Explore & Discovery"), "Explore & Discovery")
        self.assertEqual(nb.strip_id("EP-PA-005-2fa-setup"), "2fa-setup")
        self.assertEqual(nb.strip_id("Explore & Discovery"), "Explore & Discovery")
        self.assertEqual(nb.strip_id("search-form"), "search-form")

    def test_valid_case_id(self):
        self.assertEqual(nb.valid_case_id("DR-PA-005-003-01", RULES), "DR-PA-005-003-01")
        self.assertEqual(nb.valid_case_id("US-003 / DR-PA-005-003-01 v1.1, EP-005 Collections", RULES),
                         "DR-PA-005-003-01")
        self.assertIsNone(nb.valid_case_id("US-001 / DR-PA-006-001-01 v1.1 + DR-PA-006-001-02 v1.0", RULES))
        self.assertIsNone(nb.valid_case_id("US-002 / DR-002-002-03 - legacy", RULES))
        self.assertIsNone(nb.valid_case_id("<TODO>", RULES))
        self.assertIsNone(nb.valid_case_id("DR-PA-005-003-01", {"pattern": "(["}))

    def test_folder_id(self):
        self.assertEqual(nb.folder_id("DR-PA-005-003-01", RULES), "EP-PA-005")
        self.assertEqual(nb.folder_id("DR-PA-005-003-01", {"pattern": r"^DR-[A-Z]{2}-\d{3}-\d{3}-\d{2}$"}), "EP-PA-005")
        custom = {"pattern": r"^TC-(?P<epic>\d+)-\d+$"}
        self.assertEqual(nb.folder_id("TC-7-12", custom), "EP-7")


class RenameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        for args in (["init", "-q"], ["config", "user.email", "t@e"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True)
        (self.repo / ".claude").mkdir()
        self.config = {"testCasesRoot": "test-cases/", "caseIds": dict(RULES),
                       "tagRules": {"scenarioId": {"prefix": "@TC-", "digits": 2}}}
        self.save_config()
        self.root = self.repo / "test-cases"
        self.write("Collections/create-collection.feature", feature("DR-PA-005-003-01"))
        self.write("Collections/collection-screen.feature", feature("DR-PA-005-001-01"))
        self.write("Collections/share.feature", feature("<TODO>"))
        self.write("Authentication/DR-001-001-01-login.feature", feature("DR-PA-001-001-01"))
        self.write("root-level.feature", feature("DR-PA-002-001-01"))
        self.commit()

    def save_config(self):
        (self.repo / ".claude" / "qaqc.json").write_text(json.dumps(self.config), encoding="utf-8")

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self):
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=self.repo, check=True)

    def rename(self, write=True, *paths):
        out = io.StringIO()
        code = nb.main((["--write"] if write else []) + ["--config", str(self.repo / ".claude" / "qaqc.json")]
                       + [str(p) for p in (paths or [self.root])], out=out)
        return code, out.getvalue()

    def names(self):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*.feature"))

    def test_dry_run_moves_nothing(self):
        before = self.names()
        code, out = self.rename(False)
        self.assertEqual(code, 0)
        self.assertIn("dry run", out)
        self.assertEqual(self.names(), before)

    def test_files_and_folders_get_ids(self):
        code, out = self.rename()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.names(), [
            "DR-PA-002-001-01-root-level.feature",
            "EP-PA-001-Authentication/DR-PA-001-001-01-login.feature",
            "EP-PA-005-Collections/DR-PA-005-001-01-collection-screen.feature",
            "EP-PA-005-Collections/DR-PA-005-003-01-create-collection.feature",
            "EP-PA-005-Collections/share.feature",
        ])
        self.assertIn("no case id - name kept", out)

    def test_idempotent(self):
        self.rename()
        code, out = self.rename()
        self.assertEqual(code, 0)
        self.assertIn("0 rename(s)", out)

    def test_tracked_files_show_as_renames_in_git(self):
        self.rename()
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True).stdout
        self.assertIn("R  test-cases/Collections/create-collection.feature -> "
                      "test-cases/EP-PA-005-Collections/DR-PA-005-003-01-create-collection.feature", status)

    def test_mixed_epics_keep_the_folder_name(self):
        self.write("Collections/other.feature", feature("DR-PA-004-001-01"))
        code, out = self.rename()
        self.assertEqual(code, 1)
        self.assertIn("different epics (EP-PA-004, EP-PA-005)", out)
        self.assertTrue((self.root / "Collections" / "DR-PA-004-001-01-other.feature").is_file())

    def test_existing_target_is_not_overwritten(self):
        self.write("Collections/DR-PA-005-003-01-create-collection.feature", feature("DR-PA-005-009-01"))
        code, out = self.rename(True, self.root / "Collections" / "create-collection.feature")
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)
        self.assertIn("EP-PA-005-Collections/create-collection.feature", self.names())

    def test_one_file_passed_still_names_its_folder_from_all_its_files(self):
        self.write("Collections/other.feature", feature("DR-PA-004-001-01"))
        code, out = self.rename(True, self.root / "Collections" / "create-collection.feature")
        self.assertIn("different epics", out)
        self.assertIn("Collections/DR-PA-005-003-01-create-collection.feature", self.names())

    def test_names_false_turns_it_off(self):
        self.config["caseIds"]["names"] = False
        self.save_config()
        code, out = self.rename()
        self.assertEqual(code, 0)
        self.assertIn("nothing renamed", out)
        self.assertIn("Collections/create-collection.feature", self.names())

    def test_conform_state_follows_the_rename(self):
        state_dir = self.repo / ".claude" / "qaqc-conform"
        (state_dir / "reports" / "test-cases" / "Collections").mkdir(parents=True)
        (state_dir / "reports" / "test-cases" / "Collections" / "create-collection.feature.md").write_text("r")
        (state_dir / "state.json").write_text(json.dumps({"version": 1, "files": {
            "test-cases/Collections/create-collection.feature": {"status": "upgraded"}}}))
        self.rename()
        files = json.loads((state_dir / "state.json").read_text())["files"]
        self.assertEqual(list(files), ["test-cases/EP-PA-005-Collections/DR-PA-005-003-01-create-collection.feature"])
        self.assertTrue((state_dir / "reports" / "test-cases" / "EP-PA-005-Collections"
                         / "DR-PA-005-003-01-create-collection.feature.md").is_file())

    def suite(self):
        out = io.StringIO()
        code = vc.main(["--config", str(self.repo / ".claude" / "qaqc.json")], out=out)
        return code, out.getvalue()

    def test_suite_warns_about_names_before_and_not_after(self):
        code, out = self.suite()
        self.assertIn("WARN S8 Collections/create-collection.feature: should be named "
                      "DR-PA-005-003-01-create-collection.feature", out)
        self.assertIn("WARN S9 Collections: should be named EP-PA-005-Collections", out)
        self.rename()
        code, out = self.suite()
        self.assertNotIn("S8", out)
        self.assertNotIn("S9", out)

    def test_history_follows_a_staged_rename(self):
        self.rename()
        path = self.root / "EP-PA-005-Collections" / "DR-PA-005-003-01-create-collection.feature"
        path.write_text(feature("DR-PA-005-003-01", ((2, "One"),), 3), encoding="utf-8")
        code, out = self.suite()
        self.assertEqual(code, 1)
        self.assertIn("S5", out)

    def test_history_follows_an_unstaged_rename(self):
        old = self.root / "Collections" / "create-collection.feature"
        new_folder = self.root / "EP-PA-005-Collections"
        new_folder.mkdir()
        new = new_folder / "DR-PA-005-003-01-create-collection.feature"
        old.rename(new)
        new.write_text(feature("DR-PA-005-003-01", ((2, "One"),), 3), encoding="utf-8")
        code, out = self.suite()
        self.assertIn("S5", out)


if __name__ == "__main__":
    unittest.main()
