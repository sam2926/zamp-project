"""Per-document trace. Offline by default — pass --live to use the model."""
import sys, re, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data, extract as ex
from api.region import load, crop
from api.model import get_asker, echo_asker
from api.scoring import matches, squash, contains_value

def main():
    live = "--live" in sys.argv
    n = 10
    region = load(Path("data/region_customer_billing_name.json"))
    ask, is_live = get_asker() if live else (echo_asker(), False)
    docs = [d for d in data.splits()["val"] if data.has_ocr(d)][:n]
    rows = []

    for i, d in enumerate(docs, 1):
        truth = data.fields(d).get("customer_billing_name")
        words = data.words(d)
        cropped = crop(words, region)
        print(f"\n{'='*78}\n{i}. {d[:16]}")
        if not truth or truth.get("page", 0) != 0:
            print("   SKIPPED — no ground truth for this field on page 1")
            continue
        print(f"   expected      {truth['value']!r}")
        print(f"   truth box     {[round(x,3) for x in truth['box']]}")
        print(f"   in region?    {region.contains(truth['box'])}")
        print(f"   words on pg1  {len([w for w in words if w.get('page',0)==0])}  "
              f"→ inside crop {len(cropped)}")
        # is the answer's text actually present in the cropped words?
        text_in = contains_value(truth["value"], cropped)
        print(f"   answer text in crop? {text_in}")
        if live:
            r = ex.extract(words, region, ask,
                           vendor=(data.fields(d).get("vendor_name") or {}).get("value"))
            hit = matches(r.value, truth["value"])
            rows.append({
                "n": i, "expected": truth["value"].replace("\n", " / "),
                "box_in": region.contains(truth["box"]),
                "text_in": text_in,
                "said": r.value, "fallback": r.used_fallback,
                "hit": hit, "conf": r.confidence, "status": r.status,
            })

    if rows:
        print(f"\n\n{'#':<3}{'expected':<30}{'box':<6}{'text':<6}{'crop attempt':<26}"
              f"{'FALLBACK: whole page':<28}{'result':<7}{'conf':>6}")
        print("-" * 112)
        for r in rows:
            if r["fallback"]:
                crop_col = "empty → fell back"
                fb_col = (r["said"] or "NOT_FOUND")[:26]
            else:
                crop_col = (r["said"] or "")[:24]
                fb_col = "not needed"
            print(f"{r['n']:<3}{r['expected'][:28]:<30}{('Y' if r['box_in'] else 'n'):<6}"
                  f"{('Y' if r['text_in'] else 'n'):<6}{crop_col:<26}{fb_col:<28}"
                  f"{('MATCH' if r['hit'] else 'miss'):<7}{r['conf']:>6}")
        hits = sum(r["hit"] for r in rows)
        fbs = [r for r in rows if r["fallback"]]
        fb_hits = sum(r["hit"] for r in fbs)
        print("-" * 112)
        print(f"matched {hits}/{len(rows)}   fell back {len(fbs)}/{len(rows)}   "
              f"of those the whole page rescued {fb_hits}/{len(fbs)}")


if __name__ == "__main__":
    main()
