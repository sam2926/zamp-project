"""What shape should this field's value be?

A template box says roughly where a value sits, but scans drift and a fixed box lands on
the wrong row. Knowing that `amount_total_gross` must look like money lets us search a
window instead of trusting a point — and reject the label text sitting next to it.
"""
from __future__ import annotations

import re

MONEY = re.compile(r"^[\(\-]?[£$€]?\s?\d{1,3}([,\s]?\d{3})*([.,]\d{1,2})?\)?$")
DATE = re.compile(
    r"^(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}"
    r"|\d{1,2}\s?[-/]?\s?(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?,?\s?\d{2,4}"
    r"|(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?\s?\d{1,2},?\s?\d{2,4})$",
    re.I,
)
IDENT = re.compile(r"^[A-Z0-9][A-Z0-9\-/#.]{2,}$", re.I)
CURRENCY = re.compile(r"^(USD|EUR|GBP|JPY|CAD|AUD|CHF|[£$€])$", re.I)

MONEY_FIELDS = ("amount", "price", "tax", "total", "subtotal", "discount", "paid", "due")
DATE_FIELDS = ("date",)
ID_FIELDS = ("_id", "num", "code", "reference", "registration")


def kind(field_name: str) -> str:
    """money · date · ident · currency · text — from the field's name."""
    n = field_name.lower().replace("line_item_", "")
    if n.startswith("currency"):
        return "currency"
    if any(k in n for k in DATE_FIELDS):
        return "date"
    if any(k in n for k in MONEY_FIELDS):
        return "money"
    if any(n.endswith(k) or k in n for k in ID_FIELDS):
        return "ident"
    return "text"


def matches(value: str, expected: str) -> bool:
    """Does this token look like the kind of thing we are after?"""
    v = (value or "").strip()
    if not v:
        return False
    if expected == "money":
        return bool(MONEY.match(v)) and any(c.isdigit() for c in v)
    if expected == "date":
        return bool(DATE.match(v))
    if expected == "currency":
        return bool(CURRENCY.match(v))
    if expected == "ident":
        return bool(IDENT.match(v)) and any(c.isdigit() for c in v)
    return True                       # text accepts anything


def is_multiword(field_name: str) -> bool:
    """Names and addresses span several words and often several lines.

    Nearly half of all target values are multi-word or multi-line, so these must be
    assembled from a region rather than read as a single token.
    """
    n = field_name.lower()
    return kind(n) == "text" or n.endswith("_address") or n.endswith("_name")
