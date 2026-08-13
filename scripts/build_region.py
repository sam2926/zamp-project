"""Learn the crop region for customer_billing_name from the labelled documents."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data
from api.region import learn_region, save

FIELD = "customer_billing_name"
OUT = Path("data/region_customer_billing_name.json")

def main():
    build = data.splits()["build"]
    boxes = [f["box"] for d in build
             if (f := data.fields(d).get(FIELD)) and f.get("page", 0) == 0]
    print(f"{len(boxes)} labelled examples from {len(build)} documents")
    region = learn_region(boxes, coverage=0.95)
    save(region, OUT)
    l, t, r, b = region.bounds
    print(f"rectangle rows {region.r0}-{region.r1}, cols {region.c0}-{region.c1}")
    print(f"page fractions  left {l:.2f}  top {t:.2f}  right {r:.2f}  bottom {b:.2f}")
    print(f"area {region.area:.1%} of the page   → wrote {OUT}")

if __name__ == "__main__":
    main()
