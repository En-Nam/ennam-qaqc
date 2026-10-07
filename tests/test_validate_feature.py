import importlib.util
import io
import json
import tempfile
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


class CliAndHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        path = Path(self.tmp.name) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def hook(self, payload):
        err = io.StringIO()
        code = vf.run_hook(io.StringIO(json.dumps(payload)), err)
        return code, err.getvalue()

    def test_cli_exit_codes_and_summary(self):
        good = self.write("good.feature", VALID)
        bad = self.write("bad.feature", VALID + "\nFeature: Second\n")
        out = io.StringIO()
        self.assertEqual(vf.run_cli([good], out), 0)
        self.assertIn("good.feature: 0 FAIL, 0 WARN", out.getvalue())
        self.assertEqual(vf.run_cli([good, bad], io.StringIO()), 1)

    def test_cli_usage(self):
        self.assertEqual(vf.main([]), 64)

    def test_hook_ignores_non_feature_files(self):
        path = self.write("notes.md", "Feature: x\nFeature: y\n")
        self.assertEqual(self.hook({"tool_input": {"file_path": path}}), (0, ""))

    def test_hook_ignores_template(self):
        path = self.write("TEMPLATE.feature", "no feature line\n")
        self.assertEqual(self.hook({"tool_input": {"file_path": path}}), (0, ""))

    def test_hook_reports_fail_with_exit_2(self):
        path = self.write("bad.feature", VALID + "\nFeature: Second\n")
        code, err = self.hook({"tool_name": "Write", "tool_input": {"file_path": path}})
        self.assertEqual(code, 2)
        self.assertIn("G1", err)

    def test_hook_passes_valid_file(self):
        path = self.write("good.feature", VALID)
        self.assertEqual(self.hook({"tool_input": {"file_path": path}}), (0, ""))

    def test_hook_ignores_bad_payload(self):
        err = io.StringIO()
        self.assertEqual(vf.run_hook(io.StringIO("not json"), err), 0)
        self.assertEqual(vf.run_hook(io.StringIO("[]"), err), 0)


C4K_RULES = {
    "featureTags": False,
    "featureDescription": False,
    "background": False,
    "rule": False,
    "maxTitleLength": 200,
    "maxTagLength": 100,
}


def rule_fails(text, rules=C4K_RULES):
    return [f.code for f in vf.validate(text, rules) if f.severity == "FAIL"]


class ImportRulesTest(unittest.TestCase):
    def test_valid_file_passes_strict_rules(self):
        self.assertEqual(rule_fails(VALID), [])

    def test_p1_tags_on_feature_line(self):
        text = VALID.replace("Feature: Sample\n", "@area @screen\nFeature: Sample\n")
        self.assertIn("P1", rule_fails(text))
        self.assertEqual(rule_fails(text, None), [])

    def test_p1_allowed_when_rule_permits(self):
        text = VALID.replace("Feature: Sample\n", "@area @screen\nFeature: Sample\n")
        self.assertEqual(rule_fails(text, dict(C4K_RULES, featureTags=True)), [])

    def test_p2_description_under_feature(self):
        text = VALID.replace("  # As a user\n", "  As a user I want things\n")
        self.assertIn("P2", rule_fails(text))

    def test_p2_does_not_flag_scenario_description(self):
        text = VALID.replace("    Given User is on the form\n", "    Some scenario description\n    Given User is on the form\n", 1)
        self.assertNotIn("P2", rule_fails(text))

    def test_p3_background(self):
        text = VALID.replace("  # As a user\n", "  Background:\n    Given User is signed in\n")
        self.assertIn("P3", rule_fails(text))

    def test_p4_rule_keyword(self):
        text = VALID.replace("  # AC-01 - happy path.\n", "  Rule: Saving\n  # AC-01 - happy path.\n")
        self.assertIn("P4", rule_fails(text))

    def test_p5_title_too_long(self):
        text = VALID.replace("Save the form", "x" * 250)
        self.assertIn("P5", rule_fails(text))

    def test_p6_tag_too_long(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @" + "a" * 120 + " @screen", 1)
        self.assertIn("P6", rule_fails(text))

    def test_boolean_is_not_a_length_limit(self):
        self.assertEqual(rule_fails(VALID.replace("Save the form", "x" * 250), {"maxTitleLength": True}), [])


class ConfigDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "test-cases" / "Area").mkdir(parents=True)
        self.feature = self.root / "test-cases" / "Area" / "x.feature"
        self.feature.write_text(VALID.replace("Feature: Sample\n", "@area\nFeature: Sample\n"), encoding="utf-8")

    def write_config(self, data):
        (self.root / ".claude").mkdir(exist_ok=True)
        path = self.root / ".claude" / "qaqc.json"
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return path

    def test_cli_discovers_config_upwards(self):
        self.write_config({"importRules": C4K_RULES})
        out = io.StringIO()
        self.assertEqual(vf.run_cli([str(self.feature)], out), 1)
        self.assertIn("P1", out.getvalue())
        self.assertIn("import rules:", out.getvalue())

    def test_cli_explicit_config(self):
        cfg = self.root / "elsewhere.json"
        cfg.write_text(json.dumps({"importRules": C4K_RULES}), encoding="utf-8")
        self.assertEqual(vf.main(["--config", str(cfg), str(self.feature)]), 1)

    def test_no_import_rules_key_means_generic_checks_only(self):
        self.write_config({"projectContext": "PROJECT.md"})
        self.assertEqual(vf.run_cli([str(self.feature)], io.StringIO()), 0)

    def test_malformed_config_is_reported_not_fatal(self):
        self.write_config("{not json")
        out = io.StringIO()
        self.assertEqual(vf.run_cli([str(self.feature)], out), 0)
        self.assertIn("could not read", out.getvalue())

    def test_hook_uses_discovered_config(self):
        self.write_config({"importRules": C4K_RULES})
        err = io.StringIO()
        payload = json.dumps({"tool_input": {"file_path": str(self.feature)}})
        self.assertEqual(vf.run_hook(io.StringIO(payload), err), 2)
        self.assertIn("P1", err.getvalue())


class HeuristicsTest(unittest.TestCase):
    def test_g15_duplicate_title_is_warn(self):
        dup = VALID.split("  @negative")[0]
        text = dup + dup.split("Feature: Sample\n", 1)[1]
        found = [(f.code, f.severity) for f in vf.validate(text)]
        self.assertIn(("G15", "WARN"), found)
        self.assertEqual([c for c, s in found if s == "FAIL"], [])

    def test_g16_unobservable_then_is_warn(self):
        text = VALID.replace("    When User taps Save\n", "    When The stored record is inspected server-side\n")
        self.assertEqual([(f.code, f.severity) for f in vf.validate(text)], [("G16", "WARN")])

    def test_g16_ignores_given_setup(self):
        text = VALID.replace("    Given User is on the form\n", "    Given The account was created server-side\n", 1)
        self.assertEqual(codes(text), [])

    def test_g16_delivery_log(self):
        text = VALID.replace('    Then The confirmation "Saved" is displayed\n', "    Then The delivery log shows the SMS was sent\n")
        self.assertIn("G16", codes(text))


TAG_RULES = {
    "direction": ["@positive", "@negative"],
    "checkType": ["@logic", "@navigation", "@ui", "@a11y"],
    "gates": ["@not-implemented", "@blocked", "@manual", "@pending-oq"],
    "platform": ["@ios-only", "@android-only"],
    "area": ["@area"],
    "titlePrefix": {"@positive": "Positive - ", "@negative": "Negative - "},
}


def tag_fails(text, tag_rules=TAG_RULES):
    return [f.code for f in vf.validate(text, None, tag_rules) if f.severity == "FAIL"]


class TagRulesTest(unittest.TestCase):
    def test_valid_file_passes(self):
        self.assertEqual(tag_fails(VALID), [])

    def test_p7_two_check_types(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @navigation @area @screen", 1)
        self.assertIn("P7", tag_fails(text))

    def test_p7_missing_direction(self):
        text = VALID.replace("@positive @logic @area @screen", "@logic @area @screen", 1)
        self.assertIn("P7", tag_fails(text))

    def test_p8_check_type_before_direction(self):
        text = VALID.replace("@positive @logic @area @screen", "@logic @positive @area @screen", 1)
        self.assertEqual(tag_fails(text), ["P8"])

    def test_p8_gate_after_area(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @area @manual @screen", 1)
        self.assertIn("P8", tag_fails(text))

    def test_gates_and_platform_in_order_pass(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @blocked @manual @ios-only @area @screen", 1)
        self.assertEqual(tag_fails(text), [])

    def test_p9_unknown_extra_tag(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @area @screen @accessibility", 1)
        self.assertIn("P9", tag_fails(text))

    def test_p9_missing_area(self):
        text = VALID.replace("@positive @logic @area @screen", "@positive @logic @screen", 1)
        self.assertIn("P9", tag_fails(text))

    def test_p10_prefix_disagrees_with_direction(self):
        text = VALID.replace("Scenario: Positive - Save the form", "Scenario: Negative - Save the form")
        self.assertEqual(tag_fails(text), ["P10"])

    def test_no_tag_rules_no_checks(self):
        text = VALID.replace("@positive @logic @area @screen", "@logic @positive @area @screen", 1)
        self.assertEqual(tag_fails(text, None), [])

    def test_examples_tags_are_not_scenario_tags(self):
        text = VALID.replace("    Examples:\n", "    @rows\n    Examples:\n")
        self.assertEqual(tag_fails(text), [])


IMPORT_COMMENT = ["# IMPORT RULES: keep this file importable.", "# Second line of the rules."]


class ImportCommentTest(unittest.TestCase):
    def test_p11_comment_present_passes(self):
        text = VALID.replace("Feature: Sample\n", "\n".join(IMPORT_COMMENT) + "\nFeature: Sample\n")
        self.assertEqual(codes_with_comment(text), [])

    def test_p11_comment_missing_is_warn(self):
        found = [(f.code, f.severity) for f in vf.validate(VALID, None, None, IMPORT_COMMENT)]
        self.assertEqual(found, [("P11", "WARN")])

    def test_p11_comment_reworded_is_warn(self):
        text = VALID.replace("Feature: Sample\n", "# IMPORT RULES\n#   - my own words\nFeature: Sample\n")
        self.assertIn("P11", codes_with_comment(text))


def codes_with_comment(text):
    return [f.code for f in vf.validate(text, None, None, IMPORT_COMMENT)]


class ConfigTemplateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".claude").mkdir()
        (self.root / "t").mkdir()
        (self.root / "t" / "TEMPLATE.feature").write_text(
            "# header\n" + "\n".join(IMPORT_COMMENT) + "\nFeature: <name>\n", encoding="utf-8")
        (self.root / ".claude" / "qaqc.json").write_text(json.dumps({
            "template": "t/TEMPLATE.feature", "tagRules": TAG_RULES}), encoding="utf-8")
        self.feature = self.root / "t" / "x.feature"

    def test_template_comment_and_tag_rules_load_from_config(self):
        self.feature.write_text(VALID.replace("@positive @logic @area @screen", "@logic @positive @area @screen", 1),
                                encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(vf.run_cli([str(self.feature)], out), 1)
        self.assertIn("P8", out.getvalue())
        self.assertIn("P11", out.getvalue())

    def test_plugin_default_template_when_template_is_null(self):
        (self.root / ".claude" / "qaqc.json").write_text(json.dumps({"template": None}), encoding="utf-8")
        self.feature.write_text(VALID, encoding="utf-8")
        out = io.StringIO()
        vf.run_cli([str(self.feature)], out)
        self.assertIn("P11", out.getvalue())


if __name__ == "__main__":
    unittest.main()
