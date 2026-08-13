"""The learned page-region: geometry that decides what the model is allowed to see.

These catch the failure modes the design was built around — a box counted by its centre
instead of its whole footprint, a region that lets a half-value in, a learned rectangle
that isn't actually minimal.
"""
from api.region import (
    Region,
    cells_covered,
    crop,
    density_boxes,
    learn_region,
    rows,
)


def test_cells_covered_counts_whole_box_not_centre():
    # A box straddling a cell boundary must touch both cells, not just the one under
    # its centre — otherwise the region clips the value's tail.
    box = [0.19, 0.19, 0.21, 0.21]  # spans the 10<->10 boundary at grid 50
    cells = cells_covered(box, grid=50)
    assert len(cells) >= 2


def test_contains_is_strict_overlaps_is_lax():
    r = Region(10, 10, 40, 40, grid=50)
    inside = [0.30, 0.30, 0.50, 0.50]
    straddling = [0.70, 0.30, 0.90, 0.50]  # right edge pokes outside
    assert r.contains(inside)
    assert not r.contains(straddling)   # half-in is not good enough
    assert r.overlaps(straddling)       # but it still touches


def test_learn_region_is_minimal_and_covers_target():
    # Boxes clustered in the bottom-right; a couple of outliers elsewhere.
    boxes = [[0.80, 0.80, 0.85, 0.83]] * 20 + [[0.05, 0.05, 0.08, 0.07]]
    r = learn_region(boxes, coverage=0.95, grid=50)
    contained = sum(1 for b in boxes if r.contains(b))
    assert contained / len(boxes) >= 0.90       # covers the target mass
    assert r.area < 0.5                          # and stays tight, not the whole page


def test_density_boxes_roundtrip_reproduces_region():
    boxes = [[0.80, 0.80, 0.85, 0.83]] * 12 + [[0.70, 0.75, 0.74, 0.78]] * 6
    r = learn_region(boxes, coverage=0.95, grid=50)
    r2 = learn_region(density_boxes(r), coverage=0.95, grid=50)
    # Feeding the reconstructed boxes back must yield the same rectangle, so a re-learn
    # can fold in corrections without the original corpus.
    assert (r2.r0, r2.c0, r2.r1, r2.c1) == (r.r0, r.c0, r.r1, r.c1)


def test_crop_keeps_only_words_touching_the_region(words):
    r = Region(5, 18, 48, 48, grid=50)   # the deployed amount_due rectangle
    kept = {w["text"] for w in crop(words, r)}
    assert "$1,290.00" in kept           # totals block is inside
    assert "INVOICE" not in kept         # header is outside


def test_rows_groups_reading_order_lines(words):
    lines = rows(words)
    texts = [" ".join(w["text"] for w in line) for line in lines]
    assert "TOTAL DUE $1,290.00" in texts   # same row, left-to-right
