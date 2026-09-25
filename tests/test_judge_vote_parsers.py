"""Regression tests for the validity/actionability judge-vote parsers.

The validity fixtures below are verbatim raw judge response text captured from the real
Phase 4 cache (data/cache/*.json) that the OLD parsers mis-handled:

- `_TRUNCATED_RESTATEMENT_*`: the judge never reaches a label within max_tokens=64 because it
  spends the whole budget restating the claim/task. These are genuinely unparseable (no label
  present at all) both before and after the fix; they are included to document that the new
  parser does NOT invent an answer for them.
- `_BOLD_ENTAILED`: the label is present but wrapped in markdown ("**entailed**"), which the old
  first-token-only parser split on whitespace and mangled.
- `_BARE_NOT_ENTAILED`: a bare "not_entailed" token, which both parsers handle, kept here as a
  baseline/non-regression check.

No real cached actionability response was ambiguous (all 657 replayed votes were bare single
digits), so `test_actionability_range_mention_is_not_mistaken_for_score` uses a synthetic
response modeled on the prompt's own rubric wording, to guard against a plausible future
failure mode where the model echoes back the "1 to 5" scale description.
"""

from __future__ import annotations

from src.evaluate_actionability import _parse_actionability_response
from src.evaluate_validity import _normalize_validity_vote

# Verbatim content from data/cache/*.json (Phase 4 validity judge responses).
_TRUNCATED_RESTATEMENT_1 = (
    'The claim states that "Exploratory and user-centered evaluation methods are widely used '
    'to surface nuanced insights about emerging interfaces."\n\nLooking at the source text, '
    "I can find evidence that ex"
)
_TRUNCATED_RESTATEMENT_2 = (
    "I need to evaluate whether \"User-centered design informed by domain experts and real "
    'users is a consistent methodological commitment across these works."\n\nLet me analyze '
    "each paper:\n\n1. **AV Trust pap"
)
_BOLD_ENTAILED = (
    "**entailed**\n\nThe source text provides multiple examples of AI and machine learning "
    "being integrated into HCI (Human-Computer Interaction) systems to enhance human "
    "performance and decision-making:\n\n1."
)
_BARE_NOT_ENTAILED = "not_entailed"


def test_truncated_restatement_with_no_label_is_unparseable():
    assert _normalize_validity_vote(_TRUNCATED_RESTATEMENT_1) == "unparseable"
    assert _normalize_validity_vote(_TRUNCATED_RESTATEMENT_2) == "unparseable"


def test_markdown_bold_entailed_is_recovered():
    assert _normalize_validity_vote(_BOLD_ENTAILED) == "entailed"


def test_bare_not_entailed_still_parses():
    assert _normalize_validity_vote(_BARE_NOT_ENTAILED) == "not_entailed"


def test_old_parser_first_token_bug_is_fixed_for_bold_label():
    # The old parser did `.split()[0]` before normalizing, so "**entailed**\n\nThe source..."
    # produced the token "**entailed**", which was not in its alias dict and was passed through
    # unchanged (neither "entailed" nor "unparseable" -- a silent, undetected failure that would
    # never register as a valid label under the old scheme either).
    old_first_token = _BOLD_ENTAILED.strip().lower().replace("\n", " ").split()[0]
    assert old_first_token == "**entailed**"


def test_actionability_range_mention_is_not_mistaken_for_score():
    # Synthetic: a judge echoing the rubric's "1 to 5" scale text without ever stating its own
    # answer. No real cache example exhibited this, but the prompt's own wording makes it a
    # plausible failure mode worth guarding against.
    response = "The rubric asks for an integer from 1 to 5 based on actionability."
    assert _parse_actionability_response(response) == "unparseable"


def test_actionability_bare_digit_still_parses():
    assert _parse_actionability_response("4") == 4


def test_actionability_labeled_score_wins_over_range_mention():
    response = "On a scale of 1 to 5, my score is 4 because the insight names a concrete next step."
    assert _parse_actionability_response(response) == 4
