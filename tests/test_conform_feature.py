import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
_SPEC = importlib.util.spec_from_file_location("conform_feature", ROOT / "scripts" / "conform_feature.py")
cf = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cf)
vf = cf.vf

IMPORT_COMMENT = ["# IMPORT RULES: keep this file importable.", "# Second line of the rules."]

PROJECT = vf.ProjectRules(
    import_rules={"featureTags": False, "featureDescription": False, "background": False,
                  "rule": False, "maxTitleLength": 200, "maxTagLength": 100},
    tag_rules={
        "direction": ["@positive", "@negative"],
        "checkType": ["@logic", "@navigation", "@ui", "@a11y"],
        "gates": ["@not-implemented", "@blocked", "@manual", "@pending-oq"],
        "platform": ["@ios-only", "@android-only"],
        "area": ["@area"],
        "titlePrefix": {"@positive": "Positive - ", "@negative": "Negative - "},
        "triage": {"blocked": ["@blocked", "@not-implemented"], "manual": ["@ui", "@a11y", "@manual"]},
    },
    import_comment=IMPORT_COMMENT,
)

LEGACY = """\
# =============================================================================
# Feature: Legacy  (US-001)
# MAESTRO CONVERTIBILITY
#   now: something
# =============================================================================

@area @screen
Feature: Legacy
  As a user
  I want things

  Background:
    Given User is signed in

  @ui @positive # AC-01
  Scenario - Positive - Screen matches design
    When The screen loads
    Then It matches

  @negative @logic
  Scenario - Reject bad input
    When User enters "x"
    Then An error is shown
"""


def fails(text, project=PROJECT):
    return [f for f in vf.validate(text, project.import_rules, project.tag_rules, project.import_comment)
            if f.severity == "FAIL"]


class ConformTest(unittest.TestCase):
    def setUp(self):
        self.result = cf.conform(LEGACY, PROJECT)

    def test_legacy_file_fails_before(self):
        self.assertTrue(fails(LEGACY))

    def test_conformed_file_validates_clean(self):
        self.assertIsNone(self.result.problem)
        self.assertEqual(fails(self.result.text), [])

    def test_every_change_is_named(self):
        self.assertEqual(sorted(self.result.changes), ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"])

    def test_steps_and_scenarios_are_preserved(self):
        before = cf.extract(cf.fix_lines(LEGACY.split("\n"), set()))
        after = cf.extract(self.result.text.split("\n"))
        self.assertEqual(len(before), len(after))
        for (_, steps_before), (_, steps_after) in zip(before, after):
            self.assertEqual(steps_after, ["User is signed in"] + steps_before)

    def test_specific_rewrites(self):
        text = self.result.text
        self.assertIn("  # AC-01\n  @positive @ui @area @screen\n  Scenario: Positive - Screen matches design", text)
        self.assertIn("  @negative @logic @area @screen\n  Scenario: Negative - Reject bad input", text)
        self.assertIn("  # As a user\n  # I want things", text)
        self.assertNotIn("Background:", text)
        self.assertIn("\n".join(IMPORT_COMMENT) + "\nFeature: Legacy", text)
        self.assertIn("#   Triage: 1 automatable / 1 manual / 0 blocked (2 scenarios)", text)

    def test_idempotent(self):
        again = cf.conform(self.result.text, PROJECT)
        self.assertEqual(again.text, self.result.text)
        self.assertEqual(again.changes, set())

    def test_no_project_rules_only_keyword_fixes(self):
        result = cf.conform(LEGACY, vf.ProjectRules())
        self.assertEqual(sorted(result.changes), ["C1", "C2"])
        self.assertIn("@area @screen\nFeature: Legacy", result.text)

    def test_wrong_triage_line_is_recounted(self):
        text = self.result.text.replace("1 automatable / 1 manual", "2 automatable / 0 manual")
        result = cf.conform(text, PROJECT)
        self.assertEqual(result.changes, {"C9"})
        self.assertIn("1 automatable / 1 manual / 0 blocked (2 scenarios)", result.text)

    def test_reworded_import_comment_is_restored(self):
        text = self.result.text.replace(IMPORT_COMMENT[1], "# my own words")
        result = cf.conform(text, PROJECT)
        self.assertEqual(result.changes, {"C8"})
        self.assertEqual(fails(result.text), [])

    def test_crlf_line_endings_are_kept(self):
        result = cf.conform(LEGACY.replace("\n", "\r\n"), PROJECT)
        self.assertIn("\r\n", result.text)
        self.assertNotIn("\r\r", result.text)


class SafetyTest(unittest.TestCase):
    def test_lost_step_is_refused(self):
        base = cf.fix_lines(LEGACY.split("\n"), set())
        broken = [line for line in base if "Then It matches" not in line]
        self.assertIn("steps changed", cf.safety_problem(base, broken, [], []))

    def test_changed_title_is_refused(self):
        base = cf.fix_lines(LEGACY.split("\n"), set())
        renamed = [line.replace("Screen matches design", "Something else") for line in base]
        self.assertIn("title changed", cf.safety_problem(base, renamed, [], []))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "legacy.feature"
        self.path.write_text(LEGACY, encoding="utf-8")

    def test_dry_run_shows_diff_and_does_not_write(self):
        out = io.StringIO()
        self.assertEqual(cf.run([str(self.path)], out, write=False, config=None), 0)
        self.assertIn("+  Scenario: Positive - Screen matches design", out.getvalue())
        self.assertEqual(self.path.read_text(encoding="utf-8"), LEGACY)

    def test_write_changes_the_file(self):
        out = io.StringIO()
        self.assertEqual(cf.run([str(self.path)], out, write=True, config=None), 0)
        self.assertIn("Scenario: Positive - Screen matches design", self.path.read_text(encoding="utf-8"))
        self.assertIn("written", out.getvalue())

    def test_usage(self):
        self.assertEqual(cf.main([]), 64)


ID_PROJECT = vf.ProjectRules(
    import_rules=PROJECT.import_rules,
    tag_rules=dict(PROJECT.tag_rules, scenarioId={"prefix": "@TC-", "digits": 2}),
    import_comment=IMPORT_COMMENT,
    case_ids={"pattern": r"^DR-(?P<code>[A-Z]{2,4})-\d{3}-\d{3}-\d{2}$", "codes": ["PA"]},
)
LEGACY_DR = LEGACY.replace("(US-001)", "(DR-001-001-01)")


class IdentifierConformTest(unittest.TestCase):
    def setUp(self):
        self.result = cf.conform(LEGACY_DR, ID_PROJECT)

    def test_ids_assigned_last_in_tag_order(self):
        self.assertIn("@positive @ui @area @screen @TC-01\n  Scenario: Positive - Screen matches design", self.result.text)
        self.assertIn("@negative @logic @area @screen @TC-02\n  Scenario: Negative - Reject bad input", self.result.text)
        self.assertIn("C10", self.result.changes)

    def test_next_line_written(self):
        self.assertIn("# Scenario IDs: next @TC-03", self.result.text)

    def test_legacy_case_id_migrated_with_single_code(self):
        self.assertIn("# Feature: Legacy  (DR-PA-001-001-01)\n#         (formerly DR-001-001-01)", self.result.text)
        self.assertIn("C11", self.result.changes)

    def test_result_validates_clean(self):
        findings = vf.validate(self.result.text, ID_PROJECT.import_rules, ID_PROJECT.tag_rules,
                               ID_PROJECT.import_comment, ID_PROJECT.case_ids)
        self.assertEqual([f.code for f in findings if f.severity == "FAIL"], [])

    def test_idempotent(self):
        again = cf.conform(self.result.text, ID_PROJECT)
        self.assertEqual(again.changes, set())

    def test_existing_ids_kept_and_new_ones_continue(self):
        text = self.result.text.replace("@TC-01", "@TC-05").replace("next @TC-03", "next @TC-06")
        text = text.replace(" @TC-02\n", "\n")
        result = cf.conform(text, ID_PROJECT)
        self.assertIn("@TC-05\n  Scenario: Positive - Screen matches design", result.text)
        self.assertIn("@TC-06\n  Scenario: Negative - Reject bad input", result.text)
        self.assertIn("# Scenario IDs: next @TC-07", result.text)

    def test_ambiguous_case_id_left_alone(self):
        project = vf.ProjectRules(tag_rules=ID_PROJECT.tag_rules,
                                  case_ids=dict(ID_PROJECT.case_ids, codes=["PA", "WP"]))
        result = cf.conform(LEGACY_DR, project)
        self.assertNotIn("C11", result.changes)
        self.assertIn("(DR-001-001-01)", result.text)


class InvalidCaseIdPatternTest(unittest.TestCase):
    def test_invalid_pattern_skips_c11(self):
        project = vf.ProjectRules(tag_rules=ID_PROJECT.tag_rules,
                                  case_ids={"pattern": "([", "codes": ["PA"]})
        result = cf.conform(LEGACY_DR, project)
        self.assertNotIn("C11", result.changes)
        self.assertIn("(DR-001-001-01)", result.text)


if __name__ == "__main__":
    unittest.main()
