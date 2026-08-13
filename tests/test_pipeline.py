"""End-to-end extraction logic for amount_due, with the model injected as a stub.

The four outcomes the product depends on, plus the hallucination veto that keeps an
invented value out of the report.
"""
from api.fields import FIELDS
from api.pipeline import extract_amount
from api.region import load as load_region

REGION = load_region(FIELDS["amount_due"].region_path)


def test_crop_answered_is_ok_and_confident(words):
    row = extract_amount(words, REGION, lambda system, text: "$1,290.00")
    assert row["value"] == "$1,290.00"
    assert row["status"] == "ok"
    assert row["used_fallback"] is False
    assert row["confidence"] == 0.95
    assert row["box"] is not None            # located on the page


def test_fallback_answer_goes_to_review(words):
    # The stub can only find it once it sees the whole page (the header word 'INVOICE'
    # is outside the region), so this exercises the crop-miss → full-page fallback.
    def ask(system, text):
        return "$1,290.00" if "INVOICE" in text else "NOT_FOUND"

    row = extract_amount(words, REGION, ask)
    assert row["value"] == "$1,290.00"
    assert row["used_fallback"] is True
    assert row["status"] == "review"
    assert row["confidence"] == 0.65


def test_nothing_found_is_not_found(words):
    row = extract_amount(words, REGION, lambda system, text: "NOT_FOUND")
    assert row["status"] == "not_found"
    assert row["value"] is None
    assert row["confidence"] == 0.0


def test_hallucinated_value_is_vetoed(words):
    # A value that never appears in the OCR text must not be reported as fact.
    row = extract_amount(words, REGION, lambda system, text: "$9,999.99")
    assert row["status"] == "review"
    assert row["confidence"] == 0.0
    assert "verbatim" in (row["reason"] or "")
