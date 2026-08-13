"""Run our own docTR over the working set and cache text + boxes to disk.

Layout-first sampling: one document from every distinct layout before any second
document from a layout already covered. Template coverage is what training data
buys us here, and a duplicate layout teaches nothing new — so this gets near-total
layout coverage for a fraction of the compute.

Resumable: already-cached documents are skipped, so an interrupted run continues.
"""
import json, os, sys, time, warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

DATA = Path("data/docile")
OUT = Path("data/ocr_cache")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 1500


def invoices(split):
    ids = json.loads((DATA / f"{split}.json").read_text())
    out = []
    for d in ids:
        meta = json.loads((DATA / "annotations" / f"{d}.json").read_text()).get("metadata") or {}
        if meta.get("document_type") == "tax_invoice":
            out.append((d, meta.get("cluster_id")))
    return out


def layout_first(docs, limit):
    """Round-robin across layouts: every layout gets its 1st doc before any gets a 2nd."""
    by_layout = defaultdict(list)
    for doc_id, cluster in docs:
        by_layout[cluster].append(doc_id)
    order, depth = [], 0
    while len(order) < limit:
        added = False
        for cluster in sorted(by_layout, key=lambda c: (c is None, str(c))):
            bucket = by_layout[cluster]
            if depth < len(bucket):
                order.append((bucket[depth], cluster))
                added = True
                if len(order) >= limit:
                    break
        if not added:
            break
        depth += 1
    return order


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    val = invoices("val")                     # all of val — it is our reported score
    train = invoices("train")
    picked = val + layout_first(train, max(0, LIMIT - len(val)))

    layouts_total = len({c for _, c in train + val})
    layouts_covered = len({c for _, c in picked})
    todo = [(d, c) for d, c in picked if not (OUT / f"{d}.json").exists()]

    print(f"selected      : {len(picked)}  ({len(val)} val + {len(picked)-len(val)} train)")
    print(f"layouts covered: {layouts_covered} of {layouts_total}")
    print(f"already cached : {len(picked)-len(todo)}   to process: {len(todo)}\n", flush=True)

    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    model = ocr_predictor(pretrained=True)

    started, failures = time.time(), []
    for n, (doc_id, cluster) in enumerate(todo, 1):
        try:
            pages = model(DocumentFile.from_pdf(str(DATA / "pdfs" / f"{doc_id}.pdf"))).export()
            slim = {
                "doc_id": doc_id,
                "cluster_id": cluster,
                "pages": [
                    {
                        "page_idx": p["page_idx"],
                        "dimensions": list(p["dimensions"]),
                        "words": [
                            {"text": w["value"], "conf": round(w["confidence"], 4),
                             "box": [round(v, 5) for xy in w["geometry"] for v in xy]}
                            for b in p["blocks"] for l in b["lines"] for w in l["words"]
                        ],
                    }
                    for p in pages["pages"]
                ],
            }
            (OUT / f"{doc_id}.json").write_text(json.dumps(slim))
        except Exception as exc:                       # keep going; log and move on
            failures.append((doc_id, repr(exc)[:120]))

        if n % 25 == 0 or n == len(todo):
            per = (time.time() - started) / n
            print(f"  {n}/{len(todo)}  {per:.2f}s/doc  eta {per*(len(todo)-n)/60:.0f} min"
                  f"  failed={len(failures)}", flush=True)

    print(f"\ndone in {(time.time()-started)/60:.1f} min   cached={len(list(OUT.glob('*.json')))}"
          f"   failed={len(failures)}")
    if failures:
        (OUT / "_failures.json").write_text(json.dumps(failures, indent=1))
        for d, e in failures[:5]:
            print(f"  FAIL {d}: {e}")


if __name__ == "__main__":
    main()
