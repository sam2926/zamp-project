"""What we extract, and how we judge it — per field.

Today there is one field, `amount_due`, deliberately: the project went deep on one field
rather than shallow on the 55 DocILE ships. The prompt here is the exact one that produced
the reported numbers (see `scripts/baseline_field.py`), so the deployed product behaves as
measured rather than as some untested variant.

Confidence is the honest signal from the measurements, not the hand-set weights that flagged
84 of 85 documents. On the val run, whether the value fell inside its expected region
separated 99% accuracy (crop answered) from 65% (fell back). So confidence is driven by that
one fact, and it is the number the report shows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Must match scripts/baseline_field.py PROMPTS["amount_due"] — same string, same behaviour.
AMOUNT_DUE_PROMPT = """You read text extracted from a scanned invoice and return one field.

The field is the AMOUNT DUE: the total the customer must actually pay on this invoice. If
part has already been paid, it is the remaining balance, not the gross total. Captions
include "Amount Due", "Balance Due", "Total Due", "Please Pay This Amount", "Net Due".

Rules:
- Return the value exactly as it appears, including any currency symbol and separators.
  If the text reads "$1,024.00", return "$1,024.00" — do not convert to 1024.
- Return only the amount, never its caption.
- If it is not present, return exactly: NOT_FOUND

Reply with the value alone. No explanation, no quotes, no label."""

# Measured on the val run: 99% correct when the crop answered, 65% when it fell back.
# These are those two numbers, rounded down a touch so the headline never over-promises.
CONF_CROP = 0.95
CONF_FALLBACK = 0.65

_MONEYISH = re.compile(r"^[£$€]?\s?[\d][\d,]*\.?\d*$")


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    prompt: str
    region_path: Path


FIELDS: dict[str, Field] = {
    "amount_due": Field(
        name="amount_due",
        label="Amount due",
        prompt=AMOUNT_DUE_PROMPT,
        # The 80% region: tighter beat wider on the live run — fewer distractors, not less
        # context (decisions.md, "How big should the crop be?").
        region_path=Path("data/region_amount_due_80.json"),
    ),
}


def _squash(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def validate_amount(value: str | None, words: list[dict]) -> list[dict]:
    """Deterministic checks for a money value. None of these consult a model."""
    checks: list[dict] = []

    def add(rule: str, passed: bool, detail: str = ""):
        checks.append({"rule": rule, "passed": passed, "detail": detail})

    if not value:
        add("present", False, "no value returned")
        return checks

    v = value.strip()
    add("present", True)
    add("in_source_text", _squash(v) in _squash(" ".join(w["text"] for w in words)),
        "the value must appear in the OCR text; anything else was invented")
    add("has_digits", bool(re.search(r"\d", v)), "an amount contains digits")
    add("money_shaped", bool(_MONEYISH.match(v)),
        "looks like an amount — optional currency mark, digits, separators")
    return checks
