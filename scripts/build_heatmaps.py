"""Render the learned crop regions as heat maps — one card per field, plus a summary strip.

These are the picture of the central claim: we do not store where a value was, we store
where values of this kind tend to be, and that neighbourhood is a small fraction of the page.

Output is SVG rather than PNG so it stays sharp at any size on a web page, needs no plotting
dependency, and can be committed (the repo ignores raster images).

    .venv/bin/python scripts/build_heatmaps.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data
from api.region import learn_region

OUT = Path("assets/heatmaps")

FIELDS = [
    ("customer_billing_name", "who is being billed"),
    ("amount_due",            "how much is owed"),
    ("date_issue",            "when it was issued"),
    ("amount_total_gross",    "the gross total"),
    ("vendor_address",        "where it came from"),
]

COVERAGE = 0.80          # chosen per the area/coverage trade-off — see decisions.md
COMPARE = 0.95           # the looser setting, shown for contrast

# Sequential encoding: ONE hue, light to dark. A rainbow ramp would imply categories where
# the data has magnitude. Steps are the documented blue ramp, used verbatim.
RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
        "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

SURFACE   = "#fcfcfb"
PAPER     = "#ffffff"
INK       = "#0b0b0b"
INK_2     = "#52514e"
MUTED     = "#898781"
HAIRLINE  = "#e1e0d9"
FONT      = 'system-ui, -apple-system, "Segoe UI", sans-serif'

PAGE_RATIO = 1.414       # invoices are portrait pages, so the canvas is one


def colour(count: int, peak: int) -> str:
    """Density to a ramp step. Raised to a power because the distribution is long-tailed —
    linear scaling paints everything but the single hottest cell the same pale blue."""
    t = (count / peak) ** 0.55 if peak else 0.0
    return RAMP[max(0, min(int(round(t * (len(RAMP) - 1))), len(RAMP) - 1))]


def heat_cells(density: dict, grid: int, x: float, y: float, w: float, h: float) -> str:
    """The density grid, one <path> per ramp step rather than one <rect> per cell.

    2,500 cells x 5 pages is half a megabyte of markup for a picture that has 13 colours in
    it. Merging every cell of the same colour into a single path takes the summary figure
    from ~500KB to well under a tenth of that, which matters when it loads on a web page.
    """
    peak = max(density.values()) if density else 1
    cw, ch = w / grid, h / grid
    by_colour: dict[str, list[str]] = {}
    for (r, c), v in sorted(density.items()):
        if not v:
            continue
        cx, cy = x + c * cw, y + r * ch
        by_colour.setdefault(colour(v, peak), []).append(
            f"M{cx:.1f} {cy:.1f}h{cw:.1f}v{ch:.1f}h-{cw:.1f}z")
    return "".join(f'<path fill="{col}" d="{"".join(d)}"/>' for col, d in by_colour.items())


def grid_lines(x: float, y: float, w: float, h: float, grid: int) -> str:
    """Cell boundaries as hairlines."""
    cw, ch = w / grid, h / grid
    lines = []
    for i in range(1, grid):
        lines.append(f'<line x1="{x + i * cw:.1f}" y1="{y:.1f}" x2="{x + i * cw:.1f}" y2="{y + h:.1f}"/>')
        lines.append(f'<line x1="{x:.1f}" y1="{y + i * ch:.1f}" x2="{x + w:.1f}" y2="{y + i * ch:.1f}"/>')
    return f'<g stroke="{HAIRLINE}" stroke-width="0.5" opacity="0.4">{"".join(lines)}</g>'


def page(x: float, y: float, w: float, h: float, region, density: dict, grid: int,
         uid: str, ns: str, thin: bool = False) -> str:
    """One page: paper, heat, cell grid, a scrim over everything the model never sees, then the rect."""
    l, t, r, b = region.bounds
    rx, ry = x + l * w, y + t * h
    rw, rh = (r - l) * w, (b - t) * h
    sw = 1.5 if thin else 2.5

    # The scrim is the argument: four bands covering the discarded page.
    scrim = (f'<rect x="{x}" y="{y}" width="{w}" height="{ry - y:.2f}"/>'
             f'<rect x="{x}" y="{ry + rh:.2f}" width="{w}" height="{y + h - ry - rh:.2f}"/>'
             f'<rect x="{x}" y="{ry:.2f}" width="{rx - x:.2f}" height="{rh:.2f}"/>'
             f'<rect x="{rx + rw:.2f}" y="{ry:.2f}" width="{x + w - rx - rw:.2f}" height="{rh:.2f}"/>')

    return f"""
  <g>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{PAPER}" filter="url(#{ns}-paper)"/>
    <g clip-path="url(#{ns}-clip-{uid})" filter="url(#{ns}-soft)">
      {heat_cells(density, grid, x, y, w, h)}
    </g>
    <g clip-path="url(#{ns}-clip-{uid})">
      {grid_lines(x, y, w, h, grid)}
    </g>
    <g fill="{SURFACE}" opacity="0.78">{scrim}</g>
    <rect x="{rx:.2f}" y="{ry:.2f}" width="{rw:.2f}" height="{rh:.2f}"
          fill="none" stroke="{INK}" stroke-width="{sw}" rx="2"/>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="none" stroke="{HAIRLINE}"/>
  </g>"""


def defs(uid: str, x: float, y: float, w: float, h: float, blur: float, ns: str) -> str:
    return f"""
    <clipPath id="{ns}-clip-{uid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/></clipPath>
    <filter id="{ns}-soft" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur stdDeviation="{blur}"/>
    </filter>
    <filter id="{ns}-paper" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#0b0b0b" flood-opacity="0.10"/>
    </filter>
    <linearGradient id="{ns}-ramp" x1="0" y1="0" x2="1" y2="0">
      {"".join(f'<stop offset="{i / (len(RAMP) - 1):.3f}" stop-color="{c}"/>' for i, c in enumerate(RAMP))}
    </linearGradient>"""


def card(field: str, gloss: str, region, wide, n: int) -> str:
    """A single field, full size."""
    W, PAD = 520, 36
    pw = W - 2 * PAD
    ph = pw * PAGE_RATIO
    top = 176
    H = top + ph + 96

    saved = 1 - region.area / wide.area
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}" font-family='{FONT}'>
  <defs>{defs(field, PAD, top, pw, ph, 5.0, field)}</defs>
  <rect width="{W}" height="{H:.0f}" rx="14" fill="{SURFACE}"/>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1:.0f}" rx="14" fill="none" stroke="{HAIRLINE}"/>

  <text x="{PAD}" y="46" font-size="14" font-weight="600" fill="{INK_2}" letter-spacing="0.06em">
    {field.upper().replace('_', ' ')}</text>
  <text x="{PAD}" y="68" font-size="13" fill="{MUTED}">{gloss}</text>

  <text x="{PAD}" y="128" font-size="52" font-weight="700" fill="{INK}">{region.area:.1%}</text>
  <text x="{PAD + 10 + 52 * 0.62 * len(f'{region.area:.1%}'):.0f}" y="128" font-size="15" fill="{INK_2}">of the page</text>
  <text x="{PAD}" y="152" font-size="13" fill="{MUTED}">
    holds {COVERAGE:.0%} of {n:,} labelled values · {saved:.0%} smaller than the {COMPARE:.0%} region</text>

  {page(PAD, top, pw, ph, region, region.density, region.grid, field, field)}

  <g transform="translate({PAD},{top + ph + 40:.0f})">
    <text x="0" y="0" font-size="12" fill="{MUTED}">rare</text>
    <rect x="34" y="-10" width="118" height="10" rx="2" fill="url(#{field}-ramp)"/>
    <text x="160" y="0" font-size="12" fill="{MUTED}">common</text>
    <rect x="238" y="-10" width="14" height="10" rx="2" fill="none" stroke="{INK}" stroke-width="2"/>
    <text x="260" y="0" font-size="12" fill="{INK_2}">the region the model is shown</text>
  </g>
  <text x="{PAD}" y="{top + ph + 68:.0f}" font-size="12" fill="{MUTED}">
    Everything greyed out is never sent. Learned from the build split; val took no part.</text>
</svg>
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    build = data.splits()["build"]

    for field, gloss in FIELDS:
        boxes = [f["box"] for d in build
                 if (f := data.fields(d).get(field)) and f.get("page", 0) == 0]
        region = learn_region(boxes, coverage=COVERAGE)
        wide = learn_region(boxes, coverage=COMPARE)
        (OUT / f"{field}.svg").write_text(card(field, gloss, region, wide, len(boxes)))
        print(f"{field:<24}{len(boxes):>6} boxes   "
              f"{COMPARE:.0%}→{wide.area:>6.1%}   {COVERAGE:.0%}→{region.area:>6.1%}   "
              f"wrote {field}.svg")


if __name__ == "__main__":
    main()
