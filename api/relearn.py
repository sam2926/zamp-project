"""Step 9: fold human corrections back into the region.

A correction tells us two things. That this document's answer was wrong — worth little,
we will not see it again. And *where the right answer actually sat* — worth a great deal,
because it is evidence about every invoice shaped like this one.

So corrections are appended to the boxes the region was learned from, and the rectangle is
recomputed. Over time the region moves toward where this customer's invoices really put the
field, rather than where the original training set did.
"""
from __future__ import annotations

import json
from pathlib import Path

from .region import Region, learn_region, save
from .store import correction_boxes, connect

# A single correction should not move the region — one reviewer's mistake would drag it.
# Wait until there are enough to be a pattern rather than an accident.
MIN_CORRECTIONS = 15
# Corrections describe this customer's documents, so they count for more than a training
# example — but not so much that fifteen of them overwhelm three thousand.
CORRECTION_WEIGHT = 5


def should_relearn(conn, field: str, last_count: int = 0) -> bool:
    return len(correction_boxes(conn, field)) - last_count >= MIN_CORRECTIONS


def relearn(field: str, original_boxes: list[list[float]], region_path: Path,
            conn=None, coverage: float = 0.95) -> tuple[Region, dict]:
    """Recompute the region from the original examples plus weighted corrections."""
    conn = conn or connect()
    corrections = correction_boxes(conn, field)
    if not corrections:
        raise ValueError("no corrections to learn from")

    before = json.loads(region_path.read_text()) if region_path.exists() else None
    boxes = list(original_boxes) + corrections * CORRECTION_WEIGHT
    region = learn_region(boxes, coverage=coverage)
    save(region, region_path)

    report = {
        "corrections_used": len(corrections),
        "training_boxes": len(original_boxes),
        "area_before": (
            ((before["rect"][2] - before["rect"][0]) * (before["rect"][3] - before["rect"][1]))
            / (before["grid"] ** 2) if before else None
        ),
        "area_after": region.area,
        "rect_before": before["rect"] if before else None,
        "rect_after": [region.r0, region.c0, region.r1, region.c1],
    }
    return region, report
