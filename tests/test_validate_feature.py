import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("validate_feature", ROOT / "scripts" / "validate_feature.py")
vf = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vf)

VALID = """\
# =============================================================================
# Feature: Sample  (US-001)
# =============================================================================
Feature: Sample
  # As a user

  # AC-01 - happy path.
  @positive @logic @area @screen
  Scenario: Positive - Save the form
    Given User is on the form
    When User taps Save
    Then The confirmation "Saved" is displayed

  @negative @logic @area @screen
  Scenario Outline: Negative - Reject <input>
    Given User is on the form
    When User enters <input>
    Then The error "<message>" is displayed

    Examples:
      | input | message  |
      | ""    | Required |
"""


def codes(text):
    return [f.code for f in vf.validate(text)]


def fail_codes(text):
    return [f.code for f in vf.validate(text) if f.severity == "FAIL"]


class ValidFileTest(unittest.TestCase):
    def test_valid_file_has_no_findings(self):
        self.assertEqual(codes(VALID), [])

    def test_doc_string_content_is_ignored(self):
        text = VALID.replace(
            '    Then The confirmation "Saved" is displayed\n',
            '    Then The confirmation is displayed\n'
            '      """\n      free text @notatag\n      Scenario - not a keyword\n      """\n',
        )
        self.assertEqual(codes(text), [])

    def test_description_under_feature_is_allowed(self):
        # Valid Gherkin. Whether a project forbids it is a project rule, not ours.
        text = VALID.replace("  # As a user\n", "  As a user I want things\n")
        self.assertEqual(codes(text), [])

    def test_hash_inside_step_text_is_allowed(self):
        text = VALID.replace('"Saved" is displayed', '"Saved" is displayed in Berry #5A60EC')
        self.assertEqual(codes(text), [])


class FileLevelTest(unittest.TestCase):
    def test_g1_two_features(self):
        self.assertIn("G1", fail_codes(VALID + "\nFeature: Second\n"))

    def test_g1_no_feature(self):
        self.assertIn("G1", fail_codes(VALID.replace("Feature: Sample\n", "")))

    def test_g2_text_before_feature(self):
        self.assertIn("G2", fail_codes("Some intro text\n" + VALID))

    def test_g3_scenario_with_dash(self):
        text = VALID.replace("Scenario: Positive - Save the form", "Scenario - Positive - Save the form")
        self.assertIn("G3", fail_codes(text))

    def test_g3_bare_examples(self):
        self.assertIn("G3", fail_codes(VALID.replace("    Examples:\n", "    Examples\n")))

    def test_g4_trailing_comment_on_tag_line(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @area @screen # AC-01")
        self.assertIn("G4", fail_codes(text))

    def test_g4_bracket_marker_on_tag_line(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic [BACKEND] @area @screen")
        self.assertIn("G4", fail_codes(text))

    def test_g5_tag_line_at_end_of_file(self):
        self.assertIn("G5", fail_codes(VALID + "\n  @dangling\n"))

    def test_g5_tag_before_background(self):
        text = VALID.replace("  # As a user\n", "  @setup\n  Background:\n    Given User is signed in\n")
        self.assertIn("G5", fail_codes(text))

    def test_g13_step_outside_scenario(self):
        self.assertIn("G13", fail_codes(VALID.replace("  # As a user\n", "  Given a stray step\n")))

    def test_g14_text_after_steps(self):
        text = VALID.replace(
            '    Then The confirmation "Saved" is displayed\n',
            '    Then The confirmation "Saved" is displayed\n    the user is happy\n',
        )
        self.assertIn("G14", fail_codes(text))


class ScenarioLevelTest(unittest.TestCase):
    def test_g6_missing_when_and_does_not_count(self):
        text = VALID.replace("    When User taps Save\n", "    And User taps Save\n")
        found = [f for f in vf.validate(text) if f.code == "G6"]
        self.assertEqual(len(found), 1)
        self.assertIn("When", found[0].message)

    def test_g6_background_given_counts(self):
        text = VALID.replace("  # As a user\n", "  Background:\n    Given User is signed in\n")
        text = text.replace("    Given User is on the form\n", "", 1)
        self.assertNotIn("G6", fail_codes(text))

    def test_g7_outline_without_examples(self):
        self.assertIn("G7", fail_codes(VALID.split("    Examples:")[0]))

    def test_g7_examples_header_only(self):
        self.assertIn("G7", fail_codes(VALID.replace('      | ""    | Required |\n', "")))

    def test_g7_examples_in_plain_scenario(self):
        text = VALID.replace(
            '    Then The confirmation "Saved" is displayed\n',
            '    Then The confirmation "Saved" is displayed\n\n    Examples:\n      | a |\n      | 1 |\n',
        )
        self.assertIn("G7", fail_codes(text))

    def test_g8_row_cell_count_mismatch(self):
        text = VALID.replace('      | ""    | Required |\n', '      | ""    | Required | extra |\n')
        self.assertIn("G8", fail_codes(text))

    def test_g8_empty_column_name(self):
        text = VALID.replace("      | input | message  |\n", "      | input | message  | |\n")
        text = text.replace('      | ""    | Required |\n', '      | ""    | Required | x |\n')
        self.assertIn("G8", fail_codes(text))

    def test_g9_column_used_only_in_title(self):
        text = VALID.replace('    Then The error "<message>" is displayed\n', "    Then The error is displayed\n")
        text = text.replace("Reject <input>", "Reject <input> with <message>")
        found = [f for f in vf.validate(text) if f.code == "G9"]
        self.assertEqual(len(found), 1)
        self.assertIn("<message>", found[0].message)

    def test_g10_placeholder_without_column(self):
        text = VALID.replace(
            "    Given User is on the form\n    When User enters <input>",
            "    Given User is on the <screen>\n    When User enters <input>",
        )
        self.assertIn("G10", fail_codes(text))

    def test_g11_placeholder_in_plain_scenario_is_warn(self):
        text = VALID.replace("    When User taps Save\n", "    When User taps <button>\n")
        self.assertEqual([(f.code, f.severity) for f in vf.validate(text)], [("G11", "WARN")])

    def test_g12_hash_in_title_is_warn(self):
        text = VALID.replace("Scenario: Positive - Save the form", "Scenario: Positive - Save the form # AC-01")
        self.assertEqual([(f.code, f.severity) for f in vf.validate(text)], [("G12", "WARN")])


if __name__ == "__main__":
    unittest.main()
