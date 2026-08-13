"""Where does each field actually live on the page?

Templates failed because a field's exact position moves between documents. But moving is
not the same as being anywhere — across thousands of invoices a field occupies a fairly
small region of the page. This builds that region per field, so the model can be shown a
slice of the document instead of all of it.

Coordinates are already page fractions, so no resizing is needed: a 50x50 grid over the
unit square is directly comparable across every document whatever its physical size.

The number that matters is at the bottom: what fraction of the page you must keep in order
to still contain the answer N% of the time.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data                                            # noqa: E402

GRID = 50
OUT = Path("data/heatmap.json")

# The five fields present on ~95% of invoices. Everything else drops off a cliff after
# these, and an AP team needs exactly this: who it is for, how much, when, and from whom.
FIELDS = [
    "customer_billing_name",     # 97%
    "amount_due",                # 95%
    "date_issue",                # 95%
    "amount_total_gross",        # 95%
    "vendor_address",            # 91%
]


def cells_covered(box: list[float]) -> list[tuple[int, int]]:
    """Every cell the box touches, not just the one under its centre.

    Marking centres builds a region that the field's own text spills out of — we would
    hand the model a crop with the value half cut off. Covering the whole box makes the
    region larger, which is the right trade: a bigger crop that reliably contains the
    answer beats a small one that clips it.
    """
    c0 = min(int(box[0] * GRID), GRID - 1)
    c1 = min(int(box[2] * GRID), GRID - 1)
    r0 = min(int(box[1] * GRID), GRID - 1)
    r1 = min(int(box[3] * GRID), GRID - 1)
    return [(r, c) for r in range(min(r0, r1), max(r0, r1) + 1)
            for c in range(min(c0, c1), max(c0, c1) + 1)]


def build(doc_ids: list[str]) -> dict[str, dict]:
    counts: dict[str, dict[tuple[int, int], int]] = defaultdict(lambda: defaultdict(int))

    for doc_id in doc_ids:
        for name, info in data.fields(doc_id).items():
            if name in FIELDS and info.get("page", 0) == 0:
                for rc in cells_covered(info["box"]):
                    counts[name][rc] += 1

    return {name: dict(cells) for name, cells in counts.items()}


def coverage(cells: dict[tuple[int, int], int], want: float) -> tuple[int, float]:
    """Hottest cells needed to contain `want` of all occurrences, and the page area they use."""
    total = sum(cells.values())
    if not total:
        return 0, 0.0
    running = 0
    for n, count in enumerate(sorted(cells.values(), reverse=True), 1):
        running += count
        if running / total >= want:
            return n, n / (GRID * GRID)
    return len(cells), len(cells) / (GRID * GRID)


def render(cells: dict[tuple[int, int], int], width: int = 46, height: int = 22) -> str:
    """Coarse ASCII picture of where the field lands."""
    grid = [[0] * width for _ in range(height)]
    for (row, col), count in cells.items():
        grid[min(int(row / GRID * height), height - 1)][min(int(col / GRID * width), width - 1)] += count
    peak = max((v for r in grid for v in r), default=0) or 1
    ramp = " .:-=+*#%@"
    return "\n".join(
        "".join(ramp[min(int(v / peak * (len(ramp) - 1)), len(ramp) - 1)] for v in row)
        for row in grid
    )


def main():
    splits = data.splits()
    build_ids = splits["build"]
    print(f"building heat map from {len(build_ids)} documents, {GRID}x{GRID} grid\n")

    maps = build(build_ids)
    ranked = sorted(maps.items(), key=lambda kv: -sum(kv[1].values()))

    print(f"{'field':<30}{'seen':>7}{'cells@80%':>11}{'page@80%':>10}{'page@90%':>10}")
    print("-" * 68)
    saved80 = []
    for name, cells in ranked:
        n80, a80 = coverage(cells, 0.80)
        _, a90 = coverage(cells, 0.90)
        saved80.append(a80)
        print(f"{name:<30}{sum(cells.values()):>7}{n80:>11}{a80:>9.1%}{a90:>9.1%}")

    print(f"\nmean page area needed to hold 80% of occurrences: {sum(saved80)/len(saved80):.1%}")
    print(f"→ context reduction of roughly {1 - sum(saved80)/len(saved80):.0%} per field\n")

    for name, _ in ranked:
        print(f"--- {name} ---")
        print(render(maps[name]))
        print()

    OUT.write_text(json.dumps(
        {name: {f"{r},{c}": v for (r, c), v in cells.items()} for name, cells in maps.items()}))
    print(f"wrote {OUT} ({len(maps)} fields)")


if __name__ == "__main__":
    main()
