"""Where on the page a field lives, learned from labelled documents.

A field's exact coordinates are not stable — measured across this corpus, the same field
moves 4-5 line heights between two invoices of the same layout, so a stored box misses it.
Its *neighbourhood* is stable: across 3,142 invoices spanning 722 different layouts,
customer_billing_name lands inside one rectangle covering 21% of the page 92% of the time.

So we do not store where the value was. We store where values of this kind tend to be, and
hand the model that slice of the document instead of the whole thing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

GRID = 50


def cells_covered(box: list[float], grid: int = GRID) -> list[tuple[int, int]]:
    """Every cell the box touches — not the one under its centre.

    Counting centres builds a region the field's own text spills out of, and we would hand
    the model a crop with the value half cut off.
    """
    c0, c1 = sorted((min(int(box[0] * grid), grid - 1), min(int(box[2] * grid), grid - 1)))
    r0, r1 = sorted((min(int(box[1] * grid), grid - 1), min(int(box[3] * grid), grid - 1)))
    return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


@dataclass(frozen=True)
class Region:
    """A rectangle on the page, in grid cells, plus the density behind it."""

    r0: int
    c0: int
    r1: int
    c1: int
    grid: int = GRID
    density: dict[tuple[int, int], int] | None = None
    coverage: float = 0.0

    @property
    def area(self) -> float:
        return ((self.r1 - self.r0) * (self.c1 - self.c0)) / (self.grid * self.grid)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """As page fractions: left, top, right, bottom."""
        return (self.c0 / self.grid, self.r0 / self.grid,
                self.c1 / self.grid, self.r1 / self.grid)

    def contains(self, box: list[float]) -> bool:
        """True only if the box lies wholly inside. Partly-inside is not good enough —
        half a value is worse than none, because it looks like an answer."""
        return all(self.r0 <= r < self.r1 and self.c0 <= c < self.c1
                   for r, c in cells_covered(box, self.grid))

    def overlaps(self, box: list[float]) -> bool:
        """True if the box touches the region at all, even by one cell.

        Deliberately laxer than `contains`: used to decide whether a *row* is worth
        keeping, where erring outward costs a few tokens and erring inward loses the value.
        """
        left, top, right, bottom = self.bounds
        return box[0] < right and box[2] > left and box[1] < bottom and box[3] > top

    def heat(self, box: list[float]) -> float:
        """How typical this position is, 0-1, from the learned density.

        Used as a confidence signal: a value at the peak of the distribution is worth more
        than one from a cell seen twice in three thousand documents.
        """
        if not self.density:
            return 0.0
        peak = max(self.density.values())
        cells = cells_covered(box, self.grid)
        got = sum(self.density.get(rc, 0) for rc in cells)
        return min(got / (peak * len(cells)), 1.0) if peak and cells else 0.0


def learn_region(boxes: list[list[float]], coverage: float = 0.95,
                 grid: int = GRID) -> Region:
    """Smallest rectangle containing `coverage` of where this field lands.

    Brute force over every rectangle with a 2D prefix sum — 6.25M candidates at 50x50,
    a few seconds once at setup, and exact rather than a heuristic that might miss.
    """
    density: dict[tuple[int, int], int] = {}
    for box in boxes:
        for rc in cells_covered(box, grid):
            density[rc] = density.get(rc, 0) + 1

    pre = [[0.0] * (grid + 1) for _ in range(grid + 1)]
    for (r, c), v in density.items():
        pre[r + 1][c + 1] = v
    for r in range(1, grid + 1):
        for c in range(1, grid + 1):
            pre[r][c] += pre[r - 1][c] + pre[r][c - 1] - pre[r - 1][c - 1]

    need = pre[grid][grid] * coverage
    best, best_area = None, grid * grid + 1
    for r0 in range(grid):
        for r1 in range(r0 + 1, grid + 1):
            c0 = 0
            for c1 in range(1, grid + 1):
                while c0 < c1:
                    s = pre[r1][c1] - pre[r0][c1] - pre[r1][c0] + pre[r0][c0]
                    if s < need:
                        break
                    c0 += 1
                c0 = max(c0 - 1, 0)
                s = pre[r1][c1] - pre[r0][c1] - pre[r1][c0] + pre[r0][c0]
                if s >= need and (r1 - r0) * (c1 - c0) < best_area:
                    best_area = (r1 - r0) * (c1 - c0)
                    best = (r0, c0, r1, c1)

    if best is None:                                  # nothing learned; fall back to the page
        return Region(0, 0, grid, grid, grid, density, coverage)
    return Region(*best, grid=grid, density=density, coverage=coverage)


def density_boxes(region: Region) -> list[list[float]]:
    """Reconstruct representative boxes from a learned region's density: one small box in
    each cell, repeated by how many field boxes landed there.

    The region file stores the density, not the raw boxes it was learned from. Feeding these
    reconstructed boxes back through `learn_region` reproduces the same rectangle, so a
    re-learn can fold in human corrections without needing the original training corpus.
    """
    if not region.density:
        return []
    g = region.grid
    out: list[list[float]] = []
    for (r, c), n in region.density.items():
        box = [(c + 0.25) / g, (r + 0.25) / g, (c + 0.75) / g, (r + 0.75) / g]
        out.extend([box] * n)
    return out


def rows(words: list[dict]) -> list[list[dict]]:
    """Words grouped into reading-order lines, each sorted left to right.

    Rows are found by vertical overlap rather than by a fixed y-grid, because scans are
    skewed and a line of text drifts a few pixels across the page.
    """
    out: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["box"][1] + w["box"][3]) / 2):
        y = (w["box"][1] + w["box"][3]) / 2
        height = max(w["box"][3] - w["box"][1], 0.004)
        for row in out:
            if abs(y - (row[0]["box"][1] + row[0]["box"][3]) / 2) < height * 0.7:
                row.append(w)
                break
        else:
            out.append([w])
    return [sorted(r, key=lambda w: w["box"][0]) for r in out]


def crop(words: list[dict], region: Region, page: int = 0) -> list[dict]:
    """Every word that touches the region — not only those wholly inside it.

    Requiring containment silently dropped words straddling the boundary, which is exactly
    where a value that starts inside the rectangle and runs past its edge loses its tail.

    Taking the whole *row* instead was tried and measured worse on both axes: on 191 val
    documents it reached 85.3% of values for 49% of the page's tokens, against 85.9% for
    36% here. It sends strictly more words yet scores lower, because the extra words on a
    row interleave between the name's own words and break the span.
    """
    return [w for w in words
            if w.get("page", 0) == page and region.overlaps(w["box"])]


def save(region: Region, path: Path) -> None:
    path.write_text(json.dumps({
        "rect": [region.r0, region.c0, region.r1, region.c1],
        "grid": region.grid,
        "coverage": region.coverage,
        "density": {f"{r},{c}": v for (r, c), v in (region.density or {}).items()},
    }))


def load(path: Path) -> Region:
    d = json.loads(path.read_text())
    return Region(*d["rect"], grid=d["grid"], coverage=d["coverage"],
                  density={tuple(map(int, k.split(","))): v for k, v in d["density"].items()})
