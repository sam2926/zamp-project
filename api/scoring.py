"""How we decide a predicted value matches the truth.

One module, used by every script that reports a number, so the headline figure cannot
drift between harnesses.

The subtlety this exists for: billing names are multi-line — "ACME CORP\n41 HIGH ST\nLEEDS".
OCR reading order does not always reproduce the order the annotator typed, so comparing
concatenated strings marks a *correct* answer wrong purely because line 2 and line 3 swapped.
Measured on the first live run, that alone failed 3 of 9 documents. So we compare the set of
lines, not the sequence.

We do not go further than that. Fuzzy or partial matching would flatter us: "ACME CORP LTD"
is not "ACME CORP" to an AP team paying the invoice, and a scorer that says otherwise makes
the accuracy number a marketing figure rather than a measurement.
"""
from __future__ import annotations

import re


def squash(s: str | None) -> str:
    """Alphanumerics only, uppercased. Punctuation, spacing and case are OCR noise."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def line_set(s: str | None) -> frozenset[str]:
    """The value as an unordered set of squashed lines. Empty lines dropped."""
    return frozenset(x for x in (squash(ln) for ln in (s or "").splitlines()) if x)


def matches(predicted: str | None, truth: str | None) -> bool:
    """True if the prediction is the truth, ignoring line order.

    Two ways to pass, and the second is strictly wider than the first:
      - the squashed strings are equal (single-line values, and multi-line ones in order)
      - the sets of squashed lines are equal (same lines, different order)
    """
    if not predicted or not truth:
        return False
    if squash(predicted) == squash(truth):
        return True
    p, t = line_set(predicted), line_set(truth)
    return bool(p) and p == t


def contains_value(truth: str | None, words: list[dict]) -> bool:
    """Is the truth reachable at all from these words?

    Separates "the model got it wrong" from "the value was never in what we sent it" —
    the second is a crop bug, not a model failure, and they need different fixes.
    """
    blob = squash(" ".join(w["text"] for w in words))
    return all(ln in blob for ln in line_set(truth)) if truth else False
