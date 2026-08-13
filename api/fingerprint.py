"""Layout fingerprinting: is this the same form we have seen before?

A vendor's invoice template prints the same labels in the same places every time; only
the values change. So we build a signature from the *static* text and its position, and
two documents with a high enough overlap are treated as the same layout.

This decides whether a document is free to process (known layout, read stored coordinates)
or expensive (unknown layout, pay a model to map it). Getting it wrong means either paying
twice for documents we already knew, or reading a new vendor's invoice with the wrong map.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Page is divided into this many cells. Coarse enough to survive small shifts,
# fine enough that two different forms rarely collide.
GRID_COLS = 8
GRID_ROWS = 12

# Words shaped like values rather than labels. Dropped, because keeping them would
# make every invoice look like a new layout — no two share a total.
_NUMERIC = re.compile(r"\d")
_DATEISH = re.compile(r"^\d{1,4}[-/.]\d{1,2}([-/.]\d{1,4})?$")
_MONEYISH = re.compile(r"^[£$€]?[\d,]+\.?\d*$")


def is_static(word: str) -> bool:
    """True if the word looks like part of the form rather than this invoice's content."""
    w = word.strip()
    if len(w) < 2:
        return False
    if _DATEISH.match(w) or _MONEYISH.match(w):
        return False
    # Mostly digits => an id, a code, an amount. Not a label.
    digits = len(_NUMERIC.findall(w))
    if digits and digits / len(w) > 0.3:
        return False
    return any(c.isalpha() for c in w)


def _cell(box: list[float]) -> tuple[int, int]:
    """Grid cell containing the centre of a normalised [l, t, r, b] box."""
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    col = min(int(cx * GRID_COLS), GRID_COLS - 1)
    row = min(int(cy * GRID_ROWS), GRID_ROWS - 1)
    return col, row


def signature(words: list[dict]) -> frozenset[tuple[str, int, int]]:
    """(word, col, row) for every static word on the first page.

    `words` is [{"text": str, "box": [l, t, r, b], "page": int}, ...].
    Only page 0 is used: the first page carries the letterhead and totals, which is
    what identifies a vendor. Later pages are mostly line-item continuations.
    """
    sig = set()
    for w in words:
        if w.get("page", 0) != 0:
            continue
        text = w["text"].strip().upper()
        if is_static(text):
            col, row = _cell(w["box"])
            sig.add((text, col, row))
    return frozenset(sig)


def jaccard(a: frozenset, b: frozenset) -> float:
    """Shared items divided by total distinct items. 1.0 identical, 0.0 nothing in common."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Match:
    layout_id: str | None
    score: float
    known: bool
    runner_up: float = 0.0


class LayoutIndex:
    """Stores one signature per known layout and matches new documents against them.

    Two guards, both necessary:

      threshold  the match must be good in absolute terms
      margin     it must also clearly beat the runner-up

    The margin is what makes this safe. Pair-level precision of 98% answers "are these two
    the same layout?" — but retrieval asks "which of 722 layouts is this?", and small
    per-pair error compounds across every candidate. Without a margin, 19% of documents
    matched a different vendor's template. With one, 3%.

    Failing to match is cheap: the model handles the document. Matching the wrong vendor is
    not — it puts confident, wrong values into the pipeline.
    """

    def __init__(self, threshold: float = 0.10, margin: float = 2.0):
        self.threshold = threshold
        self.margin = margin
        self._sigs: dict[str, frozenset] = {}

    def add(self, layout_id: str, sig: frozenset) -> None:
        self._sigs[layout_id] = sig

    def match(self, sig: frozenset) -> Match:
        best_id, best_score, runner_up = None, 0.0, 0.0
        for layout_id, known_sig in self._sigs.items():
            score = jaccard(sig, known_sig)
            if score > best_score:
                best_id, best_score, runner_up = layout_id, score, best_score
            elif score > runner_up:
                runner_up = score

        confident = (
            best_score >= self.threshold
            and (runner_up == 0.0 or best_score >= runner_up * self.margin)
        )
        return Match(best_id, best_score, confident, runner_up)

    def match_or_create(self, sig: frozenset, new_id: str) -> Match:
        """Match against known layouts, or register this as a new one."""
        m = self.match(sig)
        if m.known:
            return m
        self.add(new_id, sig)
        return Match(new_id, m.score, False, m.runner_up)

    def __len__(self) -> int:
        return len(self._sigs)
