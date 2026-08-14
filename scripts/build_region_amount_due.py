"""Learn the crop region for amount_due from the labelled build split, at its 80% coverage.

Writes two files:
  data/region_amount_due_80.json       the live region the pipeline loads (relearn updates it)
  data/region_amount_due_80.base.json  an immutable training baseline; relearn always folds
                                        corrections into THIS, so corrections never compound.

Run this to (re)build the region from scratch — e.g. to revert all learning back to base.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data
from api.region import learn_region, save

FIELD = "amount_due"
COVERAGE = 0.80
LIVE = Path("data/region_amount_due_80.json")
BASE = Path("data/region_amount_due_80.base.json")


def main() -> None:
    build = data.splits()["build"]
    boxes = [f["box"] for d in build
             if (f := data.fields(d).get(FIELD)) and f.get("page", 0) == 0]
    print(f"{len(boxes)} labelled {FIELD} examples from {len(build)} documents")

    region = learn_region(boxes, coverage=COVERAGE)
    save(region, LIVE)
    save(region, BASE)

    l, t, r, b = region.bounds
    print(f"rectangle rows {region.r0}-{region.r1}, cols {region.c0}-{region.c1}")
    print(f"page fractions  left {l:.2f}  top {t:.2f}  right {r:.2f}  bottom {b:.2f}")
    print(f"area {region.area:.1%} of the page")
    print(f"wrote {LIVE} and {BASE}")


if __name__ == "__main__":
    main()
