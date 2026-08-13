"""Step 1: does our own docTR run reproduce the OCR shipped with DocILE?

Every number we report comes from the shipped OCR; every uploaded document goes
through our own run. If those differ, the deployed app behaves differently from
everything we measured.
"""
import json, random, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

DATA = Path("data/docile")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def shipped_words(doc_id):
    """(text, box, page) for every word in the shipped OCR."""
    ocr = json.loads((DATA / "ocr" / f"{doc_id}.json").read_text())
    out = []
    for page in ocr["pages"]:
        for block in page["blocks"]:
            for line in block["lines"]:
                for w in line["words"]:
                    (x0, y0), (x1, y1) = w["geometry"]
                    out.append((w["value"], (x0, y0, x1, y1), page["page_idx"]))
    return out, [p["dimensions"] for p in ocr["pages"]]


def our_words(pdf_path, model):
    from doctr.io import DocumentFile
    doc = DocumentFile.from_pdf(pdf_path)
    res = model(doc).export()
    out = []
    for page in res["pages"]:
        for block in page["blocks"]:
            for line in block["lines"]:
                for w in line["words"]:
                    (x0, y0), (x1, y1) = w["geometry"]
                    out.append((w["value"], (x0, y0, x1, y1), page["page_idx"]))
    return out, [list(p["dimensions"]) for p in res["pages"]]


def iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / union if union else 0.0


def main():
    random.seed(7)
    ids = json.loads((DATA / "train.json").read_text())
    invoices = [
        d for d in ids
        if (json.loads((DATA / "annotations" / f"{d}.json").read_text()).get("metadata") or {})
        .get("document_type") == "tax_invoice"
    ]
    sample = random.sample(invoices, N)

    from doctr.models import ocr_predictor
    print("loading docTR model (downloads weights on first run)...")
    model = ocr_predictor(pretrained=True)

    print(f"\n{'document':<26}{'theirs':>8}{'ours':>8}{'recall':>9}{'meanIoU':>9}{'dims':>7}")
    print("-" * 67)
    totals = []
    for doc_id in sample:
        theirs, tdims = shipped_words(doc_id)
        ours, odims = our_words(str(DATA / "pdfs" / f"{doc_id}.pdf"), model)

        ours_by_page = {}
        for t, b, p in ours:
            ours_by_page.setdefault(p, []).append((t, b))

        matched, ious = 0, []
        for t, b, p in theirs:
            best = 0.0
            for ot, ob in ours_by_page.get(p, []):
                if ot == t:
                    best = max(best, iou(b, ob))
            if best > 0.5:
                matched += 1
                ious.append(best)

        recall = matched / len(theirs) if theirs else 0
        mean_iou = sum(ious) / len(ious) if ious else 0
        dims_ok = "same" if tdims == odims else "DIFF"
        totals.append((recall, mean_iou, dims_ok))
        print(f"{doc_id[:24]:<26}{len(theirs):>8}{len(ours):>8}{recall:>8.1%}{mean_iou:>9.3f}{dims_ok:>7}")

    r = sum(t[0] for t in totals) / len(totals)
    i = sum(t[1] for t in totals) / len(totals)
    print("-" * 67)
    print(f"{'MEAN':<26}{'':>8}{'':>8}{r:>8.1%}{i:>9.3f}")
    print(f"\npage dimensions match on all: {all(t[2] == 'same' for t in totals)}")
    print("\nRecall = share of shipped words we reproduced with the same text and >0.5 box overlap.")


if __name__ == "__main__":
    main()
