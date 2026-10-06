# =============================================================================
# Feature: <Feature name>  (<CASE-ID, e.g. US-001 / DR-002-002-02>)
# Source: "<spec title>" v<n> (<author>, <DD Mon YYYY>)
# Figma: <paste the Figma URL / frame, or <TODO>>
# Implementation: <src/.../Screen.tsx and any schema/strings files, if known>
#
# Tag legend (canonical list + procedure: .claude/skills/PROJECT.md §6 —
# keep only the tags this file uses):
#   @positive @negative  -> expected vs error/edge path (one per scenario)
#   @logic               -> business rule / behaviour
#   @navigation          -> screen transition
#   @ui                  -> visual / Figma-conformance  (NOT Maestro-automatable)
#   @a11y                -> accessibility               (NOT Maestro-automatable)
#   @manual              -> tester can set it up alone, a flow cannot (NOT automatable)
#   @blocked             -> needs backend data/config; see the # [BACKEND] comment
#   @not-implemented     -> screen not built yet
#   @pending-oq          -> depends on an open question (OQ-xx)
#   @ios-only @android-only -> exists on one OS only
#   @<area>              -> folder area tag (PROJECT.md §6.2)
#   @<screen>            -> screen tag = this file's name without .feature
# Tag order: direction, check type, gates, platform, area, screen.
#
# SPEC-DIFFS (app is the source of truth — assertions match the app; file these):
#   1. <where the app diverges from the spec, and what the app actually does>
#
# PRECONDITIONS
#   Environment : dev   (appId: ${APP_ID} — see ../environments/dev.env)
#   Auth        : <signed-in required? unauthenticated -> redirected to sign-in>
#   Entry point : <how the user reaches this screen>
#   State reset : <how to restore state between runs so prefill is deterministic>
#   Markers     : [BACKEND] -> not UI-verifiable from this screen.
#
# TEST DATA
#   | role          | value             | notes                                  |
#   | <name>        | "<value>"         | <what it represents>                   |
#
# MAESTRO CONVERTIBILITY
#   ✅ now      : <scenarios automatable today via text/testID selectors>
#   [BACKEND]   : <scenarios needing backend/account control>
#   ❌ not auto : @ui Figma conformance, @a11y, and any non-deterministic timers
# =============================================================================

# IMPORT RULES: this file must import into the C4K Test Case Tool unchanged.
# See CLAUDE.md "Import compatibility". In short: no tags and no description
# under Feature:, Given + When + Then in every scenario, and comments on their
# own line only.
Feature: <Feature name>
  # As a <role>
  # I want to <capability>
  # So that <benefit>

  @positive @ui @<area> @<screen>
  Scenario: Positive - Verify the <screen> UI matches the Figma design
    Given User has navigated to the <screen> screen
    When The <screen> screen finishes loading
    Then <visible element 1 is displayed>
    And <visible element 2 is displayed>
    And All elements (color, font Poppins, size, position) match the Figma design

  @positive @logic @<area> @<screen>
  Scenario: Positive - <happy-path behaviour>
    Given <starting state>
    When <user action>
    Then <expected app-truth outcome>

  @negative @logic @<area> @<screen>
  Scenario: Negative - <error / edge path>
    Given <starting state>
    When <invalid action>
    Then <inline error / blocked outcome>

  @positive @navigation @<area> @<screen>
  Scenario: Positive - <screen transition>
    Given <starting state>
    When <user navigates>
    Then The system navigates to <destination>

  # One behaviour across an equivalence partition. Every Examples column must
  # appear as <column> in a step; notes about a row go in a # comment.
  @negative @logic @<area> @<screen>
  Scenario Outline: Negative - <behaviour> for <input>
    Given <starting state>
    When User enters <input>
    Then <expected outcome>

    Examples:
      | input     |
      | <value 1> |
      | <value 2> |

# =============================================================================
# COVERAGE (reference only — spec AC/Rule numbers, NOT used as tags)
# AC-01 -> ... | AC-02 -> ...
# =============================================================================
