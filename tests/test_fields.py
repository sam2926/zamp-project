"""Deterministic amount checks and the confidence constants."""
from api.fields import CONF_CROP, CONF_FALLBACK, validate_amount


def _passed(checks, rule):
    return next(c["passed"] for c in checks if c["rule"] == rule)


def test_money_shaped_values_pass(words):
    checks = validate_amount("$1,290.00", words)
    assert _passed(checks, "present")
    assert _passed(checks, "in_source_text")
    assert _passed(checks, "has_digits")
    assert _passed(checks, "money_shaped")


def test_non_money_is_flagged(words):
    checks = validate_amount("MAR26", words)          # a caption, not an amount
    assert not _passed(checks, "money_shaped")


def test_value_absent_from_text_fails_source_check(words):
    checks = validate_amount("$9,999.99", words)      # never on the page
    assert not _passed(checks, "in_source_text")


def test_missing_value_has_no_present():
    checks = validate_amount(None, words=[])
    assert not _passed(checks, "present")


def test_confidence_constants_are_ordered():
    # The measured signal: crop-answered is far more trustworthy than a fallback.
    assert 0 < CONF_FALLBACK < CONF_CROP <= 1.0
